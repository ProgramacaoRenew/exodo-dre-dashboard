-- ============================================================
-- 01_schema.sql — Tabela do snapshot da DRE
-- Rode no Supabase: SQL Editor → cole → Run
-- ============================================================

-- Snapshot único da DRE. Sempre id = 1 (sobrescrito a cada save).
create table if not exists public.dre_snapshot (
  id          smallint    primary key default 1,
  data        jsonb       not null,            -- array dos 21 meses (mesma forma do DATA do dashboard)
  rev         text        not null,            -- hash do conteúdo (dedup entre máquinas)
  updated_at  timestamptz not null default now(),
  constraint  single_row check (id = 1)
);

-- Linha inicial (placeholder até o publicador rodar pela 1ª vez).
insert into public.dre_snapshot (id, data, rev)
values (1, '[]'::jsonb, 'init')
on conflict (id) do nothing;
