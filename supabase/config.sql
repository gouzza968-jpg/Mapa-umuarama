-- Configurações do app controladas pelo painel (ex.: ligar/desligar o chat)
-- Rode DEPOIS do chat.sql e do admin.sql

create table if not exists public.config (
  chave         text primary key,
  valor         jsonb not null default '{}'::jsonb,
  atualizado_em timestamptz not null default now()
);
alter table public.config enable row level security;

drop policy if exists "ler config" on public.config;
create policy "ler config" on public.config for select to authenticated using (true);
drop policy if exists "admin altera config" on public.config;
create policy "admin altera config" on public.config for all to authenticated
  using (public.eh_admin()) with check (public.eh_admin());

grant select, insert, update, delete on public.config to authenticated;

insert into public.config (chave, valor) values ('chat', '{"ativo": true}') on conflict (chave) do nothing;

create or replace function public.chat_ativo() returns boolean
language sql stable security definer set search_path = public
as $$ select coalesce((select (valor->>'ativo')::boolean from public.config where chave = 'chat'), true) $$;
grant execute on function public.chat_ativo() to authenticated;

-- com o chat desligado, ninguém (exceto o administrador) envia mensagens
drop policy if exists "enviar como si mesmo" on public.mensagens;
create policy "enviar como si mesmo" on public.mensagens for insert to authenticated
  with check (
    autor = auth.uid()
    and not exists (select 1 from public.banidos b where b.autor = auth.uid())
    and (admin = false or public.eh_admin())
    and (public.chat_ativo() or public.eh_admin())
  );

do $$ begin
  alter publication supabase_realtime add table public.config;
exception when duplicate_object then null; end $$;

notify pgrst, 'reload schema';
