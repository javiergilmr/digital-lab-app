-- Planes Gratuito y Pro: cupo mensual de archivos y recorte del historial.
-- Pégalo una vez en Supabase → SQL Editor → New query → Run (después de user_stats.sql y reports.sql).
-- Se puede volver a ejecutar sin problema. Los límites de cada plan viven en services/plans.py.

-- =========================
-- Plan del usuario: columna "plan" de user_stats ('free' por defecto)
-- =========================
-- El usuario solo puede leer su fila, nunca cambiarla: el plan lo asignas tú desde el SQL Editor.
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'user_stats_plan_check') then
    alter table public.user_stats
      add constraint user_stats_plan_check check (plan in ('free', 'pro'));
  end if;
end;
$$;

-- Para pasar a alguien a Pro (o de vuelta a 'free'), cambia el correo y ejecuta:
--
--   insert into public.user_stats (user_id, plan)
--   select id, 'pro' from auth.users where email = 'cliente@correo.com'
--   on conflict (user_id) do update set plan = excluded.plan, updated_at = now();

-- =========================
-- Cupo mensual: archivos procesados por usuario y mes (el mes empieza el día 1)
-- =========================
create table if not exists public.monthly_usage (
  user_id         uuid not null references auth.users (id) on delete cascade,
  month           date not null check (month = date_trunc('month', month)::date),
  files_processed integer not null default 0,
  updated_at      timestamptz not null default now(),
  primary key (user_id, month)
);

alter table public.monthly_usage enable row level security;

drop policy if exists "Cada usuario ve su uso" on public.monthly_usage;
create policy "Cada usuario ve su uso"
  on public.monthly_usage for select
  to authenticated
  using ((select auth.uid()) = user_id);

-- Sin políticas de insert/update: el uso solo sube con esta función y nadie puede bajarlo.
-- El mes lo envía la app (su fecha local); se rechaza si no es un día 1 cercano a hoy.
create or replace function public.record_processed_file(usage_month date)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'No autenticado';
  end if;

  if usage_month <> date_trunc('month', usage_month)::date
     or usage_month not between (current_date - 40) and (current_date + 40) then
    raise exception 'Mes fuera de rango';
  end if;

  insert into public.monthly_usage as u (user_id, month, files_processed)
  values (auth.uid(), usage_month, 1)
  on conflict (user_id, month) do update set
    files_processed = u.files_processed + 1,
    updated_at      = now();
end;
$$;

revoke all on function public.record_processed_file(date) from public, anon;
grant execute on function public.record_processed_file(date) to authenticated;

-- =========================
-- Historial: la app borra los informes que pasan del límite del plan (5 en Gratuito, 100 en Pro)
-- =========================
drop policy if exists "Cada usuario borra sus informes" on public.reports;
create policy "Cada usuario borra sus informes"
  on public.reports for delete
  to authenticated
  using ((select auth.uid()) = user_id);

-- Los PDFs de esos informes se borran con la política "Cada usuario borra sus PDF" de account.sql.
