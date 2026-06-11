-- ============================================================
-- 02_policies.sql — Segurança (RLS)
-- ============================================================

alter table public.dre_snapshot enable row level security;

-- Só usuário AUTENTICADO (logado) pode LER o snapshot.
-- Sem login, nem a anon key lê nada.
drop policy if exists "leitura autenticada" on public.dre_snapshot;
create policy "leitura autenticada"
  on public.dre_snapshot
  for select
  to authenticated
  using (true);

-- Não criamos policy de INSERT/UPDATE/DELETE de propósito:
-- a escrita acontece SÓ pela Edge Function usando a service_role,
-- que faz bypass de RLS. Assim ninguém escreve pela API pública.
