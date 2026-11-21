-- Perfis dos motoboys (apelido, nome e telefone) — rode DEPOIS do chat.sql e do admin.sql
-- O telefone só aparece para os outros motoboys se o dono deixar visível; o administrador sempre vê.

create table if not exists public.perfis (
  uid              uuid primary key default auth.uid(),
  apelido          text check (apelido is null or char_length(apelido) between 2 and 20),
  nome             text check (nome is null or char_length(nome) <= 60),
  telefone         text check (telefone is null or char_length(telefone) <= 20),
  telefone_visivel boolean not null default false,
  atualizado_em    timestamptz not null default now()
);
alter table public.perfis enable row level security;

drop policy if exists "ver o proprio ou admin" on public.perfis;
create policy "ver o proprio ou admin" on public.perfis for select to authenticated
  using (uid = auth.uid() or public.eh_admin());
drop policy if exists "criar o proprio" on public.perfis;
create policy "criar o proprio" on public.perfis for insert to authenticated
  with check (uid = auth.uid());
drop policy if exists "editar o proprio" on public.perfis;
create policy "editar o proprio" on public.perfis for update to authenticated
  using (uid = auth.uid()) with check (uid = auth.uid());
drop policy if exists "apagar o proprio" on public.perfis;
create policy "apagar o proprio" on public.perfis for delete to authenticated
  using (uid = auth.uid());

-- o que os outros motoboys podem ver de um perfil (telefone só se visível; admin vê tudo)
create or replace function public.perfil_publico(p_uid uuid)
returns table (apelido text, nome text, telefone text, telefone_visivel boolean)
language sql stable security definer set search_path = public
as $$
  select p.apelido, p.nome,
         case when p.telefone_visivel or public.eh_admin() then p.telefone end,
         p.telefone_visivel
  from public.perfis p where p.uid = p_uid
$$;
grant execute on function public.perfil_publico(uuid) to authenticated;
