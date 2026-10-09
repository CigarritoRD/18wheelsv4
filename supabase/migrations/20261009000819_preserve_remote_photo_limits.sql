-- Applied as Supabase migration version 20261009000819.
-- Preserve the R2 quotas and persistent setup token in the Render repository.
alter table app_private.photos add column if not exists stored_bytes bigint not null default 0;
create table app_private.app_settings (
  key text primary key, value text not null
);
create table app_private.photo_reservations (
  token text primary key, job_id bigint not null, bytes_count bigint not null,
  photo_count integer not null, created_at double precision not null
);
create table app_private.photo_counters (
  key text primary key, used integer not null, expires double precision not null
);
create index photo_reservations_job on app_private.photo_reservations(job_id);
create index photo_counters_expiry on app_private.photo_counters(expires);
alter table app_private.app_settings enable row level security;
alter table app_private.photo_reservations enable row level security;
alter table app_private.photo_counters enable row level security;
revoke all on app_private.app_settings, app_private.photo_reservations, app_private.photo_counters
  from public, anon, authenticated;
