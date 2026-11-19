# Photos feature: setup, in order

Do these in this order. Each step says what you should see.

## BEFORE THE PROGRAM STARTS (Sun 22 Nov): tick these off
Admin > Settings. Do it the day before, not on the day.
- [ ] **Videos card: "Biggest video" = 100 MB.** (Slow Wi-Fi: a video that takes over 20 minutes to upload is deleted. 100 MB is safe, 150 MB is not.)
- [ ] Videos card: switch videos **On**. Set the pool (GB) below what Storj gives free (25 GB each account).
- [ ] Photos card: set the photo pools below the free 25 GB; "Who can upload (public)" = the mode you want (Present only is the default).
- [ ] Space sharing card: **On** (default).
- [ ] Storj: the 3 trial accounts last 30 days from creation. Check none ends before the event or before you have downloaded everything.
- [ ] The 5 real photographer logins work (try each once). Delete test photos and test videos.
- [ ] **Moving to new Storj accounts?** Order matters: (1) in Supabase > Edge Functions > Secrets put the new keys, bucket and endpoint in `STORJ_*`, `STORJ_PUB_*` and `STORJ_VID_*`; (2) add the same CORS setting to the new buckets; (3) test one photo and one video upload; (4) ONLY THEN run `sql/clear_photo_video_data.sql` in the SQL Editor (deletes all photo and video records, gifts and QR codes; keeps tickets, settings and limits; counts at the end must be 0). Old files stay in the old Storj accounts: download what you need first, then delete those buckets.
  - Details for whoever helps with the swap (a person or a new Claude session): the Edge Function `photos` (`supabase/functions/photos/index.ts`) reads ALL Storj settings from Supabase secrets when it starts; no page or file holds a key or bucket name, so no code change is needed. Secrets: `STORJ_ACCESS_KEY`, `STORJ_SECRET_KEY`, `STORJ_BUCKET` (photographers, keys under `camera/`), `STORJ_PUB_*` (attendee photos, `public/`), `STORJ_VID_*` (attendee videos, `video/`). `STORJ_ENDPOINT` is shared by all three and defaults to `https://gateway.storjshare.io`; leave it unset for new Storj accounts. One paid account for all three also works (same keys and bucket in all three sets; the folder names keep files apart), but this was never tried on live Storj. After saving secrets wait about a minute, then do the test uploads. Old rows point at old files, which is why the clear script is run last. The owner said the old photos and videos are not wanted. Not tested against real Storj accounts from the build environment: the first live test upload is the proof.
- [ ] Check in two test attendees as Present, upload a photo and a short video on a real phone (iPhone and Android), and give 10 MB to a friend by QR.
- [ ] Tell attendees: allow the camera for the QR, and keep the page open until the video shows "uploaded".
After the event: Settings > Make download links file (photos and videos), download everything, then switch uploads off.

## 0. What this adds
- **Photographers** sign in at `…/camera/` and upload into one shared space (default 10 GB).
- **Attendees** open their ticket → **Upload photos** (Booking ID + phone, already filled in) and upload into a public space (default 12 GB). Each person gets the **lower of** (public space ÷ people marked Present) **and** the cap (default 90 MB).
- Photos are stored at full quality in **Storj**. Supabase keeps only small records and tiny previews.
- Admin → **Settings → Photos**: on/off, all limits, usage, gallery, and a "download links" file.

## 1. Run the SQL (Supabase → SQL Editor)
Paste all of `sql/r2_20_photos.sql` and run. Expect "Success". It is safe to run twice.
Then paste the same text at the bottom of `sql/changes.sql` and run **Actions → Database Snapshot**.

## 2. Storj (use the MAIN Mallu Articles account, a few days before 22 Nov)
The 30-day trial starts when you sign up, and Storj deletes everything when it ends: **download all photos before then**.
1. Create a bucket (for example `ehsaas-photos`).
2. Access → create an **Advanced** access grant with **S3 credentials**: permissions Read, Write, List, Delete; limit it to that one bucket.
3. Keep the Access Key and Secret Key somewhere private. Never paste them into a chat or into GitHub.
4. Delete the test bucket, test files and test access key from the second account.

## 3. Deploy the Edge Function (Supabase dashboard)
1. Edge Functions → **Deploy a new function** → name it exactly `photos`.
2. Paste all of `supabase/functions/photos/index.ts`, deploy.
3. In the function's settings, turn **OFF "Verify JWT"** (it checks logins itself).
4. Edge Functions → **Secrets**, add: `STORJ_ACCESS_KEY`, `STORJ_SECRET_KEY`, `STORJ_BUCKET` (the bucket name).

## 4. Add the photographers
Supabase → Authentication → Users → **Add user** (email + password, tick auto-confirm), one per photographer.
Then SQL Editor, for each (use their email):
```sql
insert into staff (user_id, name, role)
select id, 'Photographer name', 'camera' from auth.users where email = 'photographer@example.com';
```
Send them the `…/camera/` link and their password.

## 5. Merge the page, then test before the event
Merge the pull request (pages go live). In Admin → Settings → Photos check the numbers, then:
1. Switch uploads **on**.
2. Upload one photo as a photographer, and one as an attendee (mark yourself Present at the gate first).
3. Check the photo appears in the gallery and the Storj bucket, then remove it.
4. Switch uploads **off** until the event if you like.

## 5b. The /gallery/ page (r2_22), added 15 Nov
One page now serves everyone: photographers (their own login) and attendees (Booking ID + phone). `/camera/` and the "Event photos" button on the ticket page both lead there.
- **Run `sql/r2_22_photo_gallery.sql` in Supabase** (after r2_20 and r2_21), then **redeploy the `photos` Edge Function** (paste the new `supabase/functions/photos/index.ts`). Then paste the SQL into `sql/changes.sql` and run Actions -> Database Snapshot. Merge the page only after both.
- **Who sees what** is an admin choice: Admin -> Settings -> Photos -> "Who sees which photos in the gallery" (own only by default; photographers see all; or everyone sees all). The database applies it, not the page.
- **Originals**: ONLY admins can download them (changed 16 Nov by r2_24: photographers can no longer). Photographers and attendees get small previews only, and photographers can still delete their own photos; share the full-size drive link after the event.
- **Delete**: admin any photo; a photographer or attendee only their own.
- Three ways to add photos (switch on the page): Instant (uploads at once), Check & upload (tick photos, capacity bar shows what fits), Draft (kept on the phone, upload later). Drafts and half-finished uploads survive a reload, but only on the same phone and browser.

## 5c. Run sql/r2_23_photos_service_read.sql (found on the first real upload, 16 Nov)
The photo Edge Function could not READ the photos table on this Supabase project (the "service_role" had no permission), so every upload ended with `NOT_FOUND` after the file had already reached Storj. r2_23 is one line: `grant select on public.photos to service_role;`. Run it in the SQL Editor (safe twice), then retry. To check: `select has_table_privilege('service_role','public.photos','select');` must say true.

## 5d. Two Storj accounts (one for photographers, one for the public) - decided 16 Nov
Each free Storj trial gives 25 GB storage and its own download allowance, so the public can have an account of its own.
- Photographers' account: the existing secrets `STORJ_ACCESS_KEY`, `STORJ_SECRET_KEY`, `STORJ_BUCKET`.
- Public account: three NEW secrets `STORJ_PUB_ACCESS_KEY`, `STORJ_PUB_SECRET_KEY`, `STORJ_PUB_BUCKET` (its own bucket name).
- The function picks the account from the photo's key: `camera/...` goes to the photographers' account, `public/...` to the public one. If the three `STORJ_PUB_*` secrets are missing, everything uses the photographers' account (one account still works).
- After redeploying the function, set the space in Admin > Settings > Photos: Total 50 GB, Photographers 23 GB, Public 23 GB (leaves about 2 GB spare in each account). The database allows this; nothing to run in Supabase.
- Photos already uploaded under `public/` before the switch stay in the old account and become unreachable. Remove the test photos first.
- NOT verified on the real service: the routing was tested only with a stand-in for the storage client (right account and bucket for each key), not with real Storj accounts. Test one upload as a photographer and one as an attendee after the switch. Check Storj's terms for running two free trials.

## 5e. Originals are admin-only (r2_24, 16 Nov)
Decision: only the organiser (an admin login) downloads originals. Steps: (1) run `sql/r2_24_originals_admin_only.sql` in Supabase, (2) redeploy the Edge Function with the new `index.ts` (its `view` action now refuses anyone who is not an admin), (3) merge the page, (4) paste the SQL into `sql/changes.sql` and run Actions > Database Snapshot. Until step 1 is run, photographers still get a Download button that the new function refuses.
NOT verified on the real project: the new refusal in the Edge Function (never executed; only syntax-checked) and the page on a phone.

## 5f. Only the admins YOU choose can download (r2_25, 16 Nov) - run AFTER r2_24
r2_25 adds a switch per admin (`staff.photo_download`, everyone starts OFF). Only an admin whose switch is on gets the Download button, the "Open" button in the admin gallery, and "Make download links file". Run `sql/r2_25_download_allowlist.sql`, redeploy the Edge Function, merge, snapshot. Then choose people in the Supabase SQL Editor (the website cannot change this switch):
```sql
-- who are the admins, and who may download now?
select s.name, u.email, s.photo_download from staff s join auth.users u on u.id = s.user_id where s.role = 'admin';
-- allow one (replace the email)
update staff set photo_download = true where user_id = (select id from auth.users where email = 'PUT-THE-EMAIL-HERE');
-- take it away again
update staff set photo_download = false where user_id = (select id from auth.users where email = 'PUT-THE-EMAIL-HERE');
```
Until you turn it on for yourself nobody can download, not even you. NOT verified on the real project: the Edge Function check (never executed here, syntax-checked only).

## 5g. Sharp previews (r2_26, 17 Nov)
Run `sql/r2_26_photo_previews.sql`, redeploy the Edge Function, merge. The page now also makes a sharp 1600-pixel preview of each photo and stores it next to the original as `<name>.p.jpg`. Originals stay locked to the admins you switched on.

## 5h. Attendee videos (r2_27, 17 Nov) - third Storj account
Only attendees upload videos (same Booking ID + phone login as photos). Nobody plays or downloads a video on the site: the page shows a sharp still picture (made in the phone). The original video goes only to the admins whose download switch is on.
1. Make a third Storj account (videos only). Make a bucket and an access grant that can read, write and delete in it (same way as 5d).
2. In Supabase > Edge Functions > Secrets add `STORJ_VID_BUCKET`, `STORJ_VID_ACCESS_KEY`, `STORJ_VID_SECRET_KEY`.
3. In the SQL Editor run `sql/r2_27_videos.sql` (safe to run twice).
4. Redeploy the Edge Function (`supabase/functions/photos/index.ts`).
5. Admin > Settings > Videos: set the video space (GB), the biggest video (MB) and the space per person (MB), then tick "Video uploads on". Suggested: 20 GB, 150 MB, 160 MB.
6. Test: log in as an attendee marked Present, Videos tab, Choose video, check the still appears, open it, delete it. Test once on a real phone (iPhone and Android).
If the third account is not set up, video uploads answer "not set up yet" and nothing else is affected.
After the event: Admin > Settings > Videos > "Make video download links file" (admins with the download switch on), then save the videos before the Storj trial ends.

## 5i. Sharing space between friends (r2_28, 18 Nov)
An attendee can give some unused photo space or video space to a friend (the friend's Booking ID + phone). Photos and videos are separate amounts. Received space can be passed on. The giver can take a gift back (all of it) only while the friend still has that much unused space. Space only moves between people: the pools and the Storj totals never change.
1. In the SQL Editor run `sql/r2_28_space_sharing.sql` (safe to run twice). No Edge Function change, no new secrets.
2. Merge the pull request. The attendee page gets a "Share" tab.
3. Admin > Settings > Space sharing: the log of who gave to whom (names, booking IDs, photo or video, MB, active or taken back) and an on/off switch. Every gift and take-back is also in the Settings log.
4. Test with two attendees marked Present: give 10 MB of photo space from one to the other, check both status bars change, upload with the friend, try Take it back.
NOT verified: anything on a real phone; the admin card was never opened in a real browser (syntax-checked only).

## 5j. Giving space by QR code (r2_29, 19 Nov)
On the Share tab the friend who wants space taps **Show my QR**; the giver taps **Scan friend's QR** (or scans it with the phone camera, which opens the page) and the page shows "Giving to <name>", so nobody types a Booking ID or phone. A code works for 30 minutes, can be scanned by many friends, and holds no phone number or Booking ID. The typed way still works. Gifts made by QR show "(QR)" in the admin log.
1. In the SQL Editor run `sql/r2_29_space_qr.sql` (run r2_28 first; safe to run twice). No Edge Function change, no new secrets.
2. Merge the pull request.
3. Test with two phones: one taps Show my QR, the other taps Scan friend's QR and gives 10 MB.
The scanner and the QR drawing load two small libraries from cdn.jsdelivr.net (jsQR, qrcode-generator) only when the Share tab needs them. If the camera is blocked the page says so and the typed way remains.
NOT verified: scanning on a real iPhone or Android (tested only with a pretend camera in desktop Chrome); camera permission wording differs per phone.

## 5k. Giving space with only the friend's Booking ID (r2_30, 19 Nov)
On the Share tab the phone-number box is gone. The giver (logged in as an attendee, marked Present) types the friend's **Booking ID** and the MB and taps Give. If the booking has one person, the page asks "Give 40 MB of photo space to <name>?". If it has several people, the page lists their names and the giver taps the right one. The QR and code work as before (a QR always points to one person).
1. In the SQL Editor run `sql/r2_30_space_by_booking.sql` (after r2_28 and r2_29; safe to run twice). No Edge Function change.
2. Merge the pull request.
3. Test: on one phone type another test attendee's Booking ID (try a booking with two people), give 10 MB to one of them, check the name shown and the admin Space sharing log.
Note: anyone who knows a Booking ID can give space to that booking (the receiver only gains) and can see the names on it. The older "Booking ID + phone" function stays in the database but the page no longer uses it.

## 6. After the event
Admin → Settings → Photos → **Make download links file**, download everything within the trial, and switch uploads off.

## What was NOT verified
- A real upload from the real GitHub Pages site to Storj through the deployed function (the pieces were tested separately: database, pages with a fake network, and a real browser upload earlier from a test page).
- Storj's CORS from your site origin (its docs say all origins are allowed by default).
- Photos bigger than claimed are deleted after upload, not blocked during it (Storj cannot enforce a size on the upload itself).
- The /gallery/ page on a real phone: the camera hand-off, drafts surviving a reload, drag-and-drop on a laptop. It was tested in a desktop browser against a pretend server only (login, uploads, check screen, drafts, resume, viewing, delete).
- Attendees stay "logged in" only by sending the Booking ID and phone with every request (no session token), the same as the Tickets page. Neither the Tickets lookup nor the photo calls limit wrong guesses; the 8-character Booking ID is what makes guessing impractical.
- How HEIC photos look in the admin gallery: some browsers cannot make a preview of them (the photo is still saved; the gallery shows "no preview").
- Videos (r2_27): never tried on a real phone. A phone may record a video format the browser cannot read a still frame from (then the video is saved with a plain "Video" tile and no still). A slow connection may need more than 20 minutes for a 150 MB video, and then the upload is refused as too late.
- The admin Videos card was never opened in a real browser (only syntax-checked).
