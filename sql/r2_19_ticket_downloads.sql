-- r2_19_ticket_downloads.sql
-- Record who OPENED their ticket page and who pressed "Download JPG" / "Download PDF", and when.
--
-- What this does (plainly):
--   Adds ONE new admin-only table, ticket_activity, and TWO new functions. It changes NO existing
--   function, table or setting (lookup_tickets stays exactly as it is).
--   1. Table ticket_activity: one row per event = which ticket, what happened ('view', 'jpg', 'pdf'
--      or 'all-pdf') and when. It holds NO phone numbers. Only an admin can read it. Nobody can write
--      to it directly; rows only arrive through the function below.
--   2. log_ticket_activity(code, phone, action, tickets): the ticket page calls it. It checks the
--      Booking ID plus phone the same way lookup_tickets does, accepts only tickets of a PAID booking,
--      and ignores tickets that were transferred away. Wrong input writes nothing and shows nothing.
--      A "view" is recorded at most once per ticket per 10 minutes.
--   3. admin_ticket_activity(): admin only. Gives the staff page one summary per ticket
--      (views, last view, downloads, last download, last format).
--
-- Honest limit: this records that the button was PRESSED. It cannot prove the file was saved or
-- opened, and it cannot see screenshots. Nothing is recorded for the time before this file was run.
--
-- Safety:
--   * First it checks the live lookup_tickets and the columns it relies on. If anything differs it
--     STOPS and changes NOTHING.
--   * Safe to run twice (create if not exists / create or replace; same result).
--   * One transaction: all or nothing.
--
-- How to run: paste the whole file into the Supabase SQL editor and press Run.
-- Expect a NOTICE "r2_19: checks passed", then a result table at the bottom (see the end of the file).
-- RUN THIS *BEFORE* MERGING THE PAGES. (The pages still work if it has not been run yet.)

begin;

-- STEP 1: look before changing
do $do$
declare
  def text;
  f_code text := $a$replace(replace(replace(upper(coalesce(p_code, '')), 'O', '0'), ' ', ''), '-', '')$a$;
  f_ph   text := $a$ph !~ '^[0-9]{10}$'$a$;
  f_lbl  text := $a$_ticket_label(t.kind, t.ticket_no, t.coord_no)$a$;
  f_out  text := $a$t.transferred_out_at is null$a$;
  missing text;
begin
  if to_regprocedure('public.lookup_tickets(text,text)') is null
     or to_regprocedure('public._ticket_label(text,integer,integer)') is null
     or to_regprocedure('public.is_admin()') is null then
    raise exception 'r2_19 STOPPED: lookup_tickets, _ticket_label or is_admin is missing. Nothing was changed.';
  end if;
  def := pg_get_functiondef('public.lookup_tickets(text,text)'::regprocedure);
  if (length(def)-length(replace(def,f_code,'')))/length(f_code) <> 1
     or (length(def)-length(replace(def,f_ph,'')))/length(f_ph) <> 1
     or (length(def)-length(replace(def,f_lbl,'')))/length(f_lbl) <> 1
     or position(f_out in def) = 0 then
    raise exception 'r2_19 STOPPED: lookup_tickets does not look like the 9 Nov version. Nothing was changed. Send the current function text to be re-checked.';
  end if;
  select string_agg(x.need, ', ') into missing from (values
      ('tickets','id'),('tickets','booking_id'),('tickets','phone'),('tickets','kind'),('tickets','ticket_no'),
      ('tickets','coord_no'),('tickets','secret'),('tickets','reg_seq'),('tickets','transferred_out_at'),
      ('bookings','id'),('bookings','booking_code'),('bookings','status'),('bookings','kind'),
      ('transfer_buyers','booking_id'),('transfer_buyers','phone')) as x(tbl, need)
    where not exists (select 1 from information_schema.columns c
                      where c.table_schema='public' and c.table_name=x.tbl and c.column_name=x.need);
  if missing is not null then
    raise exception 'r2_19 STOPPED: columns not found: %. Nothing was changed.', missing;
  end if;
  if to_regclass('public.ticket_activity') is not null
     and (select count(*) from information_schema.columns
          where table_schema='public' and table_name='ticket_activity'
            and column_name in ('id','ticket_id','action','created_at')) <> 4 then
    raise exception 'r2_19 STOPPED: a table named ticket_activity already exists with other columns. Nothing was changed.';
  end if;
  raise notice 'r2_19: checks passed';
end
$do$;

-- STEP 2: the table (admin read only, no direct writes)
create table if not exists public.ticket_activity (
  id         bigint generated always as identity primary key,
  ticket_id  uuid not null references public.tickets(id) on delete cascade,
  action     text not null check (action in ('view','jpg','pdf','all-pdf')),
  created_at timestamptz not null default now()
);
create index if not exists ticket_activity_ticket_idx on public.ticket_activity (ticket_id, created_at desc);
alter table public.ticket_activity enable row level security;
revoke all on public.ticket_activity from public, anon, authenticated;
grant select on public.ticket_activity to authenticated;
drop policy if exists admin_read_ticket_activity on public.ticket_activity;
create policy admin_read_ticket_activity on public.ticket_activity
  for select to authenticated using (is_admin());

-- STEP 3: the visitor function (writes only after the same checks as lookup_tickets)
create or replace function public.log_ticket_activity(p_code text, p_phone text, p_action text, p_tickets text[] default null)
 returns jsonb
 language plpgsql
 volatile security definer
 set search_path to 'public'
as $fn$
declare c text; ph text; b bookings%rowtype; t record; n integer := 0;
begin
  c  := replace(replace(replace(upper(coalesce(p_code, '')), 'O', '0'), ' ', ''), '-', '');
  ph := replace(replace(coalesce(p_phone, ''), ' ', ''), '-', '');
  if length(c) <> 8 or ph !~ '^[0-9]{10}$'
     or p_action is null or p_action not in ('view','jpg','pdf','all-pdf')
     or (p_tickets is not null and cardinality(p_tickets) > 10) then
    return jsonb_build_object('ok', true, 'logged', 0);
  end if;
  select * into b from bookings where booking_code = c;
  if not found or b.status <> 'paid' then return jsonb_build_object('ok', true, 'logged', 0); end if;
  if b.kind = 'transfer' and not exists (select 1 from transfer_buyers x where x.booking_id = b.id and x.phone = ph) then
    return jsonb_build_object('ok', true, 'logged', 0);
  end if;
  for t in
    select k.id from tickets k
    where k.booking_id = b.id and k.phone = ph
      and k.transferred_out_at is null
      and (k.ticket_no is not null or k.coord_no is not null)
      and (p_tickets is null or _ticket_label(k.kind, k.ticket_no, k.coord_no) = any(p_tickets))
    order by k.reg_seq
  loop
    if p_action = 'view' and exists (select 1 from ticket_activity a
         where a.ticket_id = t.id and a.action = 'view' and a.created_at > now() - interval '10 minutes') then
      continue;
    end if;
    insert into ticket_activity (ticket_id, action) values (t.id, p_action);
    n := n + 1;
  end loop;
  return jsonb_build_object('ok', true, 'logged', n);
end $fn$;

-- STEP 4: the admin summary (one row per ticket that has any activity)
create or replace function public.admin_ticket_activity()
 returns jsonb
 language plpgsql
 stable security definer
 set search_path to 'public'
as $fn$
begin
  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object(
             'ticket_id', s.ticket_id, 'views', s.views, 'last_view', s.last_view,
             'downloads', s.downloads, 'last_download', s.last_download, 'last_format', s.last_format))
    from (select ticket_id,
                 count(*) filter (where action = 'view')                          as views,
                 max(created_at) filter (where action = 'view')                   as last_view,
                 count(*) filter (where action <> 'view')                         as downloads,
                 max(created_at) filter (where action <> 'view')                  as last_download,
                 (array_agg(action order by created_at desc, id desc) filter (where action <> 'view'))[1] as last_format
          from ticket_activity group by ticket_id) s), '[]'::jsonb);
end $fn$;

revoke all on function public.log_ticket_activity(text,text,text,text[]) from public;
revoke all on function public.admin_ticket_activity() from public;
grant execute on function public.log_ticket_activity(text,text,text,text[]) to anon, authenticated;
grant execute on function public.admin_ticket_activity() to authenticated;

commit;

-- Verification (run after the block above). Expect:
--   table_exists true, rls_on true, anon_can_write false, authenticated_can_write false,
--   log_function anon = true, admin_function anon = false and authenticated = true.
select
  to_regclass('public.ticket_activity') is not null                                              as table_exists,
  (select relrowsecurity from pg_class where oid = 'public.ticket_activity'::regclass)           as rls_on,
  has_table_privilege('anon','public.ticket_activity','insert,update,delete')                    as anon_can_write,
  has_table_privilege('authenticated','public.ticket_activity','insert,update,delete')           as authenticated_can_write,
  has_function_privilege('anon','public.log_ticket_activity(text,text,text,text[])','execute')   as log_function_anon,
  has_function_privilege('anon','public.admin_ticket_activity()','execute')                      as admin_function_anon,
  has_function_privilege('authenticated','public.admin_ticket_activity()','execute')             as admin_function_authenticated;
