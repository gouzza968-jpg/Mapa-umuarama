-- Posição dos motoboys com o app em segundo plano (complementa o "ao vivo")
-- Rode DEPOIS do chat.sql e do admin.sql

create table if not exists public.posicoes (
  uid           uuid primary key default auth.uid(),
  apelido       text not null default '' check (char_length(apelido) <= 20),
  lat           double precision not null check (lat between -24.2 and -23.3),
  lon           double precision not null check (lon between -53.7 and -52.9),
  head          double precision,
  atualizado_em timestamptz not null default now()
);
alter table public.posicoes enable row level security;

drop policy if exists "ver posicoes" on public.posicoes;
create policy "ver posicoes" on public.posicoes for select to authenticated using (true);
drop policy if exists "gravar minha posicao" on public.posicoes;
create policy "gravar minha posicao" on public.posicoes for insert to authenticated with check (uid = auth.uid());
drop policy if exists "atualizar minha posicao" on public.posicoes;
create policy "atualizar minha posicao" on public.posicoes for update to authenticated using (uid = auth.uid()) with check (uid = auth.uid());
drop policy if exists "apagar minha posicao" on public.posicoes;
create policy "apagar minha posicao" on public.posicoes for delete to authenticated using (uid = auth.uid() or public.eh_admin());

grant select, insert, update, delete on public.posicoes to authenticated;

do $$ begin
  alter publication supabase_realtime add table public.posicoes;
exception when duplicate_object then null; end $$;

notify pgrst, 'reload schema';
