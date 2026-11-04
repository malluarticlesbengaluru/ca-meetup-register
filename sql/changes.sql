-- 26 Oct 2026: feedback questions after booking (full file: r2_11_feedback.sql, run after r2_10)
-- settings.ask_feedback, booking_feedback table (admin read), submit_feedback(), admin_set_ask_feedback(), get_site_flags() adds ask_feedback.

-- 26 Oct 2026: Email box on/off switch (full file: r2_10_email_switch.sql)
-- settings.ask_email (default true), admin_set_ask_email(boolean), transfer_buyers.email nullable, get_site_flags() adds ask_email,
-- submit_booking / transfer_submit / admin_transfer_approve skip email when off.

-- 13 Oct 2026: make the report view follow the caller's permissions
alter view public.report set (security_invoker = true);

-- 13 Oct 2026: internal helpers must not be callable from outside
revoke execute on function public._assign_numbers(uuid), public._booking_json(uuid)
  from public, anon, authenticated;

-- 13 Oct 2026: undo_checkin now works for coordinators too (by ticket id or number)
drop function if exists public.undo_checkin(integer);

create or replace function public.undo_checkin(
  p_ticket_no integer default null,
  p_coord boolean default false,
  p_id uuid default null
) returns void
language plpgsql
security definer
set search_path to 'public'
as $function$
declare n int;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;

  if p_id is not null then
    update tickets set checked_in_at = null, checked_in_by = null where id = p_id;
  elsif p_coord then
    update tickets set checked_in_at = null, checked_in_by = null
    where coord_no = p_ticket_no and kind = 'coordinator';
  else
    update tickets set checked_in_at = null, checked_in_by = null where ticket_no = p_ticket_no;
  end if;

  get diagnostics n = row_count;
  if n = 0 then raise exception 'INVALID_TICKET'; end if;
end $function$;

revoke execute on function public.undo_checkin(integer, boolean, uuid) from public, anon;
grant execute on function public.undo_checkin(integer, boolean, uuid) to authenticated;

-- 14 Oct 2026: daily "reconciliation pause" + 10-minute grace for people mid-registration.
-- Run this whole file once in the Supabase SQL editor. Safe to run twice.

-- 1) New settings
alter table public.settings
  add column if not exists pause_enabled boolean not null default false,
  add column if not exists pause_close_time time not null default '23:00',
  add column if not exists pause_open_time  time not null default '00:00',
  add column if not exists grace_minutes integer not null default 10,
  add column if not exists closed_at timestamptz;

alter table public.settings drop constraint if exists settings_grace_check;
alter table public.settings add constraint settings_grace_check check (grace_minutes between 1 and 60);
alter table public.settings drop constraint if exists settings_pause_times_check;
alter table public.settings add constraint settings_pause_times_check check (pause_close_time <> pause_open_time);

-- 2) People currently filling the form (one row per registration attempt). No personal data.
create table if not exists public.reg_sessions (
  id uuid primary key,
  started_at timestamptz not null default now(),
  last_seen  timestamptz not null default now()
);
revoke all on public.reg_sessions from public, anon, authenticated;


-- 3) Where are we in the daily pause? (all times in India time)
create or replace function public._pause_info(s settings)
 returns jsonb
 language plpgsql
 stable
 set search_path to 'public'
as $function$
declare ist_now timestamp; lc timestamp; op timestamp;
begin
  if not s.pause_enabled then
    return jsonb_build_object('in_pause', false, 'last_close', null, 'next_open', null, 'next_close', null);
  end if;
  ist_now := now() at time zone 'Asia/Kolkata';
  lc := ist_now::date + s.pause_close_time;
  if lc > ist_now then lc := lc - interval '1 day'; end if;      -- most recent close moment
  op := lc::date + s.pause_open_time;
  if op <= lc then op := op + interval '1 day'; end if;           -- the reopen that follows it
  return jsonb_build_object(
    'in_pause',   ist_now < op,
    'last_close', lc at time zone 'Asia/Kolkata',
    'next_open',  op at time zone 'Asia/Kolkata',
    'next_close', (lc + interval '1 day') at time zone 'Asia/Kolkata');
end $function$;


-- 3b) The moment registration closed (earliest of: switched off by hand, daily pause started, deadline passed)
create or replace function public._close_moment(s settings)
 returns timestamptz
 language plpgsql
 stable
 set search_path to 'public'
as $function$
declare pi jsonb := _pause_info(s);
begin
  return least(case when not s.is_open then s.closed_at end,
               case when (pi->>'in_pause')::boolean then (pi->>'last_close')::timestamptz end,
               case when now() > s.deadline then s.deadline end);
end $function$;


-- 4) Grace: is this person (session) allowed to finish although registration just closed?
drop function if exists public._grace_until(settings, uuid);
create or replace function public._grace_until(s settings, p_session uuid, p_slack interval default '0 seconds')
 returns timestamptz
 language plpgsql
 stable
 set search_path to 'public'
as $function$
declare cm timestamptz; r reg_sessions%rowtype;
begin
  if p_session is null then return null; end if;
  cm := _close_moment(s);
  if cm is null or now() > cm + make_interval(mins => s.grace_minutes) + p_slack then return null; end if;
  select * into r from reg_sessions where id = p_session;
  if not found or r.started_at >= cm or r.last_seen < cm - interval '10 minutes' then return null; end if;
  if exists (select 1 from bookings where submission_id = p_session) then return null; end if;
  return cm + make_interval(mins => s.grace_minutes);
end $function$;


-- 5) What the public page sees
drop function if exists public.get_public_status();
create or replace function public._public_state(s settings, p_session uuid)
 returns jsonb
 language plpgsql
 stable
 set search_path to 'public'
as $function$
declare used int; remaining int; reason text; pi jsonb; gu timestamptz; reopen timestamptz;
begin
  select count(*) into used from tickets t join bookings b on b.id = t.booking_id where b.status <> 'rejected';
  remaining := greatest(s.cap - used, 0);
  pi := _pause_info(s);
  reason := case when not s.is_open then 'not_open'
                 when now() > s.deadline then 'deadline'
                 when remaining = 0 then 'full'
                 when (pi->>'in_pause')::boolean then 'paused'
                 else null end;
  reopen := case when reason = 'paused' and (pi->>'next_open')::timestamptz <= s.deadline
                 then (pi->>'next_open')::timestamptz else null end;
  if reason = 'paused' and reopen is null then reason := 'deadline'; end if;
  gu := case when reason in ('not_open', 'paused', 'deadline') then _grace_until(s, p_session) else null end;
  return jsonb_build_object('accepting', reason is null, 'closed_reason', reason,
    'spots_left', remaining, 'price_per_head', s.price_per_head,
    'max_group', greatest(least(s.max_group, remaining), 1), 'deadline', s.deadline,
    'server_now', now(), 'grace_until', gu, 'reopen_at', reopen,
    'pause_enabled', s.pause_enabled,
    'next_close_at', case when reason is null and s.pause_enabled and (pi->>'next_close')::timestamptz < s.deadline
                          then (pi->>'next_close')::timestamptz else null end);
end $function$;

create or replace function public.get_public_status(p_session uuid default null)
 returns jsonb
 language plpgsql
 stable
 security definer
 set search_path to 'public'
as $function$
declare s settings%rowtype;
begin
  select * into s from settings where id = 1;
  return _public_state(s, p_session);
end $function$;

-- The form page calls this every 30 seconds while the person is filling the form.
create or replace function public.registration_heartbeat(p_session uuid)
 returns jsonb
 language plpgsql
 volatile
 security definer
 set search_path to 'public'
as $function$
declare s settings%rowtype; st jsonb;
begin
  if p_session is null then raise exception 'INVALID_DATA'; end if;
  select * into s from settings where id = 1;
  st := _public_state(s, p_session);
  if (st->>'accepting')::boolean then
    insert into reg_sessions (id) values (p_session)
    on conflict (id) do update set last_seen = now();
    delete from reg_sessions where last_seen < now() - interval '1 day';
  else
    -- while closed, only a person who is still inside their grace minutes gets refreshed; nobody new can start
    if (st->>'grace_until') is not null then
      update reg_sessions set last_seen = now() where id = p_session;
    end if;
  end if;
  return st;
end $function$;


-- 6) Booking: the closed check now allows the grace period
create or replace function public.submit_booking(p_submission_id uuid, p_people jsonb, p_screenshot_path text)
 returns jsonb
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare s settings%rowtype; b bookings%rowtype; n int; used int; r record; code text; pi jsonb;
begin
  select * into b from bookings where submission_id = p_submission_id;
  if found then return _booking_json(b.id); end if;

  select * into s from settings where id = 1 for update;
  select * into b from bookings where submission_id = p_submission_id;
  if found then return _booking_json(b.id); end if;

  pi := _pause_info(s);
  if (not s.is_open or (pi->>'in_pause')::boolean or now() > s.deadline) then
    -- closed right now: only people who were already filling the form get the grace minutes (+30 s for upload time)
    if _grace_until(s, p_submission_id, interval '30 seconds') is null then
      raise exception 'REGISTRATION_CLOSED';
    end if;
  end if;
  if p_people is null or jsonb_typeof(p_people) <> 'array' then raise exception 'INVALID_DATA'; end if;
  n := jsonb_array_length(p_people);
  if n < 1 or n > s.max_group then raise exception 'INVALID_GROUP_SIZE'; end if;

  select count(*) into used from tickets t join bookings bk on bk.id = t.booking_id where bk.status <> 'rejected';
  if used + n > s.cap then raise exception 'NOT_ENOUGH_SPOTS'; end if;

  for r in select value from jsonb_array_elements(p_people) loop
    if length(trim(coalesce(r.value->>'name',''))) not between 1 and 80 then raise exception 'INVALID_NAME'; end if;
    if coalesce(r.value->>'phone','') !~ '^[0-9]{10}$' then raise exception 'INVALID_PHONE'; end if;
    if coalesce(r.value->>'loc','') not in ('In Bengaluru','Outside Bengaluru') then raise exception 'INVALID_LOCATION'; end if;
    if coalesce(r.value->>'att','') not in ('Surely','Most probably') then raise exception 'INVALID_ATTENDANCE'; end if;
    if coalesce(r.value->>'food','') not in ('Veg','Non-veg') then raise exception 'INVALID_FOOD'; end if;
  end loop;

  if p_screenshot_path is null or p_screenshot_path not like p_submission_id::text || '%'
     or not exists (select 1 from storage.objects where bucket_id = 'payment-proofs' and name = p_screenshot_path)
  then raise exception 'SCREENSHOT_MISSING'; end if;

  loop
    code := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8));
    exit when not exists (select 1 from bookings where booking_code = code);
  end loop;

  insert into bookings (booking_code, submission_id, people_count, amount_expected, screenshot_path)
  values (code, p_submission_id, n, n * s.price_per_head, p_screenshot_path) returning * into b;

  insert into tickets (secret, booking_id, name, phone, location, attendance, food)
  select substr(replace(gen_random_uuid()::text, '-', ''), 1, 12), b.id,
         trim(value->>'name'), value->>'phone', value->>'loc', value->>'att', value->>'food'
  from jsonb_array_elements(p_people) with ordinality as e(value, ord) order by ord;

  return _booking_json(b.id);
end $function$;


-- 7) Admin: save settings (now with the pause options). Remembers the moment registration was switched off.
drop function if exists public.admin_update_settings(integer, integer, timestamp with time zone, boolean);
create or replace function public.admin_update_settings(
  p_cap integer default null, p_price integer default null,
  p_deadline timestamp with time zone default null, p_is_open boolean default null,
  p_pause_enabled boolean default null, p_pause_close time default null, p_pause_open time default null)
 returns void
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare s settings%rowtype;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1 for update;
  if coalesce(p_pause_close, s.pause_close_time) = coalesce(p_pause_open, s.pause_open_time) then
    raise exception 'INVALID_PAUSE_TIMES';
  end if;
  update settings set cap = coalesce(p_cap, cap), price_per_head = coalesce(p_price, price_per_head),
    deadline = coalesce(p_deadline, deadline), is_open = coalesce(p_is_open, is_open),
    pause_enabled = coalesce(p_pause_enabled, pause_enabled),
    pause_close_time = coalesce(p_pause_close, pause_close_time),
    pause_open_time = coalesce(p_pause_open, pause_open_time),
    closed_at = case when p_is_open is true then null
                     when p_is_open is false and s.is_open then now()
                     else closed_at end
  where id = 1;
end $function$;


-- 8) Admin: live status for the dashboard banner
create or replace function public.admin_registration_status()
 returns jsonb
 language plpgsql
 stable
 security definer
 set search_path to 'public'
as $function$
declare s settings%rowtype; st jsonb; cm timestamptz; gc int := 0; gu timestamptz;
begin
  if not is_staff() then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1;
  st := _public_state(s, null);
  cm := _close_moment(s);
  if cm is not null and now() <= cm + make_interval(mins => s.grace_minutes) then
    gu := cm + make_interval(mins => s.grace_minutes);
    select count(*) into gc from reg_sessions r
    where r.started_at < cm and r.last_seen >= cm - interval '10 minutes'
      and not exists (select 1 from bookings b where b.submission_id = r.id);
  end if;
  return jsonb_build_object('closed_reason', st->'closed_reason', 'accepting', st->'accepting',
    'reopen_at', st->'reopen_at', 'next_close_at', st->'next_close_at',
    'grace_count', gc, 'grace_until', case when gc > 0 then gu else null end, 'server_now', now());
end $function$;


-- 9) Who may call what
revoke execute on function public._pause_info(settings), public._close_moment(settings), public._grace_until(settings, uuid, interval),
  public._public_state(settings, uuid) from public, anon, authenticated;
revoke execute on function public.get_public_status(uuid), public.registration_heartbeat(uuid),
  public.submit_booking(uuid, jsonb, text) from public;
grant execute on function public.get_public_status(uuid), public.registration_heartbeat(uuid),
  public.submit_booking(uuid, jsonb, text) to anon, authenticated;
revoke execute on function public.admin_update_settings(integer, integer, timestamp with time zone, boolean, boolean, time, time),
  public.admin_registration_status() from public, anon;
grant execute on function public.admin_update_settings(integer, integer, timestamp with time zone, boolean, boolean, time, time),
  public.admin_registration_status() to authenticated;

-- 14 Oct 2026: a number touched by a person is never given to anyone else.
-- A person keeps their guest number AND their coordinator number for good.
-- Run this whole file once in the Supabase SQL editor.

-- 1) Remember a removed coordinator's number and QR secret on the same person
alter table public.tickets
  add column if not exists prev_coord_no integer,
  add column if not exists prev_coord_secret text;

-- a retired coordinator number can belong to only one person
create unique index if not exists tickets_prev_coord_no_uq
  on public.tickets (prev_coord_no) where prev_coord_no is not null;


-- 2) Make / remove coordinator
create or replace function public.set_coordinator(p_ticket_id uuid, p_make boolean)
 returns jsonb
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare s settings%rowtype; t tickets%rowtype; bs text;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1 for update;
  select * into t from tickets where id = p_ticket_id for update;
  if not found then raise exception 'INVALID_TICKET'; end if;

  if p_make and t.kind = 'guest' then
    if t.prev_coord_no is not null then
      -- this person was a coordinator before: they get their own old number and QR back
      update tickets set kind = 'coordinator', coord_no = t.prev_coord_no,
        orig_secret = t.secret,
        secret = coalesce(t.prev_coord_secret, substr(replace(gen_random_uuid()::text, '-', ''), 1, 12)),
        prev_coord_no = null, prev_coord_secret = null,
        marked_by = auth.uid(), marked_at = now() where id = t.id;
    else
      -- first time: next new coordinator number. Any guest number stays on record, cancelled while coordinator.
      update tickets set kind = 'coordinator', coord_no = s.next_coord, orig_secret = t.secret,
        secret = substr(replace(gen_random_uuid()::text, '-', ''), 1, 12),
        marked_by = auth.uid(), marked_at = now() where id = t.id;
      update settings set next_coord = next_coord + 1 where id = 1;
    end if;
  elsif not p_make and t.kind = 'coordinator' then
    -- the coordinator number is kept on this person (cancelled), never given to anyone else.
    -- the guest number and original QR come back, or a new guest number is given once paid.
    update tickets set kind = 'guest', prev_coord_no = t.coord_no, prev_coord_secret = t.secret,
      coord_no = null, secret = coalesce(orig_secret, secret),
      orig_secret = null, marked_by = null, marked_at = null where id = t.id;
    select status into bs from bookings where id = t.booking_id;
    if bs = 'paid' then perform _assign_numbers(t.booking_id); end if;
  end if;

  select * into t from tickets where id = t.id;
  return jsonb_build_object('id', t.id, 'kind', t.kind, 'ticket_no', t.ticket_no,
                            'label', _ticket_label(t.kind, t.ticket_no, t.coord_no));
end $function$;


-- 3) Gate check: a cancelled coordinator ticket now shows CANCELLED (not INVALID)
create or replace function public.admit_ticket(p_ticket_no integer default null::integer, p_secret text default null::text, p_approve boolean default false, p_coord boolean default false, p_id uuid default null::uuid)
 returns jsonb
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare t tickets%rowtype; b bookings%rowtype; info jsonb; who text;
begin
  if not is_staff() then raise exception 'NOT_ALLOWED'; end if;
  if p_approve then perform 1 from settings where id = 1 for update; end if;

  if p_id is not null then
    select * into t from tickets where id = p_id for update;
  elsif p_coord then
    select * into t from tickets where coord_no = p_ticket_no and kind = 'coordinator' for update;
    if not found then
      -- maybe a coordinator number that was cancelled (person is a guest again)
      select * into t from tickets where prev_coord_no = p_ticket_no for update;
      if found then
        return jsonb_build_object('result', 'cancelled', 'name', t.name,
          'label', coalesce(_ticket_label(t.kind, t.ticket_no, t.coord_no), 'not numbered yet'),
          'old_label', _ticket_label('coordinator', null, t.prev_coord_no));
      end if;
    end if;
  else
    select * into t from tickets where ticket_no = p_ticket_no for update;
  end if;
  if not found then return jsonb_build_object('result', 'invalid'); end if;

  if p_id is null and t.kind = 'coordinator' and not p_coord then
    return jsonb_build_object('result', 'cancelled', 'name', t.name,
      'label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
      'old_label', _ticket_label('guest', t.ticket_no, null));
  end if;
  if p_secret is not null and t.secret <> p_secret then
    return jsonb_build_object('result', 'invalid'); end if;

  select * into b from bookings where id = t.booking_id for update;

  if b.status = 'pending' and p_approve then
    update bookings set status = 'paid', reviewed_by = auth.uid(), reviewed_at = now(), reviewed_via = 'gate' where id = b.id;
    perform _assign_numbers(b.id);
    select * into t from tickets where id = t.id;
    b.status := 'paid';
  end if;

  info := jsonb_build_object('id', t.id, 'ticket_no', t.ticket_no, 'kind', t.kind,
    'label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
    'name', t.name, 'food', t.food,
    'booking_code', b.booking_code, 'people_count', b.people_count,
    'amount_expected', b.amount_expected, 'screenshot_path', b.screenshot_path);

  if b.status = 'rejected' then return info || jsonb_build_object('result', 'rejected'); end if;
  if b.status = 'pending' then return info || jsonb_build_object('result', 'pending'); end if;
  if t.checked_in_at is not null then
    select name into who from staff where user_id = t.checked_in_by;
    return info || jsonb_build_object('result', 'already_scanned', 'checked_in_at', t.checked_in_at, 'checked_in_by', who);
  end if;
  update tickets set checked_in_at = now(), checked_in_by = auth.uid() where id = t.id;
  return info || jsonb_build_object('result', 'ok');
end $function$;

-- =====================================================================
-- TICKET TRANSFER  (notice board + handshake; organisers approve)
-- Safe to run more than once. Run it in the Supabase SQL editor.
--
-- How it works
--   1. A ticket holder can post an ad ("ticket for sale at Rs X") on the board.
--      Posting needs Booking ID + ticket number, so only real tickets can be listed.
--   2. A buyer taps Interested (leaves name + phone). Choosing "talk" shows the seller's number.
--   3. The seller (Booking ID + ticket number) picks a buyer and starts the transfer.
--      This creates a one-time TRANSFER CODE and hides the ad. A seller who already has a
--      buyer can skip steps 1-2 and start the transfer directly.
--   4. The buyer enters ticket number + transfer code + their five details.
--   5. The organisers see the matched pair, call both, and approve or decline.
--   6. On approval the seat gets the buyer's details, the NEXT FREE ticket number and a new QR.
--      The old number is retired for ever (never given to anyone else); scanning the old QR
--      says TICKET CANCELLED. Counts do not change (same seat, same booking).
--
-- Error messages the pages should translate (text after the colon is what the database raises):
--   TRANSFERS_CLOSED, INVALID_TICKET, ALREADY_TRANSFERRED, NOT_PAID, NOT_GUEST,
--   ALREADY_CHECKED_IN, FORMER_COORDINATOR, INVALID_PRICE, INVALID_PHONE, INVALID_NAME,
--   INVALID_LOCATION, INVALID_ATTENDANCE, INVALID_FOOD, INVALID_CHOICE, ALREADY_LISTED,
--   ALREADY_IN_TRANSFER, NO_ACTIVE_LISTING, NO_ACTIVE_TRANSFER, LISTING_NOT_AVAILABLE,
--   TOO_MANY_INTERESTED, INVALID_TRANSFER, NOT_PENDING, NOT_ALLOWED, INVALID_SETTINGS
-- =====================================================================

-- 1. SETTINGS (off by default; maximum asking price defaults to the ticket price) ------------
alter table settings add column if not exists transfers_open boolean not null default false;
alter table settings add column if not exists max_resale_price integer not null default 250 check (max_resale_price >= 0);

-- 2. TABLES -----------------------------------------------------------------------------------
-- The ads on the board
create table if not exists ticket_listings (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references tickets(id) on delete cascade,
  price integer not null check (price >= 0),
  contact_phone text not null check (contact_phone ~ '^[0-9]{10}$'),
  status text not null default 'active' check (status in ('active','withdrawn','sold','closed','removed')),
  created_at timestamptz not null default now(),
  closed_at timestamptz);
create unique index if not exists ticket_listings_one_active on ticket_listings (ticket_id) where status = 'active';

-- People who tapped Interested on an ad
create table if not exists ticket_interests (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid not null references ticket_listings(id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 80),
  phone text not null check (phone ~ '^[0-9]{10}$'),
  choice text not null check (choice in ('talk','agree')),
  created_at timestamptz not null default now(),
  unique (listing_id, phone));

-- The transfer applications and their history
create table if not exists ticket_transfers (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references tickets(id) on delete cascade,
  code text not null unique,
  status text not null default 'awaiting_buyer'
    check (status in ('awaiting_buyer','pending_admin','done','declined','withdrawn')),
  price integer check (price is null or price >= 0),
  listing_id uuid references ticket_listings(id) on delete set null,
  -- the person receiving the ticket (filled when the buyer applies)
  new_name text, new_phone text, new_location text, new_attendance text, new_food text,
  buyer_applied_at timestamptz,
  -- the person who held the ticket before (filled when the organisers approve)
  from_name text, from_phone text, from_location text, from_attendance text, from_food text,
  from_ticket_no integer, to_ticket_no integer,
  payment_confirmed boolean not null default false,
  decided_by uuid references auth.users(id), decided_at timestamptz, decline_reason text,
  created_at timestamptz not null default now(),
  constraint ticket_transfers_new_values check (
    (new_phone is null or new_phone ~ '^[0-9]{10}$')
    and (new_location is null or new_location in ('In Bengaluru','Outside Bengaluru'))
    and (new_attendance is null or new_attendance in ('Surely','Most probably'))
    and (new_food is null or new_food in ('Veg','Non-veg'))),
  constraint ticket_transfers_buyer_present check (
    status not in ('pending_admin','done')
    or (new_name is not null and new_phone is not null and new_location is not null
        and new_attendance is not null and new_food is not null)));
-- only one live application per ticket; a retired number appears in history only once
create unique index if not exists ticket_transfers_one_open on ticket_transfers (ticket_id)
  where status in ('awaiting_buyer','pending_admin');
create unique index if not exists ticket_transfers_from_no_uq on ticket_transfers (from_ticket_no)
  where from_ticket_no is not null;

-- Same protection as your other tables: only admins can read, nobody can write directly
alter table ticket_listings enable row level security;
alter table ticket_interests enable row level security;
alter table ticket_transfers enable row level security;
revoke all on table ticket_listings, ticket_interests, ticket_transfers from anon, authenticated;
grant select on table ticket_listings, ticket_interests, ticket_transfers to authenticated;
drop policy if exists admin_read_listings on ticket_listings;
create policy admin_read_listings on ticket_listings for select to authenticated using (is_admin());
drop policy if exists admin_read_interests on ticket_interests;
create policy admin_read_interests on ticket_interests for select to authenticated using (is_admin());
drop policy if exists admin_read_transfers on ticket_transfers;
create policy admin_read_transfers on ticket_transfers for select to authenticated using (is_admin());

-- 3. INTERNAL HELPERS (not callable from the website) ----------------------------------------
create or replace function _norm_code(p text) returns text
language sql immutable as $$
  select replace(replace(replace(upper(coalesce(p, '')), 'O', '0'), ' ', ''), '-', '') $$;

-- Why a ticket cannot be sold/transferred right now (null = it can)
create or replace function _transfer_block_reason(t tickets, b bookings) returns text
language sql as $$
  select case
    when b.status <> 'paid' then 'NOT_PAID'
    when t.kind <> 'guest' then 'NOT_GUEST'
    when t.ticket_no is null then 'NOT_PAID'
    when t.checked_in_at is not null then 'ALREADY_CHECKED_IN'
    when t.prev_coord_no is not null then 'FORMER_COORDINATOR'
  end $$;

-- Booking ID + ticket number -> the ticket's id (the seller's proof of ownership)
create or replace function _seller_ticket(p_booking_code text, p_ticket_no integer) returns uuid
language plpgsql security definer set search_path to 'public' as $$
declare c text; b bookings%rowtype; v uuid;
begin
  c := _norm_code(p_booking_code);
  if length(c) <> 8 or p_ticket_no is null then raise exception 'INVALID_TICKET'; end if;
  select * into b from bookings where booking_code = c;
  if not found then raise exception 'INVALID_TICKET'; end if;
  select id into v from tickets where booking_id = b.id and ticket_no = p_ticket_no;
  if found then return v; end if;
  if exists (select 1 from ticket_transfers x join tickets tk on tk.id = x.ticket_id
             where tk.booking_id = b.id and x.from_ticket_no = p_ticket_no and x.status = 'done')
  then raise exception 'ALREADY_TRANSFERRED'; end if;
  raise exception 'INVALID_TICKET';
end $$;

-- 4. PUBLIC FUNCTIONS (the website calls these) ------------------------------------------------
create or replace function get_transfer_status() returns jsonb
language sql stable security definer set search_path to 'public' as $$
  select jsonb_build_object('open', transfers_open, 'max_price', max_resale_price, 'price_per_head', price_per_head)
  from settings where id = 1 $$;

-- The board: only price and age. No names, phones or ticket numbers.
create or replace function list_board() returns jsonb
language sql stable security definer set search_path to 'public' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', l.id, 'price', l.price, 'posted_at', l.created_at)
                            order by l.created_at desc), '[]'::jsonb)
  from ticket_listings l
  join tickets t on t.id = l.ticket_id
  join bookings b on b.id = t.booking_id
  where (select transfers_open from settings where id = 1)
    and l.status = 'active' and t.kind = 'guest' and t.checked_in_at is null and b.status = 'paid' $$;

create or replace function post_listing(p_code text, p_ticket_no integer, p_price integer, p_contact text) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; v uuid; t tickets%rowtype; b bookings%rowtype; l ticket_listings%rowtype; r text;
begin
  select * into s from settings where id = 1;
  if not s.transfers_open then raise exception 'TRANSFERS_CLOSED'; end if;
  v := _seller_ticket(p_code, p_ticket_no);
  select * into t from tickets where id = v for update;
  select * into b from bookings where id = t.booking_id;
  r := _transfer_block_reason(t, b);
  if r is not null then raise exception '%', r; end if;
  if p_price is null or p_price < 0 or p_price > s.max_resale_price then raise exception 'INVALID_PRICE'; end if;
  if coalesce(p_contact, '') !~ '^[0-9]{10}$' then raise exception 'INVALID_PHONE'; end if;
  if exists (select 1 from ticket_transfers where ticket_id = t.id and status in ('awaiting_buyer','pending_admin'))
  then raise exception 'ALREADY_IN_TRANSFER'; end if;
  if exists (select 1 from ticket_listings where ticket_id = t.id and status = 'active')
  then raise exception 'ALREADY_LISTED'; end if;
  insert into ticket_listings (ticket_id, price, contact_phone) values (t.id, p_price, p_contact) returning * into l;
  return jsonb_build_object('id', l.id, 'price', l.price);
end $$;

-- Seller's "Manage my listing" page: their ad, who is interested, and any live transfer
create or replace function manage_ticket(p_code text, p_ticket_no integer) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare v uuid; t tickets%rowtype; b bookings%rowtype; s settings%rowtype; l ticket_listings%rowtype;
        x ticket_transfers%rowtype; li jsonb; xi jsonb;
begin
  v := _seller_ticket(p_code, p_ticket_no);
  select * into t from tickets where id = v;
  select * into b from bookings where id = t.booking_id;
  select * into s from settings where id = 1;
  select * into l from ticket_listings where ticket_id = t.id and status = 'active';
  if found then
    li := jsonb_build_object('id', l.id, 'price', l.price, 'contact_phone', l.contact_phone, 'created_at', l.created_at,
      'interests', coalesce((select jsonb_agg(jsonb_build_object('id', i.id, 'name', i.name, 'phone', i.phone,
                  'choice', i.choice, 'created_at', i.created_at) order by i.created_at)
                  from ticket_interests i where i.listing_id = l.id), '[]'::jsonb));
  end if;
  select * into x from ticket_transfers where ticket_id = t.id and status in ('awaiting_buyer','pending_admin');
  if found then
    xi := jsonb_build_object('status', x.status, 'code', x.code, 'price', x.price, 'created_at', x.created_at,
                             'buyer_name', x.new_name, 'buyer_phone', x.new_phone);
  end if;
  return jsonb_build_object('label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
    'open', s.transfers_open, 'max_price', s.max_resale_price,
    'blocked', _transfer_block_reason(t, b), 'listing', li, 'transfer', xi);
end $$;

-- Seller deletes the ad (p_sold = false) or marks it sold/complete (p_sold = true). Works even when transfers are closed.
create or replace function close_listing(p_code text, p_ticket_no integer, p_sold boolean default false) returns void
language plpgsql security definer set search_path to 'public' as $$
declare v uuid; n int;
begin
  v := _seller_ticket(p_code, p_ticket_no);
  update ticket_listings set status = case when coalesce(p_sold, false) then 'sold' else 'withdrawn' end, closed_at = now()
  where ticket_id = v and status = 'active';
  get diagnostics n = row_count;
  if n = 0 then raise exception 'NO_ACTIVE_LISTING'; end if;
end $$;

-- Buyer taps Interested. 'talk' shows the seller's number; 'agree' only records the interest.
create or replace function express_interest(p_listing uuid, p_name text, p_phone text, p_choice text) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; l ticket_listings%rowtype; t tickets%rowtype; b bookings%rowtype; n int;
begin
  select * into s from settings where id = 1;
  if not s.transfers_open then raise exception 'TRANSFERS_CLOSED'; end if;
  select * into l from ticket_listings where id = p_listing and status = 'active';
  if not found then raise exception 'LISTING_NOT_AVAILABLE'; end if;
  select * into t from tickets where id = l.ticket_id;
  select * into b from bookings where id = t.booking_id;
  if _transfer_block_reason(t, b) is not null then raise exception 'LISTING_NOT_AVAILABLE'; end if;
  if length(trim(coalesce(p_name, ''))) not between 1 and 80 then raise exception 'INVALID_NAME'; end if;
  if coalesce(p_phone, '') !~ '^[0-9]{10}$' then raise exception 'INVALID_PHONE'; end if;
  if coalesce(p_choice, '') not in ('talk', 'agree') then raise exception 'INVALID_CHOICE'; end if;
  select count(*) into n from ticket_interests where listing_id = l.id;
  if n >= 50 and not exists (select 1 from ticket_interests where listing_id = l.id and phone = p_phone)
  then raise exception 'TOO_MANY_INTERESTED'; end if;
  insert into ticket_interests (listing_id, name, phone, choice) values (l.id, trim(p_name), p_phone, p_choice)
  on conflict (listing_id, phone) do update set name = excluded.name, choice = excluded.choice;
  return jsonb_build_object('choice', p_choice, 'price', l.price,
                            'contact_phone', case when p_choice = 'talk' then l.contact_phone end);
end $$;

-- Seller submits the transfer application. Returns the one-time transfer code to give the buyer.
-- Works with or without an ad (p_price is only used when there is no ad; it is optional).
create or replace function start_transfer(p_code text, p_ticket_no integer, p_price integer default null) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; v uuid; t tickets%rowtype; b bookings%rowtype; l ticket_listings%rowtype;
        x ticket_transfers%rowtype; r text; c text; price int;
begin
  select * into s from settings where id = 1;
  if not s.transfers_open then raise exception 'TRANSFERS_CLOSED'; end if;
  v := _seller_ticket(p_code, p_ticket_no);
  select * into t from tickets where id = v for update;
  select * into b from bookings where id = t.booking_id;
  r := _transfer_block_reason(t, b);
  if r is not null then raise exception '%', r; end if;
  if exists (select 1 from ticket_transfers where ticket_id = t.id and status in ('awaiting_buyer','pending_admin'))
  then raise exception 'ALREADY_IN_TRANSFER'; end if;
  select * into l from ticket_listings where ticket_id = t.id and status = 'active' for update;
  if found then
    price := l.price;
    update ticket_listings set status = 'closed', closed_at = now() where id = l.id;
  else
    price := p_price;
    if price is not null and (price < 0 or price > s.max_resale_price) then raise exception 'INVALID_PRICE'; end if;
  end if;
  loop
    c := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 10));
    exit when not exists (select 1 from ticket_transfers where code = c);
  end loop;
  insert into ticket_transfers (ticket_id, code, price, listing_id)
  values (t.id, c, price, l.id) returning * into x;
  return jsonb_build_object('code', x.code, 'price', x.price, 'label', _ticket_label(t.kind, t.ticket_no, t.coord_no));
end $$;

-- Seller cancels their live transfer application. Works even when transfers are closed.
create or replace function withdraw_transfer(p_code text, p_ticket_no integer) returns void
language plpgsql security definer set search_path to 'public' as $$
declare v uuid; n int;
begin
  v := _seller_ticket(p_code, p_ticket_no);
  perform 1 from tickets where id = v for update;
  update ticket_transfers set status = 'withdrawn' where ticket_id = v and status in ('awaiting_buyer','pending_admin');
  get diagnostics n = row_count;
  if n = 0 then raise exception 'NO_ACTIVE_TRANSFER'; end if;
end $$;

-- Buyer's side: ticket number + transfer code + the five details. Can be re-sent until the organisers decide.
create or replace function apply_receive(p_ticket_no integer, p_code text, p_name text, p_phone text,
                                         p_location text, p_attendance text, p_food text) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; c text; v uuid; t tickets%rowtype; b bookings%rowtype; x ticket_transfers%rowtype; r text;
begin
  select * into s from settings where id = 1;
  if not s.transfers_open then raise exception 'TRANSFERS_CLOSED'; end if;
  c := _norm_code(p_code);
  if length(c) <> 10 or p_ticket_no is null then raise exception 'INVALID_TRANSFER'; end if;
  select ticket_id into v from ticket_transfers where code = c;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  select * into t from tickets where id = v for update;           -- lock order: ticket first, then the application
  select * into x from ticket_transfers where code = c for update;
  if t.ticket_no is distinct from p_ticket_no or x.status not in ('awaiting_buyer','pending_admin')
  then raise exception 'INVALID_TRANSFER'; end if;
  select * into b from bookings where id = t.booking_id;
  r := _transfer_block_reason(t, b);
  if r is not null then raise exception '%', r; end if;
  if length(trim(coalesce(p_name, ''))) not between 1 and 80 then raise exception 'INVALID_NAME'; end if;
  if coalesce(p_phone, '') !~ '^[0-9]{10}$' then raise exception 'INVALID_PHONE'; end if;
  if coalesce(p_location, '') not in ('In Bengaluru', 'Outside Bengaluru') then raise exception 'INVALID_LOCATION'; end if;
  if coalesce(p_attendance, '') not in ('Surely', 'Most probably') then raise exception 'INVALID_ATTENDANCE'; end if;
  if coalesce(p_food, '') not in ('Veg', 'Non-veg') then raise exception 'INVALID_FOOD'; end if;
  update ticket_transfers set new_name = trim(p_name), new_phone = p_phone, new_location = p_location,
    new_attendance = p_attendance, new_food = p_food, buyer_applied_at = now(), status = 'pending_admin'
  where id = x.id;
  return lookup_transfer(c);
end $$;

-- Status page, by transfer code only. After approval it returns the buyer's own new ticket.
create or replace function lookup_transfer(p_code text) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare c text; x ticket_transfers%rowtype; t tickets%rowtype; b bookings%rowtype; res jsonb;
begin
  c := _norm_code(p_code);
  if length(c) <> 10 then return null; end if;
  select * into x from ticket_transfers where code = c;
  if not found then return null; end if;
  select * into t from tickets where id = x.ticket_id;
  select * into b from bookings where id = t.booking_id;
  res := jsonb_build_object('status', x.status, 'price', x.price, 'buyer_applied', x.new_name is not null,
                            'decline_reason', x.decline_reason);
  if x.status in ('awaiting_buyer', 'pending_admin') then
    res := res || jsonb_build_object('old_label', _ticket_label('guest', t.ticket_no, null));
  elsif x.status = 'done' then
    res := res || jsonb_build_object('old_label', _ticket_label('guest', x.from_ticket_no, null));
    -- show the ticket only while it is still the one issued by this transfer (never a later holder's)
    if t.ticket_no is not distinct from x.to_ticket_no and t.kind = 'guest' and b.status = 'paid' then
      res := res || jsonb_build_object('ticket', jsonb_build_object('label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
        'secret', t.secret, 'name', t.name, 'location', t.location, 'attendance', t.attendance, 'food', t.food));
    end if;
  end if;
  return res;
end $$;

-- 5. ADMIN FUNCTIONS --------------------------------------------------------------------------
create or replace function admin_set_transfer_settings(p_open boolean, p_max_price integer) returns void
language plpgsql security definer set search_path to 'public' as $$
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_open is null or p_max_price is null or p_max_price < 0 or p_max_price > 100000 then raise exception 'INVALID_SETTINGS'; end if;
  update settings set transfers_open = p_open, max_resale_price = p_max_price where id = 1;
end $$;

-- Approve a matched pair: new person, NEXT FREE number, new QR. The old number is retired for good.
create or replace function approve_transfer(p_id uuid, p_payment_confirmed boolean default false) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; v uuid; t tickets%rowtype; b bookings%rowtype; x ticket_transfers%rowtype; r text; new_no int;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1 for update;          -- same lock order as the gate: settings, ticket, ...
  select ticket_id into v from ticket_transfers where id = p_id;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  select * into t from tickets where id = v for update;
  select * into x from ticket_transfers where id = p_id for update;
  if x.status <> 'pending_admin' then raise exception 'NOT_PENDING'; end if;
  select * into b from bookings where id = t.booking_id;
  r := _transfer_block_reason(t, b);                                -- checked again now: it may have changed while waiting
  if r is not null then raise exception '%', r; end if;
  new_no := s.next_ticket;
  update ticket_transfers set status = 'done',
    from_name = t.name, from_phone = t.phone, from_location = t.location, from_attendance = t.attendance,
    from_food = t.food, from_ticket_no = t.ticket_no, to_ticket_no = new_no,
    payment_confirmed = coalesce(p_payment_confirmed, false), decided_by = auth.uid(), decided_at = now()
  where id = x.id;
  update tickets set ticket_no = new_no, secret = substr(replace(gen_random_uuid()::text, '-', ''), 1, 12),
    name = x.new_name, phone = x.new_phone, location = x.new_location,
    attendance = x.new_attendance, food = x.new_food
  where id = t.id;
  update settings set next_ticket = next_ticket + 1 where id = 1;
  update ticket_listings set status = 'closed', closed_at = now() where ticket_id = t.id and status = 'active';
  return jsonb_build_object('id', t.id, 'old_label', _ticket_label('guest', t.ticket_no, null),
                            'label', _ticket_label('guest', new_no, null), 'name', x.new_name);
end $$;

create or replace function decline_transfer(p_id uuid, p_reason text default null) returns void
language plpgsql security definer set search_path to 'public' as $$
declare x ticket_transfers%rowtype;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into x from ticket_transfers where id = p_id for update;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  if x.status not in ('awaiting_buyer', 'pending_admin') then raise exception 'NOT_PENDING'; end if;
  update ticket_transfers set status = 'declined', decided_by = auth.uid(), decided_at = now(),
    decline_reason = nullif(left(btrim(coalesce(p_reason, '')), 200), '') where id = x.id;
end $$;

create or replace function admin_remove_listing(p_id uuid) returns void
language plpgsql security definer set search_path to 'public' as $$
declare n int;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  update ticket_listings set status = 'removed', closed_at = now() where id = p_id and status = 'active';
  get diagnostics n = row_count;
  if n = 0 then raise exception 'NO_ACTIVE_LISTING'; end if;
end $$;


-- 6. GATE: a number retired by a transfer now says TICKET CANCELLED (everything else in admit_ticket is unchanged) --
CREATE OR REPLACE FUNCTION public.admit_ticket(p_ticket_no integer DEFAULT NULL::integer, p_secret text DEFAULT NULL::text, p_approve boolean DEFAULT false, p_coord boolean DEFAULT false, p_id uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare t tickets%rowtype; b bookings%rowtype; info jsonb; who text;
begin
  if not is_staff() then raise exception 'NOT_ALLOWED'; end if;
  if p_approve then perform 1 from settings where id = 1 for update; end if;

  if p_id is not null then
    select * into t from tickets where id = p_id for update;
  elsif p_coord then
    select * into t from tickets where coord_no = p_ticket_no and kind = 'coordinator' for update;
    if not found then
      -- maybe a coordinator number that was cancelled (person is a guest again)
      select * into t from tickets where prev_coord_no = p_ticket_no for update;
      if found then
        return jsonb_build_object('result', 'cancelled', 'name', t.name,
          'label', coalesce(_ticket_label(t.kind, t.ticket_no, t.coord_no), 'not numbered yet'),
          'old_label', _ticket_label('coordinator', null, t.prev_coord_no));
      end if;
    end if;
  else
    select * into t from tickets where ticket_no = p_ticket_no for update;
    if not found and p_ticket_no is not null then
      -- a number retired by an approved transfer: the QR is cancelled, show who holds the seat now
      select tk.* into t from ticket_transfers x join tickets tk on tk.id = x.ticket_id
       where x.from_ticket_no = p_ticket_no and x.status = 'done';
      if found then
        return jsonb_build_object('result', 'cancelled', 'name', t.name,
          'label', coalesce(_ticket_label(t.kind, t.ticket_no, t.coord_no), 'not numbered yet'),
          'old_label', _ticket_label('guest', p_ticket_no, null));
      end if;
    end if;
  end if;
  if not found then return jsonb_build_object('result', 'invalid'); end if;

  if p_id is null and t.kind = 'coordinator' and not p_coord then
    return jsonb_build_object('result', 'cancelled', 'name', t.name,
      'label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
      'old_label', _ticket_label('guest', t.ticket_no, null));
  end if;
  if p_secret is not null and t.secret <> p_secret then
    return jsonb_build_object('result', 'invalid'); end if;

  select * into b from bookings where id = t.booking_id for update;

  if b.status = 'pending' and p_approve then
    update bookings set status = 'paid', reviewed_by = auth.uid(), reviewed_at = now(), reviewed_via = 'gate' where id = b.id;
    perform _assign_numbers(b.id);
    select * into t from tickets where id = t.id;
    b.status := 'paid';
  end if;

  info := jsonb_build_object('id', t.id, 'ticket_no', t.ticket_no, 'kind', t.kind,
    'label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
    'name', t.name, 'food', t.food,
    'booking_code', b.booking_code, 'people_count', b.people_count,
    'amount_expected', b.amount_expected, 'screenshot_path', b.screenshot_path);

  if b.status = 'rejected' then return info || jsonb_build_object('result', 'rejected'); end if;
  if b.status = 'pending' then return info || jsonb_build_object('result', 'pending'); end if;
  if t.checked_in_at is not null then
    select name into who from staff where user_id = t.checked_in_by;
    return info || jsonb_build_object('result', 'already_scanned', 'checked_in_at', t.checked_in_at, 'checked_in_by', who);
  end if;
  update tickets set checked_in_at = now(), checked_in_by = auth.uid() where id = t.id;
  return info || jsonb_build_object('result', 'ok');
end $function$;

-- 7. WHO MAY CALL WHAT ---------------------------------------------------------------------------
revoke all on function _norm_code(text) from public;
revoke all on function _transfer_block_reason(tickets, bookings) from public;
revoke all on function _seller_ticket(text, integer) from public;
revoke all on function get_transfer_status() from public;
revoke all on function list_board() from public;
revoke all on function post_listing(text, integer, integer, text) from public;
revoke all on function manage_ticket(text, integer) from public;
revoke all on function close_listing(text, integer, boolean) from public;
revoke all on function express_interest(uuid, text, text, text) from public;
revoke all on function start_transfer(text, integer, integer) from public;
revoke all on function withdraw_transfer(text, integer) from public;
revoke all on function apply_receive(integer, text, text, text, text, text, text) from public;
revoke all on function lookup_transfer(text) from public;
revoke all on function admin_set_transfer_settings(boolean, integer) from public;
revoke all on function approve_transfer(uuid, boolean) from public;
revoke all on function decline_transfer(uuid, text) from public;
revoke all on function admin_remove_listing(uuid) from public;
revoke all on function admit_ticket(integer, text, boolean, boolean, uuid) from public;
-- website visitors (no login)
grant execute on function get_transfer_status() to anon, authenticated;
grant execute on function list_board() to anon, authenticated;
grant execute on function post_listing(text, integer, integer, text) to anon, authenticated;
grant execute on function manage_ticket(text, integer) to anon, authenticated;
grant execute on function close_listing(text, integer, boolean) to anon, authenticated;
grant execute on function express_interest(uuid, text, text, text) to anon, authenticated;
grant execute on function start_transfer(text, integer, integer) to anon, authenticated;
grant execute on function withdraw_transfer(text, integer) to anon, authenticated;
grant execute on function apply_receive(integer, text, text, text, text, text, text) to anon, authenticated;
grant execute on function lookup_transfer(text) to anon, authenticated;
-- signed-in staff only (admins are checked again inside each function)
grant execute on function admin_set_transfer_settings(boolean, integer) to authenticated;
grant execute on function approve_transfer(uuid, boolean) to authenticated;
grant execute on function decline_transfer(uuid, text) to authenticated;
grant execute on function admin_remove_listing(uuid) to authenticated;
grant execute on function admit_ticket(integer, text, boolean, boolean, uuid) to authenticated;

-- =====================================================================
-- TICKET TRANSFER, PART 2  (Public/Private transfer, locked price, comments, coordinator transfers)
-- Run this AFTER "transfer-feature.sql" (part 1). Safe to run more than once.
-- Run it in the Supabase SQL editor.
--
-- What changes compared with part 1
--   * Every ad / transfer is PRIVATE (buyer pays seller directly, organisers only approve)
--     or PUBLIC (buyer pays the organisers, organisers pay the seller after approval).
--   * The seller picks the price on the ad and may add a short comment (no phone numbers).
--     Editing the price closes the old ad ("edited") and opens a new one, so a buyer who
--     tapped Buy at Rs 200 can never be charged Rs 250. Starting the transfer locks the price.
--   * A buyer's tap on Buy remembers the price the buyer saw. A buyer can check the request
--     with ad + phone and is shown the transfer code once the seller has chosen them.
--   * Public transfers track the money: amount confirmed with the seller, buyer's payment proof,
--     payment received, seller paid, refund.
--   * Coordinators and former coordinators can now transfer too. On approval the buyer gets a
--     brand-new GUEST number and QR; the coordinator number (and any old guest number) is retired
--     for good. The seller's ticket is typed exactly as printed: 7, E26-007 or E26-001C.
--   * The retired-number check at the gate also covers retired coordinator numbers.
--
-- New error messages the pages should translate (the old ones from part 1 still apply, except
-- NOT_GUEST and FORMER_COORDINATOR which no longer happen):
--   INVALID_MODE, INVALID_PAYOUT, INVALID_COMMENT, INVALID_BUYER, COORDINATOR_ACK_REQUIRED,
--   WRONG_BUYER, PAYMENT_IN_PROGRESS, AMOUNT_NOT_CONFIRMED, PAYMENT_NOT_RECEIVED,
--   SCREENSHOT_MISSING, NOT_PUBLIC, INVALID_AMOUNT
-- =====================================================================

-- 1. TABLE CHANGES -----------------------------------------------------------------------------
alter table ticket_listings add column if not exists mode text not null default 'private';
alter table ticket_listings add column if not exists comment text;
alter table ticket_listings drop constraint if exists ticket_listings_mode_check;
alter table ticket_listings add constraint ticket_listings_mode_check check (mode in ('private','public'));
alter table ticket_listings drop constraint if exists ticket_listings_comment_check;
alter table ticket_listings add constraint ticket_listings_comment_check
  check (comment is null or char_length(comment) between 1 and 140);
-- an ad whose price was changed is kept as history with status 'edited'
alter table ticket_listings drop constraint if exists ticket_listings_status_check;
alter table ticket_listings add constraint ticket_listings_status_check
  check (status in ('active','withdrawn','sold','closed','removed','edited'));

alter table ticket_interests add column if not exists price_seen integer;

alter table ticket_transfers add column if not exists mode text not null default 'private';
alter table ticket_transfers add column if not exists payout text;                 -- seller's UPI ID or phone (Public only)
alter table ticket_transfers add column if not exists agreed_amount integer;       -- what the buyer pays the organisers (Public only)
alter table ticket_transfers add column if not exists amount_confirmed_at timestamptz;
alter table ticket_transfers add column if not exists amount_confirmed_by uuid references auth.users(id);
alter table ticket_transfers add column if not exists intended_phone text;         -- the buyer the seller chose (optional)
alter table ticket_transfers add column if not exists buyer_interest_id uuid references ticket_interests(id) on delete set null;
alter table ticket_transfers add column if not exists buyer_paid_at timestamptz;
alter table ticket_transfers add column if not exists buyer_screenshot_path text;
alter table ticket_transfers add column if not exists payment_received_at timestamptz;
alter table ticket_transfers add column if not exists payment_received_by uuid references auth.users(id);
alter table ticket_transfers add column if not exists seller_paid_at timestamptz;
alter table ticket_transfers add column if not exists seller_paid_ref text;
alter table ticket_transfers add column if not exists refunded_at timestamptz;
alter table ticket_transfers add column if not exists refund_ref text;
alter table ticket_transfers add column if not exists from_kind text;              -- guest / coordinator / former_coordinator
alter table ticket_transfers add column if not exists from_coord_no integer;       -- retired coordinator number

alter table ticket_transfers drop constraint if exists ticket_transfers_mode_check;
alter table ticket_transfers add constraint ticket_transfers_mode_check check (mode in ('private','public'));
alter table ticket_transfers drop constraint if exists ticket_transfers_from_kind_check;
alter table ticket_transfers add constraint ticket_transfers_from_kind_check
  check (from_kind is null or from_kind in ('guest','coordinator','former_coordinator'));
alter table ticket_transfers drop constraint if exists ticket_transfers_payout_check;
alter table ticket_transfers add constraint ticket_transfers_payout_check
  check (payout is null or payout ~ '^([0-9]{10}|[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9]{1,31})$');
alter table ticket_transfers drop constraint if exists ticket_transfers_amount_check;
alter table ticket_transfers add constraint ticket_transfers_amount_check
  check (agreed_amount is null or agreed_amount >= 0);
-- a retired coordinator number appears in history only once
create unique index if not exists ticket_transfers_from_coord_uq on ticket_transfers (from_coord_no)
  where from_coord_no is not null;

-- 2. REMOVE THE OLD VERSIONS WHOSE ARGUMENTS CHANGED -------------------------------------------
drop function if exists post_listing(text, integer, integer, text);
drop function if exists manage_ticket(text, integer);
drop function if exists close_listing(text, integer, boolean);
drop function if exists start_transfer(text, integer, integer);
drop function if exists withdraw_transfer(text, integer);
drop function if exists apply_receive(integer, text, text, text, text, text, text);
drop function if exists _seller_ticket(text, integer);

-- 3. INTERNAL HELPERS ----------------------------------------------------------------------------
-- "E26-007", "7", "e26 007" -> guest 7;  "E26-001C", "1c" -> coordinator 1;  anything else -> nulls
create or replace function _parse_ticket(p text, out kind text, out no integer)
language plpgsql immutable as $$
declare s text;
begin
  s := upper(regexp_replace(coalesce(p, ''), '[\s-]', '', 'g'));
  s := regexp_replace(s, '^E26', '');
  s := replace(s, 'O', '0');
  if s ~ '^[0-9]{1,6}C$' then kind := 'coordinator'; no := substr(s, 1, length(s) - 1)::integer;
  elsif s ~ '^[0-9]{1,6}$' then kind := 'guest'; no := s::integer;
  end if;
end $$;

-- What kind of seat this is: guest, coordinator, or a guest who used to be a coordinator
create or replace function _seller_kind(t tickets) returns text
language sql immutable as $$
  select case when t.kind = 'coordinator' then 'coordinator'
              when t.prev_coord_no is not null then 'former_coordinator'
              else 'guest' end $$;

-- Why a ticket cannot be sold/transferred right now (null = it can).
-- Coordinators and former coordinators are allowed now; only unpaid or already-scanned tickets are blocked.
create or replace function _transfer_block_reason(t tickets, b bookings) returns text
language sql as $$
  select case
    when b.status <> 'paid' then 'NOT_PAID'
    when t.kind = 'guest' and t.ticket_no is null then 'NOT_PAID'
    when t.checked_in_at is not null then 'ALREADY_CHECKED_IN'
  end $$;

-- Booking ID + ticket as printed -> the ticket's id (the seller's proof of ownership)
create or replace function _seller_ticket(p_booking_code text, p_ticket text) returns uuid
language plpgsql security definer set search_path to 'public' as $$
declare c text; b bookings%rowtype; v uuid; k text; n integer;
begin
  c := _norm_code(p_booking_code);
  if length(c) <> 8 then raise exception 'INVALID_TICKET'; end if;
  select kind, no into k, n from _parse_ticket(p_ticket);
  if k is null then raise exception 'INVALID_TICKET'; end if;
  select * into b from bookings where booking_code = c;
  if not found then raise exception 'INVALID_TICKET'; end if;
  if k = 'guest' then
    select id into v from tickets where booking_id = b.id and kind = 'guest' and ticket_no = n;
  else
    select id into v from tickets where booking_id = b.id and kind = 'coordinator' and coord_no = n;
  end if;
  if found then return v; end if;
  if exists (select 1 from ticket_transfers x join tickets tk on tk.id = x.ticket_id
             where tk.booking_id = b.id and x.status = 'done'
               and ((k = 'guest' and x.from_ticket_no = n) or (k = 'coordinator' and x.from_coord_no = n)))
  then raise exception 'ALREADY_TRANSFERRED'; end if;
  raise exception 'INVALID_TICKET';
end $$;

-- A seller's comment: short, plain text, no phone numbers / UPI IDs / links (those would skip the organisers)
create or replace function _clean_comment(p text) returns text
language plpgsql immutable as $$
declare v text;
begin
  if p is null then return null; end if;
  v := btrim(regexp_replace(p, '\s+', ' ', 'g'));
  if v = '' then return null; end if;
  if char_length(v) > 140
     or length(regexp_replace(v, '[^0-9]', '', 'g')) >= 8
     or position('@' in v) > 0
     or v ~* '(https?:|www\.)'
  then raise exception 'INVALID_COMMENT'; end if;
  return v;
end $$;

-- The seller's payout: a 10-digit phone number or a UPI ID like name@bank
create or replace function _clean_payout(p text) returns text
language plpgsql immutable as $$
declare v text;
begin
  v := btrim(coalesce(p, ''));
  if v ~ '^[0-9]{10}$' or v ~ '^[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9]{1,31}$' then return v; end if;
  raise exception 'INVALID_PAYOUT';
end $$;

-- 4. PUBLIC FUNCTIONS ----------------------------------------------------------------------------
create or replace function list_board() returns jsonb
language sql stable security definer set search_path to 'public' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', l.id, 'price', l.price, 'mode', l.mode, 'comment', l.comment,
                                               'posted_at', l.created_at) order by l.created_at desc), '[]'::jsonb)
  from ticket_listings l
  join tickets t on t.id = l.ticket_id
  join bookings b on b.id = t.booking_id
  where (select transfers_open from settings where id = 1)
    and l.status = 'active' and t.checked_in_at is null and b.status = 'paid' $$;

create or replace function post_listing(p_code text, p_ticket text, p_price integer, p_contact text,
                                        p_mode text default 'private', p_comment text default null,
                                        p_ack boolean default false) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; v uuid; t tickets%rowtype; b bookings%rowtype; l ticket_listings%rowtype; r text; cm text;
begin
  select * into s from settings where id = 1;
  if not s.transfers_open then raise exception 'TRANSFERS_CLOSED'; end if;
  v := _seller_ticket(p_code, p_ticket);
  select * into t from tickets where id = v for update;
  select * into b from bookings where id = t.booking_id;
  r := _transfer_block_reason(t, b);
  if r is not null then raise exception '%', r; end if;
  if coalesce(p_mode, '') not in ('private', 'public') then raise exception 'INVALID_MODE'; end if;
  if _seller_kind(t) <> 'guest' and not coalesce(p_ack, false) then raise exception 'COORDINATOR_ACK_REQUIRED'; end if;
  if p_price is null or p_price < 0 or p_price > s.max_resale_price then raise exception 'INVALID_PRICE'; end if;
  if coalesce(p_contact, '') !~ '^[0-9]{10}$' then raise exception 'INVALID_PHONE'; end if;
  cm := _clean_comment(p_comment);
  if exists (select 1 from ticket_transfers where ticket_id = t.id and status in ('awaiting_buyer','pending_admin'))
  then raise exception 'ALREADY_IN_TRANSFER'; end if;
  if exists (select 1 from ticket_listings where ticket_id = t.id and status = 'active')
  then raise exception 'ALREADY_LISTED'; end if;
  insert into ticket_listings (ticket_id, price, contact_phone, mode, comment)
  values (t.id, p_price, p_contact, p_mode, cm) returning * into l;
  return jsonb_build_object('id', l.id, 'price', l.price, 'mode', l.mode);
end $$;

-- Change the price (closes the old ad as 'edited' and opens a new one) and/or the comment (changed in place).
-- p_comment: null keeps the current comment, '' clears it.
create or replace function edit_listing(p_code text, p_ticket text, p_price integer, p_comment text default null) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; v uuid; t tickets%rowtype; b bookings%rowtype; l ticket_listings%rowtype;
        n ticket_listings%rowtype; r text; cm text;
begin
  select * into s from settings where id = 1;
  if not s.transfers_open then raise exception 'TRANSFERS_CLOSED'; end if;
  v := _seller_ticket(p_code, p_ticket);
  select * into t from tickets where id = v for update;
  select * into b from bookings where id = t.booking_id;
  r := _transfer_block_reason(t, b);
  if r is not null then raise exception '%', r; end if;
  if exists (select 1 from ticket_transfers where ticket_id = t.id and status in ('awaiting_buyer','pending_admin'))
  then raise exception 'ALREADY_IN_TRANSFER'; end if;
  select * into l from ticket_listings where ticket_id = t.id and status = 'active' for update;
  if not found then raise exception 'NO_ACTIVE_LISTING'; end if;
  if p_price is null or p_price < 0 or p_price > s.max_resale_price then raise exception 'INVALID_PRICE'; end if;
  cm := case when p_comment is null then l.comment else _clean_comment(p_comment) end;
  if p_price = l.price then
    update ticket_listings set comment = cm where id = l.id;
    return jsonb_build_object('id', l.id, 'price', l.price, 'changed', false);
  end if;
  update ticket_listings set status = 'edited', closed_at = now() where id = l.id;
  insert into ticket_listings (ticket_id, price, contact_phone, mode, comment)
  values (t.id, p_price, l.contact_phone, l.mode, cm) returning * into n;
  return jsonb_build_object('id', n.id, 'price', n.price, 'changed', true);
end $$;

-- Seller's "Manage my listing" page
create or replace function manage_ticket(p_code text, p_ticket text) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare v uuid; t tickets%rowtype; b bookings%rowtype; s settings%rowtype; l ticket_listings%rowtype;
        x ticket_transfers%rowtype; li jsonb; xi jsonb; hist jsonb;
begin
  v := _seller_ticket(p_code, p_ticket);
  select * into t from tickets where id = v;
  select * into b from bookings where id = t.booking_id;
  select * into s from settings where id = 1;
  select * into l from ticket_listings where ticket_id = t.id and status = 'active';
  if found then
    li := jsonb_build_object('id', l.id, 'price', l.price, 'mode', l.mode, 'comment', l.comment,
      'contact_phone', l.contact_phone, 'created_at', l.created_at,
      'interests', coalesce((select jsonb_agg(jsonb_build_object('id', i.id, 'name', i.name, 'phone', i.phone,
                  'choice', i.choice, 'price_seen', i.price_seen, 'created_at', i.created_at) order by i.created_at)
                  from ticket_interests i where i.listing_id = l.id), '[]'::jsonb));
  end if;
  select coalesce(jsonb_agg(h.j order by h.created_at desc), '[]'::jsonb) into hist
  from (select jsonb_build_object('id', o.id, 'price', o.price, 'status', o.status, 'comment', o.comment,
                                  'created_at', o.created_at, 'closed_at', o.closed_at) as j, o.created_at
        from ticket_listings o where o.ticket_id = t.id and o.status <> 'active'
        order by o.created_at desc limit 10) h;
  select * into x from ticket_transfers where ticket_id = t.id and status in ('awaiting_buyer','pending_admin');
  if found then
    xi := jsonb_build_object('status', x.status, 'code', x.code, 'mode', x.mode, 'price', x.price,
                             'agreed_amount', x.agreed_amount, 'amount_confirmed', x.amount_confirmed_at is not null,
                             'created_at', x.created_at, 'buyer_name', x.new_name, 'buyer_phone', x.new_phone,
                             'buyer_paid', x.buyer_paid_at is not null,
                             'payment_received', x.payment_received_at is not null, 'payout', x.payout);
  end if;
  return jsonb_build_object('label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
    'kind', _seller_kind(t), 'open', s.transfers_open, 'max_price', s.max_resale_price,
    'blocked', _transfer_block_reason(t, b), 'listing', li, 'history', hist, 'transfer', xi);
end $$;

-- Seller deletes the ad (p_sold = false) or marks it sold/complete (p_sold = true). Works even when transfers are closed.
create or replace function close_listing(p_code text, p_ticket text, p_sold boolean default false) returns void
language plpgsql security definer set search_path to 'public' as $$
declare v uuid; n int;
begin
  v := _seller_ticket(p_code, p_ticket);
  update ticket_listings set status = case when coalesce(p_sold, false) then 'sold' else 'withdrawn' end, closed_at = now()
  where ticket_id = v and status = 'active';
  get diagnostics n = row_count;
  if n = 0 then raise exception 'NO_ACTIVE_LISTING'; end if;
end $$;

-- Buyer taps Buy/Interested. Remembers the price the buyer saw. In a Public ad the seller's number is never shown.
create or replace function express_interest(p_listing uuid, p_name text, p_phone text, p_choice text) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; l ticket_listings%rowtype; t tickets%rowtype; b bookings%rowtype; n int;
begin
  select * into s from settings where id = 1;
  if not s.transfers_open then raise exception 'TRANSFERS_CLOSED'; end if;
  select * into l from ticket_listings where id = p_listing and status = 'active';
  if not found then raise exception 'LISTING_NOT_AVAILABLE'; end if;
  select * into t from tickets where id = l.ticket_id;
  select * into b from bookings where id = t.booking_id;
  if _transfer_block_reason(t, b) is not null then raise exception 'LISTING_NOT_AVAILABLE'; end if;
  if length(trim(coalesce(p_name, ''))) not between 1 and 80 then raise exception 'INVALID_NAME'; end if;
  if coalesce(p_phone, '') !~ '^[0-9]{10}$' then raise exception 'INVALID_PHONE'; end if;
  if coalesce(p_choice, '') not in ('talk', 'agree') then raise exception 'INVALID_CHOICE'; end if;
  select count(*) into n from ticket_interests where listing_id = l.id;
  if n >= 50 and not exists (select 1 from ticket_interests where listing_id = l.id and phone = p_phone)
  then raise exception 'TOO_MANY_INTERESTED'; end if;
  insert into ticket_interests (listing_id, name, phone, choice, price_seen)
  values (l.id, trim(p_name), p_phone, p_choice, l.price)
  on conflict (listing_id, phone) do update set name = excluded.name, choice = excluded.choice, price_seen = excluded.price_seen;
  return jsonb_build_object('choice', p_choice, 'price', l.price, 'mode', l.mode,
                            'contact_phone', case when p_choice = 'talk' and l.mode = 'private' then l.contact_phone end);
end $$;

-- The buyer's "Check my request" page: ad + the phone used when tapping Buy.
-- States: waiting, price_changed, accepted (shows the transfer code), done, ended, taken, sold, gone
create or replace function check_request(p_listing uuid, p_phone text) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare i ticket_interests%rowtype; l ticket_listings%rowtype; n ticket_listings%rowtype;
        x ticket_transfers%rowtype; t tickets%rowtype;
begin
  if coalesce(p_phone, '') !~ '^[0-9]{10}$' then raise exception 'INVALID_PHONE'; end if;
  select * into i from ticket_interests where listing_id = p_listing and phone = p_phone;
  if not found then return null; end if;
  select * into l from ticket_listings where id = p_listing;
  if l.status = 'active' then
    return jsonb_build_object('state', 'waiting', 'price', l.price, 'mode', l.mode);
  elsif l.status = 'edited' then
    select * into n from ticket_listings where ticket_id = l.ticket_id and status = 'active';
    if found then
      return jsonb_build_object('state', 'price_changed', 'old_price', i.price_seen, 'new_price', n.price,
                                'new_listing', n.id, 'mode', n.mode);
    end if;
    return jsonb_build_object('state', 'gone');
  elsif l.status = 'closed' then
    select * into x from ticket_transfers where listing_id = l.id order by created_at desc limit 1;
    if not found or x.intended_phone is distinct from p_phone then
      return jsonb_build_object('state', 'taken');
    end if;
    if x.status in ('awaiting_buyer', 'pending_admin') then
      select * into t from tickets where id = x.ticket_id;
      return jsonb_build_object('state', 'accepted', 'code', x.code, 'mode', x.mode, 'price', x.price,
                                'ticket', _ticket_label(t.kind, t.ticket_no, t.coord_no));
    elsif x.status = 'done' then
      return jsonb_build_object('state', 'done', 'code', x.code);
    end if;
    return jsonb_build_object('state', 'ended');
  elsif l.status = 'sold' then
    return jsonb_build_object('state', 'sold');
  end if;
  return jsonb_build_object('state', 'gone');
end $$;

-- Seller starts the transfer. Locks the price and returns the one-time transfer code.
--   with an ad: mode and price come from the ad; p_buyer (optional) is one of the people who tapped Buy
--   without an ad: p_mode is required; a Public transfer also needs p_price (the amount to collect)
--   Public transfers need the seller's payout (UPI ID or phone)
create or replace function start_transfer(p_code text, p_ticket text, p_price integer default null,
                                          p_mode text default null, p_payout text default null,
                                          p_buyer uuid default null, p_ack boolean default false) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; v uuid; t tickets%rowtype; b bookings%rowtype; l ticket_listings%rowtype;
        i ticket_interests%rowtype; x ticket_transfers%rowtype; r text; c text; price int; md text; po text;
begin
  select * into s from settings where id = 1;
  if not s.transfers_open then raise exception 'TRANSFERS_CLOSED'; end if;
  v := _seller_ticket(p_code, p_ticket);
  select * into t from tickets where id = v for update;
  select * into b from bookings where id = t.booking_id;
  r := _transfer_block_reason(t, b);
  if r is not null then raise exception '%', r; end if;
  if _seller_kind(t) <> 'guest' and not coalesce(p_ack, false) then raise exception 'COORDINATOR_ACK_REQUIRED'; end if;
  if exists (select 1 from ticket_transfers where ticket_id = t.id and status in ('awaiting_buyer','pending_admin'))
  then raise exception 'ALREADY_IN_TRANSFER'; end if;
  select * into l from ticket_listings where ticket_id = t.id and status = 'active' for update;
  if found then
    md := l.mode;
    price := l.price;
    if price > s.max_resale_price then raise exception 'INVALID_PRICE'; end if;
    if p_buyer is not null then
      select * into i from ticket_interests where id = p_buyer and listing_id = l.id;
      if not found then raise exception 'INVALID_BUYER'; end if;
    end if;
    update ticket_listings set status = 'closed', closed_at = now() where id = l.id;
  else
    md := coalesce(p_mode, '');
    if md not in ('private', 'public') then raise exception 'INVALID_MODE'; end if;
    if p_buyer is not null then raise exception 'INVALID_BUYER'; end if;
    price := p_price;
    if price is not null and (price < 0 or price > s.max_resale_price) then raise exception 'INVALID_PRICE'; end if;
    if md = 'public' and price is null then raise exception 'INVALID_PRICE'; end if;
  end if;
  if md = 'public' then po := _clean_payout(p_payout); end if;
  loop
    c := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 10));
    exit when not exists (select 1 from ticket_transfers where code = c);
  end loop;
  insert into ticket_transfers (ticket_id, code, price, listing_id, mode, payout, agreed_amount,
                                intended_phone, buyer_interest_id)
  values (t.id, c, price, l.id, md, po, case when md = 'public' then price end, i.phone, i.id)
  returning * into x;
  return jsonb_build_object('code', x.code, 'price', x.price, 'mode', x.mode,
                            'label', _ticket_label(t.kind, t.ticket_no, t.coord_no), 'kind', _seller_kind(t));
end $$;

-- Seller cancels their live transfer. Not possible once the buyer has paid the organisers.
create or replace function withdraw_transfer(p_code text, p_ticket text) returns void
language plpgsql security definer set search_path to 'public' as $$
declare v uuid; x ticket_transfers%rowtype;
begin
  v := _seller_ticket(p_code, p_ticket);
  perform 1 from tickets where id = v for update;
  select * into x from ticket_transfers where ticket_id = v and status in ('awaiting_buyer','pending_admin') for update;
  if not found then raise exception 'NO_ACTIVE_TRANSFER'; end if;
  if x.buyer_paid_at is not null then raise exception 'PAYMENT_IN_PROGRESS'; end if;
  update ticket_transfers set status = 'withdrawn' where id = x.id;
end $$;

-- Buyer's side: seller's ticket + transfer code + the five details.
-- If the seller chose a particular buyer, only that phone number is accepted.
create or replace function apply_receive(p_ticket text, p_code text, p_name text, p_phone text,
                                         p_location text, p_attendance text, p_food text) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; c text; v uuid; t tickets%rowtype; b bookings%rowtype; x ticket_transfers%rowtype;
        r text; k text; n integer;
begin
  select * into s from settings where id = 1;
  if not s.transfers_open then raise exception 'TRANSFERS_CLOSED'; end if;
  c := _norm_code(p_code);
  select kind, no into k, n from _parse_ticket(p_ticket);
  if length(c) <> 10 or k is null then raise exception 'INVALID_TRANSFER'; end if;
  select ticket_id into v from ticket_transfers where code = c;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  select * into t from tickets where id = v for update;           -- lock order: ticket first, then the application
  select * into x from ticket_transfers where code = c for update;
  if x.status not in ('awaiting_buyer','pending_admin')
     or not ((k = 'guest' and t.kind = 'guest' and t.ticket_no = n) or (k = 'coordinator' and t.kind = 'coordinator' and t.coord_no = n))
  then raise exception 'INVALID_TRANSFER'; end if;
  select * into b from bookings where id = t.booking_id;
  r := _transfer_block_reason(t, b);
  if r is not null then raise exception '%', r; end if;
  if x.buyer_paid_at is not null then raise exception 'PAYMENT_IN_PROGRESS'; end if;
  if length(trim(coalesce(p_name, ''))) not between 1 and 80 then raise exception 'INVALID_NAME'; end if;
  if coalesce(p_phone, '') !~ '^[0-9]{10}$' then raise exception 'INVALID_PHONE'; end if;
  if x.intended_phone is not null and x.intended_phone <> p_phone then raise exception 'WRONG_BUYER'; end if;
  if coalesce(p_location, '') not in ('In Bengaluru', 'Outside Bengaluru') then raise exception 'INVALID_LOCATION'; end if;
  if coalesce(p_attendance, '') not in ('Surely', 'Most probably') then raise exception 'INVALID_ATTENDANCE'; end if;
  if coalesce(p_food, '') not in ('Veg', 'Non-veg') then raise exception 'INVALID_FOOD'; end if;
  update ticket_transfers set new_name = trim(p_name), new_phone = p_phone, new_location = p_location,
    new_attendance = p_attendance, new_food = p_food, buyer_applied_at = now(), status = 'pending_admin'
  where id = x.id;
  return lookup_transfer(c);
end $$;

-- Public transfers only: after the organisers confirmed the amount with the seller, the buyer pays the
-- organisers and uploads the proof (file name must start with "transfer-" + the transfer code).
-- Works even if transfers were switched off meanwhile (so transfers already in progress can finish).
create or replace function submit_transfer_payment(p_ticket text, p_code text, p_screenshot_path text) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare c text; v uuid; t tickets%rowtype; x ticket_transfers%rowtype; k text; n integer;
begin
  c := _norm_code(p_code);
  select kind, no into k, n from _parse_ticket(p_ticket);
  if length(c) <> 10 or k is null then raise exception 'INVALID_TRANSFER'; end if;
  select ticket_id into v from ticket_transfers where code = c;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  select * into t from tickets where id = v for update;
  select * into x from ticket_transfers where code = c for update;
  if x.status <> 'pending_admin'
     or not ((k = 'guest' and t.kind = 'guest' and t.ticket_no = n) or (k = 'coordinator' and t.kind = 'coordinator' and t.coord_no = n))
  then raise exception 'INVALID_TRANSFER'; end if;
  if x.mode <> 'public' then raise exception 'NOT_PUBLIC'; end if;
  if x.amount_confirmed_at is null then raise exception 'AMOUNT_NOT_CONFIRMED'; end if;
  if x.payment_received_at is not null then raise exception 'PAYMENT_IN_PROGRESS'; end if;
  if p_screenshot_path is null or p_screenshot_path not like 'transfer-' || x.code || '%'
     or not exists (select 1 from storage.objects where bucket_id = 'payment-proofs' and name = p_screenshot_path)
  then raise exception 'SCREENSHOT_MISSING'; end if;
  update ticket_transfers set buyer_screenshot_path = p_screenshot_path, buyer_paid_at = now() where id = x.id;
  return lookup_transfer(c);
end $$;

-- Status page, by transfer code only. After approval it returns the buyer's own new ticket (never the Booking ID).
create or replace function lookup_transfer(p_code text) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare c text; x ticket_transfers%rowtype; t tickets%rowtype; b bookings%rowtype; res jsonb;
begin
  c := _norm_code(p_code);
  if length(c) <> 10 then return null; end if;
  select * into x from ticket_transfers where code = c;
  if not found then return null; end if;
  select * into t from tickets where id = x.ticket_id;
  select * into b from bookings where id = t.booking_id;
  res := jsonb_build_object('status', x.status, 'mode', x.mode, 'price', x.price,
    'agreed_amount', x.agreed_amount, 'amount_confirmed', x.amount_confirmed_at is not null,
    'buyer_applied', x.new_name is not null,
    'paid', x.buyer_paid_at is not null, 'payment_received', x.payment_received_at is not null,
    'refund_due', (x.mode = 'public' and x.payment_received_at is not null and x.refunded_at is null
                   and x.status in ('declined', 'withdrawn')),
    'refunded', x.refunded_at is not null, 'decline_reason', x.decline_reason);
  if x.status in ('awaiting_buyer', 'pending_admin') then
    res := res || jsonb_build_object('old_label', _ticket_label(t.kind, t.ticket_no, t.coord_no));
  elsif x.status = 'done' then
    res := res || jsonb_build_object('old_label',
      case when x.from_kind = 'coordinator' then _ticket_label('coordinator', null, x.from_coord_no)
           else _ticket_label('guest', x.from_ticket_no, null) end);
    -- show the ticket only while it is still the one issued by this transfer (never a later holder's)
    if t.ticket_no is not distinct from x.to_ticket_no and t.kind = 'guest' and b.status = 'paid' then
      res := res || jsonb_build_object('ticket', jsonb_build_object('label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
        'secret', t.secret, 'name', t.name, 'location', t.location, 'attendance', t.attendance, 'food', t.food));
    end if;
  end if;
  return res;
end $$;

-- 5. ADMIN FUNCTIONS -----------------------------------------------------------------------------
-- Public transfers: the organisers called the seller and agreed the amount the buyer must pay.
create or replace function admin_confirm_amount(p_id uuid, p_amount integer) returns void
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; x ticket_transfers%rowtype;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1;
  select * into x from ticket_transfers where id = p_id for update;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  if x.status not in ('awaiting_buyer', 'pending_admin') then raise exception 'NOT_PENDING'; end if;
  if x.mode <> 'public' then raise exception 'NOT_PUBLIC'; end if;
  if x.buyer_paid_at is not null then raise exception 'PAYMENT_IN_PROGRESS'; end if;
  if p_amount is null or p_amount < 0 or p_amount > s.max_resale_price then raise exception 'INVALID_AMOUNT'; end if;
  update ticket_transfers set agreed_amount = p_amount, amount_confirmed_at = now(), amount_confirmed_by = auth.uid()
  where id = x.id;
end $$;

-- Tick (or untick) "payment received" after checking the bank app.
create or replace function admin_mark_payment_received(p_id uuid, p_received boolean default true) returns void
language plpgsql security definer set search_path to 'public' as $$
declare x ticket_transfers%rowtype;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into x from ticket_transfers where id = p_id for update;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  if x.status <> 'pending_admin' then raise exception 'NOT_PENDING'; end if;
  if x.mode <> 'public' then raise exception 'NOT_PUBLIC'; end if;
  if x.amount_confirmed_at is null then raise exception 'AMOUNT_NOT_CONFIRMED'; end if;
  if coalesce(p_received, true) then
    update ticket_transfers set payment_received_at = coalesce(payment_received_at, now()),
      buyer_paid_at = coalesce(buyer_paid_at, now()), payment_received_by = auth.uid() where id = x.id;
  else
    -- also forget the "paid" mark if it only came from the admin's tick (the buyer never uploaded proof)
    update ticket_transfers set payment_received_at = null, payment_received_by = null,
      buyer_paid_at = case when buyer_screenshot_path is null then null else buyer_paid_at end
    where id = x.id;
  end if;
end $$;

-- After approval the organisers pay the seller by UPI and record it here.
create or replace function admin_mark_seller_paid(p_id uuid, p_ref text default null) returns void
language plpgsql security definer set search_path to 'public' as $$
declare x ticket_transfers%rowtype;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into x from ticket_transfers where id = p_id for update;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  if x.status <> 'done' or x.mode <> 'public' then raise exception 'NOT_PUBLIC'; end if;
  update ticket_transfers set seller_paid_at = coalesce(seller_paid_at, now()),
    seller_paid_ref = nullif(left(btrim(coalesce(p_ref, '')), 100), '') where id = x.id;
end $$;

-- After a declined/withdrawn Public transfer where the organisers had received the money: record the refund.
create or replace function admin_mark_refunded(p_id uuid, p_ref text default null) returns void
language plpgsql security definer set search_path to 'public' as $$
declare x ticket_transfers%rowtype;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into x from ticket_transfers where id = p_id for update;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  if x.mode <> 'public' or x.status not in ('declined', 'withdrawn') or x.payment_received_at is null
  then raise exception 'NOT_PENDING'; end if;
  update ticket_transfers set refunded_at = coalesce(refunded_at, now()),
    refund_ref = nullif(left(btrim(coalesce(p_ref, '')), 100), '') where id = x.id;
end $$;

-- Remove just the comment of an ad (for example if it is rude), keeping the ad.
create or replace function admin_clear_comment(p_id uuid) returns void
language plpgsql security definer set search_path to 'public' as $$
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  update ticket_listings set comment = null where id = p_id;
  if not found then raise exception 'NO_ACTIVE_LISTING'; end if;
end $$;

-- Approve a matched pair: new person, NEXT FREE guest number, new QR. Old numbers are retired for good.
-- A coordinator seat becomes a normal guest seat; a former coordinator loses both their numbers.
create or replace function approve_transfer(p_id uuid, p_payment_confirmed boolean default false) returns jsonb
language plpgsql security definer set search_path to 'public' as $$
declare s settings%rowtype; v uuid; t tickets%rowtype; b bookings%rowtype; x ticket_transfers%rowtype;
        r text; new_no int; k text;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into s from settings where id = 1 for update;          -- same lock order as the gate: settings, ticket, ...
  select ticket_id into v from ticket_transfers where id = p_id;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  select * into t from tickets where id = v for update;
  select * into x from ticket_transfers where id = p_id for update;
  if x.status <> 'pending_admin' then raise exception 'NOT_PENDING'; end if;
  select * into b from bookings where id = t.booking_id;
  r := _transfer_block_reason(t, b);                                -- checked again now: it may have changed while waiting
  if r is not null then raise exception '%', r; end if;
  if x.mode = 'public' then
    if x.amount_confirmed_at is null then raise exception 'AMOUNT_NOT_CONFIRMED'; end if;
    if x.payment_received_at is null then raise exception 'PAYMENT_NOT_RECEIVED'; end if;
  end if;
  k := _seller_kind(t);
  new_no := s.next_ticket;
  update ticket_transfers set status = 'done',
    from_name = t.name, from_phone = t.phone, from_location = t.location, from_attendance = t.attendance,
    from_food = t.food, from_ticket_no = t.ticket_no, to_ticket_no = new_no,
    from_kind = k,
    from_coord_no = case k when 'coordinator' then t.coord_no when 'former_coordinator' then t.prev_coord_no end,
    payment_confirmed = coalesce(p_payment_confirmed, false) or x.payment_received_at is not null,
    decided_by = auth.uid(), decided_at = now()
  where id = x.id;
  update tickets set ticket_no = new_no, secret = substr(replace(gen_random_uuid()::text, '-', ''), 1, 12),
    kind = 'guest', coord_no = null, orig_secret = null, prev_coord_no = null, prev_coord_secret = null,
    marked_by = null, marked_at = null,
    name = x.new_name, phone = x.new_phone, location = x.new_location,
    attendance = x.new_attendance, food = x.new_food
  where id = t.id;
  update settings set next_ticket = next_ticket + 1 where id = 1;
  update ticket_listings set status = 'closed', closed_at = now() where ticket_id = t.id and status = 'active';
  return jsonb_build_object('id', t.id, 'kind', k, 'mode', x.mode, 'agreed_amount', x.agreed_amount, 'payout', x.payout,
    'old_label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
    'label', _ticket_label('guest', new_no, null), 'name', x.new_name);
end $$;

-- 6. GATE: retired guest numbers AND retired coordinator numbers say TICKET CANCELLED ---------------
CREATE OR REPLACE FUNCTION public.admit_ticket(p_ticket_no integer DEFAULT NULL::integer, p_secret text DEFAULT NULL::text, p_approve boolean DEFAULT false, p_coord boolean DEFAULT false, p_id uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare t tickets%rowtype; b bookings%rowtype; info jsonb; who text;
begin
  if not is_staff() then raise exception 'NOT_ALLOWED'; end if;
  if p_approve then perform 1 from settings where id = 1 for update; end if;

  if p_id is not null then
    select * into t from tickets where id = p_id for update;
  elsif p_coord then
    select * into t from tickets where coord_no = p_ticket_no and kind = 'coordinator' for update;
    if not found then
      -- maybe a coordinator number that was cancelled (person is a guest again)
      select * into t from tickets where prev_coord_no = p_ticket_no for update;
      if found then
        return jsonb_build_object('result', 'cancelled', 'name', t.name,
          'label', coalesce(_ticket_label(t.kind, t.ticket_no, t.coord_no), 'not numbered yet'),
          'old_label', _ticket_label('coordinator', null, t.prev_coord_no));
      end if;
      -- or a coordinator number retired by an approved transfer: show who holds the seat now
      select tk.* into t from ticket_transfers x join tickets tk on tk.id = x.ticket_id
       where x.from_coord_no = p_ticket_no and x.status = 'done';
      if found then
        return jsonb_build_object('result', 'cancelled', 'name', t.name,
          'label', coalesce(_ticket_label(t.kind, t.ticket_no, t.coord_no), 'not numbered yet'),
          'old_label', _ticket_label('coordinator', null, p_ticket_no));
      end if;
    end if;
  else
    select * into t from tickets where ticket_no = p_ticket_no for update;
    if not found and p_ticket_no is not null then
      -- a number retired by an approved transfer: the QR is cancelled, show who holds the seat now
      select tk.* into t from ticket_transfers x join tickets tk on tk.id = x.ticket_id
       where x.from_ticket_no = p_ticket_no and x.status = 'done';
      if found then
        return jsonb_build_object('result', 'cancelled', 'name', t.name,
          'label', coalesce(_ticket_label(t.kind, t.ticket_no, t.coord_no), 'not numbered yet'),
          'old_label', _ticket_label('guest', p_ticket_no, null));
      end if;
    end if;
  end if;
  if not found then return jsonb_build_object('result', 'invalid'); end if;

  if p_id is null and t.kind = 'coordinator' and not p_coord then
    return jsonb_build_object('result', 'cancelled', 'name', t.name,
      'label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
      'old_label', _ticket_label('guest', t.ticket_no, null));
  end if;
  if p_secret is not null and t.secret <> p_secret then
    return jsonb_build_object('result', 'invalid'); end if;

  select * into b from bookings where id = t.booking_id for update;

  if b.status = 'pending' and p_approve then
    update bookings set status = 'paid', reviewed_by = auth.uid(), reviewed_at = now(), reviewed_via = 'gate' where id = b.id;
    perform _assign_numbers(b.id);
    select * into t from tickets where id = t.id;
    b.status := 'paid';
  end if;

  info := jsonb_build_object('id', t.id, 'ticket_no', t.ticket_no, 'kind', t.kind,
    'label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
    'name', t.name, 'food', t.food,
    'booking_code', b.booking_code, 'people_count', b.people_count,
    'amount_expected', b.amount_expected, 'screenshot_path', b.screenshot_path);

  if b.status = 'rejected' then return info || jsonb_build_object('result', 'rejected'); end if;
  if b.status = 'pending' then return info || jsonb_build_object('result', 'pending'); end if;
  if t.checked_in_at is not null then
    select name into who from staff where user_id = t.checked_in_by;
    return info || jsonb_build_object('result', 'already_scanned', 'checked_in_at', t.checked_in_at, 'checked_in_by', who);
  end if;
  update tickets set checked_in_at = now(), checked_in_by = auth.uid() where id = t.id;
  return info || jsonb_build_object('result', 'ok');
end $function$;

-- 7. WHO MAY CALL WHAT ---------------------------------------------------------------------------
-- (Supabase hands out run rights to anon/authenticated by default, so they are taken away explicitly here.)
revoke all on function _parse_ticket(text) from public, anon, authenticated;
revoke all on function _seller_kind(tickets) from public, anon, authenticated;
revoke all on function _clean_comment(text) from public, anon, authenticated;
revoke all on function _clean_payout(text) from public, anon, authenticated;
revoke all on function _norm_code(text) from public, anon, authenticated;
revoke all on function _transfer_block_reason(tickets, bookings) from public, anon, authenticated;
revoke all on function _seller_ticket(text, text) from public, anon, authenticated;

revoke all on function list_board() from public, anon, authenticated;
revoke all on function post_listing(text, text, integer, text, text, text, boolean) from public, anon, authenticated;
revoke all on function edit_listing(text, text, integer, text) from public, anon, authenticated;
revoke all on function manage_ticket(text, text) from public, anon, authenticated;
revoke all on function close_listing(text, text, boolean) from public, anon, authenticated;
revoke all on function express_interest(uuid, text, text, text) from public, anon, authenticated;
revoke all on function check_request(uuid, text) from public, anon, authenticated;
revoke all on function start_transfer(text, text, integer, text, text, uuid, boolean) from public, anon, authenticated;
revoke all on function withdraw_transfer(text, text) from public, anon, authenticated;
revoke all on function apply_receive(text, text, text, text, text, text, text) from public, anon, authenticated;
revoke all on function submit_transfer_payment(text, text, text) from public, anon, authenticated;
revoke all on function lookup_transfer(text) from public, anon, authenticated;
revoke all on function admin_confirm_amount(uuid, integer) from public, anon, authenticated;
revoke all on function admin_mark_payment_received(uuid, boolean) from public, anon, authenticated;
revoke all on function admin_mark_seller_paid(uuid, text) from public, anon, authenticated;
revoke all on function admin_mark_refunded(uuid, text) from public, anon, authenticated;
revoke all on function admin_clear_comment(uuid) from public, anon, authenticated;
revoke all on function approve_transfer(uuid, boolean) from public, anon, authenticated;
revoke all on function admit_ticket(integer, text, boolean, boolean, uuid) from public, anon, authenticated;
-- the part 1 helpers and admin functions that were not touched here: close the same gap
revoke all on function get_transfer_status() from public, anon, authenticated;
revoke all on function decline_transfer(uuid, text) from public, anon, authenticated;
revoke all on function admin_remove_listing(uuid) from public, anon, authenticated;
revoke all on function admin_set_transfer_settings(boolean, integer) from public, anon, authenticated;

-- website visitors (no login)
grant execute on function get_transfer_status() to anon, authenticated;
grant execute on function list_board() to anon, authenticated;
grant execute on function post_listing(text, text, integer, text, text, text, boolean) to anon, authenticated;
grant execute on function edit_listing(text, text, integer, text) to anon, authenticated;
grant execute on function manage_ticket(text, text) to anon, authenticated;
grant execute on function close_listing(text, text, boolean) to anon, authenticated;
grant execute on function express_interest(uuid, text, text, text) to anon, authenticated;
grant execute on function check_request(uuid, text) to anon, authenticated;
grant execute on function start_transfer(text, text, integer, text, text, uuid, boolean) to anon, authenticated;
grant execute on function withdraw_transfer(text, text) to anon, authenticated;
grant execute on function apply_receive(text, text, text, text, text, text, text) to anon, authenticated;
grant execute on function submit_transfer_payment(text, text, text) to anon, authenticated;
grant execute on function lookup_transfer(text) to anon, authenticated;
-- signed-in staff only (admins are checked again inside each function)
grant execute on function admin_set_transfer_settings(boolean, integer) to authenticated;
grant execute on function admin_confirm_amount(uuid, integer) to authenticated;
grant execute on function admin_mark_payment_received(uuid, boolean) to authenticated;
grant execute on function admin_mark_seller_paid(uuid, text) to authenticated;
grant execute on function admin_mark_refunded(uuid, text) to authenticated;
grant execute on function admin_clear_comment(uuid) to authenticated;
grant execute on function approve_transfer(uuid, boolean) to authenticated;
grant execute on function decline_transfer(uuid, text) to authenticated;
grant execute on function admin_remove_listing(uuid) to authenticated;
grant execute on function admit_ticket(integer, text, boolean, boolean, uuid) to authenticated;


-- =====================================================================
-- PART 3a  (16 Oct 2026): payment details in Settings, settings log, staff role default
-- Run it in the Supabase SQL editor, after the two transfer scripts. Safe to run more than once.
--
-- What this does
--   1. The UPI ID, the payee name and the organiser WhatsApp number now live in the database
--      (Settings), so they can be changed from the Admin page and are no longer written in the
--      public page's code. THIS FILE CONTAINS NO REAL VALUES (the repo is public): after running
--      it, open Admin > Settings > Payment details and type them in.
--   2. A log of every change to the settings and to the staff list (who, when, old and new value).
--      Changes typed straight into the Supabase SQL editor are logged too, as "database".
--   3. The staff.role column no longer has a default, so a login added without a role is refused
--      instead of silently becoming an admin.
--   4. (record only) The event date and venue setup, which was run earlier but never saved here.
--
-- Error messages the Admin page translates:
--   INVALID_UPI, INVALID_PAYEE, INVALID_WHATSAPP, NOT_ALLOWED
-- =====================================================================

-- 1. PAYMENT DETAILS ---------------------------------------------------------------------------------
alter table settings add column if not exists upi_id text;
alter table settings add column if not exists payee_name text;
alter table settings add column if not exists whatsapp_number text;

alter table settings drop constraint if exists settings_upi_id_check;
alter table settings add constraint settings_upi_id_check
  check (upi_id is null or upi_id ~ '^[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9]{1,31}$');
alter table settings drop constraint if exists settings_payee_name_check;
alter table settings add constraint settings_payee_name_check
  check (payee_name is null or char_length(payee_name) between 1 and 60);
alter table settings drop constraint if exists settings_whatsapp_check;
alter table settings add constraint settings_whatsapp_check
  check (whatsapp_number is null or whatsapp_number ~ '^[0-9]{11,15}$');   -- country code + number, digits only

-- What the public pages read. Empty (null) until an admin has typed the values in.
create or replace function get_payment_info() returns jsonb
language sql stable security definer set search_path to 'public' as $$
  select jsonb_build_object('upi_id', upi_id, 'payee_name', payee_name, 'whatsapp', whatsapp_number)
  from settings where id = 1 $$;

-- Admins only. All three values are required each time.
create or replace function admin_set_payment_info(p_upi text, p_payee text, p_whatsapp text) returns void
language plpgsql security definer set search_path to 'public' as $$
declare u text; n text; w text;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  u := btrim(coalesce(p_upi, ''));
  n := btrim(regexp_replace(coalesce(p_payee, ''), '\s+', ' ', 'g'));
  w := regexp_replace(coalesce(p_whatsapp, ''), '[^0-9]', '', 'g');       -- allows "+91 62352 02168"
  if u !~ '^[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9]{1,31}$' then raise exception 'INVALID_UPI'; end if;
  if char_length(n) not between 1 and 60 then raise exception 'INVALID_PAYEE'; end if;
  if w !~ '^[0-9]{11,15}$' then raise exception 'INVALID_WHATSAPP'; end if;
  update settings set upi_id = u, payee_name = n, whatsapp_number = w where id = 1;
end $$;

-- 2. THE LOG -------------------------------------------------------------------------------------------
create table if not exists settings_log (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  changed_by uuid,                    -- empty = made directly in the database (SQL editor)
  who text not null,
  area text not null check (area in ('settings', 'staff')),
  field text not null,
  old_value text,
  new_value text);
create index if not exists settings_log_at_idx on settings_log (at desc);

alter table settings_log enable row level security;
revoke all on table settings_log from anon, authenticated;
grant select on table settings_log to authenticated;
drop policy if exists admin_read_log on settings_log;
create policy admin_read_log on settings_log for select to authenticated using (is_admin());

-- Settings: one line per changed value. The automatic counters and the "closed at" stamp are not logged.
create or replace function _log_settings_change() returns trigger
language plpgsql security definer set search_path to 'public' as $$
declare k text; o jsonb := to_jsonb(old); n jsonb := to_jsonb(new); uid uuid := auth.uid(); nm text;
begin
  select name into nm from staff where user_id = uid;
  for k in select jsonb_object_keys(n) loop
    if k in ('next_ticket', 'next_coord', 'closed_at') then continue; end if;
    if o -> k is distinct from n -> k then
      insert into settings_log (changed_by, who, area, field, old_value, new_value)
      values (uid, coalesce(nm, case when uid is null then 'database' else 'unknown login' end),
              'settings', k, o ->> k, n ->> k);
    end if;
  end loop;
  return null;
end $$;
drop trigger if exists settings_log_trg on settings;
create trigger settings_log_trg after update on settings for each row execute function _log_settings_change();

-- Staff list: added, removed, role or name changed.
create or replace function _log_staff_change() returns trigger
language plpgsql security definer set search_path to 'public' as $$
declare uid uuid := auth.uid(); nm text; w text;
begin
  select name into nm from staff where user_id = uid;
  w := coalesce(nm, case when uid is null then 'database' else 'unknown login' end);
  if tg_op = 'INSERT' then
    insert into settings_log (changed_by, who, area, field, old_value, new_value)
    values (uid, w, 'staff', 'added', null, new.name || ' (' || new.role || ')');
  elsif tg_op = 'DELETE' then
    insert into settings_log (changed_by, who, area, field, old_value, new_value)
    values (uid, w, 'staff', 'removed', old.name || ' (' || old.role || ')', null);
  else
    if old.role is distinct from new.role then
      insert into settings_log (changed_by, who, area, field, old_value, new_value)
      values (uid, w, 'staff', 'role of ' || new.name, old.role, new.role);
    end if;
    if old.name is distinct from new.name then
      insert into settings_log (changed_by, who, area, field, old_value, new_value)
      values (uid, w, 'staff', 'name', old.name, new.name);
    end if;
  end if;
  return null;
end $$;
drop trigger if exists staff_log_trg on staff;
create trigger staff_log_trg after insert or update or delete on staff for each row execute function _log_staff_change();

-- For the banner on the Admin Overview: the latest change to the payment details in the last 7 days.
create or replace function admin_payment_alert() returns jsonb
language plpgsql stable security definer set search_path to 'public' as $$
declare r record;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select at, changed_by, who into r from settings_log
   where area = 'settings' and field in ('upi_id', 'payee_name', 'whatsapp_number') and at > now() - interval '7 days'
   order by at desc, id desc limit 1;
  if not found then return null; end if;
  return jsonb_build_object('at', r.at, 'who', r.who,
    'by_me', r.changed_by is not null and r.changed_by = auth.uid(),
    'fields', (select coalesce(jsonb_agg(l.field order by l.field), '[]'::jsonb) from settings_log l
               where l.area = 'settings' and l.at = r.at and l.field in ('upi_id', 'payee_name', 'whatsapp_number')));
end $$;

-- 3. STAFF ROLE: NO DEFAULT ---------------------------------------------------------------------------------
-- (the role must now always be written: 'admin' or 'gate'. Existing rows are not changed.)
alter table staff alter column role drop default;

-- 4. WHO MAY CALL WHAT -----------------------------------------------------------------------------------
revoke all on function get_payment_info() from public, anon, authenticated;
revoke all on function admin_set_payment_info(text, text, text) from public, anon, authenticated;
revoke all on function admin_payment_alert() from public, anon, authenticated;
revoke all on function _log_settings_change() from public, anon, authenticated;
revoke all on function _log_staff_change() from public, anon, authenticated;
grant execute on function get_payment_info() to anon, authenticated;                 -- website visitors
grant execute on function admin_set_payment_info(text, text, text) to authenticated; -- admins (checked inside)
grant execute on function admin_payment_alert() to authenticated;                    -- admins (checked inside)

-- 5. RECORD ONLY: event date and venue (already live since 15 Oct; kept here so the history is complete) --------
alter table settings add column if not exists event_at timestamptz not null default '2026-11-22 08:30:00+00';
alter table settings add column if not exists venue text not null default 'Savoury Business Hotel, Madiwala';
alter table settings drop constraint if exists settings_venue_len;
alter table settings add constraint settings_venue_len check (char_length(btrim(venue)) between 1 and 120);

create or replace function get_event_info() returns jsonb
language sql stable security definer set search_path to 'public' as $$
  select jsonb_build_object('event_at', event_at, 'venue', venue) from settings where id = 1 $$;

create or replace function admin_set_event(p_event_at timestamptz, p_venue text) returns void
language plpgsql security definer set search_path to 'public' as $$
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_event_at is null or coalesce(btrim(p_venue), '') = '' then raise exception 'INVALID_EVENT'; end if;
  update settings set event_at = p_event_at, venue = btrim(p_venue) where id = 1;
end $$;

revoke all on function get_event_info() from public, anon, authenticated;
revoke all on function admin_set_event(timestamptz, text) from public, anon, authenticated;
grant execute on function get_event_info() to anon, authenticated;
grant execute on function admin_set_event(timestamptz, text) to authenticated;


-- ============================================================================
-- 25 Oct 2026 (evening): RELEASE 2 APPLIED TO THE REAL DATABASE by the owner in the Supabase SQL editor.
-- The exact text that was run is kept in these files (each is a concatenation of the numbered pieces in this folder):
--   1. sql/rollout_A_part1_APPLIED.sql   = r2_01_prep.sql + r2_02_lookup.sql
--      (r2_02c_close_old_transfer_doors.sql had been run earlier)
--   2. new pages published
--   3. sql/rollout_A_part2_APPLIED.sql   = r2_02b_cutover + r2_03_private_transfer + r2_04_public_via_code
--                                          + r2_05_cleanup_and_ip + r2_06_transfer_settings
--   4. rehearsal with test data, then sql/r2_07_cleanup_test_data.sql (removes all bookings/tickets/transfers, restarts numbering)
-- Verified afterwards by the Database Snapshot workflow compared with the scratch copy (identical, see HANDOVER_NEXT_SESSION.md).
-- ============================================================================


-- 28 Oct 2026: r2_12 gate undo (run in Supabase by the owner on 28 Oct; full file: sql/r2_12_gate_undo.sql)
-- Gate staff can undo an admission for 2 minutes; admins any time; after 2 minutes a non-admin gets UNDO_EXPIRED.
create or replace function public.gate_undo_checkin(p_id uuid) returns void
language plpgsql security definer set search_path to 'public' as $function$
declare n int;
begin
  if not is_staff() then raise exception 'NOT_ALLOWED'; end if;
  if is_admin() then
    update tickets set checked_in_at = null, checked_in_by = null where id = p_id and checked_in_at is not null;
  else
    update tickets set checked_in_at = null, checked_in_by = null
     where id = p_id and checked_in_at is not null and checked_in_at > now() - interval '2 minutes';
  end if;
  get diagnostics n = row_count;
  if n = 0 then raise exception 'UNDO_EXPIRED'; end if;
end $function$;

revoke execute on function public.gate_undo_checkin(uuid) from public, anon;
grant execute on function public.gate_undo_checkin(uuid) to authenticated;

-- ============================================================================
-- 30 Oct 2026: r2_13 game messages (run in Supabase by the owner on 30 Oct; full file: sql/r2_13_game_messages.sql)
-- ============================================================================
-- ============================================================================
-- Release 2, piece 13: "Messages" for the game activity (a message on a ticket, shown only while an admin switch is ON)
-- Written 30 Oct 2026. Run AFTER r2_12. Tested on the scratch database before use. Safe to run twice. Changes no existing data.
--
--   game_messages  : the messages an admin writes (a short NAME for the admin, the BODY the ticket holder sees, up to 200 characters).
--   ticket_messages: which ticket has which message (at most one per ticket). Many tickets can share one message (a "team").
--   settings.show_messages: the switch. OFF (the default): the database sends NO message to anyone. ON: a ticket holder who
--                    enters the right Booking ID + phone gets their message with their ticket (paid bookings, tickets not transferred away).
--   Both tables are readable and changeable by ADMINS ONLY. Gate staff, visitors and signed-in non-staff see nothing.
--   A ticket created by a transfer inherits the message of the ticket it came from.
--   Every change by an admin is written to the Settings log (area "messages").
-- ============================================================================
alter table public.settings add column if not exists show_messages boolean not null default false;

alter table public.settings_log drop constraint if exists settings_log_area_check;
alter table public.settings_log add constraint settings_log_area_check check (area = any (array['settings','staff','transfer','messages']));

create table if not exists public.game_messages (
  id         uuid primary key default gen_random_uuid(),
  name       text not null check (char_length(name) between 1 and 60),
  body       text not null check (char_length(body) between 1 and 200),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists game_messages_name_uq on public.game_messages (lower(name));

create table if not exists public.ticket_messages (
  ticket_id   uuid primary key references public.tickets(id) on delete cascade,
  message_id  uuid not null references public.game_messages(id) on delete cascade,
  assigned_at timestamptz not null default now()
);
create index if not exists ticket_messages_message_idx on public.ticket_messages (message_id);

alter table public.game_messages enable row level security;
alter table public.ticket_messages enable row level security;
drop policy if exists admin_read_game_messages on public.game_messages;
create policy admin_read_game_messages on public.game_messages for select to authenticated using (is_admin());
drop policy if exists admin_read_ticket_messages on public.ticket_messages;
create policy admin_read_ticket_messages on public.ticket_messages for select to authenticated using (is_admin());
revoke all on public.game_messages, public.ticket_messages from public, anon, authenticated;
grant select on public.game_messages, public.ticket_messages to authenticated;

-- the switch (the Settings log records the change by itself, like the other switches)
create or replace function public.admin_set_show_messages(p_show boolean) returns void
 language plpgsql security definer set search_path to 'public' as $function$
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_show is null then raise exception 'INVALID_VALUE'; end if;
  update settings set show_messages = p_show where id = 1;
end $function$;
revoke all on function public.admin_set_show_messages(boolean) from public, anon, authenticated, service_role;
grant execute on function public.admin_set_show_messages(boolean) to authenticated;

create or replace function public._mlog(p_field text, p_old text, p_new text) returns void
 language sql security definer set search_path to 'public' as $function$
  insert into settings_log (changed_by, who, area, field, old_value, new_value)
  values (auth.uid(), _actor(), 'messages', p_field, left(p_old, 300), left(p_new, 300)) $function$;
revoke all on function public._mlog(text, text, text) from public, anon, authenticated, service_role;

-- create (p_id null) or edit a message. Returns its id.
create or replace function public.admin_save_message(p_id uuid, p_name text, p_body text) returns uuid
 language plpgsql security definer set search_path to 'public' as $function$
declare n text := trim(coalesce(p_name, '')); b text := trim(coalesce(p_body, '')); o game_messages; nid uuid;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if char_length(n) not between 1 and 60 or n ~ '[[:cntrl:]]' then raise exception 'INVALID_NAME'; end if;
  if char_length(b) not between 1 and 200 or b ~ '[[:cntrl:]]' then raise exception 'INVALID_MESSAGE'; end if;
  if p_id is null then
    if exists (select 1 from game_messages where lower(name) = lower(n)) then raise exception 'NAME_TAKEN'; end if;
    insert into game_messages (name, body) values (n, b) returning id into nid;
    perform _mlog('message added', null, n || ': ' || b);
    return nid;
  end if;
  select * into o from game_messages where id = p_id for update;
  if not found then raise exception 'NOT_FOUND'; end if;
  if exists (select 1 from game_messages where lower(name) = lower(n) and id <> p_id) then raise exception 'NAME_TAKEN'; end if;
  update game_messages set name = n, body = b, updated_at = now() where id = p_id;
  if o.name is distinct from n or o.body is distinct from b then
    perform _mlog('message edited', o.name || ': ' || o.body, n || ': ' || b);
  end if;
  return p_id;
end $function$;
revoke all on function public.admin_save_message(uuid, text, text) from public, anon, authenticated, service_role;
grant execute on function public.admin_save_message(uuid, text, text) to authenticated;

-- delete a message (everyone holding it loses it). Returns how many tickets lost it.
create or replace function public.admin_delete_message(p_id uuid) returns integer
 language plpgsql security definer set search_path to 'public' as $function$
declare o game_messages; n int;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  select * into o from game_messages where id = p_id for update;
  if not found then raise exception 'NOT_FOUND'; end if;
  select count(*) into n from ticket_messages where message_id = p_id;
  delete from game_messages where id = p_id;
  perform _mlog('message deleted', o.name || ': ' || o.body, n || ' ticket(s) lost it');
  return n;
end $function$;
revoke all on function public.admin_delete_message(uuid) from public, anon, authenticated, service_role;
grant execute on function public.admin_delete_message(uuid) to authenticated;

-- give messages: p_pairs = [{"t": "<ticket id>", "m": "<message id>"}, ...]. All or nothing. Replaces a ticket's earlier message.
-- Tickets that were transferred away are refused. The same ticket twice in one list is refused. Returns how many tickets were set.
create or replace function public.admin_assign_messages(p_pairs jsonb) returns integer
 language plpgsql security definer set search_path to 'public' as $function$
declare n int; cnt int; summ text; ids_t uuid[]; ids_m uuid[];
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_pairs is null or jsonb_typeof(p_pairs) <> 'array' then raise exception 'INVALID_PAIRS'; end if;
  cnt := jsonb_array_length(p_pairs);
  if cnt = 0 then return 0; end if;
  if cnt > 1000 then raise exception 'TOO_MANY'; end if;
  begin
    select array_agg((e->>'t')::uuid), array_agg((e->>'m')::uuid) into ids_t, ids_m from jsonb_array_elements(p_pairs) e;
  exception when others then raise exception 'INVALID_PAIRS';
  end;
  if array_position(ids_t, null) is not null or array_position(ids_m, null) is not null then raise exception 'INVALID_PAIRS'; end if;
  if (select count(distinct x) from unnest(ids_t) x) <> cnt then raise exception 'DUPLICATE_TICKET'; end if;
  if (select count(*) from tickets where id = any (ids_t) and transferred_out_at is null) <> cnt then raise exception 'TICKET_NOT_FOUND'; end if;
  if (select count(*) from game_messages where id = any (ids_m)) <> (select count(distinct x) from unnest(ids_m) x) then raise exception 'MESSAGE_NOT_FOUND'; end if;
  insert into ticket_messages (ticket_id, message_id)
    select t, m from unnest(ids_t, ids_m) as u(t, m)
    on conflict (ticket_id) do update set message_id = excluded.message_id, assigned_at = now();
  get diagnostics n = row_count;
  select string_agg(g.name || ' x' || c.k, ', ' order by g.name) into summ
    from (select m, count(*) k from unnest(ids_m) m group by m) c join game_messages g on g.id = c.m;
  perform _mlog('messages given', null, n || ' ticket(s): ' || summ);
  return n;
end $function$;
revoke all on function public.admin_assign_messages(jsonb) from public, anon, authenticated, service_role;
grant execute on function public.admin_assign_messages(jsonb) to authenticated;

-- take messages away. No arguments = from everyone. p_message = only that message's holders. p_tickets = only those tickets. Both = both rules.
create or replace function public.admin_clear_messages(p_message uuid default null, p_tickets uuid[] default null) returns integer
 language plpgsql security definer set search_path to 'public' as $function$
declare n int; nm text;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_message is not null then
    select name into nm from game_messages where id = p_message;
    if not found then raise exception 'NOT_FOUND'; end if;
  end if;
  delete from ticket_messages
   where (p_message is null or message_id = p_message)
     and (p_tickets is null or ticket_id = any (p_tickets));
  get diagnostics n = row_count;
  perform _mlog('messages cleared', null, n || ' ticket(s)' || case when nm is not null then ' of ' || nm else '' end
                || case when p_tickets is not null then ' (chosen tickets)' else '' end);
  return n;
end $function$;
revoke all on function public.admin_clear_messages(uuid, uuid[]) from public, anon, authenticated, service_role;
grant execute on function public.admin_clear_messages(uuid, uuid[]) to authenticated;

-- a ticket made by a transfer keeps the message of the ticket it came from
create or replace function public._inherit_ticket_message() returns trigger
 language plpgsql security definer set search_path to 'public' as $function$
begin
  if new.transferred_from is not null then
    insert into ticket_messages (ticket_id, message_id)
      select new.id, message_id from ticket_messages where ticket_id = new.transferred_from
      on conflict (ticket_id) do nothing;
  end if;
  return null;
end $function$;
revoke all on function public._inherit_ticket_message() from public, anon, authenticated, service_role;
drop trigger if exists tickets_inherit_message_trg on public.tickets;
create trigger tickets_inherit_message_trg after insert on public.tickets for each row execute function public._inherit_ticket_message();

-- the ticket lookup (Booking ID + phone). Same as before, plus "game_message": filled ONLY while the switch is ON,
-- only for a paid booking, and only for a ticket that was not transferred away. Otherwise null.
create or replace FUNCTION public.lookup_tickets(p_code text, p_phone text)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare b bookings%rowtype; c text; ph text; tk jsonb; bu transfer_buyers%rowtype; x transfers%rowtype; st text; gm_on boolean;
begin
  c  := replace(replace(replace(upper(coalesce(p_code, '')), 'O', '0'), ' ', ''), '-', '');
  ph := replace(replace(coalesce(p_phone, ''), ' ', ''), '-', '');
  if length(c) <> 8 or ph !~ '^[0-9]{10}$' then return jsonb_build_object('found', false); end if;
  select show_messages into gm_on from settings where id = 1;
  select * into b from bookings where booking_code = c;
  if not found then return jsonb_build_object('found', false); end if;
  if b.kind = 'transfer' then
    select * into bu from transfer_buyers where booking_id = b.id and phone = ph;
    if not found then return jsonb_build_object('found', false); end if;
    select * into x from transfers where id = bu.transfer_id;
  end if;
  select jsonb_agg(jsonb_build_object(
           'ticket_no', t.ticket_no, 'kind', t.kind, 'coord_no', t.coord_no,
           'label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
           'secret', case when b.status = 'paid' and t.transferred_out_at is null then t.secret else null end,
           'game_message', case when gm_on and b.status = 'paid' and t.transferred_out_at is null
                                then (select m.body from ticket_messages tm join game_messages m on m.id = tm.message_id where tm.ticket_id = t.id) else null end,
           'transferred', (t.transferred_out_at is not null),
           'name', t.name, 'location', t.location, 'attendance', t.attendance, 'food', t.food)
         order by t.reg_seq)
    into tk from tickets t where t.booking_id = b.id and t.phone = ph;
  if tk is null then
    if b.kind = 'transfer' then
      st := case when x.kind = 'public' and x.returned_at is not null then 'returned'
                 when x.kind = 'public' and x.return_due then 'return_due'
                 when b.status = 'rejected' then 'rejected'
                 when x.kind = 'public' and x.payment_verified_at is not null then 'payment_verified'
                 when x.kind = 'public' and x.payment_submitted_at is not null then 'payment_submitted'
                 when x.kind = 'public' and x.payment_requested_at is not null then 'payment_due'
                 else 'pending' end;
      return jsonb_build_object('found', true, 'kind', 'transfer', 'booking_code', b.booking_code, 'status', b.status,
                                'people_count', 1, 'amount_expected', 0, 'name', bu.name, 'tickets', '[]'::jsonb,
                                'transfer', jsonb_build_object('type', x.kind, 'state', st,
                                   'amount_due', case when st = 'payment_due' then x.amount_due end));
    end if;
    return jsonb_build_object('found', false);
  end if;
  return jsonb_build_object('found', true, 'kind', b.kind, 'booking_code', b.booking_code, 'status', b.status,
                            'people_count', b.people_count, 'amount_expected', b.amount_expected, 'tickets', tk);
end $function$;
revoke all on function public.lookup_tickets(text, text) from public, anon, authenticated, service_role;
grant execute on function public.lookup_tickets(text, text) to anon, authenticated;

-- ============================================================================
-- 31 Oct 2026: r2_14 pick random people / message line with heading (run in Supabase by the owner on 31 Oct; full file: sql/r2_14_game_prizes.sql)
-- ============================================================================
-- ============================================================================
-- Release 2, piece 14: "Random picks" (a line on a ticket given to randomly picked people, separate from the team message), shown under the same admin switch
-- Written 30 Oct 2026. Run AFTER r2_13. Tested on the scratch database before use. Safe to run twice. Changes no existing data.
--
--   ticket_prizes: at most one such line per ticket (up to 200 characters) with its own heading (up to 60 characters, default "You are a winner!"),
--   so it can be a prize, a clue, a task or anything else. Readable and changeable by ADMINS ONLY. (The table keeps its first name "ticket_prizes".)
--   It is separate from ticket_messages (the team message): a ticket can have a team message, a prize, both, or neither.
--   The same switch settings.show_messages decides whether anyone sees them: OFF = the database sends neither; ON = a ticket holder
--   who enters the right Booking ID + phone gets "game_message", and "game_prize" with "game_prize_heading" (paid booking, ticket not transferred away).
--   Who wins is drawn in the admin page with the browser's secure random generator (shown as a preview first); the database only stores the result.
--   A ticket made by a transfer inherits the prize as well as the team message. Changes are written to the Settings log (area "messages").
-- ============================================================================
create table if not exists public.ticket_prizes (
  ticket_id  uuid primary key references public.tickets(id) on delete cascade,
  body       text not null check (char_length(body) between 1 and 200),
  heading    text not null default 'You are a winner!' check (char_length(heading) between 1 and 60),
  created_at timestamptz not null default now()
);
alter table public.ticket_prizes enable row level security;
drop policy if exists admin_read_ticket_prizes on public.ticket_prizes;
create policy admin_read_ticket_prizes on public.ticket_prizes for select to authenticated using (is_admin());
revoke all on public.ticket_prizes from public, anon, authenticated;
grant select on public.ticket_prizes to authenticated;

-- give one line (with a heading) to a list of tickets (the picked people). All or nothing. Replaces an earlier line on those tickets. Returns how many.
-- A blank or missing heading means the default "You are a winner!".
create or replace function public.admin_set_prizes(p_tickets uuid[], p_body text, p_heading text default null) returns integer
 language plpgsql security definer set search_path to 'public' as $function$
declare b text := trim(coalesce(p_body, '')); h text := coalesce(nullif(trim(coalesce(p_heading, '')), ''), 'You are a winner!'); cnt int; n int;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if char_length(b) not between 1 and 200 or b ~ '[[:cntrl:]]' then raise exception 'INVALID_MESSAGE'; end if;
  if char_length(h) > 60 or h ~ '[[:cntrl:]]' then raise exception 'INVALID_NAME'; end if;
  if p_tickets is null then raise exception 'INVALID_PAIRS'; end if;
  cnt := coalesce(cardinality(p_tickets), 0);
  if cnt = 0 then return 0; end if;
  if cnt > 1000 then raise exception 'TOO_MANY'; end if;
  if array_position(p_tickets, null) is not null then raise exception 'INVALID_PAIRS'; end if;
  if (select count(distinct x) from unnest(p_tickets) x) <> cnt then raise exception 'DUPLICATE_TICKET'; end if;
  if (select count(*) from tickets where id = any (p_tickets) and transferred_out_at is null) <> cnt then raise exception 'TICKET_NOT_FOUND'; end if;
  insert into ticket_prizes (ticket_id, body, heading) select x, b, h from unnest(p_tickets) x
    on conflict (ticket_id) do update set body = excluded.body, heading = excluded.heading, created_at = now();
  get diagnostics n = row_count;
  perform _mlog('prizes given', null, n || ' ticket(s): ' || h || ' / ' || b);
  return n;
end $function$;
revoke all on function public.admin_set_prizes(uuid[], text, text) from public, anon, authenticated, service_role;
grant execute on function public.admin_set_prizes(uuid[], text, text) to authenticated;

-- take prizes away. No argument = from everyone; a list = only those tickets. Returns how many.
create or replace function public.admin_clear_prizes(p_tickets uuid[] default null) returns integer
 language plpgsql security definer set search_path to 'public' as $function$
declare n int;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  delete from ticket_prizes where p_tickets is null or ticket_id = any (p_tickets);
  get diagnostics n = row_count;
  perform _mlog('prizes cleared', null, n || ' ticket(s)' || case when p_tickets is not null then ' (chosen tickets)' else '' end);
  return n;
end $function$;
revoke all on function public.admin_clear_prizes(uuid[]) from public, anon, authenticated, service_role;
grant execute on function public.admin_clear_prizes(uuid[]) to authenticated;

-- a ticket made by a transfer keeps the team message AND the picked-people line (with its heading) of the ticket it came from
create or replace function public._inherit_ticket_message() returns trigger
 language plpgsql security definer set search_path to 'public' as $function$
begin
  if new.transferred_from is not null then
    insert into ticket_messages (ticket_id, message_id)
      select new.id, message_id from ticket_messages where ticket_id = new.transferred_from
      on conflict (ticket_id) do nothing;
    insert into ticket_prizes (ticket_id, body, heading)
      select new.id, body, heading from ticket_prizes where ticket_id = new.transferred_from
      on conflict (ticket_id) do nothing;
  end if;
  return null;
end $function$;
revoke all on function public._inherit_ticket_message() from public, anon, authenticated, service_role;

-- the ticket lookup: as in r2_13, plus "game_prize" and "game_prize_heading" (same rules as "game_message": switch ON, paid booking, ticket not transferred away; otherwise null)
create or replace FUNCTION public.lookup_tickets(p_code text, p_phone text)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare b bookings%rowtype; c text; ph text; tk jsonb; bu transfer_buyers%rowtype; x transfers%rowtype; st text; gm_on boolean;
begin
  c  := replace(replace(replace(upper(coalesce(p_code, '')), 'O', '0'), ' ', ''), '-', '');
  ph := replace(replace(coalesce(p_phone, ''), ' ', ''), '-', '');
  if length(c) <> 8 or ph !~ '^[0-9]{10}$' then return jsonb_build_object('found', false); end if;
  select show_messages into gm_on from settings where id = 1;
  select * into b from bookings where booking_code = c;
  if not found then return jsonb_build_object('found', false); end if;
  if b.kind = 'transfer' then
    select * into bu from transfer_buyers where booking_id = b.id and phone = ph;
    if not found then return jsonb_build_object('found', false); end if;
    select * into x from transfers where id = bu.transfer_id;
  end if;
  select jsonb_agg(jsonb_build_object(
           'ticket_no', t.ticket_no, 'kind', t.kind, 'coord_no', t.coord_no,
           'label', _ticket_label(t.kind, t.ticket_no, t.coord_no),
           'secret', case when b.status = 'paid' and t.transferred_out_at is null then t.secret else null end,
           'game_message', case when gm_on and b.status = 'paid' and t.transferred_out_at is null
                                then (select m.body from ticket_messages tm join game_messages m on m.id = tm.message_id where tm.ticket_id = t.id) else null end,
           'game_prize', case when gm_on and b.status = 'paid' and t.transferred_out_at is null
                              then (select z.body from ticket_prizes z where z.ticket_id = t.id) else null end,
           'game_prize_heading', case when gm_on and b.status = 'paid' and t.transferred_out_at is null
                              then (select z.heading from ticket_prizes z where z.ticket_id = t.id) else null end,
           'transferred', (t.transferred_out_at is not null),
           'name', t.name, 'location', t.location, 'attendance', t.attendance, 'food', t.food)
         order by t.reg_seq)
    into tk from tickets t where t.booking_id = b.id and t.phone = ph;
  if tk is null then
    if b.kind = 'transfer' then
      st := case when x.kind = 'public' and x.returned_at is not null then 'returned'
                 when x.kind = 'public' and x.return_due then 'return_due'
                 when b.status = 'rejected' then 'rejected'
                 when x.kind = 'public' and x.payment_verified_at is not null then 'payment_verified'
                 when x.kind = 'public' and x.payment_submitted_at is not null then 'payment_submitted'
                 when x.kind = 'public' and x.payment_requested_at is not null then 'payment_due'
                 else 'pending' end;
      return jsonb_build_object('found', true, 'kind', 'transfer', 'booking_code', b.booking_code, 'status', b.status,
                                'people_count', 1, 'amount_expected', 0, 'name', bu.name, 'tickets', '[]'::jsonb,
                                'transfer', jsonb_build_object('type', x.kind, 'state', st,
                                   'amount_due', case when st = 'payment_due' then x.amount_due end));
    end if;
    return jsonb_build_object('found', false);
  end if;
  return jsonb_build_object('found', true, 'kind', b.kind, 'booking_code', b.booking_code, 'status', b.status,
                            'people_count', b.people_count, 'amount_expected', b.amount_expected, 'tickets', tk);
end $function$;

revoke all on function public.lookup_tickets(text, text) from public, anon, authenticated, service_role;
grant execute on function public.lookup_tickets(text, text) to anon, authenticated;


-- ============================================================================
-- Release 2, piece 15: the "What best describes you?" question on the registration form
-- Written 2 Nov 2026. Tested on the scratch database before use. REQUIRES r2_01 to r2_14. Safe to run twice.
--
-- What changes for the registration form (submit_booking):
--   * NEW answer per person: occ = 'Article Assistant' | 'Employee' | 'Student' | 'Others'
--     and occ_detail = what they typed (exam, firm / company, or anything for Others), 1 to 100 characters.
--     Both are required. They are saved on the ticket in two new columns: occupation, occupation_detail.
--   * The email is no longer asked on the registration form and is NOT read or stored any more
--     (even if an old page still sends one). Emails already collected stay where they are (ticket_emails, admin-only).
--   * "Will you be attending?" is no longer asked. tickets.attendance may now be empty (NULL).
--     Old rows keep the answer they already have.
--   * Everything else in submit_booking is exactly as it was (closed / pause / grace, group size, cap, name, phone,
--     location, food, screenshot check, booking code, IP flag).
--
-- NOT changed on purpose: the TRANSFER form and transfer_submit still ask for email (when the Email switch is on)
-- and attendance. The Email switch in Admin > Settings keeps working for the transfer form.
--
-- ORDER: run this SQL first, then publish the new index.html (the new page sends occ / occ_detail, which the OLD
-- submit_booking would ignore while still demanding an email and attendance, so the old function would refuse every booking).
-- ============================================================================

alter table public.tickets add column if not exists occupation text;
alter table public.tickets add column if not exists occupation_detail text;

alter table public.tickets drop constraint if exists tickets_occupation_check;
alter table public.tickets add constraint tickets_occupation_check
  check (occupation is null or occupation in ('Article Assistant', 'Employee', 'Student', 'Others'));

alter table public.tickets drop constraint if exists tickets_occupation_detail_check;
alter table public.tickets add constraint tickets_occupation_detail_check
  check (occupation_detail is null or char_length(occupation_detail) between 1 and 100);

-- the two columns go together: both filled (new bookings) or both empty (old bookings, transfers)
alter table public.tickets drop constraint if exists tickets_occupation_pair_check;
alter table public.tickets add constraint tickets_occupation_pair_check
  check ((occupation is null) = (occupation_detail is null));

-- attendance is no longer asked: allow it to be empty (its allowed-values rule stays and ignores NULL)
alter table public.tickets alter column attendance drop not null;

create or replace function public.submit_booking(p_submission_id uuid, p_people jsonb, p_screenshot_path text)
 returns jsonb
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare s settings%rowtype; b bookings%rowtype; n int; used int; r record; code text; pi jsonb;
begin
  select * into b from bookings where submission_id = p_submission_id;
  if found then return _booking_json(b.id); end if;

  select * into s from settings where id = 1 for update;
  select * into b from bookings where submission_id = p_submission_id;
  if found then return _booking_json(b.id); end if;

  pi := _pause_info(s);
  if (not s.is_open or (pi->>'in_pause')::boolean or now() > s.deadline) then
    -- closed right now: only people who were already filling the form get the grace minutes (+30 s for upload time)
    if _grace_until(s, p_submission_id, interval '30 seconds') is null then
      raise exception 'REGISTRATION_CLOSED';
    end if;
  end if;
  if p_people is null or jsonb_typeof(p_people) <> 'array' then raise exception 'INVALID_DATA'; end if;
  n := jsonb_array_length(p_people);
  if n < 1 or n > s.max_group then raise exception 'INVALID_GROUP_SIZE'; end if;

  select count(*) into used from tickets t join bookings bk on bk.id = t.booking_id where bk.status <> 'rejected' and t.transferred_out_at is null;
  if used + n > s.cap then raise exception 'NOT_ENOUGH_SPOTS'; end if;

  for r in select value from jsonb_array_elements(p_people) loop
    if length(trim(coalesce(r.value->>'name',''))) not between 1 and 80 then raise exception 'INVALID_NAME'; end if;
    if coalesce(r.value->>'phone','') !~ '^[0-9]{10}$' then raise exception 'INVALID_PHONE'; end if;
    if coalesce(r.value->>'occ','') not in ('Article Assistant','Employee','Student','Others') then raise exception 'INVALID_OCCUPATION'; end if;
    if length(trim(coalesce(r.value->>'occ_detail',''))) not between 1 and 100 then raise exception 'INVALID_OCCUPATION_DETAIL'; end if;
    if coalesce(r.value->>'loc','') not in ('In Bengaluru','Outside Bengaluru') then raise exception 'INVALID_LOCATION'; end if;
    if coalesce(r.value->>'food','') not in ('Veg','Non-veg') then raise exception 'INVALID_FOOD'; end if;
  end loop;

  if p_screenshot_path is null or p_screenshot_path not like p_submission_id::text || '%'
     or not exists (select 1 from storage.objects where bucket_id = 'payment-proofs' and name = p_screenshot_path)
  then raise exception 'SCREENSHOT_MISSING'; end if;

  loop
    code := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8));
    exit when not exists (select 1 from bookings where booking_code = code);
  end loop;

  insert into bookings (booking_code, submission_id, people_count, amount_expected, screenshot_path)
  values (code, p_submission_id, n, n * s.price_per_head, p_screenshot_path) returning * into b;
  insert into booking_ips (booking_id, ip, raw) values (b.id, _client_ip(), _client_ip_raw());   -- flag only, never blocks

  -- one ticket per person, in the order listed (no email, no attendance any more)
  for r in select value, ord from jsonb_array_elements(p_people) with ordinality as e(value, ord) order by ord loop
    insert into tickets (secret, booking_id, name, phone, location, food, occupation, occupation_detail)
    values (substr(replace(gen_random_uuid()::text, '-', ''), 1, 12), b.id,
            trim(r.value->>'name'), r.value->>'phone', r.value->>'loc', r.value->>'food',
            r.value->>'occ', trim(r.value->>'occ_detail'));
  end loop;

  return _booking_json(b.id);
end $function$;

revoke all on function public.submit_booking(uuid, jsonb, text) from public, anon, authenticated, service_role;
grant execute on function public.submit_booking(uuid, jsonb, text) to anon, authenticated;



-- ============================================================================
-- Release 2, piece 15: a fifth answer to "What best describes you?": "Industrial Trainee"
-- Written 3 Nov 2026. Run BEFORE publishing the new index.html (the page may be one step behind the database, never ahead).
-- Safe to run twice. Changes no existing data. Only the list of allowed answers grows:
--   before: Article Assistant | Employee | Student | Others
--   after:  Article Assistant | Industrial Trainee | Employee | Student | Others
-- "Others" is stored exactly as before; the public page now SHOWS it as "Entrepreneur & Others" (a label only).
--
-- Two places check the answer, so two changes:
--   1. the rule on the tickets table (tickets_occupation_check);
--   2. submit_booking, the function the Register page calls. It is changed by reading the LIVE function, replacing only its list of allowed
--      answers and saving it again, so nothing else in it can be lost or become out of date. It stops with a message if it does not find
--      exactly one list to change. Who may run the function (anon, authenticated) is not touched.
-- ============================================================================

-- 1. the rule on the table
alter table tickets drop constraint if exists tickets_occupation_check;
alter table tickets add constraint tickets_occupation_check
  check (occupation is null or occupation in ('Article Assistant', 'Industrial Trainee', 'Employee', 'Student', 'Others'));

-- 2. the Register function
do $$
declare
  d   text := pg_get_functiondef('public.submit_booking(uuid,jsonb,text)'::regprocedure);
  old text := $q$not in ('Article Assistant','Employee','Student','Others')$q$;
  new text := $q$not in ('Article Assistant','Industrial Trainee','Employee','Student','Others')$q$;
begin
  if position(new in d) > 0 then
    raise notice 'submit_booking already accepts Industrial Trainee: nothing to change.';
    return;
  end if;
  if (length(d) - length(replace(d, old, ''))) / length(old) <> 1 then
    raise exception 'Expected to find the list of answers exactly once in submit_booking. Nothing was changed. Please send this message to Claude.';
  end if;
  execute replace(d, old, new);
  raise notice 'submit_booking now accepts Industrial Trainee.';
end $$;

-- 3. check (run these two lines; both should say true)
select (select pg_get_constraintdef(oid) like '%Industrial Trainee%' from pg_constraint where conname = 'tickets_occupation_check') as table_rule_ok,
       (pg_get_functiondef('public.submit_booking(uuid,jsonb,text)'::regprocedure) like '%Industrial Trainee%') as function_ok;



-- r2_15: three switches become permanent (Nov 2026, admin redesign step 2).
--   About link    -> always on          (settings.show_about = true)
--   Email box     -> never asked        (settings.ask_email  = false)
--   Feedback form -> always on          (settings.ask_feedback = true)
-- The public page and the staff page no longer read these switches; this only makes the database agree,
-- so transfer_submit stops demanding an email and submit_feedback stops refusing.
-- RUN THIS IN THE SUPABASE SQL EDITOR *BEFORE* MERGING THE PAGES. Safe to run twice.
-- NOT tested on a scratch database (it is one UPDATE on three existing columns).
update public.settings set show_about = true, ask_email = false, ask_feedback = true where id = 1;
