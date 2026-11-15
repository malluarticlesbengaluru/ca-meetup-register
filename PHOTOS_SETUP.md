# Photos feature: setup, in order

Do these in this order. Each step says what you should see.

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
- **Originals**: only admins and photographers can download them (a photographer: their own, or all if the admin allows). Attendees only get small previews; share the full-size drive link after the event.
- **Delete**: admin any photo; a photographer or attendee only their own.
- Three ways to add photos (switch on the page): Instant (uploads at once), Check & upload (tick photos, capacity bar shows what fits), Draft (kept on the phone, upload later). Drafts and half-finished uploads survive a reload, but only on the same phone and browser.

## 6. After the event
Admin → Settings → Photos → **Make download links file**, download everything within the trial, and switch uploads off.

## What was NOT verified
- A real upload from the real GitHub Pages site to Storj through the deployed function (the pieces were tested separately: database, pages with a fake network, and a real browser upload earlier from a test page).
- Storj's CORS from your site origin (its docs say all origins are allowed by default).
- Photos bigger than claimed are deleted after upload, not blocked during it (Storj cannot enforce a size on the upload itself).
- The /gallery/ page on a real phone: the camera hand-off, drafts surviving a reload, drag-and-drop on a laptop. It was tested in a desktop browser against a pretend server only (login, uploads, check screen, drafts, resume, viewing, delete).
- Attendees stay "logged in" only by sending the Booking ID and phone with every request (no session token), the same as the Tickets page. Neither the Tickets lookup nor the photo calls limit wrong guesses; the 8-character Booking ID is what makes guessing impractical.
- How HEIC photos look in the admin gallery: some browsers cannot make a preview of them (the photo is still saved; the gallery shows "no preview").
