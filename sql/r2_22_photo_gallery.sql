-- ============================================================================
-- Release 2, piece 22: PHOTO GALLERY (who sees what, listing, delete your own, originals for admin + photographers)
-- Written 14 Nov 2026. Run AFTER r2_20_photos.sql and r2_21. Safe to run twice. Changes no existing data.
--
--   1. New admin setting  photo_visibility  (default 'own'):
--        'own'           every person sees only their own photos; admins see everything
--        'photographers' photographers see all photos (theirs and the public's); attendees see only their own
--        'all'           everyone who is logged in sees every photo
--      Admins change it in Admin > Settings > Photos (admin_set_photo_visibility). The settings log records the change.
--   2. photo_camera_list  (photographer or admin login)  and  photo_public_list  (Booking ID + phone): one page of photos at a time,
--      newest first, with the small preview picture. They apply the visibility setting here in the database, not in the page.
--      Viewing works even when uploads are switched off. An attendee who has not been marked Present can still VIEW (a paid ticket is enough).
--   3. photo_original_key: which full-size original a login may download. Admins: any. Photographers: their own, or any when
--      visibility is 'photographers' or 'all'. Attendees: never (they only get the small preview; originals are shared later).
--   4. photo_remove_camera / photo_remove_public: a photographer or attendee deletes THEIR OWN photo (admins keep admin_photo_remove).
--      Only the Edge Function (service_role) can call 3 and 4; it has already checked who is asking.
-- ============================================================================

-- ---- 1. the setting ------------------------------------------------------------------------------------------------------
alter table public.settings
  add column if not exists photo_visibility text not null default 'own' check (photo_visibility in ('own', 'photographers', 'all'));

create or replace function public.admin_set_photo_visibility(p_value text) returns void
 language plpgsql security definer set search_path to 'public' as $function$
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_value is null or p_value not in ('own', 'photographers', 'all') then raise exception 'INVALID_VISIBILITY'; end if;
  update settings set photo_visibility = p_value where id = 1;
end $function$;
revoke all on function public.admin_set_photo_visibility(text) from public, anon, authenticated, service_role;
grant execute on function public.admin_set_photo_visibility(text) to authenticated;

-- ---- 2. listing ----------------------------------------------------------------------------------------------------------
-- photographers and admins. p_before = the created_at of the last photo already shown (null for the first page).
create or replace function public.photo_camera_list(p_before timestamptz default null, p_limit integer default 24) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; adm boolean; lim integer; items jsonb;
begin
  if not (is_camera() or is_admin()) then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1;
  adm := is_admin();
  lim := least(greatest(coalesce(p_limit, 24), 1), 48);
  select coalesce(jsonb_agg(jsonb_build_object('id', q.id, 'kind', q.kind, 'bytes', q.bytes_actual, 'thumb', q.thumb,
                                                'at', q.created_at, 'mine', q.mine, 'by', q.by) order by q.created_at desc), '[]'::jsonb)
    into items
    from (select p.id, p.kind, p.bytes_actual, p.thumb, p.created_at,
                 (p.kind = 'camera' and p.uploader = auth.uid()) as mine,
                 case when p.kind = 'camera' then st.name end as by
            from photos p left join staff st on st.user_id = p.uploader
           where p.status = 'stored'
             and (p_before is null or p.created_at < p_before)
             and (adm or s.photo_visibility in ('photographers', 'all') or (p.kind = 'camera' and p.uploader = auth.uid()))
           order by p.created_at desc limit lim) q;
  return jsonb_build_object('ok', true, 'items', items, 'page', lim, 'visibility', s.photo_visibility, 'can_download', true);
end $function$;
revoke all on function public.photo_camera_list(timestamptz, integer) from public, anon, authenticated, service_role;
grant execute on function public.photo_camera_list(timestamptz, integer) to authenticated;

-- attendees (Booking ID + the ticket's own phone, the same check as the Tickets page and the upload page)
create or replace function public.photo_public_list(p_code text, p_phone text, p_before timestamptz default null, p_limit integer default 24) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; lim integer; items jsonb;
begin
  select * into s from settings where id = 1;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.all_ids is null then return jsonb_build_object('ok', false, 'error', coalesce(w.err, 'MISMATCH')); end if;
  lim := least(greatest(coalesce(p_limit, 24), 1), 48);
  select coalesce(jsonb_agg(jsonb_build_object('id', q.id, 'kind', q.kind, 'bytes', q.bytes_actual, 'thumb', q.thumb,
                                                'at', q.created_at, 'mine', q.mine, 'by', q.by) order by q.created_at desc), '[]'::jsonb)
    into items
    from (select p.id, p.kind, p.bytes_actual, p.thumb, p.created_at,
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

-- ---- 3. which original may this login download? (Edge Function only) -----------------------------------------------------
create or replace function public.photo_original_key(p_id uuid, p_user uuid) returns text
 language plpgsql stable security definer set search_path to 'public' as $function$
declare r photos%rowtype; s settings%rowtype; rl text;
begin
  select role into rl from staff where user_id = p_user;
  if rl is null or rl not in ('admin', 'camera') then return null; end if;
  select * into r from photos where id = p_id and status = 'stored';
  if not found then return null; end if;
  select * into s from settings where id = 1;
  if rl = 'admin' or s.photo_visibility in ('photographers', 'all') or (r.kind = 'camera' and r.uploader = p_user) then
    return r.object_key;
  end if;
  return null;
end $function$;
revoke all on function public.photo_original_key(uuid, uuid) from public, anon, authenticated, service_role;
grant execute on function public.photo_original_key(uuid, uuid) to service_role;

-- ---- 4. delete your own (Edge Function only) -----------------------------------------------------------------------------
create or replace function public.photo_remove_camera(p_id uuid, p_user uuid) returns text
 language plpgsql security definer set search_path to 'public' as $function$
declare r photos%rowtype;
begin
  if not exists (select 1 from staff where user_id = p_user and role in ('admin', 'camera')) then return null; end if;
  select * into r from photos where id = p_id for update;
  if not found or r.status <> 'stored' or r.kind <> 'camera' or r.uploader is distinct from p_user then return null; end if;
  update photos set status = 'removed', thumb = null where id = p_id;
  insert into settings_log (changed_by, who, area, field, old_value, new_value)
  values (p_user, 'photographer', 'settings', 'photo removed (own)', left(r.object_key, 300), null);
  return r.object_key;
end $function$;
revoke all on function public.photo_remove_camera(uuid, uuid) from public, anon, authenticated, service_role;
grant execute on function public.photo_remove_camera(uuid, uuid) to service_role;

create or replace function public.photo_remove_public(p_id uuid, p_code text, p_phone text) returns text
 language plpgsql security definer set search_path to 'public' as $function$
declare r photos%rowtype; w record;
begin
  select * into w from _photo_public_who(p_code, p_phone);
  if w.all_ids is null then return null; end if;
  select * into r from photos where id = p_id for update;
  if not found or r.status <> 'stored' or r.kind <> 'public' or not (r.ticket_id = any (w.all_ids)) then return null; end if;
  update photos set status = 'removed', thumb = null where id = p_id;
  insert into settings_log (changed_by, who, area, field, old_value, new_value)
  values (null, 'attendee', 'settings', 'photo removed (own)', left(r.object_key, 300), null);
  return r.object_key;
end $function$;
revoke all on function public.photo_remove_public(uuid, text, text) from public, anon, authenticated, service_role;
grant execute on function public.photo_remove_public(uuid, text, text) to service_role;

-- ---- 5. safety: a preview picture must be a plain base64 jpeg/png/webp (nothing that could carry markup) ----------------
-- NOT VALID = checked for every new or changed row; existing rows (if any) are left alone.
alter table public.photos drop constraint if exists photos_thumb_format;
alter table public.photos add constraint photos_thumb_format
  check (thumb is null or thumb ~ '^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$') not valid;
