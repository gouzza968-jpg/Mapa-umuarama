-- Administração do Mapa Umuarama
-- Rode uma vez no Supabase (SQL Editor -> New query -> cole tudo -> Run), DEPOIS do chat.sql.
-- No final, troque SEU_EMAIL pelo e-mail da conta de administrador.

-- quem é administrador
create table if not exists public.admins (
  uid       uuid primary key references auth.users(id) on delete cascade,
  criado_em timestamptz not null default now()
);
alter table public.admins enable row level security;
drop policy if exists "admin ve a si" on public.admins;
create policy "admin ve a si" on public.admins for select to authenticated using (uid = auth.uid());

create or replace function public.eh_admin() returns boolean
language sql stable security definer set search_path = public
as $$ select exists (select 1 from public.admins where uid = auth.uid()) $$;
grant execute on function public.eh_admin() to authenticated;

-- motoboys bloqueados no chat
create table if not exists public.banidos (
  autor     uuid primary key,
  apelido   text,
  motivo    text,
  criado_em timestamptz not null default now(),
  por       uuid default auth.uid()
);
alter table public.banidos enable row level security;
drop policy if exists "ler banidos" on public.banidos;
create policy "ler banidos" on public.banidos for select to authenticated using (true);
drop policy if exists "admin bloqueia" on public.banidos;
create policy "admin bloqueia" on public.banidos for insert to authenticated with check (public.eh_admin());
drop policy if exists "admin desbloqueia" on public.banidos;
create policy "admin desbloqueia" on public.banidos for delete to authenticated using (public.eh_admin());

-- mensagens: selo de administrador, bloqueio e exclusão pelo admin
alter table public.mensagens add column if not exists admin boolean not null default false;

drop policy if exists "enviar como si mesmo" on public.mensagens;
create policy "enviar como si mesmo" on public.mensagens for insert to authenticated
  with check (
    autor = auth.uid()
    and not exists (select 1 from public.banidos b where b.autor = auth.uid())
    and (admin = false or public.eh_admin())
  );

drop policy if exists "apagar as proprias" on public.mensagens;
drop policy if exists "apagar as proprias ou admin" on public.mensagens;
create policy "apagar as proprias ou admin" on public.mensagens for delete to authenticated
  using (autor = auth.uid() or public.eh_admin());

-- fotos: admin pode apagar qualquer uma
drop policy if exists "chat fotos admin apaga" on storage.objects;
create policy "chat fotos admin apaga" on storage.objects for delete to authenticated
  using (bucket_id = 'chat-fotos' and public.eh_admin());

do $$ begin
  alter publication supabase_realtime add table public.banidos;
exception when duplicate_object then null; end $$;

-- >>> torne a sua conta administradora (troque o e-mail) <<<
insert into public.admins (uid)
select id from auth.users where email = 'SEU_EMAIL'
on conflict do nothing;
