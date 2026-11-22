-- Radares no mapa (cadastrados pelo painel do administrador)
-- Rode DEPOIS do admin.sql

create table if not exists public.radares (
  id         bigint generated always as identity primary key,
  lat        double precision not null check (lat between -24.2 and -23.3),
  lon        double precision not null check (lon between -53.7 and -52.9),
  tipo       text not null default 'fixo' check (tipo in ('fixo','semaforo','lombada','portatil')),
  velocidade int check (velocidade between 10 and 130),
  descricao  text not null default '' check (char_length(descricao) <= 160),
  fonte      text not null default 'painel' check (char_length(fonte) <= 120),
  criado_em  timestamptz not null default now()
);
alter table public.radares enable row level security;

drop policy if exists "ver radares" on public.radares;
create policy "ver radares" on public.radares for select to anon, authenticated using (true);
drop policy if exists "admin cadastra radar" on public.radares;
create policy "admin cadastra radar" on public.radares for insert to authenticated with check (public.eh_admin());
drop policy if exists "admin altera radar" on public.radares;
create policy "admin altera radar" on public.radares for update to authenticated using (public.eh_admin()) with check (public.eh_admin());
drop policy if exists "admin apaga radar" on public.radares;
create policy "admin apaga radar" on public.radares for delete to authenticated using (public.eh_admin());

grant select on public.radares to anon, authenticated;
grant insert, update, delete on public.radares to authenticated;

-- Trechos de fiscalização com radar portátil na PR-323 em Umuarama
-- (Planejamento Operacional DER/PR – Batalhão de Polícia Rodoviária, 18/06/2025).
-- O documento informa só o km; a posição no mapa é aproximada: ajuste pelo painel se precisar.
insert into public.radares (lat, lon, tipo, velocidade, descricao, fonte)
select * from (values
  (-23.77786, -53.28466, 'portatil', 60, 'PR-323 km 296 ao 297,5 · fiscalização com radar portátil (local aproximado)', 'DER/PR – BPR, planejamento 18/06/2025'),
  (-23.78171, -53.30563, 'portatil', 60, 'PR-323 km 298,5 ao 299,5 · fiscalização com radar portátil (local aproximado)', 'DER/PR – BPR, planejamento 18/06/2025')
) v(lat, lon, tipo, velocidade, descricao, fonte)
where not exists (select 1 from public.radares r where r.fonte = v.fonte);

do $$ begin
  alter publication supabase_realtime add table public.radares;
exception when duplicate_object then null; end $$;

notify pgrst, 'reload schema';
