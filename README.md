# DRE Dashboard — Êxodo Logística

Dashboard web (com login) que mostra a DRE em tempo real. A planilha Excel
continua no OneDrive; um **publicador** lê a aba DRE e envia para o **Supabase**,
e o **dashboard** (hospedado na **Vercel**) atualiza sozinho via **Realtime**.
O visual é exatamente o mockup aprovado — só mudou a camada de dados.

```
Excel/OneDrive → Publicador (lê DRE) → Edge Function → Supabase (banco+realtime)
                                                              │
                                          Dashboard (Vercel) ◄┘  ← login obrigatório
```

## Estrutura

```
index.html                      Dashboard (login + Supabase Realtime)
vercel.json                     Config do deploy estático
supabase/
  01_schema.sql                 Tabela dre_snapshot
  02_policies.sql               RLS (só logado lê)
  03_realtime.sql               Habilita Realtime
  functions/publish-dre/        Edge Function (recebe o POST do publicador)
publicador/
  publicador.py                 Lê a DRE e publica no Supabase
  requirements.txt
  .env.example                  Modelo de configuração (DEV)
```

---

## Passo a passo (fase 1 — validar o fluxo)

### 1. Supabase
1. Crie um projeto em https://supabase.com (região São Paulo).
2. **SQL Editor** → rode, na ordem: `01_schema.sql`, `02_policies.sql`, `03_realtime.sql`.
3. **Authentication → Providers → Email**: ligado. Desligue "Allow new users to sign up".
4. **Authentication → Users → Add user**: crie os usuários (e-mail + senha) que poderão ver o painel.
5. **Settings → API**: anote `Project URL` e a **anon key** (para o frontend).

### 2. Edge Function
Com a [Supabase CLI](https://supabase.com/docs/guides/cli):
```bash
supabase login
supabase link --project-ref SEU_REF
supabase functions deploy publish-dre --no-verify-jwt
supabase secrets set PUBLISH_SECRET="um-segredo-forte-aqui"
```
(`SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` são injetadas automaticamente.)

### 3. Dashboard (frontend)
Em `index.html`, preencha no topo do bloco de dados:
```js
const SB_URL  = "https://SEU-PROJETO.supabase.co";
const SB_ANON = "SUA_ANON_KEY";
```

### 4. Deploy na Vercel
1. Suba este projeto para um repositório **privado** no GitHub.
2. Vercel → **Add New Project → Import** → framework **Other** (sem build).
3. Deploy → URL `https://...vercel.app`. Sem login do Supabase, o painel não mostra dados.
4. No Supabase **Auth → URL Configuration**: ponha a URL da Vercel em `Site URL` e `Redirect URLs`.

### 5. Publicador (na máquina do financeiro e na sua)
```bash
cd publicador
pip install -r requirements.txt
copy .env.example .env      # edite: DRE_XLSX, SUPABASE_URL, PUBLISH_SECRET
python publicador.py
```
Salve a planilha no Excel → em segundos o painel atualiza sozinho.

> **Importante:** marque o `.xlsx` como "Sempre manter neste dispositivo" no OneDrive,
> para o publicador sempre achar o arquivo local.

---

## Fase 2 (depois de validar)
Transformar o publicador em tarefa automática (Agendador de Tarefas, oculto,
inicia com o Windows) e, na sequência, no serviço `Exodo DRE Sync Service` com
instalador `DRE Sync Setup.exe` (sem exigir Python). Ver o briefing do projeto.

## Segurança
- `service_role` **nunca** sai do servidor (fica na Edge Function).
- Frontend usa só a **anon key** (pública) + **login obrigatório** (RLS bloqueia o resto).
- Publicador autentica na Edge Function por um **segredo** rotacionável.
- `.env`, `config.json` e `*.xlsx` ficam fora do git.
