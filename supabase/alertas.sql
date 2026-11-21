-- Alertas de blitz no mapa (reportados pelos motoboys, visíveis para todos)
-- Rode DEPOIS do chat.sql e do admin.sql

create table if not exists public.alertas (
  id         bigint generated always as identity primary key,
  tipo       text not null default 'blitz' check (tipo in ('blitz')),
  lat        double precision not null check (lat between -24.2 and -23.3),
  lon        double precision not null check (lon between -53.7 and -52.9),
  autor      uuid not null default auth.uid(),
  apelido    text not null default '' check (char_length(apelido) <= 20),
  sim        int not null default 0,   -- "ainda está lá"
  nao        int not null default 0,   -- "não está mais"
  criado_em  timestamptz not null default now(),
  expira_em  timestamptz not null default now() + interval '2 hours'
);
create index if not exists alertas_expira on public.alertas (expira_em);
alter table public.alertas enable row level security;

drop policy if exists "ver alertas" on public.alertas;
create policy "ver alertas" on public.alertas for select to authenticated using (true);
drop policy if exists "reportar alerta" on public.alertas;
create policy "reportar alerta" on public.alertas for insert to authenticated
  with check (
    autor = auth.uid()
    and not exists (select 1 from public.banidos b where b.autor = auth.uid())
    -- no máximo 3 alertas por motoboy a cada 30 minutos
    and (select count(*) from public.alertas a where a.autor = auth.uid() and a.criado_em > now() - interval '30 minutes') < 3
  );
drop policy if exists "apagar alerta" on public.alertas;
create policy "apagar alerta" on public.alertas for delete to authenticated
  using (autor = auth.uid() or public.eh_admin());

grant select, insert, delete on public.alertas to authenticated;

-- votos: um por motoboy por alerta
create table if not exists public.alertas_votos (
  alerta bigint not null references public.alertas(id) on delete cascade,
  autor  uuid not null default auth.uid(),
  ainda  boolean not null,
  primary key (alerta, autor)
);
alter table public.alertas_votos enable row level security;
grant select on public.alertas_votos to authenticated;
drop policy if exists "ver votos" on public.alertas_votos;
create policy "ver votos" on public.alertas_votos for select to authenticated using (autor = auth.uid());

-- "ainda está lá" estende +1 h; "não está mais" de 2 motoboys (ou do autor) remove o alerta
create or replace function public.votar_alerta(p_id bigint, p_ainda boolean) returns void
language plpgsql security definer set search_path = public
as $$
declare a public.alertas;
begin
  if auth.uid() is null then raise exception 'sem login'; end if;
  select * into a from public.alertas where id = p_id and expira_em > now();
  if not found then return; end if;
  insert into public.alertas_votos (alerta, autor, ainda) values (p_id, auth.uid(), p_ainda)
    on conflict (alerta, autor) do update set ainda = excluded.ainda;
  update public.alertas set
    sim = (select count(*) from public.alertas_votos v where v.alerta = p_id and v.ainda),
    nao = (select count(*) from public.alertas_votos v where v.alerta = p_id and not v.ainda),
    expira_em = case when p_ainda then greatest(expira_em, least(now() + interval '1 hour', criado_em + interval '6 hours')) else expira_em end
  where id = p_id;
  -- 2 motoboys dizendo "não está mais" (ou o próprio autor): o alerta é removido
  if not p_ainda and (a.autor = auth.uid() or (select count(*) from public.alertas_votos v where v.alerta = p_id and not v.ainda) >= 2) then
    delete from public.alertas where id = p_id;
  end if;
end $$;
grant execute on function public.votar_alerta(bigint, boolean) to authenticated;

do $$ begin
  alter publication supabase_realtime add table public.alertas;
exception when duplicate_object then null; end $$;

notify pgrst, 'reload schema';
