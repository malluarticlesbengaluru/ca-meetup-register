-- ============================================================================
-- Release 2, piece 25: only the admins YOU choose may download originals
-- Written 16 Nov 2026. Run AFTER r2_24. Safe to run twice. Changes no photos.
--
-- r2_24 made originals admin-only. This narrows it further: an admin may download only if their own switch
-- "photo_download" is on. Everyone starts OFF. You turn it on for chosen admins in the Supabase SQL Editor (the
-- admin page cannot change it, and no one can change it for themselves from the website).
--   1. staff.photo_download (default false).
--   2. photo_may_download(user): true only for an admin whose switch is on (Edge Function only).
--   3. photo_original_key: gives a file only when photo_may_download is true.
--   4. photo_camera_list: can_download = true only for such an admin (so the page shows the Download button only to them).
-- The Edge Function also asks photo_may_download before "view" and before "export" (download everything).
-- ============================================================================
alter table public.staff add column if not exists photo_download boolean not null default false;

create or replace function public.photo_may_download(p_user uuid) returns boolean
 language sql stable security definer set search_path to 'public' as $function$
  select exists (select 1 from staff where user_id = p_user and role = 'admin' and photo_download)
$function$;
revoke all on function public.photo_may_download(uuid) from public, anon, authenticated, service_role;
grant execute on function public.photo_may_download(uuid) to service_role;

create or replace function public.photo_original_key(p_id uuid, p_user uuid) returns text
 language plpgsql stable security definer set search_path to 'public' as $function$
declare r photos%rowtype;
begin
  if not photo_may_download(p_user) then return null; end if;
  select * into r from photos where id = p_id and status = 'stored';
  if not found then return null; end if;
  return r.object_key;
end $function$;
revoke all on function public.photo_original_key(uuid, uuid) from public, anon, authenticated, service_role;
grant execute on function public.photo_original_key(uuid, uuid) to service_role;

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
  return jsonb_build_object('ok', true, 'items', items, 'page', lim, 'visibility', s.photo_visibility,
                            'can_download', photo_may_download(auth.uid()));
end $function$;
revoke all on function public.photo_camera_list(timestamptz, integer) from public, anon, authenticated, service_role;
grant execute on function public.photo_camera_list(timestamptz, integer) to authenticated;
