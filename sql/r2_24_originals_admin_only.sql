-- ============================================================================
-- Release 2, piece 24: ONLY ADMINS may download the full-size originals
-- Written 16 Nov 2026. Run AFTER r2_22 (and r2_23). Safe to run twice. Changes no data.
--
-- Decision (organiser, 16 Nov): during and after the event nobody but an admin may download an original. Photographers
-- can still take, upload, see their own small previews and delete their own photos; attendees likewise. Everyone else
-- gets the originals later, through the link the organiser shares once everything is saved to a safe drive.
--   1. photo_original_key (used only by the Edge Function) now answers only for an admin login. For anyone else: nothing,
--      whatever the "who sees which photos" setting is.
--   2. photo_camera_list now tells the page can_download = true for an admin and false for a photographer, so the page
--      hides the Download button for photographers.
-- ============================================================================
create or replace function public.photo_original_key(p_id uuid, p_user uuid) returns text
 language plpgsql stable security definer set search_path to 'public' as $function$
declare r photos%rowtype; rl text;
begin
  select role into rl from staff where user_id = p_user;
  if rl is distinct from 'admin' then return null; end if;
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
  return jsonb_build_object('ok', true, 'items', items, 'page', lim, 'visibility', s.photo_visibility, 'can_download', adm);
end $function$;
revoke all on function public.photo_camera_list(timestamptz, integer) from public, anon, authenticated, service_role;
grant execute on function public.photo_camera_list(timestamptz, integer) to authenticated;
