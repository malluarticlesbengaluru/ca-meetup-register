-- r2_18_bulk_approve.sql
-- Approve several payments at once, after a preview of the ticket numbers.
--
-- What this does (plainly):
--   Adds TWO new admin-only functions. It changes NO existing function
--   (set_booking_status, _assign_numbers, admit_ticket and the r2_16 rule stay exactly as they are).
--   1. admin_preview_approval(ids)  READ ONLY. Tells the page which ticket numbers each
--      booking WOULD get, in the order given. Changes nothing.
--   2. admin_approve_bookings(ids, expected_next)  Approves the bookings in one go, in the
--      order given, using the same steps as set_booking_status (status paid, reviewed_by,
--      reviewed_at, reviewed_via = 'admin', then _assign_numbers). A booking that is no longer
--      pending is skipped and reported. If the next free ticket number is no longer the one the
--      preview was based on, it stops with NUMBERS_CHANGED and approves NOTHING.
--   Gate accounts are refused (NOT_ALLOWED) by both.
--
-- Safety:
--   * First it reads the live set_booking_status and checks the lines it copies appear EXACTLY
--     ONCE. If anything differs, it STOPS and changes NOTHING.
--   * Safe to run twice (create or replace; same result).
--   * All-or-nothing: one transaction.
--
-- How to run: paste the whole file into the Supabase SQL editor and press Run.
-- Expect a NOTICE "r2_18: checks passed", then a result table at the bottom
-- (both functions: anon = false, authenticated = true; the gate/admin split is the check inside).

-- STEP 1: look before changing
do $do$
declare
  def text := pg_get_functiondef('public.set_booking_status(uuid,text)'::regprocedure);
  l_upd text := $a$update bookings set status = p_status, reviewed_by = auth.uid(), reviewed_at = now(), reviewed_via = 'admin'$a$;
  l_num text := $a$if p_status = 'paid' then perform _assign_numbers(p_booking);$a$;
  l_lck text := $a$perform 1 from settings where id = 1 for update;$a$;
  l_trf text := $a$kind = 'transfer') then raise exception 'USE_TRANSFER_TOOLS'$a$;
begin
  if (length(def)-length(replace(def,l_upd,'')))/length(l_upd) <> 1
     or (length(def)-length(replace(def,l_num,'')))/length(l_num) <> 1
     or (length(def)-length(replace(def,l_lck,'')))/length(l_lck) <> 1
     or (length(def)-length(replace(def,l_trf,'')))/length(l_trf) <> 1 then
    raise exception 'r2_18 STOPPED: set_booking_status does not look like the 5 Nov version. Nothing was changed. Send the current function text to be re-checked.';
  end if;
  if not exists (select 1 from pg_proc where proname = '_assign_numbers' and pronamespace = 'public'::regnamespace)
     or not exists (select 1 from pg_proc where proname = 'is_admin' and pronamespace = 'public'::regnamespace) then
    raise exception 'r2_18 STOPPED: _assign_numbers or is_admin was not found. Nothing was changed.';
  end if;
  raise notice 'r2_18: checks passed.';
end $do$;

-- STEP 2: read-only preview
create or replace function public.admin_preview_approval(p_ids uuid[])
returns jsonb
language plpgsql
stable
security definer
set search_path to 'public'
as $fn$
declare
  nxt int; r record; b bookings%rowtype; t record;
  rows jsonb := '[]'::jsonb; ppl jsonb; n_ok int := 0; n_people int := 0; n_amt bigint := 0;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_ids is null or cardinality(p_ids) = 0 then return jsonb_build_object('rows','[]'::jsonb,'next_ticket',null,'bookings',0,'people',0,'amount',0); end if;
  if cardinality(p_ids) > 200 then raise exception 'TOO_MANY'; end if;
  select next_ticket into nxt from settings where id = 1;
  -- same order as given, each booking once
  for r in select id from (select u.id, min(u.ord) o from unnest(p_ids) with ordinality u(id, ord) group by u.id) q order by o loop
    select * into b from bookings where id = r.id;
    if not found then
      rows := rows || jsonb_build_object('booking_id', r.id, 'ok', false, 'reason', 'NOT_FOUND');
    elsif b.kind = 'transfer' then
      rows := rows || jsonb_build_object('booking_id', b.id, 'booking_code', b.booking_code, 'ok', false, 'reason', 'TRANSFER');
    elsif b.status <> 'pending' then
      rows := rows || jsonb_build_object('booking_id', b.id, 'booking_code', b.booking_code, 'ok', false, 'reason', 'NOT_PENDING', 'status', b.status);
    else
      ppl := '[]'::jsonb;
      for t in select id, name, kind, ticket_no from tickets where booking_id = b.id order by reg_seq loop
        if t.kind = 'guest' and t.ticket_no is null then
          ppl := ppl || jsonb_build_object('name', t.name, 'ticket_no', nxt); nxt := nxt + 1;   -- same rule as _assign_numbers
        else
          ppl := ppl || jsonb_build_object('name', t.name, 'ticket_no', t.ticket_no, 'kind', t.kind);
        end if;
      end loop;
      rows := rows || jsonb_build_object('booking_id', b.id, 'booking_code', b.booking_code, 'ok', true,
                'people_count', b.people_count, 'amount', b.amount_expected, 'people', ppl);
      n_ok := n_ok + 1; n_people := n_people + b.people_count; n_amt := n_amt + b.amount_expected;
    end if;
  end loop;
  return jsonb_build_object('rows', rows,
           'next_ticket', (select next_ticket from settings where id = 1),   -- the number the preview started from
           'bookings', n_ok, 'people', n_people, 'amount', n_amt);
end $fn$;

-- STEP 3: approve (one transaction)
create or replace function public.admin_approve_bookings(p_ids uuid[], p_expected_next integer default null)
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $fn$
declare
  s_next int; r record; b bookings%rowtype; t record;
  ok_rows jsonb := '[]'::jsonb; skip_rows jsonb := '[]'::jsonb; ppl jsonb;
  n_ok int := 0; n_people int := 0; n_amt bigint := 0;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  if p_ids is null or cardinality(p_ids) = 0 then raise exception 'NO_BOOKINGS'; end if;
  if cardinality(p_ids) > 200 then raise exception 'TOO_MANY'; end if;
  -- same lock as set_booking_status: nobody else hands out numbers while this runs
  perform 1 from settings where id = 1 for update;
  select next_ticket into s_next from settings where id = 1;
  if p_expected_next is not null and p_expected_next <> s_next then
    raise exception 'NUMBERS_CHANGED' using detail = 'The next free ticket number is now ' || s_next || ', not ' || p_expected_next || '. Nothing was approved.';
  end if;
  for r in select id from (select u.id, min(u.ord) o from unnest(p_ids) with ordinality u(id, ord) group by u.id) q order by o loop
    select * into b from bookings where id = r.id for update;
    if not found then
      skip_rows := skip_rows || jsonb_build_object('booking_id', r.id, 'reason', 'NOT_FOUND');
    elsif b.kind = 'transfer' then
      skip_rows := skip_rows || jsonb_build_object('booking_id', b.id, 'booking_code', b.booking_code, 'reason', 'TRANSFER');
    elsif b.status <> 'pending' then
      skip_rows := skip_rows || jsonb_build_object('booking_id', b.id, 'booking_code', b.booking_code, 'reason', 'NOT_PENDING', 'status', b.status);
    else
      -- exactly what set_booking_status does for 'paid'
      update bookings set status = 'paid', reviewed_by = auth.uid(), reviewed_at = now(), reviewed_via = 'admin'
      where id = b.id;
      perform _assign_numbers(b.id);
      ppl := '[]'::jsonb;
      for t in select name, ticket_no from tickets where booking_id = b.id order by reg_seq loop
        ppl := ppl || jsonb_build_object('name', t.name, 'ticket_no', t.ticket_no);
      end loop;
      ok_rows := ok_rows || jsonb_build_object('booking_id', b.id, 'booking_code', b.booking_code, 'people_count', b.people_count, 'amount', b.amount_expected, 'people', ppl);
      n_ok := n_ok + 1; n_people := n_people + b.people_count; n_amt := n_amt + b.amount_expected;
    end if;
  end loop;
  return jsonb_build_object('approved', ok_rows, 'skipped', skip_rows, 'bookings', n_ok, 'people', n_people, 'amount', n_amt);
end $fn$;

-- STEP 4: who may call them (the is_admin() check inside is what stops gate accounts)
revoke all on function public.admin_preview_approval(uuid[]) from public, anon, authenticated;
revoke all on function public.admin_approve_bookings(uuid[], integer) from public, anon, authenticated;
grant execute on function public.admin_preview_approval(uuid[]) to authenticated;
grant execute on function public.admin_approve_bookings(uuid[], integer) to authenticated;

-- STEP 5: verification (expect 2 rows: anon_can_run = false, signed_in_can_run = true, has_admin_check = true)
select p.proname,
       has_function_privilege('anon', p.oid, 'execute') as anon_can_run,
       has_function_privilege('authenticated', p.oid, 'execute') as signed_in_can_run,
       position('is_admin()' in pg_get_functiondef(p.oid)) > 0 as has_admin_check
from pg_proc p
where p.pronamespace = 'public'::regnamespace and p.proname in ('admin_preview_approval','admin_approve_bookings')
order by 1;
