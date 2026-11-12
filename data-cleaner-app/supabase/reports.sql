-- Historial de informes y PDFs guardados ("Mi panel").
-- Pégalo una vez en Supabase → SQL Editor → New query → Run. Se puede volver a ejecutar sin problema.

-- =========================
-- Historial: una fila por archivo procesado
-- =========================
create table if not exists public.reports (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null default auth.uid() references auth.users (id) on delete cascade,
  created_at    timestamptz not null default now(),
  report_name   text not null default '',
  file_name     text not null default '',
  rows_initial  integer not null default 0,
  rows_final    integer not null default 0,
  rows_fixed    integer not null default 0,
  rows_removed  integer not null default 0,
  total_sold    numeric(14, 2) not null default 0,
  total_profit  numeric(14, 2),
  margin_pct    numeric(7, 2),
  pdf_path      text
);

create index if not exists reports_user_created_idx on public.reports (user_id, created_at desc);

-- Cada usuario solo lee y agrega sus propios informes
alter table public.reports enable row level security;

drop policy if exists "Cada usuario ve sus informes" on public.reports;
create policy "Cada usuario ve sus informes"
  on public.reports for select
  to authenticated
  using ((select auth.uid()) = user_id);

drop policy if exists "Cada usuario agrega sus informes" on public.reports;
create policy "Cada usuario agrega sus informes"
  on public.reports for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

-- =========================
-- PDFs: bucket privado, una carpeta por usuario (reports/<user_id>/<id>.pdf)
-- =========================
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('reports', 'reports', false, 5242880, array['application/pdf'])
on conflict (id) do nothing;

drop policy if exists "Cada usuario sube sus PDF" on storage.objects;
create policy "Cada usuario sube sus PDF"
  on storage.objects for insert
  to authenticated
  with check (
    bucket_id = 'reports'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

drop policy if exists "Cada usuario lee sus PDF" on storage.objects;
create policy "Cada usuario lee sus PDF"
  on storage.objects for select
  to authenticated
  using (
    bucket_id = 'reports'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );
