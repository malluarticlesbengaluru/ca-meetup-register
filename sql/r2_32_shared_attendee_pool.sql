-- ============================================================================
-- Release 2, piece 32: ONE SHARED SPACE FOR ATTENDEES (photos and videos together), spread over up to three Storj accounts
-- Written 21 Nov 2026. Run AFTER r2_28 (and r2_29 to r2_31). Safe to run twice. Changes no photo and no video already saved.
--
-- Switch: settings.attendee_shared (default OFF). While it is OFF everything behaves exactly as before (separate photo pool, video pool and caps).
-- While it is ON, for attendees only (photographers are not touched):
--   * ONE pool (settings.attendee_pool_mb, default 75 GB) holds photos and videos together; nobody has a separate photo or video amount.
--   * Each person's space = the lower of (pool / people marked Present) and settings.attendee_cap_mb, per person on the booking login,
--     used by photos and videos together. Space received from friends (or given away) counts for both, whatever "kind" the gift was made as.
--   * "Biggest photo" (photo_max_pub_mb) and "Biggest video" (video_max_mb) still limit one file.
--   * The old photo_pool_pub_mb, photo_cap_pub_mb, video_pool_mb and video_cap_mb are ignored for attendees until the switch is turned off.
--   * New files are stored in the attendee Storj account that holds the least so far (keys "att/1/...", "att/2/...", "att/3/...").
--       account 1 = the "public" photo account (STORJ_PUB_*), 2 = the video account (STORJ_VID_*), 3 = the new account (STORJ_ATT_*).
--     The Edge Function tells the database which of the three exist (p_acc); files saved before keep their old keys and accounts.
-- Re-created below: _space_net, _space_left, photo_public_status, photo_reserve, video_public_status, video_reserve, space_overview.
-- New: three settings columns, _att_* helpers, admin_set_attendee_space, admin_attendee_summary.
-- ============================================================================
alter table public.settings add column if not exists attendee_shared  boolean not null default false;
alter table public.settings add column if not exists attendee_pool_mb integer not null default 76800 check (attendee_pool_mb between 0 and 10000000);
alter table public.settings add column if not exists attendee_cap_mb  integer not null default 500   check (attendee_cap_mb between 1 and 100000);

-- ---- helpers ------------------------------------------------------------------------------------------------------------
-- photo and video bytes of one person (all live tickets of the login), counting claims of the last 20 minutes that wait for their upload
create or replace function public._att_mine(p_all uuid[]) returns bigint
 language sql stable security definer set search_path to 'public' as $function$
  select (select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0) from photos
           where ticket_id = any(p_all) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes')))::bigint
       + (select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0) from videos
           where ticket_id = any(p_all) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes')))::bigint $function$;
revoke all on function public._att_mine(uuid[]) from public, anon, authenticated, service_role;

-- everything attendees use in the shared pool: public photos and videos
create or replace function public._att_used_all() returns bigint
 language sql stable security definer set search_path to 'public' as $function$
  select _photo_used('public') + _video_used() $function$;
revoke all on function public._att_used_all() from public, anon, authenticated, service_role;

-- one person's limit in the shared pool: per-person share x people on the login + received - given
create or replace function public._att_limit(p_count integer, p_key uuid) returns bigint
 language sql stable security definer set search_path to 'public' as $function$
  select _photo_person_bytes(s.attendee_pool_mb, s.attendee_cap_mb, _photo_present()) * coalesce(p_count, 0) + _space_net('all', p_key)
    from settings s where s.id = 1 $function$;
revoke all on function public._att_limit(integer, uuid) from public, anon, authenticated, service_role;

-- bytes held by one attendee storage account (1, 2 or 3): old keys public/ (1) and video/ (2), new keys att/<n>/
create or replace function public._att_acct_used(p_n integer) returns bigint
 language sql stable security definer set search_path to 'public' as $function$
  select (select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0) from photos
           where kind = 'public' and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'))
             and (object_key like 'att/' || p_n || '/%' or (p_n = 1 and object_key like 'public/%')))::bigint
       + (select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0) from videos
           where (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'))
             and (object_key like 'att/' || p_n || '/%' or (p_n = 2 and object_key like 'video/%')))::bigint $function$;
revoke all on function public._att_acct_used(integer) from public, anon, authenticated, service_role;

-- which of the available accounts gets the next file: the one holding the least (lowest number on a tie). Unknown list = accounts 1 and 2.
create or replace function public._att_pick(p_acc integer[]) returns integer
 language sql stable security definer set search_path to 'public' as $function$
  select coalesce((select n from unnest(coalesce(nullif(p_acc, '{}'::integer[]), array[1, 2])) n where n in (1, 2, 3) order by _att_acct_used(n), n limit 1), 1) $function$;
revoke all on function public._att_pick(integer[]) from public, anon, authenticated, service_role;

-- ---- gifts: while the shared pool is on, a gift counts for photos and videos together --------------------------------------------
create or replace function public._space_net(p_kind text, p_key uuid) returns bigint
 language sql stable security definer set search_path to 'public' as $function$
  select coalesce(sum(case when to_key = p_key then mb else -mb end), 0)::bigint * 1048576
    from space_transfers
   where status = 'active' and (to_key = p_key or from_key = p_key)
     and (p_kind = 'all' or kind = p_kind or (select attendee_shared from settings where id = 1)) $function$;
revoke all on function public._space_net(text, uuid) from public, anon, authenticated, service_role;

create or replace function public._space_left(p_kind text, p_ids uuid[], p_all uuid[]) returns bigint
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; lim bigint; mine bigint;
begin
  select * into s from settings where id = 1;
  if s.attendee_shared then
    return _att_limit(coalesce(array_length(p_ids, 1), 0), p_all[1]) - _att_mine(p_all);
  end if;
  if p_kind = 'photo' then
    lim := _photo_person_bytes(s.photo_pool_pub_mb, s.photo_cap_pub_mb, _photo_present()) * coalesce(array_length(p_ids, 1), 0) + _space_net('photo', p_all[1]);
    select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from photos
     where ticket_id = any(p_all) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
  else
    lim := s.video_cap_mb::bigint * 1048576 * coalesce(array_length(p_ids, 1), 0) + _space_net('video', p_all[1]);
    select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from videos
     where ticket_id = any(p_all) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
  end if;
  return lim - mine;
end $function$;
revoke all on function public._space_left(text, uuid[], uuid[]) from public, anon, authenticated, service_role;

-- ---- photos --------------------------------------------------------------------------------------------------------------------
create or replace function public.photo_public_status(p_code text, p_phone text) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; present int; per bigint; lim bigint; mine bigint; pool bigint; pused bigint;
begin
  select * into s from settings where id = 1;
  if not s.photos_on then return jsonb_build_object('ok', false, 'error', 'PHOTOS_OFF'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  present := _photo_present();
  if s.attendee_shared then
    lim := _att_limit(array_length(w.ids, 1), w.all_ids[1]); mine := _att_mine(w.all_ids);
    pool := s.attendee_pool_mb::bigint * 1048576; pused := _att_used_all();
  else
    per  := _photo_person_bytes(s.photo_pool_pub_mb, s.photo_cap_pub_mb, present);
    lim  := per * array_length(w.ids, 1) + _space_net('photo', w.all_ids[1]);
    select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from photos
     where ticket_id = any(w.all_ids) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
    pool := s.photo_pool_pub_mb::bigint * 1048576; pused := _photo_used('public');
  end if;
  return jsonb_build_object('ok', true, 'limit_bytes', lim, 'used_bytes', mine,
           'left_bytes', greatest(0, least(lim - mine, pool - pused)),
           'pool_left_bytes', greatest(0, pool - pused),
           'max_bytes', s.photo_max_pub_mb::bigint * 1048576, 'present', present, 'shared', s.attendee_shared);
end $function$;
revoke all on function public.photo_public_status(text, text) from public, anon, authenticated, service_role;
grant execute on function public.photo_public_status(text, text) to anon, authenticated;

-- the old six-argument version is replaced by one with a seventh, optional argument (the storage accounts that exist)
drop function if exists public.photo_reserve(text, uuid, text, text, bigint, text);
create or replace function public.photo_reserve(p_kind text, p_user uuid, p_code text, p_phone text, p_bytes bigint, p_ext text, p_acc integer[] default null)
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
  if s.attendee_shared then
    lim := _att_limit(array_length(w.ids, 1), w.all_ids[1]); mine := _att_mine(w.all_ids);
    pool := s.attendee_pool_mb::bigint * 1048576; used := _att_used_all();
  else
    per  := _photo_person_bytes(s.photo_pool_pub_mb, s.photo_cap_pub_mb, present);
    lim  := per * array_length(w.ids, 1) + _space_net('photo', w.all_ids[1]);
    select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from photos
     where ticket_id = any(w.all_ids) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
    pool := s.photo_pool_pub_mb::bigint * 1048576; used := _photo_used('public');
  end if;
  if mine + p_bytes > lim then return jsonb_build_object('ok', false, 'error', 'PERSON_FULL'); end if;
  if used + p_bytes > pool then return jsonb_build_object('ok', false, 'error', 'POOL_FULL'); end if;
  owner := w.ids[1];
  k := case when s.attendee_shared then 'att/' || _att_pick(p_acc) || '/' else 'public/' end || owner::text || '/' || pid::text || '.' || ext;
  insert into photos (id, kind, ticket_id, object_key, bytes_claimed) values (pid, 'public', owner, k, p_bytes);
  return jsonb_build_object('ok', true, 'id', pid, 'key', k, 'left_bytes', least(lim - mine - p_bytes, pool - used - p_bytes));
end $function$;
revoke all on function public.photo_reserve(text, uuid, text, text, bigint, text, integer[]) from public, anon, authenticated, service_role;
grant execute on function public.photo_reserve(text, uuid, text, text, bigint, text, integer[]) to service_role;

-- ---- videos --------------------------------------------------------------------------------------------------------------------
create or replace function public.video_public_status(p_code text, p_phone text) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; lim bigint; mine bigint; pool bigint; pused bigint;
begin
  select * into s from settings where id = 1;
  if not s.videos_on then return jsonb_build_object('ok', false, 'error', 'VIDEOS_OFF'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  if s.attendee_shared then
    lim := _att_limit(array_length(w.ids, 1), w.all_ids[1]); mine := _att_mine(w.all_ids);
    pool := s.attendee_pool_mb::bigint * 1048576; pused := _att_used_all();
  else
    lim := s.video_cap_mb::bigint * 1048576 * array_length(w.ids, 1) + _space_net('video', w.all_ids[1]);
    select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from videos
     where ticket_id = any(w.all_ids) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
    pool := s.video_pool_mb::bigint * 1048576; pused := _video_used();
  end if;
  return jsonb_build_object('ok', true, 'limit_bytes', lim, 'used_bytes', mine,
           'left_bytes', greatest(0, least(lim - mine, pool - pused)), 'max_bytes', s.video_max_mb::bigint * 1048576, 'shared', s.attendee_shared);
end $function$;
revoke all on function public.video_public_status(text, text) from public, anon, authenticated, service_role;
grant execute on function public.video_public_status(text, text) to anon, authenticated;

drop function if exists public.video_reserve(text, text, bigint, text);
create or replace function public.video_reserve(p_code text, p_phone text, p_bytes bigint, p_ext text, p_acc integer[] default null) returns jsonb
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
  if s.attendee_shared then
    lim := _att_limit(array_length(w.ids, 1), w.all_ids[1]); mine := _att_mine(w.all_ids);
    pool := s.attendee_pool_mb::bigint * 1048576; used := _att_used_all();
  else
    lim := s.video_cap_mb::bigint * 1048576 * array_length(w.ids, 1) + _space_net('video', w.all_ids[1]);
    select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from videos
     where ticket_id = any(w.all_ids) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
    pool := s.video_pool_mb::bigint * 1048576; used := _video_used();
  end if;
  if mine + p_bytes > lim then return jsonb_build_object('ok', false, 'error', 'PERSON_FULL'); end if;
  if used + p_bytes > pool then return jsonb_build_object('ok', false, 'error', 'POOL_FULL'); end if;
  k := case when s.attendee_shared then 'att/' || _att_pick(p_acc) || '/' else 'video/' end || w.ids[1]::text || '/' || vid::text || '.' || ext;
  insert into videos (id, ticket_id, object_key, bytes_claimed) values (vid, w.ids[1], k, p_bytes);
  return jsonb_build_object('ok', true, 'id', vid, 'key', k, 'left_bytes', least(lim - mine - p_bytes, pool - used - p_bytes));
end $function$;
revoke all on function public.video_reserve(text, text, bigint, text, integer[]) from public, anon, authenticated, service_role;
grant execute on function public.video_reserve(text, text, bigint, text, integer[]) to service_role;

-- ---- the Share screen: one flag more ('shared'), the rest as before ---------------------------------------------------------------
create or replace function public.space_overview(p_code text, p_phone text) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; me uuid; ph bigint; vd bigint; items jsonb;
begin
  select * into s from settings where id = 1;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  me := w.all_ids[1];
  ph := greatest(0, _space_left('photo', w.ids, w.all_ids)); vd := greatest(0, _space_left('video', w.ids, w.all_ids));
  select coalesce(jsonb_agg(jsonb_build_object('id', q.id, 'kind', q.kind, 'mb', q.mb, 'dir', q.dir, 'other', q.other, 'status', q.status, 'at', q.created_at,
           'can_return', q.dir = 'out' and q.status = 'active'
              and _space_left(q.kind, (select array_agg(t.id order by t.reg_seq) from tickets t where t.booking_id = (select booking_id from tickets where id = q.other_key) and t.phone = (select phone from tickets where id = q.other_key) and t.transferred_out_at is null),
                                      (select array_agg(t.id order by t.reg_seq) from tickets t where t.booking_id = (select booking_id from tickets where id = q.other_key) and t.phone = (select phone from tickets where id = q.other_key) and t.transferred_out_at is null))
                  >= q.mb::bigint * 1048576) order by q.created_at desc), '[]'::jsonb)
    into items
    from (select x.id, x.kind, x.mb, x.status, x.created_at, case when x.from_key = me then 'out' else 'in' end as dir,
                 case when x.from_key = me then x.to_key else x.from_key end as other_key,
                 (select t.name from tickets t where t.id = case when x.from_key = me then x.to_key else x.from_key end) as other
            from space_transfers x where x.from_key = me or x.to_key = me order by x.created_at desc limit 40) q;
  return jsonb_build_object('ok', true, 'sharing_on', s.space_sharing_on, 'shared', s.attendee_shared,
    'photo', jsonb_build_object('on', s.photos_on, 'give_bytes', ph, 'net_bytes', _space_net('photo', me)),
    'video', jsonb_build_object('on', s.videos_on, 'give_bytes', vd, 'net_bytes', _space_net('video', me)),
    'items', items);
end $function$;
revoke all on function public.space_overview(text, text) from public, anon, authenticated, service_role;
grant execute on function public.space_overview(text, text) to anon, authenticated;

-- ---- admin ---------------------------------------------------------------------------------------------------------------------
create or replace function public.admin_set_attendee_space(p_shared boolean default null, p_pool_mb integer default null, p_cap_mb integer default null) returns void
 language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; yn text[] := array['off', 'on'];
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_pool_mb is not null and p_pool_mb not between 0 and 10000000 then raise exception 'INVALID_POOL'; end if;
  if p_cap_mb is not null and p_cap_mb not between 1 and 100000 then raise exception 'INVALID_CAP'; end if;
  select * into s from settings where id = 1 for update;
  update settings set attendee_shared = coalesce(p_shared, attendee_shared), attendee_pool_mb = coalesce(p_pool_mb, attendee_pool_mb),
         attendee_cap_mb = coalesce(p_cap_mb, attendee_cap_mb) where id = 1;
  if p_shared is not null and p_shared is distinct from s.attendee_shared then
    insert into settings_log (changed_by, who, area, field, old_value, new_value)
    values (auth.uid(), _actor(), 'settings', 'shared attendee space (photos + videos)', yn[1 + s.attendee_shared::int], yn[1 + p_shared::int]);
  end if;
  if p_pool_mb is not null and p_pool_mb is distinct from s.attendee_pool_mb then
    insert into settings_log (changed_by, who, area, field, old_value, new_value)
    values (auth.uid(), _actor(), 'settings', 'attendee shared space (MB)', s.attendee_pool_mb::text, p_pool_mb::text);
  end if;
  if p_cap_mb is not null and p_cap_mb is distinct from s.attendee_cap_mb then
    insert into settings_log (changed_by, who, area, field, old_value, new_value)
    values (auth.uid(), _actor(), 'settings', 'attendee cap per person (MB)', s.attendee_cap_mb::text, p_cap_mb::text);
  end if;
end $function$;
revoke all on function public.admin_set_attendee_space(boolean, integer, integer) from public, anon, authenticated, service_role;
grant execute on function public.admin_set_attendee_space(boolean, integer, integer) to authenticated;

create or replace function public.admin_attendee_summary() returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; present int;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1;
  present := _photo_present();
  return jsonb_build_object('shared', s.attendee_shared, 'pool_bytes', s.attendee_pool_mb::bigint * 1048576, 'cap_bytes', s.attendee_cap_mb::bigint * 1048576,
    'used_bytes', _att_used_all(), 'photo_bytes', _photo_used('public'), 'video_bytes', _video_used(), 'present', present,
    'per_person_bytes', _photo_person_bytes(s.attendee_pool_mb, s.attendee_cap_mb, present),
    'accounts', jsonb_build_array(_att_acct_used(1), _att_acct_used(2), _att_acct_used(3)));
end $function$;
revoke all on function public.admin_attendee_summary() from public, anon, authenticated, service_role;
grant execute on function public.admin_attendee_summary() to authenticated;
