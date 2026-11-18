-- ============================================================================
-- Release 2, piece 28: SHARING SPACE (an attendee gives some of their photo or video space to a friend)
-- Written 18 Nov 2026. Run AFTER r2_27. Safe to run twice. Changes no photo and no video.
--
-- Space only MOVES between people: the shared pools (and so the Storj totals) never change.
--   * A person (Booking ID + phone, the same login as uploads) gives whole MB of unused PHOTO space or unused VIDEO space to another
--     person (the friend's Booking ID + phone). Photos and videos are separate amounts.
--   * Space that was received can be given on again (A to B to C). You can only give away what you still have left unused.
--   * The giver can take a gift back (all of it, in one go) only while the receiver still has that much unused space.
--   * One person's space = their normal space + all they received - all they gave (active transfers only).
--   * Every transfer and every take-back is saved (table space_transfers), shown to admins (Admin > Settings > Space sharing),
--     and written to the settings log. Admins can switch sharing off (settings.space_sharing_on).
-- The four places that work out an attendee's space (photo_public_status, photo_reserve, video_public_status, video_reserve)
-- are re-created below with ONE change each: "+ _space_net(kind, person)".
-- A person is identified by their oldest live ticket under that login (all_ids[1]).
-- ============================================================================
alter table public.settings add column if not exists space_sharing_on boolean not null default true;

create table if not exists public.space_transfers (
  id          uuid primary key default gen_random_uuid(),
  kind        text not null check (kind in ('photo', 'video')),
  from_key    uuid not null references public.tickets(id) on delete cascade,
  to_key      uuid not null references public.tickets(id) on delete cascade,
  mb          integer not null check (mb between 1 and 100000),
  status      text not null default 'active' check (status in ('active', 'returned')),
  created_at  timestamptz not null default now(),
  returned_at timestamptz,
  check (from_key <> to_key)
);
create index if not exists space_transfers_from_idx on public.space_transfers (from_key);
create index if not exists space_transfers_to_idx on public.space_transfers (to_key);
alter table public.space_transfers enable row level security;
drop policy if exists admin_read_space_transfers on public.space_transfers;
create policy admin_read_space_transfers on public.space_transfers for select to authenticated using (is_admin());
revoke all on public.space_transfers from public, anon, authenticated;
grant select on public.space_transfers to authenticated;
grant select on public.space_transfers to service_role;

-- net bytes this person received minus gave (active transfers only)
create or replace function public._space_net(p_kind text, p_key uuid) returns bigint
 language sql stable security definer set search_path to 'public' as $function$
  select coalesce(sum(case when to_key = p_key then mb else -mb end), 0)::bigint * 1048576
    from space_transfers where kind = p_kind and status = 'active' and (to_key = p_key or from_key = p_key) $function$;
revoke all on function public._space_net(text, uuid) from public, anon, authenticated, service_role;

-- unused bytes this person has right now (their limit minus what they used); can be negative. p_ids = tickets allowed to upload.
create or replace function public._space_left(p_kind text, p_ids uuid[], p_all uuid[]) returns bigint
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; lim bigint; mine bigint;
begin
  select * into s from settings where id = 1;
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

-- ---- the four existing functions, each with the one "+ _space_net" change -------------------------------------------------
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
  lim  := per * array_length(w.ids, 1) + _space_net('photo', w.all_ids[1]);
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
  lim  := per * array_length(w.ids, 1) + _space_net('photo', w.all_ids[1]);
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

create or replace function public.video_public_status(p_code text, p_phone text) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; lim bigint; mine bigint; pool bigint; pused bigint;
begin
  select * into s from settings where id = 1;
  if not s.videos_on then return jsonb_build_object('ok', false, 'error', 'VIDEOS_OFF'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  lim := s.video_cap_mb::bigint * 1048576 * array_length(w.ids, 1) + _space_net('video', w.all_ids[1]);
  select coalesce(sum(coalesce(bytes_actual, bytes_claimed)), 0)::bigint into mine from videos
   where ticket_id = any(w.all_ids) and (status = 'stored' or (status = 'reserved' and created_at > now() - interval '20 minutes'));
  pool := s.video_pool_mb::bigint * 1048576; pused := _video_used();
  return jsonb_build_object('ok', true, 'limit_bytes', lim, 'used_bytes', mine,
           'left_bytes', greatest(0, least(lim - mine, pool - pused)), 'max_bytes', s.video_max_mb::bigint * 1048576);
end $function$;
revoke all on function public.video_public_status(text, text) from public, anon, authenticated, service_role;
grant execute on function public.video_public_status(text, text) to anon, authenticated;

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
  lim := s.video_cap_mb::bigint * 1048576 * array_length(w.ids, 1) + _space_net('video', w.all_ids[1]);
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

-- ---- attendee side ---------------------------------------------------------------------------------------------------------
-- what this person has, gave, received, and the history (last 40), for the "Share" screen
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
  return jsonb_build_object('ok', true, 'sharing_on', s.space_sharing_on,
    'photo', jsonb_build_object('on', s.photos_on, 'give_bytes', ph, 'net_bytes', _space_net('photo', me)),
    'video', jsonb_build_object('on', s.videos_on, 'give_bytes', vd, 'net_bytes', _space_net('video', me)),
    'items', items);
end $function$;
revoke all on function public.space_overview(text, text) from public, anon, authenticated, service_role;
grant execute on function public.space_overview(text, text) to anon, authenticated;

-- give whole MB of unused space to a friend (their Booking ID + phone)
create or replace function public.space_give(p_code text, p_phone text, p_to_code text, p_to_phone text, p_kind text, p_mb integer) returns jsonb
 language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; r record; me uuid; other uuid; left_b bigint; tid uuid; n1 text; n2 text;
begin
  select * into s from settings where id = 1 for update;             -- same lock as the upload checks, so nothing can slip in between
  if p_kind not in ('photo', 'video') then return jsonb_build_object('ok', false, 'error', 'BAD_KIND'); end if;
  if p_mb is null or p_mb < 1 or p_mb > 100000 then return jsonb_build_object('ok', false, 'error', 'BAD_AMOUNT'); end if;
  if not s.space_sharing_on then return jsonb_build_object('ok', false, 'error', 'SHARING_OFF'); end if;
  if (p_kind = 'photo' and not s.photos_on) or (p_kind = 'video' and not s.videos_on) then return jsonb_build_object('ok', false, 'error', 'FEATURE_OFF'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  select * into r from _photo_public_who(p_to_code, p_to_phone);
  if r.all_ids is null then return jsonb_build_object('ok', false, 'error', case when r.err = 'NOT_PAID' then 'TO_NOT_PAID' else 'TO_MISMATCH' end); end if;
  me := w.all_ids[1]; other := r.all_ids[1];
  if me = other or w.all_ids && r.all_ids then return jsonb_build_object('ok', false, 'error', 'SAME_PERSON'); end if;
  left_b := _space_left(p_kind, w.ids, w.all_ids);
  if p_mb::bigint * 1048576 > left_b then return jsonb_build_object('ok', false, 'error', 'TOO_MUCH', 'give_bytes', greatest(0, left_b)); end if;
  insert into space_transfers (kind, from_key, to_key, mb) values (p_kind, me, other, p_mb) returning id into tid;
  select name into n1 from tickets where id = me; select name into n2 from tickets where id = other;
  insert into settings_log (changed_by, who, area, field, old_value, new_value)
  values (null, 'attendee', 'settings', 'space given (' || p_kind || 's)', left(coalesce(n1, '?') || ' > ' || coalesce(n2, '?'), 300), p_mb || ' MB');
  return jsonb_build_object('ok', true, 'id', tid);
end $function$;
revoke all on function public.space_give(text, text, text, text, text, integer) from public, anon, authenticated, service_role;
grant execute on function public.space_give(text, text, text, text, text, integer) to anon, authenticated;

-- take a gift back (all of it), only while the receiver still has that much unused space
create or replace function public.space_return(p_code text, p_phone text, p_id uuid) returns jsonb
 language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; x space_transfers%rowtype; oids uuid[]; n1 text; n2 text;
begin
  select * into s from settings where id = 1 for update;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  select * into x from space_transfers where id = p_id for update;
  if not found or x.from_key <> w.all_ids[1] then return jsonb_build_object('ok', false, 'error', 'NOT_FOUND'); end if;
  if x.status <> 'active' then return jsonb_build_object('ok', false, 'error', 'ALREADY'); end if;
  select array_agg(t.id order by t.reg_seq) into oids from tickets t
   where t.booking_id = (select booking_id from tickets where id = x.to_key) and t.phone = (select phone from tickets where id = x.to_key) and t.transferred_out_at is null;
  if oids is null or oids[1] <> x.to_key or _space_left(x.kind, oids, oids) < x.mb::bigint * 1048576 then
    return jsonb_build_object('ok', false, 'error', 'TAKEN'); end if;
  update space_transfers set status = 'returned', returned_at = now() where id = p_id;
  select name into n1 from tickets where id = x.from_key; select name into n2 from tickets where id = x.to_key;
  insert into settings_log (changed_by, who, area, field, old_value, new_value)
  values (null, 'attendee', 'settings', 'space taken back (' || x.kind || 's)', left(coalesce(n1, '?') || ' < ' || coalesce(n2, '?'), 300), x.mb || ' MB');
  return jsonb_build_object('ok', true);
end $function$;
revoke all on function public.space_return(text, text, uuid) from public, anon, authenticated, service_role;
grant execute on function public.space_return(text, text, uuid) to anon, authenticated;

-- ---- admin side -----------------------------------------------------------------------------------------------------------
create or replace function public.admin_space_transfers(p_limit integer default 100) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare items jsonb; s settings%rowtype;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1;
  select coalesce(jsonb_agg(jsonb_build_object('id', x.id, 'kind', x.kind, 'mb', x.mb, 'status', x.status, 'at', x.created_at, 'returned_at', x.returned_at,
           'from', ft.name, 'from_code', fb.booking_code, 'to', tt.name, 'to_code', tb.booking_code) order by x.created_at desc), '[]'::jsonb)
    into items
    from (select * from space_transfers order by created_at desc limit least(greatest(coalesce(p_limit, 100), 1), 500)) x
    join tickets ft on ft.id = x.from_key join bookings fb on fb.id = ft.booking_id
    join tickets tt on tt.id = x.to_key join bookings tb on tb.id = tt.booking_id;
  return jsonb_build_object('ok', true, 'on', s.space_sharing_on, 'items', items,
    'active_mb_photo', (select coalesce(sum(mb), 0) from space_transfers where kind = 'photo' and status = 'active'),
    'active_mb_video', (select coalesce(sum(mb), 0) from space_transfers where kind = 'video' and status = 'active'));
end $function$;
revoke all on function public.admin_space_transfers(integer) from public, anon, authenticated, service_role;
grant execute on function public.admin_space_transfers(integer) to authenticated;

create or replace function public.admin_set_space_sharing(p_on boolean) returns void
 language plpgsql security definer set search_path to 'public' as $function$
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  update settings set space_sharing_on = coalesce(p_on, space_sharing_on) where id = 1;
end $function$;
revoke all on function public.admin_set_space_sharing(boolean) from public, anon, authenticated, service_role;
grant execute on function public.admin_set_space_sharing(boolean) to authenticated;
