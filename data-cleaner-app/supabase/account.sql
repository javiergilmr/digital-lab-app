-- Eliminar cuenta desde "Mi panel".
-- Pégalo una vez en Supabase → SQL Editor → New query → Run (después de reports.sql). Se puede volver a ejecutar sin problema.

-- Cada usuario puede borrar sus propios PDFs del bucket "reports"
drop policy if exists "Cada usuario borra sus PDF" on storage.objects;
create policy "Cada usuario borra sus PDF"
  on storage.objects for delete
  to authenticated
  using (
    bucket_id = 'reports'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

-- Borra al usuario que llama. Sus filas de user_stats y reports se borran solas (on delete cascade).
-- La app borra antes sus PDFs con la API de Storage, que es la única forma permitida de borrar archivos.
create or replace function public.delete_my_account()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'No autenticado';
  end if;

  delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
