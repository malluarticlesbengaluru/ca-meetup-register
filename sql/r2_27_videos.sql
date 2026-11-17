-- ============================================================================
-- Release 2, piece 27: ATTENDEE VIDEOS (third Storj account; the page shows a sharp still picture, never plays the video)
-- Written 17 Nov 2026. Run AFTER r2_26. Safe to run twice. Changes no photo and no existing rule.
--
-- Videos live in their OWN table and their OWN limits, so nothing about photos can change. Rules:
--   * Only attendees upload videos (Booking ID + phone, same login and same "Present" rule as photos). Photographers do not.
--   * Admin-set limits (Admin > Settings > Photos): videos on/off, the shared video space, the biggest single video, and the space
--     one person (one ticket) may use for videos. The still preview counts together with the video.
--   * The page shows a still frame (made in the phone, about 1600 px) next to a tiny one saved in the database. Nobody plays or
--     downloads a video on the site, because every byte served counts against Storj's free download allowance.
--   * Who sees a still: the owner always; every admin; and every attendee when the photo setting "who sees photos" is "all".
--   * The original video: only admins whose photo_download switch is on (the same switch as for photo originals).
-- ============================================================================
alter table public.settings
  add column if not exists videos_on       boolean not null default false,
  add column if not exists video_pool_mb   integer not null default 20480 check (video_pool_mb between 0 and 10000000),
  add column if not exists video_max_mb    integer not null default 150   check (video_max_mb between 1 and 2000),
  add column if not exists video_cap_mb    integer not null default 160   check (video_cap_mb between 1 and 100000);

create table if not exists public.videos (
  id            uuid primary key default gen_random_uuid(),
  ticket_id     uuid not null references public.tickets(id) on delete cascade,   -- the person the space belongs to
  object_key    text not null unique,                                             -- video/<ticket>/<id>.<ext> at the third Storj account
  bytes_claimed bigint not null check (bytes_claimed > 0),
  bytes_actual  bigint check (bytes_actual > 0),                                  -- video + still preview
  preview_bytes bigint check (preview_bytes is null or preview_bytes between 1 and 2097152),
  status        text not null default 'reserved' check (status in ('reserved', 'stored', 'failed', 'expired', 'removed')),
  thumb         text check (thumb is null or (char_length(thumb) <= 80000 and thumb ~ '^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$')),
  created_at    timestamptz not null default now(),
  confirmed_at  timestamptz
);
create index if not exists videos_status_idx on public.videos (status);
create index if not exists videos_ticket_idx on public.videos (ticket_id);
alter table public.videos enable row level security;
drop policy if exists admin_read_videos on public.videos;
create policy admin_read_videos on public.videos for select to authenticated using (is_admin());
revoke all on public.videos from public, anon, authenticated;
grant select on public.videos to authenticated;
grant select on public.videos to service_role;

-- video space in use: stored videos plus claims made in the last 20 minutes that still wait for their upload
create or replace function public._video_used() returns bigint
 language sql stable security definer set search_path to 'public' as $function$
  select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint from videos
   where status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes') $function$;
revoke all on function public._video_used() from public, anon, authenticated, service_role;

-- ---- attendee side -------------------------------------------------------------------------------------------------------
create or replace function public.get_videos_info() returns jsonb
 language sql stable security definer set search_path to 'public' as $function$
  select jsonb_build_object('on', s.videos_on, 'max_bytes', s.video_max_mb::bigint * 1048576) from settings s where s.id = 1 $function$;
revoke all on function public.get_videos_info() from public, anon, authenticated, service_role;
grant execute on function public.get_videos_info() to anon, authenticated;

create or replace function public.video_public_status(p_code text, p_phone text) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; lim bigint; mine bigint; pool bigint; pused bigint;
begin
  select * into s from settings where id = 1;
  if not s.videos_on then return jsonb_build_object('ok', false, 'error', 'VIDEOS_OFF'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  lim := s.video_cap_mb::bigint * 1048576 * array_length(w.ids, 1);
  select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from videos
   where ticket_id = any(w.all_ids) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
  pool := s.video_pool_mb::bigint * 1048576; pused := _video_used();
  return jsonb_build_object('ok', true, 'limit_bytes', lim, 'used_bytes', mine,
           'left_bytes', greatest(0, least(lim - mine, pool - pused)), 'max_bytes', s.video_max_mb::bigint * 1048576);
end $function$;
revoke all on function public.video_public_status(text, text) from public, anon, authenticated, service_role;
grant execute on function public.video_public_status(text, text) to anon, authenticated;

-- the stills an attendee may see: their own; everyone's when "who sees photos" is "all"
create or replace function public.video_public_list(p_code text, p_phone text, p_before timestamptz default null, p_limit integer default 24) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; lim integer; items jsonb;
begin
  select * into s from settings where id = 1;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.all_ids is null then return jsonb_build_object('ok', false, 'error', coalesce(w.err, 'MISMATCH')); end if;
  lim := least(greatest(coalesce(p_limit, 24), 1), 48);
  select coalesce(jsonb_agg(jsonb_build_object('id', q.id, 'bytes', q.bytes_actual, 'thumb', q.thumb, 'at', q.created_at,
                                                'mine', q.mine, 'pv', q.pv) order by q.created_at desc), '[]'::jsonb)
    into items
    from (select v.id, v.bytes_actual, v.thumb, v.created_at, (v.preview_bytes is not null) as pv, (v.ticket_id = any (w.all_ids)) as mine
            from videos v
           where v.status = 'stored' and (p_before is null or v.created_at < p_before)
             and (s.photo_visibility = 'all' or v.ticket_id = any (w.all_ids))
           order by v.created_at desc limit lim) q;
  return jsonb_build_object('ok', true, 'items', items, 'page', lim, 'can_download', false);
end $function$;
revoke all on function public.video_public_list(text, text, timestamptz, integer) from public, anon, authenticated, service_role;
grant execute on function public.video_public_list(text, text, timestamptz, integer) to anon, authenticated;

-- ---- Edge Function doors (service_role only) -----------------------------------------------------------------------------
create or replace function public.video_reserve(p_code text, p_phone text, p_bytes bigint, p_ext text) returns jsonb
 language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; ext text; vid uuid := gen_random_uuid(); k text; w record; lim bigint; mine bigint; pool bigint; used bigint;
begin
  select * into s from settings where id = 1 for update;            -- one claim at a time, so a race cannot beat the totals
  ext := lower(coalesce(p_ext, ''));
  if p_bytes is null or p_bytes <= 0 then return jsonb_build_object('ok', false, 'error', 'BAD_SIZE'); end if;
  if not s.videos_on then return jsonb_build_object('ok', false, 'error', 'VIDEOS_OFF'); end if;
  if ext not in ('mp4', 'mov', 'm4v', 'webm', '3gp') then return jsonb_build_object('ok', false, 'error', 'BAD_TYPE'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  if p_bytes > s.video_max_mb::bigint * 1048576 then return jsonb_build_object('ok', false, 'error', 'TOO_BIG'); end if;
  lim := s.video_cap_mb::bigint * 1048576 * array_length(w.ids, 1);
  select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from videos
   where ticket_id = any(w.all_ids) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
  if mine + p_bytes > lim then return jsonb_build_object('ok', false, 'error', 'PERSON_FULL'); end if;
  pool := s.video_pool_mb::bigint * 1048576; used := _video_used();
  if used + p_bytes > pool then return jsonb_build_object('ok', false, 'error', 'POOL_FULL'); end if;
  k := 'video/' || w.ids[1]::text || '/' || vid::text || '.' || ext;
  insert into videos (id, ticket_id, object_key, bytes_claimed) values (vid, w.ids[1], k, p_bytes);
  return jsonb_build_object('ok', true, 'id', vid, 'key', k, 'left_bytes', least(lim - mine - p_bytes, pool - used - p_bytes));
end $function$;
revoke all on function public.video_reserve(text, text, bigint, text) from public, anon, authenticated, service_role;
grant execute on function public.video_reserve(text, text, bigint, text) to service_role;

-- the Edge Function passes the object key so it can look up the file at Storj (the key is never given to the page)
create or replace function public.video_key(p_id uuid) returns text
 language sql stable security definer set search_path to 'public' as $function$ select object_key from videos where id = p_id $function$;
revoke all on function public.video_key(uuid) from public, anon, authenticated, service_role;
grant execute on function public.video_key(uuid) to service_role;

create or replace function public.video_confirm(p_id uuid, p_actual bigint, p_thumb text, p_preview bigint default null) returns jsonb
 language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; r videos%rowtype;
begin
  select * into s from settings where id = 1 for update;
  select * into r from videos where id = p_id for update;
  if not found then return jsonb_build_object('ok', false, 'error', 'NOT_FOUND'); end if;
  if r.status = 'stored' then return jsonb_build_object('ok', true, 'already', true); end if;
  if r.status <> 'reserved' then return jsonb_build_object('ok', false, 'error', 'NOT_RESERVED'); end if;
  if r.created_at < now() - interval '20 minutes' then
    update videos set status = 'expired' where id = p_id;
    return jsonb_build_object('ok', false, 'error', 'EXPIRED', 'key', r.object_key);
  end if;
  if p_actual is null or p_actual <= 0 or p_actual > r.bytes_claimed then
    update videos set status = 'failed' where id = p_id;
    return jsonb_build_object('ok', false, 'error', 'SIZE_MISMATCH', 'key', r.object_key);
  end if;
  update videos set status = 'stored', bytes_actual = p_actual, confirmed_at = now(),
         thumb = case when p_thumb is not null and char_length(p_thumb) <= 80000 and p_thumb ~ '^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$' then p_thumb end,
         preview_bytes = case when p_preview is not null and p_preview between 1 and 2097152 and p_preview < p_actual then p_preview end
   where id = p_id;
  return jsonb_build_object('ok', true);
end $function$;
revoke all on function public.video_confirm(uuid, bigint, text, bigint) from public, anon, authenticated, service_role;
grant execute on function public.video_confirm(uuid, bigint, text, bigint) to service_role;

create or replace function public.video_fail(p_id uuid) returns void
 language sql security definer set search_path to 'public' as $function$
  update videos set status = 'failed' where id = p_id and status = 'reserved' $function$;
revoke all on function public.video_fail(uuid) from public, anon, authenticated, service_role;
grant execute on function public.video_fail(uuid) to service_role;

-- the Storj name of the sharp still, only if this login may see this video. p_user set = staff login; null = attendee.
create or replace function public.video_preview_key(p_id uuid, p_user uuid, p_code text, p_phone text) returns text
 language plpgsql stable security definer set search_path to 'public' as $function$
declare r videos%rowtype; s settings%rowtype; w record;
begin
  select * into r from videos where id = p_id and status = 'stored' and preview_bytes is not null;
  if not found then return null; end if;
  select * into s from settings where id = 1;
  if p_user is not null then
    if exists (select 1 from staff where user_id = p_user and role = 'admin') then return r.object_key || '.p.jpg'; end if;
    return null;
  end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.all_ids is null then return null; end if;
  if s.photo_visibility = 'all' or r.ticket_id = any (w.all_ids) then return r.object_key || '.p.jpg'; end if;
  return null;
end $function$;
revoke all on function public.video_preview_key(uuid, uuid, text, text) from public, anon, authenticated, service_role;
grant execute on function public.video_preview_key(uuid, uuid, text, text) to service_role;

-- the original video: only an admin whose photo_download switch is on
create or replace function public.video_original_key(p_id uuid, p_user uuid) returns text
 language plpgsql stable security definer set search_path to 'public' as $function$
declare k text;
begin
  if not photo_may_download(p_user) then return null; end if;
  select object_key into k from videos where id = p_id and status = 'stored';
  return k;
end $function$;
revoke all on function public.video_original_key(uuid, uuid) from public, anon, authenticated, service_role;
grant execute on function public.video_original_key(uuid, uuid) to service_role;

create or replace function public.video_remove_public(p_id uuid, p_code text, p_phone text) returns text
 language plpgsql security definer set search_path to 'public' as $function$
declare r videos%rowtype; w record;
begin
  select * into w from _photo_public_who(p_code, p_phone);
  if w.all_ids is null then return null; end if;
  select * into r from videos where id = p_id for update;
  if not found or r.status <> 'stored' or not (r.ticket_id = any (w.all_ids)) then return null; end if;
  update videos set status = 'removed', thumb = null where id = p_id;
  insert into settings_log (changed_by, who, area, field, old_value, new_value)
  values (null, 'attendee', 'settings', 'video removed (own)', left(r.object_key, 300), null);
  return r.object_key;
end $function$;
revoke all on function public.video_remove_public(uuid, text, text) from public, anon, authenticated, service_role;
grant execute on function public.video_remove_public(uuid, text, text) to service_role;

-- ---- admin side ----------------------------------------------------------------------------------------------------------
create or replace function public.admin_video_list(p_before timestamptz default null, p_limit integer default 24) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare lim integer; items jsonb;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  lim := least(greatest(coalesce(p_limit, 24), 1), 48);
  select coalesce(jsonb_agg(jsonb_build_object('id', q.id, 'bytes', q.bytes_actual, 'thumb', q.thumb, 'at', q.created_at,
                                                'mine', false, 'pv', q.pv, 'by', q.by) order by q.created_at desc), '[]'::jsonb)
    into items
    from (select v.id, v.bytes_actual, v.thumb, v.created_at, (v.preview_bytes is not null) as pv,
                 (select t.name from tickets t where t.id = v.ticket_id) as by
            from videos v where v.status = 'stored' and (p_before is null or v.created_at < p_before)
           order by v.created_at desc limit lim) q;
  return jsonb_build_object('ok', true, 'items', items, 'page', lim, 'can_download', photo_may_download(auth.uid()));
end $function$;
revoke all on function public.admin_video_list(timestamptz, integer) from public, anon, authenticated, service_role;
grant execute on function public.admin_video_list(timestamptz, integer) to authenticated;

create or replace function public.admin_video_remove(p_id uuid) returns text
 language plpgsql security definer set search_path to 'public' as $function$
declare r videos%rowtype;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into r from videos where id = p_id for update;
  if not found or r.status <> 'stored' then raise exception 'NOT_FOUND'; end if;
  update videos set status = 'removed', thumb = null where id = p_id;
  insert into settings_log (changed_by, who, area, field, old_value, new_value)
  values (auth.uid(), _actor(), 'settings', 'video removed', left(r.object_key, 300), null);
  return r.object_key;
end $function$;
revoke all on function public.admin_video_remove(uuid) from public, anon, authenticated, service_role;
grant execute on function public.admin_video_remove(uuid) to authenticated;

create or replace function public.admin_set_video_settings(p_on boolean default null, p_pool_mb integer default null,
  p_max_mb integer default null, p_cap_mb integer default null) returns void
 language plpgsql security definer set search_path to 'public' as $function$
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_pool_mb is not null and p_pool_mb not between 0 and 10000000 then raise exception 'INVALID_POOL'; end if;
  if p_max_mb is not null and p_max_mb not between 1 and 2000 then raise exception 'INVALID_MAX'; end if;
  if p_cap_mb is not null and p_cap_mb not between 1 and 100000 then raise exception 'INVALID_CAP'; end if;
  update settings set videos_on = coalesce(p_on, videos_on), video_pool_mb = coalesce(p_pool_mb, video_pool_mb),
         video_max_mb = coalesce(p_max_mb, video_max_mb), video_cap_mb = coalesce(p_cap_mb, video_cap_mb) where id = 1;
end $function$;
revoke all on function public.admin_set_video_settings(boolean, integer, integer, integer) from public, anon, authenticated, service_role;
grant execute on function public.admin_set_video_settings(boolean, integer, integer, integer) to authenticated;

create or replace function public.admin_video_summary() returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1;
  return jsonb_build_object('on', s.videos_on, 'pool_bytes', s.video_pool_mb::bigint * 1048576, 'used_bytes', _video_used(),
    'max_bytes', s.video_max_mb::bigint * 1048576, 'cap_bytes', s.video_cap_mb::bigint * 1048576,
    'count', (select count(*) from videos where status = 'stored'),
    'people', (select count(distinct ticket_id) from videos where status = 'stored'),
    'unfinished', (select count(*) from videos where status in ('reserved', 'failed', 'expired')));
end $function$;
revoke all on function public.admin_video_summary() from public, anon, authenticated, service_role;
grant execute on function public.admin_video_summary() to authenticated;
