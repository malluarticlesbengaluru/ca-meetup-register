-- ============================================================================
-- Release 2, piece 29: GIVE SPACE BY QR (the friend who receives shows a QR; the giver scans it)
-- Written 18 Nov 2026. Run AFTER r2_28. Safe to run twice. Changes no photo, no video and no existing function.
--
-- The receiving person taps "Show my QR". The page asks for a short code (10 characters, valid 30 minutes) and draws it as a QR.
-- The giver scans it (in the page, or with the phone camera which opens the page) and the code fills in the friend, so nobody has to
-- type a Booking ID and phone number. The code carries NO phone number and NO Booking ID: it only points to the receiving person.
-- One code can be scanned by many friends (a group giving to the one with the best camera). It stops working after 30 minutes.
--   space_make_code(code, phone)            the receiver asks for their code
--   space_code_peek(token)                  the giver sees WHO the code belongs to (the name on the ticket) before confirming
--   space_give_token(code, phone, token, kind, mb)   same rules as space_give, the friend is found by the code
-- ============================================================================
create table if not exists public.space_codes (
  token      text primary key check (token ~ '^[A-Z2-9]{10}$'),
  ticket_id  uuid not null references public.tickets(id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);
create index if not exists space_codes_ticket_idx on public.space_codes (ticket_id);
alter table public.space_codes enable row level security;
revoke all on public.space_codes from public, anon, authenticated;
grant select on public.space_codes to service_role;      -- nobody reads codes from the website; only the functions below touch them

create or replace function public._space_token() returns text
 language plpgsql volatile set search_path to 'public' as $function$
declare alpha constant text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; h text := replace(gen_random_uuid()::text, '-', ''); t text := ''; i int;
begin
  for i in 0..9 loop t := t || substr(alpha, 1 + (('x' || substr(h, 1 + i * 2, 2))::bit(8)::int % 32), 1); end loop;
  return t;
end $function$;
revoke all on function public._space_token() from public, anon, authenticated, service_role;

-- the receiver asks for a code (a still-valid one is reused)
create or replace function public.space_make_code(p_code text, p_phone text) returns jsonb
 language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; me uuid; tok text; exp timestamptz;
begin
  select * into s from settings where id = 1;
  if not s.space_sharing_on then return jsonb_build_object('ok', false, 'error', 'SHARING_OFF'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.all_ids is null then return jsonb_build_object('ok', false, 'error', coalesce(w.err, 'MISMATCH')); end if;
  me := w.all_ids[1];
  delete from space_codes where expires_at < now() - interval '1 day';
  select token, expires_at into tok, exp from space_codes where ticket_id = me and expires_at > now() + interval '10 minutes' order by expires_at desc limit 1;
  if tok is null then
    loop
      tok := _space_token(); exp := now() + interval '30 minutes';
      begin insert into space_codes (token, ticket_id, expires_at) values (tok, me, exp); exit;
      exception when unique_violation then null; end;
    end loop;
  end if;
  return jsonb_build_object('ok', true, 'token', tok, 'expires_at', exp);
end $function$;
revoke all on function public.space_make_code(text, text) from public, anon, authenticated, service_role;
grant execute on function public.space_make_code(text, text) to anon, authenticated;

-- internal: a code (as scanned or typed) -> the receiving person's tickets. Null when unknown, expired or the booking is not paid.
create or replace function public._space_code_all(p_token text) returns uuid[]
 language plpgsql stable security definer set search_path to 'public' as $function$
declare tk text := upper(regexp_replace(coalesce(p_token, ''), '[^A-Za-z0-9]', '', 'g')); tid uuid; res uuid[];
begin
  select ticket_id into tid from space_codes where token = tk and expires_at > now();
  if tid is null then return null; end if;
  select array_agg(t.id order by t.reg_seq) into res from tickets t
   where t.booking_id = (select booking_id from tickets where id = tid) and t.phone = (select phone from tickets where id = tid)
     and t.transferred_out_at is null and exists (select 1 from bookings b where b.id = t.booking_id and b.status = 'paid');
  return res;
end $function$;
revoke all on function public._space_code_all(text) from public, anon, authenticated, service_role;

-- the giver checks who the code belongs to
create or replace function public.space_code_peek(p_token text) returns jsonb
 language plpgsql stable security definer set search_path to 'public' as $function$
declare a uuid[] := _space_code_all(p_token);
begin
  if a is null then return jsonb_build_object('ok', false, 'error', 'CODE_INVALID'); end if;
  return jsonb_build_object('ok', true, 'name', (select name from tickets where id = a[1]));
end $function$;
revoke all on function public.space_code_peek(text) from public, anon, authenticated, service_role;
grant execute on function public.space_code_peek(text) to anon, authenticated;

-- same as space_give, the friend is found by the code
create or replace function public.space_give_token(p_code text, p_phone text, p_token text, p_kind text, p_mb integer) returns jsonb
 language plpgsql security definer set search_path to 'public' as $function$
declare s settings%rowtype; w record; oall uuid[]; me uuid; other uuid; left_b bigint; tid uuid; n1 text; n2 text;
begin
  select * into s from settings where id = 1 for update;             -- same lock as the upload checks
  if p_kind not in ('photo', 'video') then return jsonb_build_object('ok', false, 'error', 'BAD_KIND'); end if;
  if p_mb is null or p_mb < 1 or p_mb > 100000 then return jsonb_build_object('ok', false, 'error', 'BAD_AMOUNT'); end if;
  if not s.space_sharing_on then return jsonb_build_object('ok', false, 'error', 'SHARING_OFF'); end if;
  if (p_kind = 'photo' and not s.photos_on) or (p_kind = 'video' and not s.videos_on) then return jsonb_build_object('ok', false, 'error', 'FEATURE_OFF'); end if;
  select * into w from _photo_public_who(p_code, p_phone);
  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;
  oall := _space_code_all(p_token);
  if oall is null then return jsonb_build_object('ok', false, 'error', 'CODE_INVALID'); end if;
  me := w.all_ids[1]; other := oall[1];
  if me = other or w.all_ids && oall then return jsonb_build_object('ok', false, 'error', 'SAME_PERSON'); end if;
  left_b := _space_left(p_kind, w.ids, w.all_ids);
  if p_mb::bigint * 1048576 > left_b then return jsonb_build_object('ok', false, 'error', 'TOO_MUCH', 'give_bytes', greatest(0, left_b)); end if;
  insert into space_transfers (kind, from_key, to_key, mb) values (p_kind, me, other, p_mb) returning id into tid;
  select name into n1 from tickets where id = me; select name into n2 from tickets where id = other;
  insert into settings_log (changed_by, who, area, field, old_value, new_value)
  values (null, 'attendee', 'settings', 'space given (' || p_kind || 's)', left(coalesce(n1, '?') || ' > ' || coalesce(n2, '?') || ' (QR)', 300), p_mb || ' MB');
  return jsonb_build_object('ok', true, 'id', tid);
end $function$;
revoke all on function public.space_give_token(text, text, text, text, integer) from public, anon, authenticated, service_role;
grant execute on function public.space_give_token(text, text, text, text, integer) to anon, authenticated;
