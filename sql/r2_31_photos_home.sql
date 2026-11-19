-- r2_31: admin switch for the "Event photos" link on the public home page (default OFF).
--   Run once in the Supabase SQL editor. Safe to run again.
--   Off  = the home page shows nothing about photos (the gallery and uploads still follow "Photo uploads on").
--   On   = the home page shows an "Event photos" section at the bottom and an "Event photos" item in its menu.
alter table public.settings add column if not exists photos_home boolean not null default false;

create or replace function public.admin_set_photos_home(p_value boolean) returns void
 language plpgsql security definer set search_path to 'public' as $function$
declare old boolean;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_value is null then raise exception 'INVALID_VALUE'; end if;
  select photos_home into old from settings where id = 1;
  if old is distinct from p_value then
    update settings set photos_home = p_value where id = 1;
    insert into settings_log (changed_by, who, area, field, old_value, new_value)
    values (auth.uid(), _actor(), 'settings', 'photos link on home page', case when old then 'on' else 'off' end, case when p_value then 'on' else 'off' end);
  end if;
end $function$;
revoke all on function public.admin_set_photos_home(boolean) from public, anon, authenticated, service_role;
grant execute on function public.admin_set_photos_home(boolean) to authenticated;

-- the public page reads this (no personal data); 'home' is the new key
create or replace function public.get_photos_info() returns jsonb
 language sql stable security definer set search_path to 'public' as $function$
  select jsonb_build_object('on', s.photos_on, 'mode', s.photo_public_mode, 'max_bytes', s.photo_max_pub_mb::bigint * 1048576, 'home', s.photos_home)
    from settings s where s.id = 1 $function$;
revoke all on function public.get_photos_info() from public, anon, authenticated, service_role;
grant execute on function public.get_photos_info() to anon, authenticated;
