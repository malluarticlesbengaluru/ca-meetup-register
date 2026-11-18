-- ============================================================================
-- ONE-TIME CLEAN-UP before the program: removes ALL photo and video records from the database.
-- NOT part of the normal setup. Run it ONCE, in the Supabase SQL Editor, after you have switched to the new Storj accounts.
-- It deletes: the list of photos, the list of videos (with their small preview pictures), all space gifts and all QR codes.
-- It keeps: tickets, bookings, staff, all settings and limits, and the settings log (the admin history).
-- It does NOT touch Storj. Old files stay in the old Storj accounts until you delete those buckets or the trials end.
-- Cannot be undone. The last lines show the counts; all should be 0.
-- ============================================================================
begin;
delete from public.space_codes;
delete from public.space_transfers;
delete from public.videos;
delete from public.photos;
commit;
select (select count(*) from public.photos) as photos_left, (select count(*) from public.videos) as videos_left,
       (select count(*) from public.space_transfers) as gifts_left, (select count(*) from public.space_codes) as codes_left;
