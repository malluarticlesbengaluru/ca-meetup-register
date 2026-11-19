-- ============================================================================
-- Release 2, piece 30: GIVE SPACE WITH ONLY THE FRIEND'S BOOKING ID (no phone number needed)
-- Written 19 Nov 2026. Run AFTER r2_28 (and r2_29). Safe to run twice. Changes no photo, no video and no existing function.
--
-- The giver is still checked with their own Booking ID + phone (they are logged in as an attendee, and must be Present).
-- The friend is found by Booking ID alone. A booking can hold several people (different phone numbers). The page lists the names
-- in the booking and the giver taps the right one; with one person only, that person is used.
--   space_booking_peek(booking_id)    the people in that booking: [{id, name}] (id = that person's oldest ticket)
--   space_give_booking(code, phone, to_booking, kind, mb, to_person)  same rules as space_give; to_person (optional) picks the person,
--                                     left out = the booking's first person (that is what the QR code path always meant)
-- The older space_give (friend's Booking ID + phone) stays in the database; the page no longer uses it.
-- ============================================================================
create or replace function public._space_booking_all(p_booking text) returns uuid[]
 language plpgsql stable security definer set search_path to 'public' as $function$
declare bc text := upper(regexp_replace(coalesce(p_booking, ''), '[^A-Za-z0-9]', '', 'g')); bid uuid; first_id uuid; ph text; res uuid[];
begin
  if length(bc) < 4 then return null; end if;
  select id into bid from bookings where booking_code = bc and status = 'paid';
  if bid is null then return null; end if;
  select id, phone into first_id, ph from tickets where booking_id = bid and transferred_out_at is null order by reg_seq limit 1;
  if first_id is null then return null; end if;
  select array_agg(t.id order by t.reg_seq) into res from tickets t where t.booking_id = bid and t.phone = ph and t.transferred_out_at is null;
  return res;
end $function$;
revoke all on function public._space_booking_all(text) from public, anon, authenticated, service_role;

-- the people of a paid booking: one row per phone number, id = that person's oldest live ticket
create or replace function public._space_booking_people(p_booking text) returns table(id uuid, name text, phone text, seq bigint)
 language sql stable security definer set search_path to 'public' as $function$
  select f.id, f.name, f.phone, f.reg_seq from (
    select distinct on (t.phone) t.id, t.name, t.phone, t.reg_seq
      from tickets t join bookings b on b.id = t.booking_id
     where b.booking_code = upper(regexp_replace(coalesce(p_booking, ''), '[^A-Za-z0-9]', '', 'g'))
       and length(regexp_replace(coalesce(p_booking, ''), '[^A-Za-z0-9]', '', 'g')) >= 4
       and b.status = 'paid' and t.transferred_out_at is null
     order by t.phone, t.reg_seq) f
  order by f.reg_seq;
$function$;
revoke all on function public._space_booking_people(text) from public, anon, authenticated, service_role;

create or replace function public.space_booking_peek(p_to_code text) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare ppl jsonb;
begin
  select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.name) order by p.seq) into ppl from _space_booking_people(p_to_code) p;
  if ppl is null then return jsonb_build_object('ok', false, 'error', 'TO_NOT_FOUND'); end if;
  return jsonb_build_object('ok', true, 'name', ppl->0->>'name', 'people', ppl);
end $function$;
revoke all on function public.space_booking_peek(text) from public, anon, authenticated, service_role;
grant execute on function public.space_booking_peek(text) to anon, authenticated;

drop function if exists public.space_give_booking(text, text, text, text, integer);   -- the first version of this file (no to_person)
create or replace function public.space_give_booking(p_code text, p_phone text, p_to_code text, p_kind text, p_mb integer, p_to_person uuid default null) returns jsonb
 language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; oall uuid[]; me uuid; other uuid; left_b bigint; tid uuid; n1 text; n2 text; pick record;
begin
  select * into s from settings where id = 1 for update;             -- same lock as the upload checks
  if p_kind not in ('photo', 'video') then return jsonb_build_object('ok', false, 'error', 'BAD_KIND'); end if;
  if p_mb is null or p_mb < 1 or p_mb > 100000 then return jsonb_build_object('ok', false, 'error', 'BAD_AMOUNT'); end if;
  if not s.space_sharing_on then return jsonb_build_object('ok', false, 'error', 'SHARING_OFF'); end if;
  if (p_kind = 'photo' and not s.photos_on) or (p_kind = 'video' and not s.videos_on) then return jsonb_build_object('ok', false, 'error', 'FEATURE_OFF'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  if p_to_person is null then
    oall := _space_booking_all(p_to_code);
  else   -- the chosen person must be one of the people of that booking
    select * into pick from _space_booking_people(p_to_code) p where p.id = p_to_person;
    if pick.id is not null then
      select array_agg(t.id order by t.reg_seq) into oall from tickets t
       where t.booking_id = (select booking_id from tickets where id = pick.id) and t.phone = pick.phone and t.transferred_out_at is null;
    end if;
  end if;
  if oall is null then return jsonb_build_object('ok', false, 'error', 'TO_NOT_FOUND'); end if;
  me := w.all_ids[1]; other := oall[1];
  if me = other or w.all_ids && oall then return jsonb_build_object('ok', false, 'error', 'SAME_PERSON'); end if;
  left_b := _space_left(p_kind, w.ids, w.all_ids);
  if p_mb::bigint * 1048576 > left_b then return jsonb_build_object('ok', false, 'error', 'TOO_MUCH', 'give_bytes', greatest(0, left_b)); end if;
  insert into space_transfers (kind, from_key, to_key, mb) values (p_kind, me, other, p_mb) returning id into tid;
  select name into n1 from tickets where id = me; select name into n2 from tickets where id = other;
  insert into settings_log (changed_by, who, area, field, old_value, new_value)
  values (null, 'attendee', 'settings', 'space given (' || p_kind || 's)', left(coalesce(n1, '?') || ' > ' || coalesce(n2, '?'), 300), p_mb || ' MB');
  return jsonb_build_object('ok', true, 'id', tid);
end $function$;
revoke all on function public.space_give_booking(text, text, text, text, integer, uuid) from public, anon, authenticated, service_role;
grant execute on function public.space_give_booking(text, text, text, text, integer, uuid) to anon, authenticated;
