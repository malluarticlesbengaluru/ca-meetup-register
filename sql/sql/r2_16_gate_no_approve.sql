-- r2_16_gate_no_approve.sql
-- Only admins may approve a pending payment at the gate.
--
-- What this does (plainly):
--   admit_ticket(..., p_approve => true) marks a booking Paid and admits the person.
--   Today any staff account can do that. This adds ONE line at the top of the function:
--   if p_approve is true and the caller is not an admin, stop with the error ADMIN_ONLY.
--   Normal scanning (p_approve = false) is not touched. Gate accounts can still scan
--   and admit people whose payment is already confirmed.
--
-- Safety:
--   * It reads the live function text and checks that the three lines it depends on each
--     appear EXACTLY ONCE. If anything differs (for example the function was edited after
--     the 5 Nov snapshot), it stops with an error and changes NOTHING.
--   * Safe to run twice: if the guard is already there it says so and does nothing.
--   * The whole block is all-or-nothing. Owner, grants and SECURITY DEFINER stay as they are.
--
-- How to run: paste the whole file into the Supabase SQL editor and press Run.
-- Expect a NOTICE saying "applied" (first run) or "already applied" (second run),
-- then a result row from the verification query at the bottom.

do $do$
declare
  fn      regprocedure := 'public.admit_ticket(integer,text,boolean,boolean,uuid)'::regprocedure;
  def     text;
  new_def text;
  a_staff text := $a$if not is_staff() then raise exception 'NOT_ALLOWED'; end if;$a$;
  a_lock  text := $a$if p_approve then perform 1 from settings where id = 1 for update; end if;$a$;
  a_pay   text := $a$if b.status = 'pending' and p_approve then$a$;
  guard   text := $a$if p_approve and not is_admin() then raise exception 'ADMIN_ONLY'; end if;$a$;
begin
  def := pg_get_functiondef(fn);

  -- already done? then do nothing
  if position(guard in def) > 0 then
    raise notice 'r2_16: already applied, nothing changed.';
    return;
  end if;

  -- the helper we rely on must exist
  if not exists (select 1 from pg_proc where proname = 'is_admin' and pronamespace = 'public'::regnamespace) then
    raise exception 'r2_16 STOPPED: function is_admin() was not found. Nothing was changed.';
  end if;

  -- the function text must match what we expect, each key line exactly once
  if (length(def) - length(replace(def, a_staff, ''))) / length(a_staff) <> 1
     or (length(def) - length(replace(def, a_lock, ''))) / length(a_lock) <> 1
     or (length(def) - length(replace(def, a_pay, ''))) / length(a_pay) <> 1
     or position('SECURITY DEFINER' in def) = 0 then
    raise exception 'r2_16 STOPPED: admit_ticket does not look like the 5 Nov version. Nothing was changed. Send the current function text to be re-checked.';
  end if;

  -- put the guard just before the approve lock, i.e. right after the staff check
  new_def := replace(def, a_lock, guard || E'\n  ' || a_lock);

  if (length(new_def) - length(replace(new_def, guard, ''))) / length(guard) <> 1 then
    raise exception 'r2_16 STOPPED: patched text did not come out as expected. Nothing was changed.';
  end if;

  execute new_def;
  raise notice 'r2_16: applied. Gate accounts can no longer approve payments.';
end
$do$;

-- Verification (run after the block above; expect: true, true, and the same two grants as before)
select
  position($v$if p_approve and not is_admin() then raise exception 'ADMIN_ONLY'; end if;$v$
           in pg_get_functiondef(p.oid)) > 0 as gate_blocked_in_database,
  p.prosecdef                                  as security_definer,
  p.proacl::text                               as who_can_run
from pg_proc p
where p.oid = 'public.admit_ticket(integer,text,boolean,boolean,uuid)'::regprocedure;
