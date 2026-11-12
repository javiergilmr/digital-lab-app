-- Stats del panel de usuario ("Mi panel").
-- Pégalo una vez en Supabase → SQL Editor → New query → Run. Se puede volver a ejecutar sin problema.

-- Una fila por usuario con sus contadores
create table if not exists public.user_stats (
  user_id        uuid primary key references auth.users (id) on delete cascade,
  files_uploaded integer not null default 0,
  rows_processed bigint  not null default 0,
  rows_fixed     bigint  not null default 0,
  rows_removed   bigint  not null default 0,
  plan           text    not null default 'free',
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

-- Cada usuario solo puede leer su propia fila
alter table public.user_stats enable row level security;

drop policy if exists "Cada usuario ve sus stats" on public.user_stats;
create policy "Cada usuario ve sus stats"
  on public.user_stats for select
  to authenticated
  using ((select auth.uid()) = user_id);

-- No hay políticas de insert/update: los contadores solo cambian con esta función,
-- que suma a la fila del usuario que llama y nunca toca el plan
create or replace function public.record_activity(
  files     integer default 0,
  processed integer default 0,
  fixed     integer default 0,
  removed   integer default 0
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'No autenticado';
  end if;

  if least(files, processed, fixed, removed) < 0
     or greatest(files, processed, fixed, removed) > 10000000 then
    raise exception 'Valores fuera de rango';
  end if;

  insert into public.user_stats as s (user_id, files_uploaded, rows_processed, rows_fixed, rows_removed)
  values (auth.uid(), files, processed, fixed, removed)
  on conflict (user_id) do update set
    files_uploaded = s.files_uploaded + excluded.files_uploaded,
    rows_processed = s.rows_processed + excluded.rows_processed,
    rows_fixed     = s.rows_fixed     + excluded.rows_fixed,
    rows_removed   = s.rows_removed   + excluded.rows_removed,
    updated_at     = now();
end;
$$;

revoke all on function public.record_activity(integer, integer, integer, integer) from public, anon;
grant execute on function public.record_activity(integer, integer, integer, integer) to authenticated;
