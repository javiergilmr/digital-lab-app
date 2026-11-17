-- Límite de uso de la demo: archivos subidos por usuario y mes (se reinicia el día 1).
-- Pégalo una vez en Supabase → SQL Editor → New query → Run (después de user_stats.sql).
-- Se puede volver a ejecutar sin problema. El límite (10) vive en services/monthly_quota.py.

create table if not exists public.monthly_usage (
  user_id        uuid not null references auth.users (id) on delete cascade,
  month          date not null check (month = date_trunc('month', month)::date),
  files_uploaded integer not null default 0,
  updated_at     timestamptz not null default now(),
  primary key (user_id, month)
);

-- Cada usuario solo puede leer sus filas
alter table public.monthly_usage enable row level security;

drop policy if exists "Cada usuario ve su uso" on public.monthly_usage;
create policy "Cada usuario ve su uso"
  on public.monthly_usage for select
  to authenticated
  using ((select auth.uid()) = user_id);

-- Sin políticas de insert/update: el uso solo sube con esta función y nadie puede bajarlo.
-- Suma un archivo al mes actual (UTC) solo si queda cupo; devuelve true si lo sumó.
create or replace function public.claim_monthly_file(max_files integer)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  this_month date := date_trunc('month', (now() at time zone 'utc'))::date;
  claimed    integer;
begin
  if auth.uid() is null then
    raise exception 'No autenticado';
  end if;

  if max_files < 1 or max_files > 1000 then
    raise exception 'Límite fuera de rango';
  end if;

  insert into public.monthly_usage as u (user_id, month, files_uploaded)
  values (auth.uid(), this_month, 1)
  on conflict (user_id, month) do update set
    files_uploaded = u.files_uploaded + 1,
    updated_at     = now()
  where u.files_uploaded < max_files
  returning files_uploaded into claimed;

  return claimed is not null;
end;
$$;

revoke all on function public.claim_monthly_file(integer) from public, anon;
grant execute on function public.claim_monthly_file(integer) to authenticated;
