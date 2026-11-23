-- Radares no mapa: qualquer motoboy pode adicionar; o administrador edita e remove qualquer um
-- Rode DEPOIS do chat.sql e do admin.sql

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
alter table public.radares add column if not exists autor uuid default auth.uid();
alter table public.radares add column if not exists apelido text not null default '' check (char_length(apelido) <= 20);
-- tipos: radar fixo, radar de semáforo, lombada eletrônica, radar portátil e semáforo comum (farol)
alter table public.radares drop constraint if exists radares_tipo_check;
alter table public.radares add constraint radares_tipo_check check (tipo in ('fixo','semaforo','lombada','portatil','farol'));
alter table public.radares enable row level security;

drop policy if exists "ver radares" on public.radares;
create policy "ver radares" on public.radares for select to anon, authenticated using (true);
drop policy if exists "admin cadastra radar" on public.radares;
drop policy if exists "cadastrar radar" on public.radares;
create policy "cadastrar radar" on public.radares for insert to authenticated
  with check (
    autor = auth.uid()
    and (
      public.eh_admin()
      or (
        not exists (select 1 from public.banidos b where b.autor = auth.uid())
        -- no máximo 5 radares por motoboy a cada hora
        and (select count(*) from public.radares r where r.autor = auth.uid() and r.criado_em > now() - interval '1 hour') < 5
      )
    )
  );
drop policy if exists "admin altera radar" on public.radares;
drop policy if exists "alterar radar" on public.radares;
create policy "alterar radar" on public.radares for update to authenticated
  using (public.eh_admin() or autor = auth.uid()) with check (public.eh_admin() or autor = auth.uid());
drop policy if exists "admin apaga radar" on public.radares;
drop policy if exists "apagar radar" on public.radares;
create policy "apagar radar" on public.radares for delete to authenticated using (public.eh_admin() or autor = auth.uid());

grant select on public.radares to anon, authenticated;
grant insert, update, delete on public.radares to authenticated;

-- Remove os radares da lista oficial (DER/PR) que entraram na primeira versão deste arquivo.
-- Os radares do mapa são só os cadastrados pelo administrador no painel.
delete from public.radares where fonte like 'DER/PR%';

do $$ begin
  alter publication supabase_realtime add table public.radares;
exception when duplicate_object then null; end $$;

notify pgrst, 'reload schema';
