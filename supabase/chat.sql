-- Chat dos motoboys (Mapa Umuarama)
-- Rode uma vez no Supabase: SQL Editor -> New query -> cole tudo -> Run

create table if not exists public.mensagens (
  id         bigint generated always as identity primary key,
  criado_em  timestamptz not null default now(),
  autor      uuid not null default auth.uid(),
  apelido    text not null check (char_length(apelido) between 2 and 20),
  texto      text not null check (char_length(texto) between 1 and 500),
  sala       text not null default 'geral',
  lat        double precision,
  lon        double precision,
  foto       text
);
alter table public.mensagens add column if not exists foto text;
alter table public.mensagens drop constraint if exists mensagens_texto_check;
alter table public.mensagens add constraint mensagens_texto_check check (char_length(texto) <= 500 and (char_length(texto) >= 1 or foto is not null));

create index if not exists mensagens_sala_data on public.mensagens (sala, criado_em desc);

alter table public.mensagens enable row level security;

-- qualquer motoboy do app (login anônimo) pode ler
drop policy if exists "ler mensagens" on public.mensagens;
create policy "ler mensagens" on public.mensagens
  for select to authenticated using (true);

-- só envia em nome de si mesmo
drop policy if exists "enviar como si mesmo" on public.mensagens;
create policy "enviar como si mesmo" on public.mensagens
  for insert to authenticated with check (autor = auth.uid());

-- só apaga as próprias mensagens
drop policy if exists "apagar as proprias" on public.mensagens;
create policy "apagar as proprias" on public.mensagens
  for delete to authenticated using (autor = auth.uid());

-- mensagens chegam na hora para quem está com o app aberto
do $$ begin
  alter publication supabase_realtime add table public.mensagens;
exception when duplicate_object then null; end $$;

-- fotos do chat (armazenamento público para leitura; cada um envia na sua própria pasta)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('chat-fotos', 'chat-fotos', true, 2097152, array['image/jpeg','image/png','image/webp'])
on conflict (id) do nothing;

drop policy if exists "chat fotos enviar" on storage.objects;
create policy "chat fotos enviar" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'chat-fotos' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "chat fotos ver" on storage.objects;
create policy "chat fotos ver" on storage.objects
  for select using (bucket_id = 'chat-fotos');

drop policy if exists "chat fotos apagar" on storage.objects;
create policy "chat fotos apagar" on storage.objects
  for delete to authenticated
  using (bucket_id = 'chat-fotos' and (storage.foldername(name))[1] = auth.uid()::text);
