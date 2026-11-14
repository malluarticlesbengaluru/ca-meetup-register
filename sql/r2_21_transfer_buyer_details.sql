-- ============================================================================
-- Release 2, piece 21: a person taking over a ticket (transfer buyer) is now asked the SAME two extra questions as registration
-- Written 14 Nov 2026. Run AFTER r2_19. Tested on the scratch database before use. Safe to run twice. Changes no existing data.
--
--   "What best describes you?" (Article Assistant / Industrial Trainee / Employee / Student / Others) and the follow-up answer
--   (firm, company, exam or what they do, 1 to 100 characters). Both REQUIRED for new transfer applications, exactly as in registration.
--   1. transfer_buyers gets two columns: occupation, occupation_detail (empty for applications made BEFORE this change, which still work).
--   2. transfer_submit refuses an application without them (INVALID_OCCUPATION / INVALID_OCCUPATION_DETAIL) and saves them.
--   3. admin_transfer_approve copies them onto the new ticket, so the People list, role chart and exports include transferred guests.
--      An old application with no answers still gets approved; its ticket simply has no role, as before.
-- ============================================================================

alter table public.transfer_buyers add column if not exists occupation text;
alter table public.transfer_buyers add column if not exists occupation_detail text;
alter table public.transfer_buyers drop constraint if exists transfer_buyers_occupation_check;
alter table public.transfer_buyers add constraint transfer_buyers_occupation_check
  check (occupation is null or occupation = any (array['Article Assistant','Industrial Trainee','Employee','Student','Others']));
alter table public.transfer_buyers drop constraint if exists transfer_buyers_occupation_detail_check;
alter table public.transfer_buyers add constraint transfer_buyers_occupation_detail_check
  check (occupation_detail is null or (char_length(occupation_detail) between 1 and 100));
alter table public.transfer_buyers drop constraint if exists transfer_buyers_occupation_pair_check;
alter table public.transfer_buyers add constraint transfer_buyers_occupation_pair_check check ((occupation is null) = (occupation_detail is null));

CREATE OR REPLACE FUNCTION public.transfer_submit(p_code text, p_submission_id uuid, p_buyer jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare s settings%rowtype; c text; x transfers%rowtype; t tickets%rowtype; sb bookings%rowtype; bu transfer_buyers%rowtype;
        bk bookings%rowtype; bcode text; v_food text; v_email text; v_name text; v_occ text; v_occd text;
begin
  if p_submission_id is null then return jsonb_build_object('ok', false, 'error', 'INVALID_DATA'); end if;
  -- the same submission again: give back the same answer (a retry after a bad connection)
  select * into bu from transfer_buyers where submission_id = p_submission_id;
  if found then
    select * into bk from bookings where id = bu.booking_id;
    return jsonb_build_object('ok', true, 'booking_code', bk.booking_code, 'status', bk.status, 'replay', true);
  end if;

  select * into s from settings where id = 1;
  if not s.transfers_open then return jsonb_build_object('ok', false, 'error', 'TRANSFERS_CLOSED'); end if;
  if s.transfer_cutoff_at is not null and now() > s.transfer_cutoff_at then
    return jsonb_build_object('ok', false, 'error', 'CUTOFF_PASSED'); end if;
  c := upper(regexp_replace(coalesce(p_code, ''), '[\s-]', '', 'g'));
  if c !~ '^[A-Z2-9]{6}$' then return jsonb_build_object('ok', false, 'error', 'INVALID_CODE'); end if;

  if p_buyer is null or jsonb_typeof(p_buyer) <> 'object' then return jsonb_build_object('ok', false, 'error', 'INVALID_DATA'); end if;
  v_name := trim(coalesce(p_buyer->>'name', ''));
  v_email := case when s.ask_email then lower(trim(coalesce(p_buyer->>'email', ''))) else null end;
  if length(v_name) not between 1 and 80 then return jsonb_build_object('ok', false, 'error', 'INVALID_NAME'); end if;
  if coalesce(p_buyer->>'phone', '') !~ '^[0-9]{10}$' then return jsonb_build_object('ok', false, 'error', 'INVALID_PHONE'); end if;
  v_occ := coalesce(p_buyer->>'occ', ''); v_occd := trim(coalesce(p_buyer->>'occ_detail', ''));   -- same two questions and rules as the registration form
  if v_occ not in ('Article Assistant', 'Industrial Trainee', 'Employee', 'Student', 'Others') then return jsonb_build_object('ok', false, 'error', 'INVALID_OCCUPATION'); end if;
  if length(v_occd) not between 1 and 100 then return jsonb_build_object('ok', false, 'error', 'INVALID_OCCUPATION_DETAIL'); end if;
  if s.ask_email and (length(v_email) not between 5 and 120 or v_email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$') then return jsonb_build_object('ok', false, 'error', 'INVALID_EMAIL'); end if;
  if coalesce(p_buyer->>'loc', '') not in ('In Bengaluru', 'Outside Bengaluru') then return jsonb_build_object('ok', false, 'error', 'INVALID_LOCATION'); end if;
  if coalesce(p_buyer->>'att', '') not in ('Surely', 'Most probably') then return jsonb_build_object('ok', false, 'error', 'INVALID_ATTENDANCE'); end if;
  if not s.transfer_food_locked and coalesce(p_buyer->>'food', '') not in ('Veg', 'Non-veg') then return jsonb_build_object('ok', false, 'error', 'INVALID_FOOD'); end if;
  if coalesce(p_buyer->>'consent', '') <> 'true' then return jsonb_build_object('ok', false, 'error', 'INVALID_CONSENT'); end if;

  -- first valid submission wins
  select * into x from transfers where code = c and status = 'code_active' and code_expires_at > now() for update;
  if not found then return jsonb_build_object('ok', false, 'error', 'INVALID_CODE'); end if;
  select * into t from tickets where id = x.ticket_id for update;
  select * into sb from bookings where id = t.booking_id;
  if t.transferred_out_at is not null or t.checked_in_at is not null or sb.status <> 'paid' then
    return jsonb_build_object('ok', false, 'error', 'NOT_AVAILABLE'); end if;
  v_food := case when s.transfer_food_locked then t.food else p_buyer->>'food' end;

  begin
    loop
      bcode := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8));
      exit when not exists (select 1 from bookings where booking_code = bcode);
    end loop;
    insert into bookings (booking_code, submission_id, people_count, amount_expected, screenshot_path, kind)
    values (bcode, p_submission_id, 1, 0, null, 'transfer') returning * into bk;
    insert into transfer_buyers (transfer_id, submission_id, booking_id, name, phone, email, location, attendance, food, consent_at, occupation, occupation_detail)
    values (x.id, p_submission_id, bk.id, v_name, p_buyer->>'phone', v_email, p_buyer->>'loc', p_buyer->>'att', v_food, now(), v_occ, v_occd);
  exception when unique_violation then
    return jsonb_build_object('ok', false, 'error', 'TRY_AGAIN');
  end;
  update transfers set status = 'pending_admin', updated_at = now() where id = x.id;
  perform _tlog('private transfer: buyer submitted', 'code_active', _ticket_label(t.kind, t.ticket_no, t.coord_no) || ' (' || left(x.id::text, 8) || ')');
  return jsonb_build_object('ok', true, 'mode', x.kind, 'booking_code', bk.booking_code, 'status', 'pending',
                            'seller_name', t.name, 'food', v_food);
end $function$;

CREATE OR REPLACE FUNCTION public.admin_transfer_approve(p_transfer uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare x transfers%rowtype; t tickets%rowtype; sb bookings%rowtype; bu transfer_buyers%rowtype; bk bookings%rowtype; nt tickets%rowtype; old_lbl text;
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  perform 1 from settings where id = 1 for update;                       -- same lock order as set_booking_status
  select * into x from transfers where id = p_transfer for update;
  if not found then raise exception 'INVALID_TRANSFER'; end if;
  if x.status <> 'pending_admin' then raise exception 'NOT_PENDING'; end if;
  if x.seller_call_confirmed_at is null then raise exception 'CALL_NOT_CONFIRMED'; end if;
  if x.kind = 'public' and x.payment_verified_at is null then raise exception 'PAYMENT_NOT_VERIFIED'; end if;
  select * into t from tickets where id = x.ticket_id for update;
  select * into sb from bookings where id = t.booking_id for update;
  if t.transferred_out_at is not null then raise exception 'SELLER_ALREADY_TRANSFERRED'; end if;
  if t.checked_in_at is not null then raise exception 'SELLER_CHECKED_IN'; end if;
  if sb.status <> 'paid' or (t.ticket_no is null and t.coord_no is null) then raise exception 'SELLER_TICKET_INVALID'; end if;
  select * into bu from transfer_buyers where transfer_id = x.id and status = 'active' for update;
  if not found then raise exception 'NO_BUYER'; end if;
  select * into bk from bookings where id = bu.booking_id for update;
  if bk.kind <> 'transfer' or bk.status <> 'pending' then raise exception 'BUYER_BOOKING_INVALID'; end if;
  old_lbl := _ticket_label(t.kind, t.ticket_no, t.coord_no);
  insert into tickets (secret, booking_id, name, phone, location, attendance, food, kind, transferred_from, occupation, occupation_detail)
  values (substr(replace(gen_random_uuid()::text, '-', ''), 1, 12), bk.id, bu.name, bu.phone,
          bu.location, bu.attendance, bu.food, 'guest', t.id, bu.occupation, bu.occupation_detail)
  returning * into nt;
  if bu.email is not null then insert into ticket_emails (ticket_id, email) values (nt.id, bu.email); end if;   -- email stays in the admin-only table
  update tickets set transferred_out_at = now() where id = t.id;
  update bookings set status = 'paid', reviewed_by = auth.uid(), reviewed_at = now(), reviewed_via = 'admin' where id = bk.id;
  perform _assign_numbers(bk.id);
  select * into nt from tickets where id = nt.id;
  update transfers set status = 'done', decided_at = now(), decided_by = auth.uid(), result_ticket_id = nt.id, updated_at = now() where id = x.id;
  update transfer_buyers set status = 'done' where id = bu.id;
  perform _tlog(x.kind || ' transfer: APPROVED', old_lbl, _ticket_label(nt.kind, nt.ticket_no, nt.coord_no) || ' (' || left(x.id::text, 8) || ')');
  return jsonb_build_object('new_label', _ticket_label(nt.kind, nt.ticket_no, nt.coord_no),
                            'old_label', old_lbl, 'booking_code', bk.booking_code);
end $function$;

revoke all on function public.transfer_submit(text, uuid, jsonb) from public, anon, authenticated, service_role;
grant execute on function public.transfer_submit(text, uuid, jsonb) to anon, authenticated;
revoke all on function public.admin_transfer_approve(uuid) from public, anon, authenticated, service_role;
grant execute on function public.admin_transfer_approve(uuid) to authenticated;
