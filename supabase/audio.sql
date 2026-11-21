-- Áudios no chat (estilo WhatsApp)
-- Rode DEPOIS do chat.sql

alter table public.mensagens add column if not exists audio text;
alter table public.mensagens add column if not exists audio_seg int check (audio_seg between 0 and 120);
alter table public.mensagens add column if not exists audio_onda text check (char_length(audio_onda) <= 80);

-- mensagem pode ter só áudio (sem texto)
alter table public.mensagens drop constraint if exists mensagens_texto_check;
alter table public.mensagens add constraint mensagens_texto_check
  check (char_length(texto) <= 500 and (char_length(texto) >= 1 or foto is not null or audio is not null));

-- o mesmo armazenamento das fotos aceita áudio (até 3 MB por arquivo)
update storage.buckets
   set allowed_mime_types = array['image/jpeg','image/png','image/webp','audio/webm','audio/ogg','audio/mp4','audio/aac','audio/mpeg'],
       file_size_limit = 3145728
 where id = 'chat-fotos';

notify pgrst, 'reload schema';
