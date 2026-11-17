-- ============================================================================
-- Release 2, piece 26: SHARP PREVIEWS (a 1600-pixel picture next to each photo; the original stays locked)
-- Written 16 Nov 2026. Run AFTER r2_25. Safe to run twice. Changes no existing photo.
--
-- Until now a photo's only preview was a tiny picture (about 360 pixels) saved inside the database. Now the page also makes a
-- sharp preview (long side 1600 pixels, about 300 to 500 KB) and uploads it to Storj next to the original, with the file name
-- of the original plus ".p.jpg". The lightbox shows that sharp preview. Who may see a preview is exactly who may see the photo
-- in the lists (the visibility setting). Originals are still only for the admins whose photo_download switch is on.
--   1. photos.preview_bytes: size of the sharp preview in Storj (empty = this photo has none, e.g. an iPhone HEIC on Android).
--   2. photo_confirm gets a fourth, optional argument (the preview size). The preview counts in the same space as the photo:
--      the Edge Function passes original + preview as the size used.
--   3. photo_preview_key(photo, user, code, phone): the Storj name of the preview, only if that login may see that photo.
--   4. photo_camera_list and photo_public_list now say per photo whether a sharp preview exists ('pv').
-- ============================================================================
alter table public.photos add column if not exists preview_bytes bigint;
alter table public.photos drop constraint if exists photos_preview_bytes_check;
alter table public.photos add constraint photos_preview_bytes_check
  check (preview_bytes is null or preview_bytes between 1 and 2097152) not valid;

drop function if exists public.photo_confirm(uuid, bigint, text);
create or replace function public.photo_confirm(p_id uuid, p_actual bigint, p_thumb text, p_preview bigint default null) returns jsonb
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
         thumb = case when p_thumb is not null and char_length(p_thumb) <= 80000 then p_thumb end,
         preview_bytes = case when p_preview is not null and p_preview between 1 and 2097152 and p_preview < p_actual then p_preview end
   where id = p_id;
  return jsonb_build_object('ok', true);
end $function$;
revoke all on function public.photo_confirm(uuid, bigint, text, bigint) from public, anon, authenticated, service_role;
grant execute on function public.photo_confirm(uuid, bigint, text, bigint) to service_role;

-- the Storj name of the sharp preview, if (and only if) this login may see this photo. Edge Function only.
-- p_user set: a staff login (admin: any; photographer: own, or all when visibility allows). p_user null: an attendee (Booking ID + phone).
create or replace function public.photo_preview_key(p_id uuid, p_user uuid, p_code text, p_phone text) returns text
 language plpgsql stable security definer set search_path to 'public' as $function$
declare r photos%rowtype; s settings%rowtype; rl text; w record;
begin
  select * into r from photos where id = p_id and status = 'stored' and preview_bytes is not null;
  if not found then return null; end if;
  select * into s from settings where id = 1;
  if p_user is not null then
    select role into rl from staff where user_id = p_user;
    if rl = 'admin'
       or (rl = 'camera' and (s.photo_visibility in ('photographers', 'all') or (r.kind = 'camera' and r.uploader = p_user))) then
      return r.object_key || '.p.jpg';
    end if;
    return null;
  end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.all_ids is null then return null; end if;
  if s.photo_visibility = 'all' or (r.kind = 'public' and r.ticket_id = any (w.all_ids)) then
    return r.object_key || '.p.jpg';
  end if;
  return null;
end $function$;
revoke all on function public.photo_preview_key(uuid, uuid, text, text) from public, anon, authenticated, service_role;
grant execute on function public.photo_preview_key(uuid, uuid, text, text) to service_role;

-- the lists now carry 'pv' (true when a sharp preview exists)
create or replace function public.photo_camera_list(p_before timestamptz default null, p_limit integer default 24) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; adm boolean; lim integer; items jsonb;
begin
  if not (is_camera() or is_admin()) then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1;
  adm := is_admin();
  lim := least(greatest(coalesce(p_limit, 24), 1), 48);
  select coalesce(jsonb_agg(jsonb_build_object('id', q.id, 'kind', q.kind, 'bytes', q.bytes_actual, 'thumb', q.thumb,
                                                'at', q.created_at, 'mine', q.mine, 'by', q.by, 'pv', q.pv) order by q.created_at desc), '[]'::jsonb)
    into items
    from (select p.id, p.kind, p.bytes_actual, p.thumb, p.created_at, (p.preview_bytes is not null) as pv,
                 (p.kind = 'camera' and p.uploader = auth.uid()) as mine,
                 case when p.kind = 'camera' then st.name end as by
            from photos p left join staff st on st.user_id = p.uploader
           where p.status = 'stored'
             and (p_before is null or p.created_at < p_before)
             and (adm or s.photo_visibility in ('photographers', 'all') or (p.kind = 'camera' and p.uploader = auth.uid()))
           order by p.created_at desc limit lim) q;
  return jsonb_build_object('ok', true, 'items', items, 'page', lim, 'visibility', s.photo_visibility,
                            'can_download', photo_may_download(auth.uid()));
end $function$;
revoke all on function public.photo_camera_list(timestamptz, integer) from public, anon, authenticated, service_role;
grant execute on function public.photo_camera_list(timestamptz, integer) to authenticated;

create or replace function public.photo_public_list(p_code text, p_phone text, p_before timestamptz default null, p_limit integer default 24) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; lim integer; items jsonb;
begin
  select * into s from settings where id = 1;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.all_ids is null then return jsonb_build_object('ok', false, 'error', coalesce(w.err, 'MISMATCH')); end if;
  lim := least(greatest(coalesce(p_limit, 24), 1), 48);
  select coalesce(jsonb_agg(jsonb_build_object('id', q.id, 'kind', q.kind, 'bytes', q.bytes_actual, 'thumb', q.thumb,
                                                'at', q.created_at, 'mine', q.mine, 'by', q.by, 'pv', q.pv) order by q.created_at desc), '[]'::jsonb)
    into items
    from (select p.id, p.kind, p.bytes_actual, p.thumb, p.created_at, (p.preview_bytes is not null) as pv,
                 (p.kind = 'public' and p.ticket_id = any (w.all_ids)) as mine,
                 case when p.kind = 'camera' then st.name end as by
            from photos p left join staff st on st.user_id = p.uploader
           where p.status = 'stored'
             and (p_before is null or p.created_at < p_before)
             and (s.photo_visibility = 'all' or (p.kind = 'public' and p.ticket_id = any (w.all_ids)))
           order by p.created_at desc limit lim) q;
  return jsonb_build_object('ok', true, 'items', items, 'page', lim, 'visibility', s.photo_visibility, 'can_download', false);
end $function$;
revoke all on function public.photo_public_list(text, text, timestamptz, integer) from public, anon, authenticated, service_role;
grant execute on function public.photo_public_list(text, text, timestamptz, integer) to anon, authenticated;
