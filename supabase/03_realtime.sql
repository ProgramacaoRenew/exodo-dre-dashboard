-- ============================================================
-- 03_realtime.sql — Habilita Realtime na tabela
-- ============================================================

-- Adiciona a tabela à publicação do Realtime (ignora se já estiver).
do $$
begin
  alter publication supabase_realtime add table public.dre_snapshot;
exception
  when duplicate_object then null;  -- já estava na publicação
end $$;

-- Garante payload completo da linha nos eventos de UPDATE.
alter table public.dre_snapshot replica identity full;
