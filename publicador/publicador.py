# -*- coding: utf-8 -*-
"""
Publicador DRE — Êxodo Logística
--------------------------------
Vigia a planilha (mtime), lê a aba DRE com openpyxl (valores em cache que o
Excel grava ao salvar) e publica o JSON na Edge Function do Supabase, que grava
no banco. O dashboard recebe via Realtime e atualiza sozinho.

NÃO precisa do Excel rodando. NÃO usa a service_role (essa fica só no servidor).

Configuração (variáveis de ambiente; em DEV use um arquivo .env ao lado):
  DRE_XLSX        caminho do arquivo .xlsx (no OneDrive)
  SUPABASE_URL    https://SEU-PROJETO.supabase.co
  PUBLISH_SECRET  segredo compartilhado com a Edge Function

Na fase 2 (serviço), a config virá de C:\\ProgramData\\ExodoDRESync\\config.json.
"""
import os
import sys
import json
import time
import hashlib
import logging
import tempfile
import shutil

import requests
import openpyxl

# ── Pasta do app (ao lado do .exe quando empacotado; senão, do script) ───────
def _app_dir():
    if getattr(sys, "frozen", False):     # rodando como .exe (PyInstaller)
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = _app_dir()

# ── .env opcional (DEV) ─────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(APP_DIR, ".env"))
except Exception:
    pass

# ── Config ───────────────────────────────────────────────────────────────────
# Ordem de busca: configuracao.txt (chave=valor, à prova de barra do Windows)
# → config.json → ProgramData → variáveis de ambiente (.env).
_LOCAL_TXT = os.path.join(APP_DIR, "configuracao.txt")
_LOCAL_CFG = os.path.join(APP_DIR, "config.json")
_PROGRAMDATA_CFG = r"C:\ProgramData\ExodoDRESync\config.json"


def _parse_kv(text):
    """Formato simples chave=valor. Barra invertida é LITERAL (ideal p/ Windows)."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _load_config():
    cfg = {}
    for path in (_LOCAL_TXT, _LOCAL_CFG, _PROGRAMDATA_CFG):
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8-sig") as f:
                    text = f.read()
                cfg = _parse_kv(text) if path.endswith(".txt") else json.loads(text)
                break
            except Exception:
                cfg = {}
    return {
        "xlsx":   cfg.get("xlsx_path")    or os.environ.get("DRE_XLSX", ""),
        "url":    cfg.get("supabase_url") or os.environ.get("SUPABASE_URL", ""),
        "secret": cfg.get("publish_secret") or os.environ.get("PUBLISH_SECRET", ""),
    }


CFG = _load_config()
RELAY_URL = CFG["url"].rstrip("/") + "/functions/v1/publish-dre"
POLL_SECONDS = 2.0
SHEET = "DRE"
ROW = {"rec": 4, "dvar": 5, "lb": 6, "dfix": 7, "dout": 8, "ll": 9,
       "mb": 11, "ml": 12, "inv": 13}
COL_FIRST, COL_LAST = 2, 22   # B..V = 21 meses

# ── Log (arquivo + console) ─────────────────────────────────────────────────
_LOG_DIR = r"C:\ProgramData\ExodoDRESync"
try:
    os.makedirs(_LOG_DIR, exist_ok=True)
    _log_path = os.path.join(_LOG_DIR, "log.txt")
except Exception:
    _log_path = os.path.join(tempfile.gettempdir(), "exodo_dre_sync.log")

_handlers = [logging.FileHandler(_log_path, encoding="utf-8")]
if sys.stdout is not None:          # em .exe --noconsole, stdout é None
    _handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=_handlers,
)
log = logging.getLogger("publicador")


def _num(v):
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def read_dre(xlsx_path):
    """Lê os valores já calculados (cache) da aba DRE. Retorna lista de meses."""
    tmp = os.path.join(tempfile.gettempdir(), "_dre_pub_read.xlsx")
    last = None
    for _ in range(8):                       # retry: evita ler durante o save
        try:
            shutil.copy2(xlsx_path, tmp)
            break
        except (PermissionError, OSError) as e:
            last = e
            time.sleep(0.4)
    else:
        raise last

    wb = openpyxl.load_workbook(tmp, data_only=True, read_only=True)
    try:
        ws = wb[SHEET]
        grid = {}
        wanted = set(ROW.values()) | {3}     # 3 = rótulos dos meses
        for r, row in enumerate(ws.iter_rows(min_row=1, max_row=13,
                                             min_col=1, max_col=COL_LAST), start=1):
            if r in wanted:
                grid[r] = [c.value for c in row]   # index 0 == coluna A
    finally:
        wb.close()

    headers = grid.get(3, [])
    out = []
    for col in range(COL_FIRST, COL_LAST + 1):
        lbl = headers[col - 1] if col - 1 < len(headers) else None
        if not lbl:
            continue
        label = str(lbl).strip()
        yr = label.split("/")[-1].strip() if "/" in label else ""
        cell = lambda key: grid.get(ROW[key], [None] * COL_LAST)[col - 1]
        out.append({
            "label": label, "yr": yr,
            "rec":  round(_num(cell("rec")), 2),
            "dvar": round(_num(cell("dvar")), 2),
            "dfix": round(_num(cell("dfix")), 2),
            "dout": round(_num(cell("dout")), 2),
            "lb":   round(_num(cell("lb")), 2),
            "ll":   round(_num(cell("ll")), 2),
            "mb":   round(_num(cell("mb")) * 100, 2),
            "ml":   round(_num(cell("ml")) * 100, 2),
            "inv":  round(_num(cell("inv")), 2),
        })
    return out


def _is_empty_cache(data):
    """True se nenhum mês tem receita/lucro (cache não recalculado)."""
    return not any(d["rec"] or d["lb"] or d["ll"] for d in data)


def _content_hash(data):
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()


def publish(data, rev):
    r = requests.post(
        RELAY_URL,
        headers={"x-publish-secret": CFG["secret"], "Content-Type": "application/json"},
        data=json.dumps({"data": data, "rev": rev}),
        timeout=20,
    )
    r.raise_for_status()


def main():
    missing = [k for k in ("xlsx", "url", "secret") if not CFG[k]]
    if missing:
        log.error("Configuração faltando: %s. Defina via .env ou config.json.", missing)
        sys.exit(1)
    if not os.path.exists(CFG["xlsx"]):
        log.error("Planilha não encontrada: %s", CFG["xlsx"])
        sys.exit(1)

    log.info("Publicador iniciado. Vigiando: %s", CFG["xlsx"])
    last_mtime = None
    last_hash = None

    while True:
        try:
            mtime = os.path.getmtime(CFG["xlsx"])
            if mtime != last_mtime:
                data = read_dre(CFG["xlsx"])
                if _is_empty_cache(data):
                    log.warning("Cache vazio — salve a planilha no Excel p/ recalcular.")
                else:
                    h = _content_hash(data)
                    if h != last_hash:
                        publish(data, h)
                        last_hash = h
                        log.info("DRE publicada (%d meses, rev=%s).", len(data), h[:8])
                    else:
                        log.info("Sem mudança no conteúdo; nada a publicar.")
                last_mtime = mtime
        except requests.RequestException as e:
            log.error("Falha ao publicar: %s", e)
        except Exception as e:
            log.exception("Erro inesperado: %s", e)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
