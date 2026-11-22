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

-- Remove os radares da lista oficial (DER/PR) que entraram na primeira versão deste arquivo.
-- Os radares do mapa são só os cadastrados pelo administrador no painel.
delete from public.radares where fonte like 'DER/PR%';

do $$ begin
  alter publication supabase_realtime add table public.radares;
exception when duplicate_object then null; end $$;

notify pgrst, 'reload schema';
