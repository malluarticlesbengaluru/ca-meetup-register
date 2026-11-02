-- ============================================================================
-- Release 2, piece 15: colour theme of the public registration page, chosen by an admin in Settings
-- Written 31 Oct 2026. Run AFTER r2_14. Tested on the scratch database before use. Safe to run twice. Changes no existing data.
--
--   settings.theme : which colour theme the PUBLIC page (index.html) shows. One of
--                    navy (the original dark navy + amber, the default), emerald, charcoal, mango, sky, terracotta.
--   get_site_flags(): also returns "theme" (visitors need it to colour the page; it is not a secret).
--   admin_set_theme(text): admins only; any other word is refused (INVALID_THEME). The Settings log records the change by itself.
-- ============================================================================
alter table public.settings add column if not exists theme text not null default 'navy';
alter table public.settings drop constraint if exists settings_theme_check;
alter table public.settings add constraint settings_theme_check check (theme = any (array['navy','emerald','charcoal','mango','sky','terracotta']));

create or replace function public.get_site_flags() returns jsonb
 language sql stable security definer set search_path to 'public' as $function$
  select jsonb_build_object('show_about', s.show_about, 'ask_email', s.ask_email, 'ask_feedback', s.ask_feedback, 'theme', s.theme) from settings s where s.id = 1
$function$;
revoke all on function public.get_site_flags() from public, anon, authenticated, service_role;
grant execute on function public.get_site_flags() to anon, authenticated;

create or replace function public.admin_set_theme(p_theme text) returns void
 language plpgsql security definer set search_path to 'public' as $function$
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_theme is null or p_theme <> all (array['navy','emerald','charcoal','mango','sky','terracotta']) then raise exception 'INVALID_THEME'; end if;
  update settings set theme = p_theme where id = 1;
end $function$;
revoke all on function public.admin_set_theme(text) from public, anon, authenticated, service_role;
grant execute on function public.admin_set_theme(text) to authenticated;
