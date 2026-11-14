-- ============================================================================
-- Release 2, piece 20: PHOTOS (photographer logins and a public camera, stored outside Supabase)
-- Written 14 Nov 2026. Run AFTER r2_19. Tested on the scratch database before use. Safe to run twice. Changes no existing data.
--
-- The photos themselves live in Storj (an outside storage service); Supabase keeps only the records: who uploaded, how many bytes,
-- where the file is, and a tiny preview picture for the admin gallery. Nothing here ever receives or stores a photo file.
--
--   1. A new staff role "camera" (photographers). They are NOT gate staff and NOT admins.
--      is_staff() now means "admin or gate" ONLY, so a camera login cannot read bookings, tickets, phone numbers or payment proofs
--      (the five read rules and four functions that use is_staff() behave exactly as before for admin and gate).
--      is_camera() is the new check used by the photo functions.
--   2. Settings (admins change them in Admin, Settings, Photos; every change is written to the Settings log by the existing trigger):
--        photos_on            the master switch (default OFF: nothing can be uploaded)
--        photo_pool_cam_mb    ONE shared space for all photographers (default 10240 = 10 GB)
--        photo_pool_pub_mb    ONE shared space for the public (default 12288 = 12 GB)
--        photo_cap_pub_mb     the most ONE person can use (default 90 MB)
--        photo_max_cam_mb / photo_max_pub_mb   the biggest single photo (default 25 MB / 15 MB)
--        photo_total_mb       all the space available at the storage service (default 25600 = 25 GB); the two pools may not add up to more
--        photo_public_mode    'present' (default: only people the gate has marked Present) or 'any' (any paid ticket)
--   3. Each public person's space = the LOWER of (public pool / people Present) and the cap. People with the same phone number
--      in one booking share one combined space (that space times the number of those tickets).
--   4. Space is claimed BEFORE an upload starts (under a lock, so two phones can never claim the last megabytes), and kept for
--      20 minutes. The storage service is then asked for the real file size; a file bigger than the claim is deleted and refused.
--   5. Only the Edge Function (service_role) can reserve or confirm. Visitors can only ask for their own status.
-- ============================================================================

-- ---- 1. the camera role --------------------------------------------------------------------------------------------------
alter table public.staff drop constraint if exists staff_role_check;
alter table public.staff add constraint staff_role_check check (role = any (array['admin','gate','camera']));

-- is_staff(): admin or gate only (a camera login is not "staff" for any of the old rules)
create or replace function public.is_staff() returns boolean
 language sql stable security definer set search_path to 'public' as $function$
  select exists (select 1 from public.staff where user_id = auth.uid() and role in ('admin', 'gate')) $function$;
revoke all on function public.is_staff() from public, anon, authenticated, service_role;
grant execute on function public.is_staff() to authenticated;

create or replace function public.is_camera() returns boolean
 language sql stable security definer set search_path to 'public' as $function$
  select exists (select 1 from public.staff where user_id = auth.uid() and role = 'camera') $function$;
revoke all on function public.is_camera() from public, anon, authenticated, service_role;
grant execute on function public.is_camera() to authenticated;

-- ---- 2. settings ---------------------------------------------------------------------------------------------------------
alter table public.settings
  add column if not exists photos_on          boolean not null default false,
  add column if not exists photo_pool_cam_mb  integer not null default 10240 check (photo_pool_cam_mb between 0 and 1000000),
  add column if not exists photo_pool_pub_mb  integer not null default 12288 check (photo_pool_pub_mb between 0 and 1000000),
  add column if not exists photo_cap_pub_mb   integer not null default 90    check (photo_cap_pub_mb between 1 and 100000),
  add column if not exists photo_max_cam_mb   integer not null default 25    check (photo_max_cam_mb between 1 and 500),
  add column if not exists photo_max_pub_mb   integer not null default 15    check (photo_max_pub_mb between 1 and 100),
  add column if not exists photo_total_mb     integer not null default 25600 check (photo_total_mb between 0 and 10000000),
  add column if not exists photo_public_mode  text    not null default 'present' check (photo_public_mode in ('present', 'any'));
alter table public.settings drop constraint if exists settings_photo_pools_check;
alter table public.settings add constraint settings_photo_pools_check check (photo_pool_cam_mb + photo_pool_pub_mb <= photo_total_mb);

-- ---- 3. the records ------------------------------------------------------------------------------------------------------
create table if not exists public.photos (
  id            uuid primary key default gen_random_uuid(),
  kind          text not null check (kind in ('camera', 'public')),
  uploader      uuid references auth.users(id),                              -- a photographer (kind camera)
  ticket_id     uuid references public.tickets(id) on delete cascade,        -- the person the space belongs to (kind public)
  object_key    text not null unique,                                        -- where the file is at the storage service
  bytes_claimed bigint not null check (bytes_claimed > 0),
  bytes_actual  bigint check (bytes_actual > 0),
  status        text not null default 'reserved' check (status in ('reserved', 'stored', 'failed', 'expired', 'removed')),
  thumb         text check (thumb is null or char_length(thumb) <= 80000),   -- a tiny preview picture (data address) for the admin gallery
  created_at    timestamptz not null default now(),
  confirmed_at  timestamptz,
  constraint photos_owner_chk check ((kind = 'camera' and uploader is not null and ticket_id is null)
                                  or (kind = 'public' and ticket_id is not null and uploader is null))
);
create index if not exists photos_kind_status_idx on public.photos (kind, status);
create index if not exists photos_ticket_idx on public.photos (ticket_id) where ticket_id is not null;
create index if not exists photos_uploader_idx on public.photos (uploader) where uploader is not null;

alter table public.photos enable row level security;
drop policy if exists admin_read_photos on public.photos;
create policy admin_read_photos on public.photos for select to authenticated using (is_admin());
revoke all on public.photos from public, anon, authenticated;
grant select on public.photos to authenticated;

-- ---- 4. internal helpers (nobody outside the database can call these) ---------------------------------------------------
-- people the gate has marked Present: paid, not transferred away
create or replace function public._photo_present() returns integer
 language sql stable security definer set search_path to 'public' as $function$
  select count(*)::int from tickets t join bookings b on b.id = t.booking_id
   where t.checked_in_at is not null and t.transferred_out_at is null and b.status = 'paid' $function$;
revoke all on function public._photo_present() from public, anon, authenticated, service_role;

-- bytes in use in one pool: stored photos, plus claims made in the last 20 minutes that are still waiting for their upload
create or replace function public._photo_used(p_kind text) returns bigint
 language sql stable security definer set search_path to 'public' as $function$
  select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint from photos
   where kind = p_kind and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes')) $function$;
revoke all on function public._photo_used(text) from public, anon, authenticated, service_role;

-- one person's space in bytes: the lower of (public pool / people Present, at least 1) and the cap
create or replace function public._photo_person_bytes(p_pool_mb integer, p_cap_mb integer, p_present integer) returns bigint
 language sql immutable set search_path to 'public' as $function$
  select least(p_cap_mb::numeric * 1048576, floor(p_pool_mb::numeric * 1048576 / greatest(coalesce(p_present, 0), 1)))::bigint $function$;
revoke all on function public._photo_person_bytes(integer, integer, integer) from public, anon, authenticated, service_role;

-- who is this public visitor? Booking ID + the ticket's own phone, exactly like the Tickets page.
-- err: MISMATCH (nothing matches), NOT_PAID, NOT_PRESENT (mode "present" and the gate has not admitted them), or null (fine)
-- all_ids: every live ticket of that booking with that phone; ids: the ones allowed to use the space right now
create or replace function public._photo_public_who(p_code text, p_phone text, out err text, out ids uuid[], out all_ids uuid[])
 language plpgsql stable security definer set search_path to 'public' as $function$
declare c text; ph text; b bookings%rowtype; s settings%rowtype;
begin
  select * into s from settings where id = 1;
  c  := replace(replace(replace(upper(coalesce(p_code, '')), 'O', '0'), ' ', ''), '-', '');
  ph := replace(replace(coalesce(p_phone, ''), ' ', ''), '-', '');
  if length(c) <> 8 or ph !~ '^[0-9]{10}$' then err := 'MISMATCH'; return; end if;
  select * into b from bookings where booking_code = c;
  if not found then err := 'MISMATCH'; return; end if;
  select array_agg(t.id order by t.reg_seq) into all_ids
    from tickets t where t.booking_id = b.id and t.phone = ph and t.transferred_out_at is null;
  if all_ids is null then err := 'MISMATCH'; return; end if;
  if b.status <> 'paid' then err := 'NOT_PAID'; all_ids := null; return; end if;
  if s.photo_public_mode = 'present' then
    select array_agg(t.id order by t.reg_seq) into ids from tickets t where t.id = any(all_ids) and t.checked_in_at is not null;
    if ids is null then err := 'NOT_PRESENT'; return; end if;
  else
    ids := all_ids;
  end if;
end $function$;
revoke all on function public._photo_public_who(text, text) from public, anon, authenticated, service_role;

-- ---- 5. what visitors and photographers may ask --------------------------------------------------------------------------
-- the public page: is the photo feature on, and what are its rules? (no personal data)
create or replace function public.get_photos_info() returns jsonb
 language sql stable security definer set search_path to 'public' as $function$
  select jsonb_build_object('on', s.photos_on, 'mode', s.photo_public_mode, 'max_bytes', s.photo_max_pub_mb::bigint * 1048576)
    from settings s where s.id = 1 $function$;
revoke all on function public.get_photos_info() from public, anon, authenticated, service_role;
grant execute on function public.get_photos_info() to anon, authenticated;

-- a public visitor's own space, after Booking ID + phone
create or replace function public.photo_public_status(p_code text, p_phone text) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; present int; per bigint; lim bigint; mine bigint; pool bigint; pused bigint;
begin
  select * into s from settings where id = 1;
  if not s.photos_on then return jsonb_build_object('ok', false, 'error', 'PHOTOS_OFF'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  present := _photo_present();
  per  := _photo_person_bytes(s.photo_pool_pub_mb, s.photo_cap_pub_mb, present);
  lim  := per * array_length(w.ids, 1);
  select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from photos
   where ticket_id = any(w.all_ids) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
  pool := s.photo_pool_pub_mb::bigint * 1048576; pused := _photo_used('public');
  return jsonb_build_object('ok', true, 'limit_bytes', lim, 'used_bytes', mine,
           'left_bytes', greatest(0, least(lim - mine, pool - pused)),
           'pool_left_bytes', greatest(0, pool - pused),
           'max_bytes', s.photo_max_pub_mb::bigint * 1048576, 'present', present);
end $function$;
revoke all on function public.photo_public_status(text, text) from public, anon, authenticated, service_role;
grant execute on function public.photo_public_status(text, text) to anon, authenticated;

-- a photographer's (or admin's) view of the shared photographer space
create or replace function public.photo_camera_status() returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; pool bigint; used bigint; mine record;
begin
  if not (is_camera() or is_admin()) then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1;
  pool := s.photo_pool_cam_mb::bigint * 1048576; used := _photo_used('camera');
  select count(*)::int as n, coalesce(sum(bytes_actual), 0)::bigint as b into mine
    from photos where kind = 'camera' and uploader = auth.uid() and status = 'stored';
  return jsonb_build_object('on', s.photos_on, 'pool_bytes', pool, 'used_bytes', used, 'left_bytes', greatest(0, pool - used),
           'max_bytes', s.photo_max_cam_mb::bigint * 1048576, 'my_count', mine.n, 'my_bytes', mine.b);
end $function$;
revoke all on function public.photo_camera_status() from public, anon, authenticated, service_role;
grant execute on function public.photo_camera_status() to authenticated;

-- ---- 6. the Edge Function's doors (service_role only) --------------------------------------------------------------------
-- claim space for ONE photo. p_kind 'camera' needs p_user (the login the Edge Function has already verified);
-- 'public' needs the Booking ID + phone. Returns {ok:true, id, key, left_bytes} or {ok:false, error}.
create or replace function public.photo_reserve(p_kind text, p_user uuid, p_code text, p_phone text, p_bytes bigint, p_ext text)
 returns jsonb language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; ext text; pid uuid := gen_random_uuid(); k text; pool bigint; used bigint; mine bigint;
        w record; present int; per bigint; lim bigint; owner uuid;
begin
  select * into s from settings where id = 1 for update;            -- one claim at a time: the totals can never be beaten by a race
  ext := lower(coalesce(p_ext, ''));
  if p_kind not in ('camera', 'public') then return jsonb_build_object('ok', false, 'error', 'BAD_KIND'); end if;
  if p_bytes is null or p_bytes <= 0 then return jsonb_build_object('ok', false, 'error', 'BAD_SIZE'); end if;
  if not s.photos_on then return jsonb_build_object('ok', false, 'error', 'PHOTOS_OFF'); end if;
  if p_kind = 'camera' then
    if p_user is null or not exists (select 1 from staff where user_id = p_user and role in ('camera', 'admin')) then
      return jsonb_build_object('ok', false, 'error', 'NOT_ALLOWED'); end if;
    if ext not in ('jpg', 'jpeg', 'png', 'heic', 'heif', 'webp', 'dng') then return jsonb_build_object('ok', false, 'error', 'BAD_TYPE'); end if;
    if p_bytes > s.photo_max_cam_mb::bigint * 1048576 then return jsonb_build_object('ok', false, 'error', 'TOO_BIG'); end if;
    pool := s.photo_pool_cam_mb::bigint * 1048576; used := _photo_used('camera');
    if used + p_bytes > pool then return jsonb_build_object('ok', false, 'error', 'POOL_FULL'); end if;
    k := 'camera/' || p_user::text || '/' || pid::text || '.' || ext;
    insert into photos (id, kind, uploader, object_key, bytes_claimed) values (pid, 'camera', p_user, k, p_bytes);
    return jsonb_build_object('ok', true, 'id', pid, 'key', k, 'left_bytes', pool - used - p_bytes);
  end if;
  -- public
  if ext not in ('jpg', 'jpeg', 'png', 'heic', 'heif', 'webp') then return jsonb_build_object('ok', false, 'error', 'BAD_TYPE'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  if p_bytes > s.photo_max_pub_mb::bigint * 1048576 then return jsonb_build_object('ok', false, 'error', 'TOO_BIG'); end if;
  present := _photo_present();
  per  := _photo_person_bytes(s.photo_pool_pub_mb, s.photo_cap_pub_mb, present);
  lim  := per * array_length(w.ids, 1);
  select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from photos
   where ticket_id = any(w.all_ids) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
  if mine + p_bytes > lim then return jsonb_build_object('ok', false, 'error', 'PERSON_FULL'); end if;
  pool := s.photo_pool_pub_mb::bigint * 1048576; used := _photo_used('public');
  if used + p_bytes > pool then return jsonb_build_object('ok', false, 'error', 'POOL_FULL'); end if;
  owner := w.ids[1];
  k := 'public/' || owner::text || '/' || pid::text || '.' || ext;
  insert into photos (id, kind, ticket_id, object_key, bytes_claimed) values (pid, 'public', owner, k, p_bytes);
  return jsonb_build_object('ok', true, 'id', pid, 'key', k, 'left_bytes', least(lim - mine - p_bytes, pool - used - p_bytes));
end $function$;
revoke all on function public.photo_reserve(text, uuid, text, text, bigint, text) from public, anon, authenticated, service_role;
grant execute on function public.photo_reserve(text, uuid, text, text, bigint, text) to service_role;

-- the upload is done and the storage service reported the real size. Keeps the claim only if the file is not bigger than claimed.
create or replace function public.photo_confirm(p_id uuid, p_actual bigint, p_thumb text) returns jsonb
 language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; r photos%rowtype;
begin
  select * into s from settings where id = 1 for update;            -- same lock as photo_reserve, so the totals stay exact
  select * into r from photos where id = p_id for update;
  if not found then return jsonb_build_object('ok', false, 'error', 'NOT_FOUND'); end if;
  if r.status = 'stored' then return jsonb_build_object('ok', true, 'already', true); end if;
  if r.status <> 'reserved' then return jsonb_build_object('ok', false, 'error', 'NOT_RESERVED'); end if;
  if r.created_at < now() - interval '20 minutes' then
    update photos set status = 'expired' where id = p_id;
    return jsonb_build_object('ok', false, 'error', 'EXPIRED', 'key', r.object_key);
  end if;
  if p_actual is null or p_actual <= 0 or p_actual > r.bytes_claimed then
    update photos set status = 'failed' where id = p_id;
    return jsonb_build_object('ok', false, 'error', 'SIZE_MISMATCH', 'key', r.object_key);
  end if;
  update photos set status = 'stored', bytes_actual = p_actual, confirmed_at = now(),
         thumb = case when p_thumb is not null and char_length(p_thumb) <= 80000 then p_thumb end
   where id = p_id;
  return jsonb_build_object('ok', true);
end $function$;
revoke all on function public.photo_confirm(uuid, bigint, text) from public, anon, authenticated, service_role;
grant execute on function public.photo_confirm(uuid, bigint, text) to service_role;

-- the upload did not happen (the phone gave up, no network): free the claimed space at once
create or replace function public.photo_fail(p_id uuid) returns void
 language sql security definer set search_path to 'public' as $function$
  update photos set status = 'failed' where id = p_id and status = 'reserved' $function$;
revoke all on function public.photo_fail(uuid) from public, anon, authenticated, service_role;
grant execute on function public.photo_fail(uuid) to service_role;

-- ---- 7. admin ------------------------------------------------------------------------------------------------------------
-- change the rules (any argument left out stays as it is). The Settings log records each changed value by itself.
create or replace function public.admin_set_photo_settings(
  p_on boolean default null, p_pool_cam_mb integer default null, p_pool_pub_mb integer default null,
  p_cap_pub_mb integer default null, p_max_cam_mb integer default null, p_max_pub_mb integer default null,
  p_total_mb integer default null, p_mode text default null) returns void
 language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; cam int; pub int; tot int;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_pool_cam_mb is not null and p_pool_cam_mb not between 0 and 1000000 then raise exception 'INVALID_POOL'; end if;
  if p_pool_pub_mb is not null and p_pool_pub_mb not between 0 and 1000000 then raise exception 'INVALID_POOL'; end if;
  if p_cap_pub_mb is not null and p_cap_pub_mb not between 1 and 100000 then raise exception 'INVALID_CAP'; end if;
  if p_max_cam_mb is not null and p_max_cam_mb not between 1 and 500 then raise exception 'INVALID_MAX'; end if;
  if p_max_pub_mb is not null and p_max_pub_mb not between 1 and 100 then raise exception 'INVALID_MAX'; end if;
  if p_total_mb is not null and p_total_mb not between 0 and 10000000 then raise exception 'INVALID_TOTAL'; end if;
  if p_mode is not null and p_mode not in ('present', 'any') then raise exception 'INVALID_MODE'; end if;
  select * into s from settings where id = 1 for update;
  cam := coalesce(p_pool_cam_mb, s.photo_pool_cam_mb); pub := coalesce(p_pool_pub_mb, s.photo_pool_pub_mb); tot := coalesce(p_total_mb, s.photo_total_mb);
  if cam + pub > tot then raise exception 'POOLS_TOO_BIG'; end if;
  update settings set
    photos_on         = coalesce(p_on, photos_on),
    photo_pool_cam_mb = cam, photo_pool_pub_mb = pub, photo_total_mb = tot,
    photo_cap_pub_mb  = coalesce(p_cap_pub_mb, photo_cap_pub_mb),
    photo_max_cam_mb  = coalesce(p_max_cam_mb, photo_max_cam_mb),
    photo_max_pub_mb  = coalesce(p_max_pub_mb, photo_max_pub_mb),
    photo_public_mode = coalesce(p_mode, photo_public_mode)
  where id = 1;
end $function$;
revoke all on function public.admin_set_photo_settings(boolean, integer, integer, integer, integer, integer, integer, text) from public, anon, authenticated, service_role;
grant execute on function public.admin_set_photo_settings(boolean, integer, integer, integer, integer, integer, integer, text) to authenticated;

-- the numbers behind the Photos card
create or replace function public.admin_photo_summary() returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; present int; per bigint;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1;
  present := _photo_present();
  per := _photo_person_bytes(s.photo_pool_pub_mb, s.photo_cap_pub_mb, present);
  return jsonb_build_object(
    'on', s.photos_on, 'mode', s.photo_public_mode, 'present', present, 'person_bytes', per,
    'total_bytes', s.photo_total_mb::bigint * 1048576,
    'cam', jsonb_build_object('pool_bytes', s.photo_pool_cam_mb::bigint * 1048576, 'used_bytes', _photo_used('camera'),
             'count', (select count(*) from photos where kind = 'camera' and status = 'stored')),
    'pub', jsonb_build_object('pool_bytes', s.photo_pool_pub_mb::bigint * 1048576, 'used_bytes', _photo_used('public'),
             'count', (select count(*) from photos where kind = 'public' and status = 'stored'),
             'people', (select count(distinct ticket_id) from photos where kind = 'public' and status = 'stored')),
    'by_camera', coalesce((select jsonb_agg(jsonb_build_object('name', x.name, 'count', x.n, 'bytes', x.b) order by x.b desc)
       from (select coalesce(st.name, 'removed login') as name, count(*) as n, sum(p.bytes_actual) as b
               from photos p left join staff st on st.user_id = p.uploader
              where p.kind = 'camera' and p.status = 'stored' group by 1) x), '[]'::jsonb),
    'unfinished', (select count(*) from photos where status in ('reserved', 'failed', 'expired')));
end $function$;
revoke all on function public.admin_photo_summary() from public, anon, authenticated, service_role;
grant execute on function public.admin_photo_summary() to authenticated;

-- take one photo out of the gallery (the Edge Function then deletes the file). Returns where the file is.
create or replace function public.admin_photo_remove(p_id uuid) returns text
 language plpgsql security definer set search_path to 'public' as $function$
declare r photos%rowtype;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into r from photos where id = p_id for update;
  if not found or r.status <> 'stored' then raise exception 'NOT_FOUND'; end if;
  update photos set status = 'removed', thumb = null where id = p_id;
  insert into settings_log (changed_by, who, area, field, old_value, new_value)
  values (auth.uid(), _actor(), 'settings', 'photo removed', left(r.object_key, 300), null);
  return r.object_key;
end $function$;
revoke all on function public.admin_photo_remove(uuid) from public, anon, authenticated, service_role;
grant execute on function public.admin_photo_remove(uuid) to authenticated;
