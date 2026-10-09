-- Applied to Supabase project kiuvljeudopvaumkkrrd as version 20261008235936.
-- Complete the indexes for foreign keys used by the app and session revocation.
create index if not exists activity_user on app_private.activity(user_id);
create index if not exists notifications_job on app_private.notifications(job_id);
create index if not exists photos_uploader on app_private.photos(uploaded_by);
create index if not exists sessions_user on app_private.sessions(user_id);
