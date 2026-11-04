-- r2_15: three switches become permanent (Nov 2026, admin redesign step 2).
--   About link    -> always on          (settings.show_about = true)
--   Email box     -> never asked        (settings.ask_email  = false)
--   Feedback form -> always on          (settings.ask_feedback = true)
-- The public page and the staff page no longer read these switches; this only makes the database agree,
-- so transfer_submit stops demanding an email and submit_feedback stops refusing.
-- RUN THIS IN THE SUPABASE SQL EDITOR *BEFORE* MERGING THE PAGES. Safe to run twice.
-- NOT tested on a scratch database (it is one UPDATE on three existing columns).
update public.settings set show_about = true, ask_email = false, ask_feedback = true where id = 1;
