# HANDOVER FOR THE NEXT CLAUDE SESSION

> **9 Nov 2026, handover synced with the code (read from the repo at `5796ab9`; `main` already includes the notes pull request #52; nothing was run, no test, and no live database or Admin value was read).** Where this block disagrees with an older line below, this block is right for the code. `PROJECT_NOTES.md` has the same facts in its own 9 Nov block.
> - **Owner decisions of 9 Nov 2026 (not open work):** the venue is fixed as Bloom Creative Zone, Haralur (the database default for `settings.venue` still says Savoury Business Hotel, Madiwala; the live page prefers the Admin value, so check Admin, Settings, Event details); the ticket's left-side picture (`assets/ticket-left.jpg`, venue and date baked in) is not changed; the photos for `abay`, `dana-fathima`, `muhammed-shamal` and `muhsina` are not available, so those people keep showing initials; the sponsor video (about 9.7 MB) stays; the member count is 1000+ (the About page says so in both places).
> - **SQL that is live and not described further down:** `r2_13` game messages, `r2_14` pick random people, the 2 Nov "What best describes you?" change (`tickets.occupation`, `tickets.occupation_detail`; answers Article Assistant, Industrial Trainee, Employee, Student, Others; it exists only inside `sql/changes.sql`, labelled "piece 15"), **`r2_15_fixed_switches.sql`** (About always on, Email never asked, Feedback always on), **`r2_16_gate_no_approve.sql`** (`admit_ticket` with approve on stops with `ADMIN_ONLY` for a gate account), **`r2_17`** (up to three organiser contacts; `admin_set_contacts`; `get_payment_info` now also returns `contacts`) and **`r2_18_bulk_approve.sql`** (`admin_preview_approval`, `admin_approve_bookings`). **`sql/r2_17_contacts.sql` was never committed and is lost** (the test `scratch-db/test_r2_17.py` still expects it at `/home/claude/sql/r2_17_contacts.sql`); r2_17 was run in Supabase on 7 Nov and its result is in the snapshot. The plan agreed with the owner: look for the original in the Supabase SQL editor history or the earlier chat; if it cannot be found, add a clearly marked reconstruction built from the snapshot.
> - **Database (snapshot of 9 Nov 2026, 13:18 IST):** 16 tables, the `report` view, 77 functions of which 22 are internal helpers (names starting with `_`) and 55 have other names (54 are callable by `authenticated`, 16 of those also by `anon`; the 55th is Supabase's own `rls_auto_enable`). Section 7 and Appendix A below were patched on 9 Nov for the functions added or changed since 26 Oct.
> - **Registration form (as the database now expects it):** `submit_booking` takes `name`, `phone`, `loc`, `food`, `occ` and `occ_detail` per person. It no longer takes an email or an attendance answer (`tickets.attendance` is nullable and nothing fills it); the old error codes `INVALID_EMAIL` and `INVALID_ATTENDANCE` are gone and `INVALID_OCCUPATION` and `INVALID_OCCUPATION_DETAIL` are new. `get_site_flags()` still exists, but neither page reads it any more.
> - **Pages:** the public page has a new Home (hero, poster, **"See walkthrough" panel that loads `tutorial.html?embed=1` in an iframe**), `members`, `teams` and `team` views, a landscape 2000 x 668 ticket (coordinators get a blue picture) with optional message and prize panels, and no `home-fx.js` or `logo-fluid.js` (deleted 4 Nov; `assets/page-fx.js` remains). The staff page screens are now **Today, Payments (with Scan screenshots), People, Gate, Transfers, Game messages, Feedback, Settings**, with light and dark themes; Settings has a Contacts card; Payments has bulk approve with a ticket-number preview; the Approve and admit button on the gate result is shown to admins only. `tutorial.html` holds embedded copies of the two pages; whether they are regenerated when the pages change was not checked.
> - **Test files in the repo on 9 Nov (none re-run):** database `test_r2_01` to `_06`, `_08` to `_14`, `_17`, `_18` and `mutate_r2_12` to `_14` (there is no `test_r2_15` or `_16`); browser scripts `run_admin`, `run_approve`, `run_desk`, `run_form`, `run_frame`, `run_gamemsg`, `run_gate`, `run_home`, `run_home_touch`, `run_messages`, `run_pagefx`, `run_people`, `run_public`, `run_public_fixed`, `run_qrimage`, `run_settings`, `run_smooth`, `run_startup`, `run_transfers`. The suite counts quoted in sections 0, 9 and 11 are from 28 to 29 Oct and are out of date; several older public-page scripts are known to test the old Home or form.
> - **Still never verified by anyone:** a real gate-staff login on a phone (the 6 Nov real scan was on the admin page), a complete real payment, the real database through the newest pages, and the pages on a range of real phones.
>
> **6 Nov 2026, ownership transfer and gate scanner fix:**
> - **Repo moved:** it is now `malluarticlesbengaluru/ca-meetup-register` (transferred from `rameezmunirrr-gh`). Older links in this file still name the old owner. GitHub redirects them, so they work; replace them when convenient.
> - **Bug found and fixed: the gate camera could not scan since the 28 Oct merge.** `admin/index.html` calls `jsQR(...)` in the camera loop (`gCamAttach`) but never loaded the library. The old stand-alone gate page loaded it, and `gate/index.html` is now only a forwarder. Fix: added `<script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"></script>` after the Chart.js tag in `admin/index.html`. The browser suites missed it because they fake the camera.
> - **Verified on a real phone, 6 Nov 2026:** a real ticket QR scans and checks in; scanning it again is refused; a short non-ticket QR shows NOT A TICKET. A Google Pay UPI QR (logo in the middle, long link) is not decoded, which is a known jsQR limit and harmless because it is not a ticket.
> - **Still not verified:** a real gate-staff login (the scan above was on the admin page), scanning in bright light or on older phones, and printed tickets.
>
> **Open items found by a code review on 6 Nov (read from the code, not all re-checked):**
> 1. The ticket's left side is a fixed picture (`assets/ticket-left.jpg`) with "Bloom Creative Zone / Haralur", "NOV 22, 2026" and the co-sponsor baked in. Changing the date or venue in Admin Settings will not change the ticket. Its tagline reads "Where strangers feels like home" (likely a typo).
> 2. The venue is inconsistent: the page's built-in `CONFIG` says Bloom Creative Zone, Haralur, but the database default is Savoury Business Hotel, Madiwala. The live page prefers the Admin value, so check Admin → Settings → Event details.
> 3. About page says "600+ members" in the text and "1000+" in its facts chip.
> 4. Home step 2 says "open your UPI app", but the app deliberately does not open one. Reword.
> 5. Member photos referenced but missing: `abay`, `dana-fathima`, `muhammed-shamal`, `muhsina` (those people show initials).
> 6. The sponsor video is about 10 MB.
> 7. The share-preview image address (`og:image`) needs checking.
> 8. The database suites were not re-run and need a rebuilt test database. The test counts quoted below (public 101, admin 73, gate 35) may be out of date after the 4 and 5 Nov redesigns.

> **4 Nov 2026 cleanup of the public Home (owner request):** `assets/home-fx.js`, `assets/logo-fluid.js` and the stray root `akhina-a-r.jpg` were deleted, together with the old Home design's CSS (about 20 KB, all of it dead since the BURGUNDY `.bhome` Home: nothing renders `.home` or `#logo`) and the browser suite `scratch-db/browser/run_homefx.py`. Any other mention of `home-fx.js` or `logo-fluid.js` in this file or the handover describes the old design. The Home pop-up on scroll now lives in `homeMount()` in `index.html` (each section follows whichever is further along: a timed pop from the moment it enters the screen, or its scroll position). `run_home.py`, `run_home_touch.py` and `run_public.py` still test the OLD Home and fail on the current one; they need rewriting for `.bhome`.

**Project:** Ehsaas'26 meetup registration app (repo `malluarticlesbengaluru/ca-meetup-register` since 6 Nov 2026, public; GitHub Pages + Supabase project `CA-meetup-2026`).
**Rewritten:** 26 Oct 2026 (evening, India time), by the session that took the project over from the previous Claude session after its credits ran out. It replaces the earlier version, which had grown into three layers (a 23 Oct body under two "override" blocks) and described a world where nothing was applied yet.
**How it was checked:** against the repo (`main` at `abb7817`, PR #12 merged), the live database snapshot of 26 Oct 11:17 UTC (`b86a59c`, run by the owner by hand on request), and a test database rebuilt from the repo in this session. Where something was NOT verified, the line says so.
**Updated later on 26 Oct 2026 (same day):** the owner's answers to the section-1 questions are recorded in section 1 and 0.1; `PROJECT_NOTES.md` was brought up to date (commit `b53fee7`, verified); the task list in section 11 is updated.
**Updated 5 Nov 2026 (ADMIN REDESIGN, all 7 steps done):** the staff page (`admin/index.html`) was redesigned in seven steps; see "ADMIN REDESIGN" in `PROJECT_NOTES.md` for each step. In short: smoothness engine (PR #48); new frame with side menu / bottom bar, top bar search, light and dark, Today screen (PR #49, with the About link and Feedback always on and email never asked: `sql/r2_15_fixed_switches.sql`, **already run and merged by the owner**); payment review desk (PR #49); People chips and table view, Gate progress bar and Not-here-yet list; Transfers count tiles, collapsible money panel, phone-friendly tables; Settings sticky section bar. **Browser suites to run before any admin change** (from `scratch-db/browser`): `run_admin.py` 69, `run_gate.py` 35, `run_messages.py` 111, `run_smooth.py` 71, `run_frame.py` 19, `run_desk.py` 25, `run_people.py` 26, `run_transfers.py` 15, `run_settings.py` 9, and for the public page `run_public_fixed.py` 7 (the older `run_public.py` is out of date with the live registration form and needs a rewrite before it can be used again). **Never verified:** a real phone, the real database and storage bucket, the real camera scan.

**Updated again on 27 Oct 2026:** Claude now has **push access** to the repo (section 10): it works on a branch and the owner merges the pull request. **All three browser suites were re-run and pass (public 101, admin 47, gate 9).** The public pages were restyled a second time, the whole public text was reworded, the phone layout was fixed, and the payment QR now carries the logo (the owner scanned it in several UPI apps: works). Sections 0.1 to 0.4, 2, 4.1, 6, 8, 9, 10 and 11 reflect this.
**Updated again on 28 Oct 2026:** the **staff side was rebuilt** (PRs #19 to #28): a green theme matching the public pages, cards and previews instead of wide tables, linked data with a back gesture, a new gate flow (results stay on screen; Next scan / Home page / Undo; an Admitted list; camera retry), and the **gate scanner merged into the admin page** (`gate/index.html` now only forwards). One new SQL file, `sql/r2_12_gate_undo.sql` (gate staff can undo for 2 minutes, admins any time), applied by the owner. Browser suites: **public 101, admin 73, gate 35**. Sections 0.1 to 0.4, 2, 4.2, 4.3, 6, 8.4, 9 and 11 are updated.
**Updated again on 29 Oct 2026 (later):** two test files were added and nothing else changed (no page, no SQL, no database change): `scratch-db/test_r2_12.py` (56 checks, a database suite for `gate_undo_checkin`) and `scratch-db/mutate_r2_12.py` (breaks `r2_12` in 16 ways; all 16 are caught). The database total is now **11 suites, 731 checks**. The CHECKPOINT, sections 2, 8.4, 9 and 11 are updated.
**Updated 30 Oct 2026 (Messages, part 1 of 2, database only):** new `sql/r2_13_game_messages.sql` (**run by the owner in Supabase on 30 Oct 2026**; recorded in `sql/changes.sql`; a new snapshot is still to be taken and compared): tables `game_messages` and `ticket_messages` (admin-only), switch `settings.show_messages` (default OFF), admin functions `admin_set_show_messages`, `admin_save_message`, `admin_delete_message`, `admin_assign_messages` (a list of ticket+message pairs, all or nothing), `admin_clear_messages`, a trigger so a transferred ticket keeps its message, Settings-log area `messages`, and `lookup_tickets` now returns `game_message` per ticket ONLY while the switch is ON (paid booking, ticket not transferred away). Tests: `scratch-db/test_r2_13.py` (88 checks) and `scratch-db/mutate_r2_13.py` (44 deliberate mistakes, all caught). Part 2 (the admin Messages tab, the Settings switch and the ticket display) is the next pull request. After the owner runs the SQL: paste it into `sql/changes.sql`, run Actions, Database Snapshot, compare. Not verified: the real database (only the scratch one), a real transfer creating the new ticket (the trigger was tested by inserting such a ticket directly).
**Updated 31 Oct 2026 (Pick random people; was "Prizes / lottery"):** `sql/r2_14_game_prizes.sql` (**RUN by the owner on 31 Oct 2026, the NEW version with the heading; recorded in `sql/changes.sql`; the 31 Oct snapshot compared with a scratch build: identical except the known differences, i.e. storage policies, event triggers, `rls_auto_enable`, storage buckets and the privilege letters `Dxtm`**). Neutral wording because the line is not always a prize: it can be a message, task or clue for N randomly picked people. Table `ticket_prizes` (`body` 1-200 characters, `heading` 1-60 characters, default 'You are a winner!', admin-only), `admin_set_prizes(uuid[], text, text default null)` (blank/null heading means the default; heading over 60 or with control characters is refused with INVALID_NAME; the old 2-argument call still works), `admin_clear_prizes(uuid[] default null)`, the transfer trigger copies line AND heading, and `lookup_tickets` returns `game_prize` and `game_prize_heading` (same rules as `game_message`: switch `show_messages` ON, paid booking, ticket not transferred away). Pages: Messages tab card **3. Pick random people** (group: paid or only present; how many people; leave out people who already have a message line; optional heading; the message line; secure random draw; preview, Draw again, Save; "Picked so far" list with heading and line, Take away, Take every message line away), a 🎲 picked tag on People cards, a Message line row in a person's sheet. The public ticket shows team message and message line as two separate panels, each only when it exists (neither: exactly as before, 900 x 1480); the heading is the label of the second panel and shrinks (down to 12 px) when long. Tests: `scratch-db/test_r2_14.py` 72, `mutate_r2_14.py` 48 of 48; `run_messages.py` 111, `mutate_messages_page.py` 49 of 49 (one equivalent mutant left out on purpose, see the comment in the file); `run_gamemsg.py` 37, `mutate_gamemsg.py` 24 of 24; older suites unchanged and green. **Not verified:** this on the real database and real phones; the real Fraunces font in the panels; how a 60-character heading looks on a real ticket; the owner must announce picked people out loud (they only see it by opening Tickets with Booking ID and phone).
**Updated 30 Oct 2026 (Messages, part 2 of 2, the pages):** `admin/index.html` gets a **Messages tab** (only after `r2_13` has been run; before that the tab and the Settings card stay hidden and nothing breaks): a banner with Show/Hide, a list of messages (name for the admin, text for the ticket; add, edit, delete, take away), a **Give messages** tool (group: everyone with a paid ticket, or only people present, optionally only people with no message yet; **deal out at random** into the ticked messages as evenly as possible, with a preview and a confirmation before anything is saved, optionally keeping each booking together; or **one message to the whole group**; or take messages away), a **Who has what** roster, a message tag on People cards and a Message select in a person's sheet, and a **Game messages** card in Settings. `index.html` draws the message as a panel under the ticket (the ticket is taller only when it has a message; with none it is exactly as before) and **View Ticket now asks the database again first** so a message switched on later appears (falls back to what is on screen if that fails). New suites: `scratch-db/browser/run_messages.py` (69, stateful stand-in for the five database functions; `mutate_messages_page.py`: 24 of 24 mistakes caught) and `run_gamemsg.py` (23, real QR library; `mutate_gamemsg.py`: 11 of 11 caught). Other suites unchanged: public 101, admin 73, gate 35, startup 29, pagefx 26, homefx 38, qrimage 32. **Not verified:** the Messages tab and the new ticket panel on real phones; the real database through the page (the page was tested against a stand-in; the SQL separately against the scratch database); the real Fraunces font in the panel (the sandbox used a fallback font, so line breaks will differ a little on phones); whether the ticket QR still scans from the taller ticket picture (the QR itself is unchanged and drawn the same way).
**Confirmed 30 Oct 2026 (snapshot of 30 Oct, 10:20 UTC, compared with a scratch copy built from `r2_01` to `r2_13`):** columns, constraints, indexes, views, view options, row-level security, triggers and **every function body with its execute rights** are IDENTICAL, so `r2_13` is live exactly as tested (the new tables `game_messages` and `ticket_messages` have `authenticated` read-only and no `anon` rights, as intended). The only differences are the known ones: the two storage policies, the Supabase event triggers, `rls_auto_enable`, and the extra privilege letters Supabase adds (`service_role`, `m`), which show on every old table too. The Messages feature has still not been used on the real site by the owner.
**Updated again on 29 Oct 2026 (home page speed, part A):** the public Home card is no longer rebuilt when live answers arrive. Before, the page drew Home and then redrew it three more times (event info, payment info, site flags), so the card faded in **4 times** (measured), the logo element was replaced and the page jumped back to the top if the visitor had started scrolling. Now `refreshHome()` patches the date, time, venue and the About button into the existing card. A new browser script, `scratch-db/browser/run_startup.py` (12 checks, includes a deliberate-mistake control), tests this. Only `index.html` and that script changed.
**Updated again on 29 Oct 2026 (home page speed, part B; stacked on part A, so merge A first):** the public page no longer waits for the Supabase and QR libraries before drawing Home. Both script tags are now `async` (with `onload`/`onerror` flags); `db` is a thin wrapper (`db.rpc` and `db.storage.from().upload`, the only calls the page makes) that waits for the library on every call; `whenQR()` and `qrReady` make the pay screens and the ticket drawing wait for the QR library. In a simulated slow network (Supabase library 4 s, QR library 2 s) Home appeared after **4018 ms on the old page and 23 ms on the new one** (the seconds on a real phone are not measured). `run_startup.py` now has 29 checks, with deliberate-mistake controls for each rule.
**Updated again on 29 Oct 2026 (Share/Download QR picture):** the picture people get from **Share QR** and **Download QR** now shows "Pay ₹amount", "to <payee>" (when set), the QR, and the **UPI ID** underneath, plus "Scan with any UPI app". `blobQR()` builds it on a new canvas and draws the page's own QR **1:1 (never scaled)**, so it scans exactly as well; the QR on the page is unchanged. Works for the registration and the transfer payment screens. New script `scratch-db/browser/run_qrimage.py` (21 checks: the real `qrcode-generator` from npm and the real logo, the PNG decoded with OpenCV and compared with the payment link; long UPI ID and payee, no payee, a 5-digit amount; three deliberate-mistake controls). One-time setup for it: `mkdir -p /home/claude/qrtest && cd /home/claude/qrtest && npm i qrcode-generator@1.4.4`. Not changed: `drawQR`, the logo patch, the ticket QR.
**Updated again on 29 Oct 2026 (UPI check warning):** a warning note now tells payers: "**Important:** After you scan, check that the UPI ID shown in your app matches the UPI ID below." It is on both pay screens (registration and transfer payment), between the QR and the UPI ID (class `.verify`, amber), and in the Share/Download picture (an amber box between the QR and the UPI ID). The owner asked for it on 29 Oct 2026; the wording is a polished version of their sentence. `run_qrimage.py` now has 32 checks (the warning in the picture and on the screen, its position, the picture still scans; two more mistake controls).
**Updated again on 30 Oct 2026 (Home motion):** the public Home page got a calm set of animations, chosen by the owner from another Claude session's demo (that demo was NOT copied: it was built from an older copy of the page and would have undone the speed work; its heavy parts were left out on purpose). **Kept:** very slow drifting discs behind the heading, slowly flowing colour bands, a gentle pulse on the small diamond between the title and the date, a short entrance (about 1.2 s, played once per visit: pres line, title letters, ornament, date/time/venue rows, buttons; buttons start appearing after ~0.4 s), a soft ripple and press-in on the big buttons, a light sweep over the buttons (Register at 3 s, Tickets 5 s, About 7 s, repeating every 8 s, never two at once), a few dim glowing particles in the BACKGROUND only (12 on a phone, 20 on desktop; a fixed canvas behind `main`, so never on a card), a flash on a tapped date/time/venue row, and **desktop only** (real mouse: `(hover:hover) and (pointer:fine)`) the card tilting toward the pointer with a light glare and the logo's two heads looking at the pointer. **Left out on purpose:** jelly wobble on scroll, droplet bursts and rings on every tap, the repeating title wave, buttons drifting toward the finger, heavy particle swarms. Everything is off for "reduce motion". Files: `assets/home-fx.js` (loaded as `?v=1`: **bump the number whenever it changes**), the motion CSS block in `index.html` (search "Home motion"), a hook at the end of `render()`, `main` is now `position:relative;z-index:1`. New script `scratch-db/browser/run_homefx.py` (38 checks incl. 6 mistake controls). Measured (headless, not a real phone): 59 to 60 frames per second even with the CPU slowed 6 times, same as before. Not checked: real phones, Safari on iPhone, how it feels.
**Updated again on 30 Oct 2026 (motion on every public screen, payment screens fixed):** (1) On the two **payment screens** (`pay` and the transfer `tpay`, both QR pages) the scroll-reveal is **off**: `reveal()` returns at once for them, so the "Upload your payment screenshot" card is never hidden below the QR (it used to stay invisible until scrolled to, which made people think the page ended at Copy UPI ID / Share QR / Download QR). Every other screen keeps the scroll-reveal exactly as before (owner: "everything else is fine"). (2) New `assets/page-fx.js?v=1` gives **every screen except Home** a short entrance (about 0.6 s: heading, then each block, staggered) that plays only when the screen changes or its content first arrives (not on a redraw of the same screen, because `render()` is called in about 60 places), and a soft **ripple on every button**; the press-in (`scale .97`), the clipping the ripple needs, and a slowly flowing header stripe (`.kasavu`) are CSS in `index.html`. Reduced motion switches all of it off. The ripple moved out of `home-fx.js` (now `?v=2`) into `page-fx.js`; do not add it back there or Home gets two ripples (a test checks). Particles and the button sweep stay on Home only (decision of this session; the owner can ask for more). New script `scratch-db/browser/run_pagefx.py` (26 checks incl. 5 mistake controls). **`run_public.py` now loads the real motion scripts too**, so the whole booking flow is tested with the entrance running. Suites: public 101, admin 73, gate 35, startup 29, qrimage 32, homefx 38, pagefx 26. Not checked: real phones.
**Updated 3 Nov 2026 (new Home design, branch `home-new-design`; page and scripts only, no SQL):** the owner brought a finished design (`Ehsaas26-Home-animation-demo-4.html`) and Home was replaced by it. New in `index.html`: the Home markup (`vHome`) with a hero (logo, title, venue pill, a **Register · ₹price** button, a live "Only N spots left" line), the poster, When & where as two cards with line icons, What's in store as four coloured cards, the story paragraph (its words light up while scrolling), the sponsor card (kept), an amber join card, **two countdowns** (registration deadline and the meetup) and a floating Register button; a second `<style>` block holds the Home motion CSS (all scoped to `html.fx`, set only when the visitor has NOT asked for reduced motion; the reveal rules are scoped to `.home` so other screens are untouched). **`assets/home-fx.js` was rewritten (`?v=3`)** for the new markup (the old one only knew the removed `.invite` card). **New data on Home:** `loadHomeStatus()` calls the existing read-only `get_public_status` (at most every 30 s, never blocks Home) for the live price, the spots left and the deadline; the spots line is shown only when 20 or fewer remain (same rule as the Register page) or when the hall is full; the registration countdown is hidden when registration is not open or the status call fails. A **returning visitor** (booking ID saved on the device) sees View my ticket as the main button and Register another booking as the second. The long hero entrance plays once per visit (class `again` afterwards). The demo's toast, "Replay intro" and "Preview: returning visitor" buttons and its fake click messages were NOT carried over. New suite `scratch-db/browser/run_home.py` (**49 checks**; five deliberate mistakes are all caught: swapped button routing, the 20-spot rule, the registration countdown when closed, the returning label, the reveal style leaking onto the form). **Known and not caused by this change:** `run_startup.py`, `run_homefx.py` and `run_pagefx.py` wait for the old `.invite` card and already failed on `main` before this change; `run_public.py` already failed on `main` at the form (it looks for the old Attending chips); `run_qrimage.py` needs `npm i qrcode-generator@1.4.4` in `/home/claude/qrtest` first. They need rewriting for the current pages. **Not verified:** real phones, Safari on iPhone, the real Supabase through the new Home (a mock was used), the real Manrope font.
**Read order:** (1) this file, (2) `PROJECT_NOTES.md` (decision log, database design and changelog; brought up to date on 26, 27 and 28 Oct 2026), (3) the SQL in `sql/` and the tests in `scratch-db/` only when you work on them.
**Where the two documents disagree:** trust the live snapshot and the SQL files + tests first, then this file, then the notes, and tell the owner.

---

## CHECKPOINT: end of the 26 to 28 Oct 2026 session (owner closed the session here)

**State:** `main` is clean and equal to the remote; every pull request (#1 to #30) is merged; the three browser suites pass on `main` (public 101, admin 73, gate 35); `r2_12_gate_undo.sql` is live (confirmed in the snapshot of 28 Oct 2026) and recorded in `sql/changes.sql`. The app is still in **testing mode**: registration on for testing, test data only, transfers off, not ready for launch.

**Added after the checkpoint, 29 Oct 2026: the animated logo on the public home page.** The owner wrote this and committed it straight to `main` (commits `947d7d6` to `55ddc1c`, 28 Oct); Claude reviewed it on 29 Oct.
- **What it is:** `assets/logo-fluid.js` (loaded by `index.html` as `assets/logo-fluid.js?v=2`) draws the logo as inline SVG on the **home page only**. Two bodies slide together and merge through an SVG "goo" blur filter, two heads bud out, and the grey centre is the exact overlap of the two bodies (a clip-path, not a separate shape). It uses spring physics and ends in the crisp logo after about 3.4 seconds. All the "how loose is the fluid" numbers are in the `TUNE` object at the top of the script.
- **How the page uses it:** `vHome()` renders a `.logo-wrap` holding the old PNG (`#logo-fallback`) and the SVG (`#logo`, hidden at first). After each render, `render()` unhides the SVG, calls `LogoFluid.mount(l,{jiggle:false,replay:false})` and hides the PNG. If anything throws, the SVG is hidden again and the PNG comes back. On the public page the scroll-squish (`jiggle`) and tap-to-replay are **off**; the script supports both. The app re-renders the home view while it loads, so `mount` carries on a running animation (under 6 seconds old) instead of restarting it. The loop stops by itself when the logo leaves the page.
- **Reduced motion:** with "reduce motion" on, the finished logo is drawn with no animation.
- **Cache-busting:** the script is loaded with `?v=2`. **Bump the number whenever `logo-fluid.js` changes**, or phones keep the old copy.
- **Test change:** the owner edited `run_public.py` (the "look" check now looks for `.logo-wrap #logo-fallback` and `svg#logo`).
- **Checked by Claude on 29 Oct:** all three suites still pass (public 101, admin 73, gate 35); in headless Chromium at 390 px wide the animation runs from budding heads to the finished logo with no script errors, the PNG is hidden once the SVG is up, and the reduced-motion render shows the finished logo.
- **Not checked:** how it feels and performs on real phones (especially older Android ones: the blur filter is redrawn every frame for about 3.4 seconds), and Safari on iPhone.
- **Still open:** the standalone logo **SVG file** for the About page is still wanted from the owner; the animation does not replace it.

**Pending, in the order I would do it (nothing blocks anything else):**
1. **Real-account tests (the owner):** create a gate login, then on a phone: sign in at `/admin/` (only the Gate tab must show), scan a real ticket, Undo within 2 minutes (works) and after 2 minutes (says ask an admin), deny the camera and press Try again. Also an admin Undo after 2 minutes, and the staff page on real phones. Report what is odd and Claude fixes it.
2. ~~A database test suite for `r2_12`.~~ **Done 29 Oct 2026:** `scratch-db/test_r2_12.py` (56 checks: visitors and non-staff refused; gate staff inside and after the 2 minutes, including 119 and 121 seconds; admins any time; wrong, empty and never-admitted ids; only the one ticket and only the two check-in columns change; the old `undo_checkin` is still admin-only; two undos at the same instant) and `scratch-db/mutate_r2_12.py` (16 deliberate mistakes, all caught). It tests the SQL file; the live function in the 28 Oct snapshot was compared with that file and is identical. Not covered: a real account on a real phone (item 1).
3. **About page content** from the owner (text, reels as links, photos with permission) and the logo as an SVG.
4. **Wording pass on the staff page** (its look and phone layout were rebuilt, its text only partly reworded).
5. **Housekeeping:** a real `README.md`; G15 and G17 (section 12); old merged branches (none are left on GitHub at the checkpoint).
6. **Left out on purpose, ask before building:** tappable Overview pie slices; tappable "rejected: N" on the Present card; the Settings log linked to bookings.
7. **Pre-launch checklist** (section 11) when the owner decides, then launch. After the event: section 11, item 10.

**Never verified by anyone:** a complete real payment; a real gate account (the real 2-minute undo, the real camera scan on the merged page); the admin side of the undo rule on a real account (the database rule itself, for gate and admin accounts, is tested on a scratch copy since 29 Oct 2026); the new staff page on a range of real phones; the transfer screens against the real database (transfers are off).

---

## 0. The 60-second summary

**0.1 What exists and works (all built, tested, applied live)**
- Registration for up to 5 people per booking with a UPI QR for the exact total, a payment screenshot, manual verification by admins (with in-browser OCR to catch reused or fake proofs), numbers given only when a booking is marked paid, QR tickets (JPG/PDF) and a gate scanner.
- **Release 2 is LIVE** (applied by the owner on 25 Oct 2026): ticket lookup by **Booking ID + phone**, email per person (admin-only table), **private and public ticket transfers** through one code flow (admin phone call = identity check), an IP flag (flag only), and the Admin tools for all of it (Transfers tab, money panel, settings).
- Added 25 to 26 Oct and also live: coordinators can transfer (`r2_08`); an About link with an on/off switch (`r2_09`); an Email-box on/off switch (`r2_10`); optional feedback questions on the Booking ID page with a switch and an admin Feedback tab (`r2_11`); a resubmit bug fix; the **restyle** (first version: public pages navy/amber/ivory with the Mallu Articles Bengaluru logo, which was **replaced on 27 Oct 2026**, see the next bullets; Admin and Gate "Midnight Emerald").
- **Owner's answers, 26 Oct 2026 (late):** registration is switched **ON for testing only**; there is **test data only, no real bookings**; **transfers are OFF**; the app is **not ready for launch** (still being modified; the owner will fix all settings when all work is done); the gate members' logins are **not created or tested**; Supabase sign-ups are **OFF** (verified by the owner on 26 Oct). No deadline pressure: the 31 Oct deadline is not to be considered; accuracy and quality come first. See section 1.
- **27 Oct 2026 (all merged by the owner as PRs #13 to #18; nothing in the database changed):** the **public pages were restyled again** to match the owner's own "Join the Event Team" page (dark navy with amber, five accent colours, Manrope; section 4.1); the **whole public text was reworded** (registration, review, payment, done, tickets, closed screens, then the transfer screens, and the About page now says "Coming soon"); the **phone layout was fixed** after the pages were first looked at in a 390 px wide browser (the Review table overflowed and is now stacked cards); the **Done screen** lost its Name/Food table and shows "Share your thoughts" below "Pending verification"; the **payment QR carries the logo** in a round navy patch (section 4.1). Admin and Gate were NOT touched.

- **27 to 28 Oct 2026 (PRs #19 to #28, all merged by the owner; one SQL file):** the staff page was restyled in green to match the public pages and made phone-and-laptop friendly, in stages (header and pinned scrolling tabs, Overview, Bookings, People, Settings); **every number is now explained** (each Overview and Transfers card opens the list behind it, with the working) and names, Booking IDs and "and N others" open **previews** (bottom sheet on a phone, side panel on a laptop) that stack, with the **back gesture** closing them; a Find box; People has a Present / Not present filter. The **gate** got result screens that stay until the gate person presses **Next scan**, **Home page** or **Undo**, an **Admitted list** with previews, and a camera retry; the **2-minute gate undo** needs `sql/r2_12_gate_undo.sql` (**applied by the owner on 28 Oct**); then the **gate scanner was merged into the admin page** (a Gate tab; gate staff see only that tab; `/gate/` forwards). Details: sections 4.2 and 4.3, and notes sections 6 and 13.

**0.2 What is verified, what is not**
- **Verified in this session (26 Oct):** all 10 database suites pass, **675 checks** (62, 54, 153, 157, 77, 68, 36, 14, 26, 28). The live database structure equals the tested one: every function body and execute right, all columns, constraints, indexes, views, row-level security and triggers are identical between the live snapshot and a scratch copy built from the pre-Release-2 snapshot plus `r2_01` to `r2_11`. Remaining differences are Supabase's own items (storage policies, event triggers, `rls_auto_enable`) and Supabase default privilege letters on older objects (see G15).
- **Verified on 27 and 28 Oct 2026:** the three browser suites pass: **public 101, admin 73, gate 35** (`scratch-db/browser/`; Chromium and Playwright are pre-installed in the chat sandbox, section 9; the gate suite now loads `admin/index.html`). Screens were looked at in screenshots at 390 x 844 and at laptop width. The payment QR with the logo was decoded by three independent decoders, and then **scanned by the owner in several real UPI apps: it works.** The owner merged and used the new staff screens and said the linked details "work wonderfully".
- **Not verified (28 Oct additions first):** a real gate account (none exists yet), so the real 2-minute undo for a non-admin and the real camera scan on the merged page; the admin side of the undo rule (the tests only used a gate account); the staff page on real phones (the owner has used it on their own); the exact SQL of `r2_12` against the live database beyond the owner running it successfully; the new public look on a wider range of phones and browsers than the owner's own; the transfer screens against the real database (transfers are off, only simulated data was used); the Google fonts in the sandbox screenshots (a fallback font was shown there).
- **Never verified by anyone:** a complete real payment (real money moving and an admin matching it), and the gate members' logins. The owner has scanned the QR in several UPI apps and checked the 25 Oct rehearsal on their own phone.

**0.3 Documents (state on 26 Oct 2026, later)**
- `PROJECT_NOTES.md`: **brought up to date on 26 Oct 2026 and again on 27 Oct 2026** (first update: commit `b53fee7`; the old Release 2 design and audit sections were removed from it and remain in git history, commit `55c4176`). It describes Release 2, `r2_08` to `r2_11`, the restyle, the switches, the files table and the pre-launch checklist.
- `README.md` contains only the repo name. `sql/README.md` is the owner's guide to the sql folder (not reviewed in this session).

**0.4 Owner:** a beginner working alone, in the browser (GitHub + Supabase). Plain language, step by step. **Since 27 Oct 2026 Claude has push access to the repo: it works on a branch, and the owner opens the pull-request link and presses Create pull request, then Merge** (section 10). Standing order: structure and safety first, looks last (looks and wording of the public pages are now done; the staff page was restyled green to match, 27 to 28 Oct).

---

## 1. FIRST QUESTIONS TO ASK THE OWNER (ANSWERED 26 Oct 2026; re-ask only what has changed)

**Owner's answers (26 Oct 2026):**
1. *Situation:* registration is ON for testing; test data only, no real bookings; transfers OFF.
2. *Dates:* the deadline is 31 Oct 2026, but Claude is **not to mind it**: focus only on accurate, high-quality working results, wasting no time, credits or effort. The real opening date is not fixed.
3. *Pre-launch checklist:* **not ready for launch**; still under modification; the owner will fix all settings when all work is done. Gate members' logins **not tested** (not created). **Supabase sign-ups: OFF, verified by the owner on 26 Oct 2026.** Real UPI ID / payee / WhatsApp, the real test payment and the final price: not asked yet (still to do at launch time).
4. *Delivery:* the previous Claude session was disconnected from the repo and is not linked to anything. Claude is now the owner's **instructor** and delivers **complete files** for upload in the GitHub web editor, then verifies against a fresh download. (Verified working on 26 Oct: `git clone` and `curl` on raw URLs.) **Changed on 27 Oct 2026:** the owner attached the repo to the chat with push access, so Claude now pushes branches and the owner merges the pull request (section 10).
5. *SQL after `r2_11`:* not asked; the snapshot of 26 Oct 11:17 UTC shows nothing newer than `r2_11`. Ask again if the owner reports running anything.

The original questions follow, for reference.

1. **What is today's real situation?** Is registration still closed? Are there real bookings, or test data again since the clean-up on 25 Oct (`r2_07`)? Are transfers still OFF?
2. **Dates.** The last record says: deadline 31 Oct 2026 23:59:59 IST (check Admin → Settings), event Sunday 22 Nov 2026 2 PM at Savoury Business Hotel, Madiwala. What is the real opening date, and should the deadline move?
3. **Pre-launch checklist** (notes section 11, status unknown): real UPI ID, payee name and WhatsApp number entered; a small real test payment scanned in two UPI apps; the gate members' logins created and tested; price final (₹250 and cap 150 were the last recorded values); sign-ups still off in Supabase Auth.
4. **How changes are delivered now.** The previous session pushed branches and pull requests through a GitHub connection; the owner merged each PR. That connection has been removed (owner, 26 Oct 2026). Unless the owner chooses another route, deliver **complete files** for the owner to upload in the GitHub web editor, then verify against a fresh download of the repo.
5. If any SQL was run in Supabase after `r2_11`: ask for it, add it to `sql/changes.sql`, and run the Database Snapshot workflow.

---

## 2. STATE OF EACH ENVIRONMENT

> **9 Nov 2026:** the table below was written on 26 to 28 Oct. For the current state (repo `main`, the SQL list through `r2_18`, the database size, the files) use the 9 Nov block at the top and the `sql/` folder itself.


| Place | What is there (verified 26 Oct 2026 unless stated) |
|---|---|
| **Live Supabase** | Release 2 fully applied: `r2_01` to `r2_06` (kept as `sql/rollout_A_part1_APPLIED.sql` = r2_01 + r2_02 and `sql/rollout_A_part2_APPLIED.sql` = r2_02b + r2_03 + r2_04 + r2_05 + r2_06), the data clean-up `r2_07`, then `r2_08`, `r2_09`, `r2_10`, `r2_11`. Evidence: the snapshot `b86a59c` contains `ask_email`, `ask_feedback`, `booking_feedback`, `submit_feedback`, the three switch functions, and its function bodies equal the scratch copy. 14 tables/views, 64 functions (19 internal helpers). Settings and data are not in the snapshot. |
| **Repo `main`** | At `f690a8a` (28 Oct 2026, PR #28 merged), plus the documentation branch of 28 Oct. `index.html` (about 87 KB), `admin/index.html` (about 112 KB; the staff page including the gate scanner), `gate/index.html` (about 0.6 KB forwarder), `assets/`, `sql/` (now with `r2_12_gate_undo.sql`), `scratch-db/`, `.github/workflows/`, this file, `PROJECT_NOTES.md`, `README.md`. 28 pull requests merged in all; feature branches are merged and still exist on GitHub (housekeeping). |
| **GitHub Pages** | The "pages build and deployment" runs #153 to #159 on 26 Oct were all green in the owner's screenshot (the latest about 16:30 IST, right after PR #12). |
| **GitHub Actions** | `Database Snapshot` (nightly 2:00 AM India time, also by hand: Actions → Database Snapshot → Run workflow; writes `sql/schema_snapshot.txt` only when something changed), `Supabase Keepalive` (every 3 days, keeps the free project awake), and GitHub's own pages build. |
| **Test database** | Not part of the live system. Rebuilt from the repo in each chat (section 9). |

**The `sql/` folder**

| File | Meaning |
|---|---|
| `schema_snapshot.txt` | Nightly export of the live structure. The truth. Never edit by hand. |
| `changes.sql` | Hand-kept history of SQL run in Supabase (newest entries are at the TOP for r2_10 and r2_11, and a Release-2 note is at the bottom). Not guaranteed complete. |
| `r2_01` to `r2_06` (+ `r2_02b`, `r2_02c`) | Release 2 backend pieces. Applied. Kept because the tests build on them. |
| `r2_07_cleanup_test_data.sql` | Deletes ALL bookings, tickets, emails, transfers, IP records, scans and sessions, restarts numbering at 1, switches transfers off; keeps staff, settings and the settings log. **Refuses to run while registration is open.** Run once on 25 Oct. Do not run again after real bookings exist. |
| `r2_08` coordinators can transfer; `r2_09` About switch; `r2_10` Email switch; `r2_11` feedback | Applied. |
| `r2_12_gate_undo.sql` | `gate_undo_checkin(uuid)`: gate staff undo an admission for 2 minutes, admins any time. **Applied by the owner on 28 Oct 2026.** Recorded in `changes.sql` (28 Oct 2026) and **confirmed live in the snapshot of 28 Oct 2026, 09:53 UTC** (body identical to the file; execute rights `authenticated` only); the database suite is `scratch-db/test_r2_12.py` (56 checks, added 29 Oct 2026, with `mutate_r2_12.py`, which breaks the SQL 16 ways and confirms the suite notices each one). |
| `archive/r2_04_admin_matched_NOT_USED.sql` (and `scratch-db/archive/`) | Abandoned designs. **Never apply.** |

---

## 3. THE TRANSFER CASE, EXPLAINED IN FULL (reused from the earlier handover, patched for r2_08 to r2_11)

### 3.1 The idea in plain words

The meetup is limited to a hall of 150. People cannot get refunds, only **transfers**: a ticket holder who cannot come hands the seat to someone else. The organisers handle this by **phone**; the app records it and makes it safe. There are two kinds, but one single flow of screens:

- **Private transfer:** the two people already know each other. Money is settled **between them**; the organisers are never involved in money.
- **Public transfer:** the seller has no buyer. The organisers find one, collect the money, and pay the seller. They are intermediaries.

**The same code flow serves both.** The seller fills a form and gets a short **code**. Someone gives that code to a buyer (the seller themself in a private case; an admin in a public case). The buyer types the code, fills a Transfer Form, and gets a **new Booking ID**. An admin phones the **seller's registered number** (this call is the real identity check), ticks a box, and presses **Transfer**. In one database step the seller's ticket is cancelled and a new ticket is issued to the buyer. The number of people in the hall never changes.

### 3.2 The objects involved

| Thing | Meaning |
|---|---|
| `transfers` | One sale of one seat. Columns: `kind` (`private`/`public`), `status`, `code`, `code_expires_at`, seller snapshot (`seller_name`, `seller_phone`), call tick (`seller_call_confirmed_at/by`), and for **public**: `seller_upi`, `amount_due`, `payment_requested_*`, `payment_screenshot_path`, `payment_submitted_at`, `payment_verified_*`, `amount_received`, `seller_paid_*`, `payout_reference`, `return_due`, `returned_*`, `return_reference`. Admin-read-only. |
| `transfer_buyers` | The buyer's form (name, phone, email (may be empty when the Email switch is OFF), location, attendance, food, consent, `booking_id`). Admin-read-only. |
| `bookings.kind` | `registration` (normal) or `transfer` (a buyer's booking: **amount 0, no screenshot, no ticket until approved**, never counts as a seat or as income). |
| `tickets.transferred_out_at` | Set on the seller's ticket when it is transferred away. The row **stays**, with its number retired forever. **Every count of people must ignore rows where this is set.** |
| `tickets.transferred_from` | On the buyer's new ticket: points to the seller's old ticket. Used by the gate to follow a seat that moved more than once. |
| `ticket_emails` | Admin-only table (`ticket_id`, `email`). `tickets` has NO email column (emails were moved out on 24 Oct so gate staff cannot read them). Filled by `submit_booking` and the Transfer step. When the Email switch is OFF nothing is asked or stored; emails already collected stay. |
| `booking_ips` | Admin-only IP per registration (flag only). |
| `settings_log` | Every transfer step is written here (`area = 'transfer'`), with who did it, never with phones, emails, UPI IDs or QR secrets. |

**`transfers.status` values in use:** `code_active` (seller made a code, no buyer yet), `pending_admin` (buyer applied, waiting for the admin), `done`, `rejected`, `withdrawn` (closed automatically, e.g. the seller's booking was rejected), `replaced` (a newer code for the same seat). Only one of `code_active`/`pending_admin` can exist per seat (database-enforced).

**`transfer_buyers.status`:** `active` (applied) → `done` / `rejected` / `released`.

### 3.3 Who can do what (permissions)

- **Visitors (no login):** only the functions in section 7.1. They can never read any table.
- **Gate staff:** can read `tickets`/`bookings` (existing rule) and use `admit_ticket`. They see **zero rows** of the new transfer tables and of `booking_ips`.
- **Admins:** read all transfer tables and call the `admin_*` functions. **One admin will do the transfer work in practice; every admin has the authority.** Every admin function checks `is_admin()` itself.

### 3.4 Scenarios (each lists what happens, what changes, what the screens must show)

**S1. Private transfer, normal case** (money between seller and buyer)
1. *Seller* (Asha, ticket E26-001, Booking ID `A`, phone P1) opens Tickets, Transfer tickets, Private, **Sell**, enters Booking ID + ticket number + phone. `private_sell` creates a `transfers` row (`private`, `code_active`, code valid `private_code_hours`: 2 h by default in the database; the owner set 24 h in Admin → Settings → Transfers). Screen: the 6-character code and when it expires (alphabet `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`: no 0, O, 1, I).
2. Asha tells the buyer the code by herself (WhatsApp, etc.).
3. *Buyer* opens Private, **Buy**, types the code: `transfer_open` returns `{ok, mode:'private', seller_name, expires_at, food_locked, food}`. The buyer fills the Transfer Form (name, phone, email, location, attendance, food, consent tick that money is between the two people) and sends `transfer_submit`. Result: a **new Booking ID** (kind `transfer`, pending), the transfer becomes `pending_admin`. Screen: "The organizers will be notified…", the Booking ID (saved on the device), a Contact now button. **No ticket, no seat, no change to any count yet.**
4. *Admin* sees the pending transfer: the original ticket beside the buyer's details. Phones the **seller's registered number** (not the number typed in any form): "Shall I transfer this ticket to Mr. B? We assume the payment is settled between you." Ticks the box (`admin_transfer_confirm_call`).
5. *Admin* presses **Transfer** (`admin_transfer_approve`). One transaction: re-checks the seller's ticket is still valid and **not checked in**; creates the buyer's ticket with the **next guest number** and a new QR secret in the buyer's booking; sets the seller's ticket `transferred_out_at`; marks the buyer's booking paid and numbers it with the normal rule; transfer becomes `done`; writes the log.
6. Result: seller's lookup shows the ticket as transferred (no QR); buyer's lookup shows the new ticket; the gate shows the old QR as CANCELLED (naming the current holder); all counts unchanged.

**S2. Public transfer, normal case** (money through the organisers)
1. *Seller* chooses Public, **Sell**: Booking ID, ticket, phone **and payout UPI ID** (or 10-digit phone). **No price.** `public_sell` makes a `public` code (same lifetime rules).
2. *Admin* sees every active code in the Transfers tab (both kinds). The seller usually contacts the admin; the admin finds a buyer and gives them the code. If finding a buyer takes days the admin **extends** the code (`admin_transfer_extend_code`, 1 to 168 hours; also revives an expired code).
3. *Buyer* types the code and fills the Transfer Form (no payment yet). Gets a new Booking ID; the buyer's status page shows "pending".
4. *Admin* phones the seller (is the ticket still theirs? reads back the payout UPI ID), ticks the call, presses **Ask buyer to pay** (`admin_transfer_request_payment`). `amount_due` is fixed to the standard `price_per_head` at that moment.
5. *Buyer's* status page (Booking ID + phone) now shows **Pay ₹X** with the UPI QR (from `get_payment_info`) and a screenshot upload. The page uploads the image to the `payment-proofs` bucket as `<submission_id>.jpg` and calls `transfer_pay`.
6. *Admin* checks the bank and enters the amount **actually received** (any amount from 1 to 1,000,000; more or less than asked is fine): `admin_transfer_verify_payment`.
7. *Admin* presses **Transfer**: needs **both** the call tick **and** the verified payment. Same swap as S1.
8. *Admin* pays the seller **exactly the amount received** and marks it with a reference (`admin_transfer_mark_paid`).
9. The **Transfer money panel** (`admin_transfer_money`) shows: awaiting payment, awaiting verification, verified and waiting for Transfer, to pay out, paid out, return due, returned, **held now**. The buyer's money never enters the registration revenue (their booking has amount 0).

**S3. Public transfer fails after the buyer paid** (the money must go back)
- *Cases:* the seller walked into the hall (Transfer refused: `SELLER_CHECKED_IN`), the seller's booking was rejected by an admin (the transfer closes **automatically**), the admin rejects it (wrong person, seller unreachable), the amount is wrong.
- *What happens:* `admin_transfer_reject` (or the automatic close) sets `return_due = true` **if a screenshot was uploaded**. The panel shows it under "return due". The admin sends the money back and records it with `admin_transfer_mark_returned(transfer, reference)` (a reference like "no money received" is acceptable). The buyer's page shows `return_due` then `returned`. The seller's seat is untouched and they can start a new transfer.
- *If the buyer never uploaded a screenshot:* no return is created.

**S4. The hall is full** (the normal reason transfers exist)
- Registrations are refused (`NOT_ENOUGH_SPOTS`), but a transfer is a **swap**, not a new seat, so it must always work. Tested: with the cap reached, Transfer works and the hall stays exactly as full; a normal registration is still refused afterwards.

**S5. A seat moves twice or more.** The buyer has a Booking ID, ticket number and phone, so they can sell on like any ticket (owner's decision). The old tickets keep their retired numbers; the gate follows `transferred_from` links to name the **current** holder.

**S6. Code problems.** A second request for the same seat **replaces** the old code (the old one stops working, even across private/public). The seller can cancel an active code (`transfer_cancel`); once a buyer applied only an admin can end it (`CONTACT_ADMIN`). Wrong, expired, used, replaced or cancelled codes all answer exactly `INVALID_CODE`. Two buyers racing for one code: the first valid submission wins (tested with 8 at once). The same form sent twice returns the same Booking ID.

**S7. Rules that block a transfer** (shown to the seller only after the three details matched): `NOT_CONFIRMED` (booking not paid), `ALREADY_CHECKED_IN`, `ALREADY_TRANSFERRED`, `TRANSFERS_CLOSED`, `CUTOFF_PASSED` (after `transfer_cutoff_at` no new code, buyer form or payment upload; admin actions on existing transfers continue). A seller with wrong details always gets exactly `MISMATCH` and learns nothing. **Coordinator tickets CAN be sold** (owner decision 25 Oct 2026, built in `r2_08`): the buyer always becomes a normal GUEST (only an admin can make a coordinator), the coordinator's guest number and coordinator number are both retired for good, and an admin can no longer change the coordinator status of a ticket that was already transferred away (`ALREADY_TRANSFERRED`). There are no free passes: guests of honour enter without registration or gate checks and are outside this app.

**S8. Food lock.** Once the food order is placed the admin turns on `transfer_food_locked`: the form hides the food choice and the buyer gets the **seller's** food.

**S9. Gate day.** `admit_ticket` on a transferred-out ticket returns `cancelled` with the **current holder's name and ticket label** and the old label. The new ticket admits once, then `already_scanned`. Gate staff searching by name can still find retired tickets (see section 4, Gate).

**S10. Abuse and mistakes.** Seller and buyer never see each other's phone, email, Booking ID or ticket number (the seller sees the buyer's **name** after they applied; the buyer sees the seller's **name** when the form opens). Guessing: Booking ID (8 hex) + phone, or a 6-character code (about a billion combinations), is not throttled by owner's decision because the admin's phone call to the seller stops a wrong taker. IP flag: registrations record the visitor's address; admin sees addresses with 5 or more registrations; **never blocks**.

**S11. Cleaning test data before launch.** Transfer rows are removed with their tickets/bookings by foreign keys; `settings_log` is not cleared (fine); also empty the `payment-proofs` bucket. `admin_clear_client_ips()` deletes all stored IPs after the event.


---

## 4. THE PAGES AS BUILT (updated 28 Oct 2026)

> **9 Nov 2026:** this section describes the pages as of 28 Oct. Since then the public Home, the ticket, the registration form and the whole staff page layout were redesigned (see the 9 Nov block at the top). The code is the truth: read `index.html` and `admin/index.html` before relying on a screen description here.


All three are single HTML files with inline JavaScript and the Supabase client `db`, drawing views by building HTML strings. Only the public publishable key is in them (safe by design). Everything that changes data goes through database functions.

### 4.1 Public page `index.html`
- **Look (second restyle, 27 Oct 2026, modelled on the owner's "Join the Event Team" page):** page `#081020`; a navy hero gradient (`#000838` to `#081860`) with two soft discs behind the heading; dark cards `#101838` with a 3 px amber (`#F0A000`) top edge; amber primary buttons with dark text; five accent colours (pink `#D82890`, violet `#7820E0`, teal `#20C8A0`, blue `#3050F0`, orange `#E86818`) used for the option chips (outlined, filled when chosen), the small bar before a card heading and a thin stripe under the header; font **Manrope** for everything on screen. **Fraunces and Jost are still loaded on purpose: the ticket IMAGE (drawn on a canvas) still uses them and is unchanged.** Home keeps a navy invitation card with the logo. Motion: cards below the fold fade and rise in on scroll (`reveal()`; switched off for reduced motion), heading bars grow from a dot, chips pop when chosen, buttons lift on hover. Dark only (no light mode). CSS variables: `--bg`, `--card`, `--ink`, `--mute`, `--brand` (blue), `--accent` (amber), `--pink`, `--violet`, `--teal`, `--orange`. Logo files in `assets/`: `logo-mark.png` (transparent), `icon-192.png`, `apple-touch-icon.png`, `og-image.jpg` (the WhatsApp preview). The owner has not supplied an SVG.
- **Phone first:** the layout was checked at 390 x 844. Review shows each person as a stacked card (no table, so nothing overflows); below 480 px buttons use less padding so labels like "Download QR" stay on one line; option chips are about 44 px tall; the consent checkbox is 22 px and amber; `main` keeps the safe-area padding.
- **Wording (27 Oct 2026):** all visitor text was rewritten to be clearer and more professional (registration, review, payment, done, tickets, closed and error screens, the transfer screens and the shared error messages in `XERR`). Meaning and rules did not change. Note for later edits: **`scratch-db/browser/run_public.py` has many checks that look for exact sentences; update them with any wording change.**
- **Startup order (29 Oct 2026, part B):** the two library tags (`#qr-lib`, `#sb-lib`) are `async` in the head. `libReady()` resolves when a tag loaded, failed, or after 20 s; `db` is a wrapper object, not the Supabase client (the client is created on the first call, in `sbGet()`), and answers `{error:{message:"no client"}}` if the library never arrives, which every caller already treated as a failure. `loadEvent()` starts its 2.5 s limit only after the library is there, so a slow download no longer loses the live date. **Any new code that uses `db.auth`, `db.from` or another client method must add it to the wrapper first.** Any new code that draws a QR must go through `whenQR()` (or `await qrReady`).
- **Home motion (30 Oct 2026):** see the update line at the top of this file. `HomeFX.mount()` is called by `render()` for Home, `HomeFX.unmount()` for every other step; the entrance title is split into letter spans once per visit (the `h1` keeps its text and an `aria-label`). Do not give the particle canvas (`#fxc`) a z-index above `main` (a test paints it red to prove it cannot reach a card).
- **Home updates in place (29 Oct 2026):** at start the page draws Home once with the built-in text (`CONFIG`), then `refreshHome()` patches the live date, time, venue and the About button into that same card when `get_event_info` and `get_site_flags` answer. The payment details do not touch Home (it shows none), so only the closed and done screens redraw for them. Do not call `render()` for Home when data arrives: it restarts the fade-in and the logo and scrolls to the top.
- **Flags (changed Nov 2026):** `loadFlags()` still calls `get_site_flags()` into `S.flags`, but nothing reads it any more: since `r2_15` and the admin redesign the About link is always on, the Email box is never asked and the feedback card is always on. The database switches `show_about`, `ask_email` and `ask_feedback` and their admin functions still exist.
- **Views (`S.step`):** `loading`, `home`, `about` (says "Coming soon" until the owner sends content), `closed`, `error`; registration: `form` (1 to 5 people, fixed "+91" box, Email right after Phone when the switch is on), `summary`, `pay` (UPI QR drawn in the page with the logo in a round patch, copy UPI ID, share/download QR, screenshot upload), `done` (Booking ID, "Pending verification", then the optional "Share your thoughts" feedback card; no Name/Food table); `tickets` (Booking ID + phone, saved Booking IDs as tap-to-fill chips, never the phone), `ticket` (tickets drawn on a canvas, JPG/PDF; a navy header with the logo; guest badge amber, coordinator badge ivory with maroon accents; no Booking ID drawn on the ticket); transfers: `xmenu` (Transfer tickets, shown only when `get_transfer_info().open` and the cut-off has not passed), `xsell` (seller form, private or public), `xcode` (the seller's code, its expiry and a Copy button; the seller's later status and a Cancel-code button appear on the Tickets page for a confirmed booking, via `transfer_status` and `transfer_cancel`), `xbuy` (type the code; ONE "I want to buy" button, the code itself decides private or public), `xform` (Transfer Form), `xdone` (the buyer's new Booking ID), `tpay` (public buyer: amount, UPI QR, screenshot upload).
- **On the device:** only Booking IDs are remembered (`mm_mine` up to 20, `mm_hist` up to 10, `mm_last`). The phone number is never stored.
- **Payment QR with the logo (27 Oct 2026):** `drawQR()` draws the QR with error-correction level **Q** and a navy circle 24% of the QR's width carrying the logo (`paintLogo`, logo preloaded as `QRLOGO`). Used by the Pay and transfer-Pay screens, so also by Share QR and Download QR. The TICKET QR (`drawTickets`) is unchanged. Tested with the real `qrcode-generator` and three decoders (OpenCV, ZXing, jsQR) on five UPI links at several sizes, blurred and as JPEG: readable up to about 28% (square patch), failing from 35%; an oversized circle fails every copy. **Level H was tried and is WORSE**: the QR gets so dense (up to 65 x 65 modules) that decoders miss it even without a logo. Do not enlarge the logo or change the level without re-running that test (method in section 9). The owner scanned the QR in several UPI apps on 27 Oct 2026: it works.
- **Resubmit rule:** `S.sid` (the submission ID) is the idempotency key of `submit_booking`. After a SUCCESSFUL booking `resetBookingForm()` clears the form and the ID; a FAILED send keeps the same ID on purpose (no duplicate bookings). This was a real bug fixed on 26 Oct.
- **Daily pause + 10-minute grace** and the heartbeat every 30 seconds are unchanged from Release 1 (notes section 8).

### 4.2 Staff page `admin/index.html` (admin dashboard + gate scanner, one login; rebuilt 27 to 28 Oct 2026)
One email-and-password login for everybody. **Admins** get the dashboard tabs; **gate staff** see only the Gate tab (counts, camera, Find a person, Admitted list; no amounts, emails or payment details). The roles are still just `admin` and `gate` in the `staff` table; the owner decided on 28 Oct 2026 to keep access as it is (a 0-to-3 access-level idea was dropped). **Look:** dark green "Midnight Emerald" rebuilt to match the public page (page `#04140F`, cards `#0A2219` with a coloured top edge, brand green `#2FD39B`, amber accent, font **Manrope**, rounded corners, tabs that scroll sideways and stay pinned on a phone). Designed for **phone and laptop equally**. The page still loads on a database that lacks a newer piece (it hides the tab or card instead of crashing). Counts are computed in the browser and **ignore retired tickets**; transfer bookings are hidden from Bookings and from the OCR queue.
- **Previews and the back gesture (28 Oct):** tapping a card, a name, a Booking ID or "and N others" opens a **preview sheet** (bottom sheet on a phone, side panel on a laptop) instead of changing tab. Every sheet and every tab change is a browser-history step, so the phone's back gesture closes the sheet or returns to the last tab with the scroll position. Sheets stack (card, person, booking, person) and **Back** unwinds them. Deeper links ("Open in People tab ›", "Open in Bookings tab ›") change tab, highlight the card, and back returns to the earlier place with the same sheet open. The header **Find** button opens a search sheet (name, phone, ticket or Booking ID) from any tab. Code: `nav`, `openSheet`, `gotoTab`, `pSheet`, `bSheet`, `lSheet`, `renderSheet`.
- **Overview:** six cards (Active tickets, Spots used with a progress bar, Pending, Expected total, Present at event, Coordinators). **Each card opens the list behind its number with the working** (for example "₹750 confirmed + ₹0 pending = ₹750", booking by booking). Three **full pie charts** (Food, Location, Attendance; Chart.js, percentage on each slice, an HTML legend, drawn at 2x sharpness) with a switch between Confirmed + Pending and **Confirmed only** (use this for final food and hall numbers). Pie slices are NOT yet tappable (the owner left that out on 28 Oct). The IP banner's network addresses open the bookings behind them. The registration status banner and the payment-details-changed banner are unchanged.
- **Bookings:** one **card** per registration booking (code, time, amount, status, people as links, OCR-read transaction ID, review flags with tappable booking codes, big Screenshot / Paid / Reject / Pending buttons). Status chips Pending / Paid / Rejected / All with counts, a search box, "Needs review only". Pending first, newest first.
- **People:** one **card** per person (tap-to-call phone, tap-to-mail email, location / attendance / food tags, booking-ID chip that opens the booking preview, Make / Remove coordinator, Present with Undo); a collapsible **Filters** panel (payment, food, location, attendance, **Present / Not present yet**, type, show transferred tickets); the shown and present counts; **Download Excel (CSV)** with an Email column; retired tickets dimmed as Transferred.
- **Gate tab (merged 28 Oct 2026):** live counters (Present / Confirmed, Veg, Non-veg; paid bookings only, retired tickets ignored; refreshed every 30 seconds while the tab is open); camera scan (jsQR) of `E26-007|<12 hex>` or `E26-001C|<12 hex>` (anything else shows NOT A TICKET); **Find a person** (at least 2 characters; tapping Open then Admit skips the QR checks; a retired ticket shows a Transferred pill, never an Admit button); the **Admitted (N)** list, latest first, with name, ticket, Booking ID and entry time, whose names open the same person / booking previews (a person's preview has an **Admit** button when they are not in yet). The camera turns **off when you leave the tab**. **Result screens no longer close by themselves** (ADMITTED, ALREADY SCANNED, PAYMENT PENDING with Approve and admit (admins only since `r2_16`: a gate account sees a note to ask an admin, and the database refuses with `ADMIN_ONLY`), PAYMENT REJECTED, TICKET CANCELLED, INVALID TICKET, COULDN'T CHECK): buttons **Next scan** (closes and starts the camera if it is off), **Home page** (closes and turns the camera off) and, on ADMITTED only, **Undo** (asks first, then calls `gate_undo_checkin`, falling back to `undo_checkin`). **Gate staff can undo for 2 minutes, admins any time**; after 2 minutes the page says "ask an admin" without calling the database. **Camera permission:** the button shows Asking, then Try again after a denial with plain steps (browsers decide whether the prompt returns; a page cannot force it) and the camera starts by itself if the permission is allowed later. The only functions the Gate tab calls are `admit_ticket` and the undo functions. Gate staff load only a few columns of `tickets` and `bookings`.
- **Transfers** (appears only once the database has the transfer tables; shows the number waiting): the money cards **each open the list of transfers that add up to the amount** (the list checks itself against the card and warns if they differ), seller and buyer names are previews, waiting transfers (call tick, Ask to pay, verify the amount received, **Transfer**, or Reject), active codes with Extend and Cancel, seller payouts, buyer returns, history.
- **Scan screenshots:** OCR runs in the admin's browser (nothing leaves the computer) and saves transaction IDs, an image hash and amounts; the three counts (not scanned, unreadable, scanned) open their booking lists.
- **Feedback** (appears only when the feedback table exists): answers with the average and a 1-to-5 split (the rating counts open the answers); "Name and N others" opens the booking and everyone in it; booking codes open the booking preview.
- **Settings:** a responsive grid of cards (one column on a phone) with a jump bar: Registration settings (open, daily pause, cap, price, deadline), Payment details (locked until **Change** is pressed; the other admin sees a banner for 7 days after a change), Event details, Ticket transfers, Repeat-registration flag (IP threshold), About link, Email box, Feedback questions, a "Before you open registration" checklist and the Settings log (permanent: nobody can clear it). A live status banner (open / paused / closed, and how many people are inside their grace minutes) refreshes every 15 seconds.
- **Code map (inline script):** `S` is the state object; `load()` reads everything for admins; `view()` draws the header and tabs and calls `vOverview`, `vGate`, `vBookings`, `vPeople`, `vTransfers`, `vScan`, `vFeedback`, `vSettings`; `nav()` / `openSheet()` / `gotoTab()` / `popstate` handle the back gesture; `pSheet`, `bSheet`, `lSheet` build the previews (`lSheet` keys: `active`, `spots`, `pending`, `expected`, `present`, `coords`, `t_<money key>`, `fb:<n>`, `scan_un|scan_bad|scan_all`, `ip:<address>`); the gate code is the `g...` functions (`gLoad`, `gSync`, `gCounts`, `vGate`, `gResults`, `gAdmitted`, `gShow`, `gResult`, `gAdmit`, `gUndo`, `gCamStart`, `gCamStop`, `gCamAttach`, `gAct`). Chart.js draws the pies; the page's own `.sheet` CSS draws previews.
- **Reading rules:** it reads these tables directly (allowed to staff by row-level security): `bookings`, `tickets`, `screenshot_scans`, `settings`, `settings_log`, `staff`, and (admins only) `ticket_emails`, `transfers`, `transfer_buyers`, `booking_feedback`. **Gate staff** load only `tickets` (id, numbers, name, phone, food, booking, check-in, retired flag) and `bookings` (id, code, status) and their previews hide location, attendance, email, amounts, payment ID and screenshots.
- **Test selectors you may need:** the Overview cards are `.card.stat` (first `span` is the label, `b` the number); the booking and people lists are inside `#tbl` (cards `.bk` and `.pc`); the Gate tab uses `#counts`, `#camtoggle`, `#gfq`, `#gres`, `#admlist`; sheets are `#sheetbg`; result screens are `.ov`.

### 4.3 Gate (now a tab of the staff page; `gate/index.html` only forwards)
- See 4.2, "Gate tab". The old stand-alone page had its own look (light/dark Midnight Emerald), an auto-closing ADMITTED screen and no admitted list; all of that was replaced on 28 Oct 2026 (PRs #26 to #28).
- `gate/index.html` is a 0.6 KB page with a meta refresh and `location.replace("../admin/#gate")`, so printed links and bookmarks still work. Opening `/admin/#gate` as an admin selects the Gate tab; a gate account always lands on it.
- Counters and search **ignore retired tickets** (`transferred_out_at`, with a retry without the column on an older database). Search shows a retired ticket with a Transferred pill and the note "Ask for their current ticket", never an Admit button.
- Functions called: `admit_ticket`, `gate_undo_checkin` (falls back to `undo_checkin` when the first does not exist), and, for the payment screenshot on a pending result, the `payment-proofs` storage bucket's signed URL.

---

## 5. SETTINGS AND SWITCHES

| What | Column in `settings` | Changed by (admin only, logged) | Visitors read it through |
|---|---|---|---|
| Registration open, cap, price per person, deadline, daily pause | `is_open`, `cap`, `price_per_head`, `deadline`, `pause_*`, `closed_at`, `grace_minutes` (fixed 10) | `admin_update_settings` | `get_public_status` |
| Event date and venue | `event_at`, `venue` | `admin_set_event` | `get_event_info` |
| UPI ID, payee name, WhatsApp number | `upi_id`, `payee_name`, `whatsapp_number` | `admin_set_payment_info` (format-checked; a banner shows the other admin for 7 days) | `get_payment_info` |
| Transfers on/off, cut-off time, food lock, code lifetime (1 to 168 h), IP flag threshold (2 to 1000) | `transfers_open`, `transfer_cutoff_at`, `transfer_food_locked`, `private_code_hours`, `ip_flag_threshold` | `admin_set_transfer_settings` (refuses to switch transfers ON while the UPI ID, payee name or WhatsApp number is missing: `PAYMENT_INFO_MISSING`) | `get_transfer_info` (not the threshold) |
| About link | `show_about` (default ON) | `admin_set_show_about` | `get_site_flags` |
| Email box | `ask_email` (default ON) | `admin_set_ask_email` | `get_site_flags` |
| Feedback questions | `ask_feedback` (default ON) | `admin_set_ask_feedback` | `get_site_flags` |
| (unused) | `max_resale_price` | nobody | nobody |

**Since `r2_15` (Nov 2026) these three switches are fixed in the database (About on, Email off, Feedback on) and neither page reads them; the paragraph below describes how they worked before.** Another switch, `settings.show_messages` (default OFF, `admin_set_show_messages`), decides whether tickets show the game message and the picked-people line. The organiser contacts (up to three, `contact1_name`, `whatsapp_number`, `contact2_*`, `contact3_*`) are set with `admin_set_contacts` (contact 1 required, numbers 11 to 15 digits).

Switch behaviour: **Email OFF**: forms hide the box, no email is asked or stored, emails already collected stay (admin-only). **Feedback OFF**: the questions are hidden and `submit_feedback` answers `FEEDBACK_OFF`; saved answers stay. Feedback is one row per registration booking (rating 1 to 5 and/or a comment up to 1000 characters; sending again replaces it), readable by admins only. `ticket_emails`, `transfers`, `transfer_buyers`, `booking_ips` and `booking_feedback` are admin-read-only; gate staff see zero rows. Values at the last record (14 to 16 Oct, notes section 1): cap 150, price ₹250, deadline 31 Oct 2026 23:59:59 IST; the owner set the transfer code lifetime to 24 hours. **Read the live values in Admin → Settings; the database is the truth.**

---

## 6. DECISIONS AND HISTORY

### 6.1 Owner decisions made 25 to 26 Oct 2026 (they replace the defaults of the old section 8)
1. Money is returned to a public buyer who paid when the transfer fails (recorded as a return with a reference; normal registrations stay no-refund).
2. Transfer codes last 24 hours (setting; the admin can also Extend any code up to 168 h).
3. No extra spam protection for now (the IP flag only; it never blocks).
4. Waiting transfers do not expire by themselves (the admin sees the age).
5. **Coordinators can transfer their ticket** like anyone else (`r2_08`).
6. **There are no free passes**: guests of honour enter without registration or gate checks, outside this app.
7. Seller and buyer see only each other's NAME (never phone, email, UPI, ticket number or Booking ID).
8. The text says the organisers "may call" (not "will call").
9. The two "I want to buy" buttons were merged into one (the code decides private or public; a private code typed in the public flow works by design).
Earlier, still binding: emails admin-only in their own table (G3); Booking ID + phone for ticket lookup; a received ticket can be sold on; no marketplace; tap-to-pay `upi://` links must never return; no Booking ID on the ticket image; numbers are never reused (notes section 9).

### 6.1b Owner decisions of 27 Oct 2026
1. The **public pages** take the look of the owner's "Join the Event Team" page and are **phone first**. **Admin and Gate were not to change at that time** (they kept Midnight Emerald); this was **superseded on 27 to 28 Oct 2026**, see 6.1c.
2. Public text should be clear, short and professional. The owner's example: the feedback box says "Please share a few words about the program" with a placeholder ("It could be anything: your suggestions, expectations, ideas and more. This helps us run the program better!"). Two sentences that the old tests called "exact" were reworded in the same pass: the Request-received line (now "The organisers have been notified of your request and will take the next steps shortly.") and the mismatch message (now "The details don't match. Please check the Booking ID, the ticket number and the phone number registered for that ticket."). The owner may ask to revert them.
3. The **logo goes on the PAYMENT QR only**, in a circle in the centre; never on the ticket QR.
4. The **Done screen**: no Name/Food table; "Share your thoughts" sits below "Pending verification".
5. The About page stays a placeholder ("Coming soon") until the owner sends the content.

### 6.1c Owner decisions of 27 to 28 Oct 2026
1. The **admin page** is restyled to match the public pages, in **green**, for **phone and laptop equally**, done **stage by stage** (header and tabs and Overview, then Bookings, People, Settings), with **full pie charts**.
2. **"Easy data access":** every number must show how it was reached (names, phones, amounts); names, Booking IDs and "and N others" are links; the first step is a **preview**, and only a deeper step goes to the tab; **the back gesture must return to the previous place**. The pie slices were left out.
3. **Gate:** results must **not** close automatically; three buttons **Next scan / Home page / Undo**; an **Admitted list** below Find a person (name, entry time, Booking ID, latest first) whose names open previews; the camera must ask permission again after a denial (what is possible is limited by the browser).
4. **Undo:** gate staff for **2 minutes**, anything later needs an admin.
5. **Merge gate and admin into one page**; access stays **admin and gate** (a levels 0 to 3 design with an Access tab and a clearable settings log was reviewed and dropped; the log stays permanent).

### 6.2 What happened
- **16 to 17 Oct:** Release 1 done; Release 2 designed and its database part written and tested on a scratch Postgres (pieces 1 to 5).
- **23 to 24 Oct:** first handover written; emails moved to `ticket_emails`; piece 6; all three pages rewritten; 572 database checks + 108 browser checks.
- **25 Oct:** rollout with the owner: snapshot, `r2_01` + `r2_02`, pages published (PR #1, then PR #2 for the "New Booking ID" line), `r2_02b` to `r2_06`, snapshot comparison (identical), rehearsal on the real site (registration with email and +91; lookup by Booking ID + phone; private transfer; public transfer with screenshot, verify, transfer, payout; reject path; gate refused the old QR and showed retired tickets as Transferred). The real visitor IP showed in both `cf=` and `xff=` of `booking_ips.raw`, so the IP-header question (G10) is closed. Test data was cleaned with `r2_07` and the `payment-proofs` bucket emptied.
- **25 to 26 Oct:** `r2_08` (coordinators), amount-difference warning, About link (`r2_09`), restyle with the logo (public) and Midnight Emerald (admin, gate), Email switch (`r2_10`) and the email-after-phone order, feedback (`r2_11`), the resubmit fix, the "and N others" wording. Each was a branch + pull request merged by the owner; rule used: **run the SQL FIRST, then merge the PR** (the pages cope with the database being one step behind).
- **26 to 27 Oct (the next session):** push access to the repo was attached; the three browser suites were re-run (101 / 47 / 9); the public pages were restyled (PR #13), reworded and fixed for phones (#14), the Done screen was changed (#15), the payment QR got the logo (#16, then a round patch in #17), and the transfer screens and About page were reworded (#18). Each was a branch + pull request merged by the owner. No SQL was run.
- **27 to 28 Oct:** PRs #19 (docs), #20 (admin theme, header, tabs, Overview, full pies), #21 (Bookings cards), #22 (People cards and filters), #23 (Settings grid), #24 (preview sheets, back gesture, Present filter), #25 (every card's list, linked names, Find), #26 and #27 (gate flow, admitted list, camera retry, 2-minute undo plus `r2_12`), #28 (gate merged into the staff page). SQL run by the owner: `r2_12_gate_undo.sql` only. Claude worked on a branch per step; the owner merged each pull request; the Stop hook's "unpushed commit" warnings were false alarms every time (verify with `git ls-remote --heads origin <branch>` against `git rev-parse HEAD`).

---

## 7. API REFERENCE (from the live snapshot of 26 Oct 2026, patched 9 Nov 2026 for the functions added or changed since; real responses in Appendix B)

### 7.1 Visitor functions (anyone with the public key)

Seller, buyer and feedback functions never raise for user mistakes; they **return** `{ok:false, error:'CODE'}` (one shape for the page). Lookups return `{found:false}` for every kind of wrong input.

| Function | Parameters | Success |
|---|---|---|
| `get_public_status(p_session)` | session uuid or null | registration state, spots left, price, max group, pause info |
| `registration_heartbeat(p_session)` | | same JSON (daily-pause logic) |
| `get_payment_info()` | | UPI ID, payee name, WhatsApp number (null = not set up) |
| `get_event_info()` | | `event_at`, `venue` |
| `get_site_flags()` | | `{show_about, ask_email, ask_feedback}` |
| `get_transfer_info()` | | `{open, cutoff_at, cutoff_passed, food_locked, code_hours, ask_price, server_now}` |
| `submit_booking(p_submission_id, p_people jsonb, p_screenshot_path)` | 1 to 5 objects `name, phone (10 digits), loc, food, occ, occ_detail` (checked against the 9 Nov snapshot: no email and no attendance any more; `occ` is Article Assistant, Industrial Trainee, Employee, Student or Others; `occ_detail` is 1 to 100 characters) | the booking (code, status, tickets); **raises** on invalid input |
| `submit_feedback(p_booking_code, p_rating, p_comment)` | rating 1 to 5 and/or comment | `{ok:true}` or `{ok:false,error}` |
| `lookup_tickets(p_code, p_phone)` | Booking ID + 10-digit phone | `{found:true, kind, booking_code, status, people_count, amount_expected, tickets:[...]}`; transfer bookings also `transfer:{type, state, amount_due}` |
| `private_sell(p_booking_code, p_ticket, p_phone)` | ticket like `E26-001` | `{ok, code, expires_at, hours, ticket_label}` |
| `public_sell(p_booking_code, p_ticket, p_phone, p_upi)` | + payout UPI/phone | `{ok, mode:'public', code, expires_at, hours, ticket_label}` |
| `transfer_status(p_booking_code, p_phone)` | the seller | `{found, transfers:[...]}` |
| `transfer_cancel(p_booking_code, p_ticket, p_phone)` | the seller | `{ok}`; `CONTACT_ADMIN` once a buyer applied |
| `transfer_open(p_code)` | the buyer | `{ok, mode, seller_name, expires_at, food_locked, food?}` |
| `transfer_submit(p_code, p_submission_id, p_buyer jsonb)` | `name, phone, email (optional when the switch is off), loc, att, food (ignored when locked), consent:'true'` | `{ok, mode, booking_code, status:'pending', seller_name, food}` |
| `transfer_pay(p_booking_code, p_phone, p_submission_id, p_screenshot_path)` | public buyer, after payment was requested | `{ok, amount_due}` |

Screenshots go straight to the `payment-proofs` storage bucket (anyone may upload, only staff may read through short-lived signed links; size limit and image types enforced), named `<submission_id>.<jpg|png|webp>`.

### 7.2 Staff and admin functions (login required; each checks the role inside)
- **Staff:** `admit_ticket`, `save_scan`, `admin_registration_status`, `is_staff`.
- **Admin, existing:** `undo_checkin`, `set_booking_status` (refuses transfer bookings: `USE_TRANSFER_TOOLS`), `set_coordinator` (refuses a retired ticket: `ALREADY_TRANSFERRED`), `admin_update_settings`, `admin_set_event`, `admin_set_payment_info`, `admin_payment_alert`, `is_admin`.
- **Admin, Release 2:** `admin_set_transfer_settings`, `admin_set_show_about`, `admin_set_ask_email`, `admin_set_ask_feedback`, `admin_transfer_confirm_call(id, bool)`, `admin_transfer_extend_code(id, hours)`, `admin_transfer_request_payment(id)`, `admin_transfer_verify_payment(id, amount)`, `admin_transfer_approve(id)`, `admin_transfer_reject(id, note)`, `admin_transfer_mark_paid(id, reference)`, `admin_transfer_mark_returned(id, reference)`, `admin_transfer_money()`, `admin_ip_flags()`, `admin_clear_client_ips()`. **Added after 26 Oct (checked against the 9 Nov snapshot):** `gate_undo_checkin(id)` (r2_12); `admin_set_show_messages`, `admin_save_message`, `admin_delete_message`, `admin_assign_messages`, `admin_clear_messages` (r2_13); `admin_set_prizes`, `admin_clear_prizes` (r2_14); `admin_set_contacts(name1, num1, name2, num2, name3, num3)` (r2_17); `admin_preview_approval(ids)` and `admin_approve_bookings(ids, expected_next)` (r2_18, admin only). `admit_ticket` with approve on stops with `ADMIN_ONLY` for a gate account (r2_16). `get_payment_info` also returns `contacts`, a list of name and number.
- **Internal (not callable by anyone but the database owner):** 19 helpers such as `_assign_numbers`, `_booking_json`, `_client_ip`, `_find_seller_ticket`, `_tlog`. `_ticket_label` is callable by anyone (pure formatting, harmless). `rls_auto_enable` is Supabase's own event-trigger function.

- **`gate_undo_checkin(p_id uuid)`** (added 28 Oct 2026, `sql/r2_12_gate_undo.sql`; not in the 26 Oct snapshot the rest of this section was generated from): `NOT_ALLOWED` for non-staff; admins can clear any check-in; other staff only if it was made within 2 minutes, else `UNDO_EXPIRED`. Returns nothing. The older `undo_checkin(p_ticket_no, p_coord, p_id)` stays admin-only.

### 7.3 Rules the database enforces that the page need not repeat (but should mirror)

One open transfer per seat; a code is unique among active codes; Transfer needs the call tick (and, for public, a verified payment); the seller's ticket must be paid, a guest ticket, not checked in and not already transferred; a transfer booking never counts as a seat or as income; the swap uses the normal numbering rule (`_assign_numbers`) and never reuses a number; the cap is never checked at Transfer (it is a swap).


---

## 8. OPEN ITEMS AND RISKS

### 8.1 Open decisions and unknowns (ask the owner)
1. **Registration opening date and the deadline** (section 1, question 2). Owner, 26 Oct: not fixed; not to be considered for now.
2. **The pre-launch checklist** (section 1, question 3), including a real payment in a real UPI app (never verified). Owner, 26 Oct: not ready; sign-ups confirmed off; gate logins not created.
3. **Daily pause and transfers:** should transfers pause too? Default in use: no.
4. **About page content** (text, reels as links, photos with permission for faces) and the logo as an **SVG** (only a PNG exists). The About page currently says "Coming soon" (reworded 27 Oct 2026).
5. **After the event:** run `select admin_ip_flags();` once to review, then `select admin_clear_client_ips();` to delete every stored address. Decide what to do with emails, feedback comments and payment screenshots (nothing sends email yet; no retention rule exists).
6. **Staff:** the owner and one friend are admins; the two gate members and any other organisers are added at the end (notes section 2: Supabase Authentication user, then a `staff` row with the role written explicitly).

### 8.2 Status of the gaps found in the 17 Oct review
| ID | Finding | Status |
|---|---|---|
| G1 | No function to change the transfer settings | Resolved: `admin_set_transfer_settings` (r2_06) |
| G2 | No visitor-readable "are transfers open" | Resolved: `get_transfer_info` (r2_06) |
| G3 | Emails readable by every staff login | Resolved: separate admin-only table `ticket_emails` |
| G4, G5, G6 | Admin and gate double counting; admin lists transfer bookings; Tickets page auto-fetch | Resolved in the rewritten pages (browser suites re-run and passing on 27 Oct 2026) |
| G7 | Wrong rollout order breaks things | Done in the right order on 25 Oct. For any future piece: SQL first, then merge the page |
| G8 | Scratch copy did not reproduce old-table permissions | Resolved (`build.py` reproduces RLS and grants from the snapshot) |
| G9 | `_ticket_label` callable by anyone | Open, harmless |
| G10 | Which header carries the real IP | Closed 25 Oct (both `cf=` and `xff=` showed the real address; the code prefers `cf-connecting-ip`) |
| G11 | `baseline.py` obsolete | Done (deleted) |
| G12 | Pending transfers never expire | Owner decision: stays manual; the admin sees the age |
| G13 | Coordinator tickets cannot be sold | Resolved: they can (r2_08) |
| G14 | No rollback picture | The nightly snapshot history, `changes.sql` and the `rollout_A_*_APPLIED.sql` files |

### 8.3 New findings of this session (26 Oct 2026)
- **G15 (low, optional):** Supabase's default privileges (TRUNCATE, REFERENCES, TRIGGER, MAINTAIN) exist on a few older objects for the API roles: `keepalive` (anon and authenticated), `report` (anon), and for `service_role` on most tables. They are not reachable through the API (it cannot issue TRUNCATE) and the new tables carry only staff SELECT. If the owner wants it tidy: revoke truncate, references and trigger on `keepalive` and `report` from `anon, authenticated` in the SQL editor, then re-run the snapshot. **Not applied, not tested.**
- **G16:** the documents were stale (section 0.3). **Resolved 26 Oct 2026:** this file was rewritten and `PROJECT_NOTES.md` brought up to date.
- **G17:** `scratch-db/test_r2_08.py` and `test_r2_09.py` hardcode the SQL folder as `/home/claude/ca-meetup-register/scratch-db/`, so they fail unless copies of the SQL files are placed there (section 9 does this; do not commit those copies). Cleaner fix: make them use `/home/claude/ca-meetup-register/sql/` like `test_r2_10.py`.
- **G18:** the test counts in the old files said `test_r2_02` has 55 checks (572 in total); it has 54 (675 in total across all ten suites). No test fails.
- **G19:** the browser suites could not be run here. **Resolved 27 Oct 2026:** they run (Chromium is pre-installed; section 9).
- **G20:** the old recipe told the next session to use the CURRENT `schema_snapshot.txt` as the test base. That no longer works because it already contains Release 2; use the pre-Release-2 snapshot `161e7ed` (section 9).


---

### 8.4 Open after 28 Oct 2026

> **9 Nov 2026:** still open from this list: the real gate account test, the housekeeping and the owner's knowingly left gaps. New since: the lost `sql/r2_17_contacts.sql` and the out-of-date test counts (see the 9 Nov block at the top).

- **Real gate account:** none exists yet. Test with a real gate login on a phone: sign in at `/admin/` (it should show only the Gate tab), scan a real ticket, press Undo within 2 minutes (it should work) and after 2 minutes (it should say ask an admin), and try the camera permission flow (deny, then Try again).
- **`r2_12`:** in `sql/changes.sql` and confirmed in the 28 Oct snapshot. Its database suite now exists (`scratch-db/test_r2_12.py`, 56 checks, 29 Oct 2026). One behaviour worth knowing, found while writing it and not changed: a wrong id, an empty id and a ticket that was never admitted all raise the same `UNDO_EXPIRED`, so the Gate page's "ask an admin" wording also appears in those cases. The function also leaves no record of who undid what.
- **Gaps the owner knowingly left:** tappable pie slices; the Settings log is not linked; the Present card's "rejected: N" is not tappable.
- **Housekeeping still open:** about 24 merged branches on GitHub could be deleted; a real `README.md`; G15 and G17 (notes section 12); the About page content from the owner.

## 9. THE TEST ENVIRONMENT (rebuild in about 10 minutes; Claude's container is wiped between chats)

> **9 Nov 2026:** the commands and counts below are from 29 Oct (`test_r2_01` to `_12`, 731 checks). The repo now also has `test_r2_13`, `_14`, `_17` and `_18` and many more browser scripts (listed in the 9 Nov block at the top); none was re-run on 9 Nov, and `test_r2_17` cannot run until `r2_17_contacts.sql` exists again.


**Principle:** the test database is built from the **pre-Release-2** snapshot (commit `161e7ed`, 17 Oct 2026), then `r2_01` to `r2_11` are applied on top. The current snapshot already contains them. Run everything with bash. `github.com`, PyPI and npm are reachable; the repo is public, so no login is needed (a full clone, not a shallow one, because `git show` needs history).

```bash
mkdir -p /home/claude/sql /home/claude/scratch && cd /home/claude
git clone https://github.com/malluarticlesbengaluru/ca-meetup-register.git && cd ca-meetup-register
git show 161e7ed:sql/schema_snapshot.txt > /home/claude/sql/schema_snapshot.txt   # the BASE (pre-Release-2)
cp sql/r2_*.sql /home/claude/scratch/ && cp scratch-db/*.py /home/claude/scratch/
cp sql/r2_0*.sql sql/r2_1*.sql scratch-db/      # test_r2_08/09 look here (G17); do not commit these copies
apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql
pip install -q psycopg2-binary --break-system-packages
rm -rf /tmp/pgdata && mkdir /tmp/pgdata && chown postgres /tmp/pgdata
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /tmp/pgdata -A trust >/dev/null"
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/pgdata -o '-p 5544 -k /tmp' -l /tmp/pg.log start"
cd /home/claude/scratch && python3 build.py
for n in 01 02 03 04 05 06 08 09 10 11 12; do python3 test_r2_$n.py | tail -1; done
# expected: 62, 54, 153, 157, 77, 68, 36, 14, 26, 28, 56 passed (731), 0 failed
# (test_r2_12.py reads the SQL straight from the repo's sql/ folder; mutate_r2_12.py is the deliberate-mistake check for it)
```

**How the harness works** (`lib.py`): `fresh([sql files])` rebuilds the database from `build.sql` and applies the files; `seed()` makes an open event, one admin, booking A (Asha 9000000001, Ben 9000000002) and booking B (Carl 9000000003), all paid; `call(role, sql, params, uid, headers)` runs one statement as `anon`, `authenticated` (with `uid` as the logged-in user) or `postgres`; `call_new` + `par` run statements at the same instant on separate connections (race tests); `sql()` runs as superuser; `T` collects PASS/FAIL and **a script that crashes halfway counts as a failure**. `ensure_server()` restarts Postgres if it stopped. Test scripts hardcode `/home/claude/scratch` and `/home/claude/sql`.

**Replica quirks (patched in `lib.fresh`):** `settings_log.id` and `tickets.reg_seq` are identity columns in production but the snapshot does not show it; `report` is a view; `storage.objects` is a stub; the roles `anon/authenticated/service_role` and `auth.uid()` are stand-ins (user id from `request.jwt.claim.sub`; request headers from `request.headers`). `build.py` also reproduces the row-level security, policies and table grants of the old tables from the snapshot. Not reproduced: Supabase's default privilege letters (G15), storage policies, event triggers, `rls_auto_enable`.

**Gotchas that cost time before:** in `psycopg2` a literal `%` in a statement that has parameters must be `%%`; `ON_ERROR_STOP` makes a failing SQL file stop `fresh()`; the first pass of function creation may report an ordering error that the second pass fixes (expected); uuid values come back as strings.

**Comparing the real database with the tested one** (do this after ANY SQL goes live, as on 25 and 26 Oct): (1) ask the owner to run Actions → Database Snapshot → Run workflow, then `git pull`; (2) in the scratch folder run a script that calls `fresh([...all r2 files except r2_07, in order r2_01, r2_02, r2_02b, r2_02c, r2_03, r2_04, r2_05, r2_06, r2_08, r2_09, r2_10, r2_11])`; (3) take the SQL between `<<'SQL'` and `SQL` in `.github/workflows/schema-snapshot.yml`, remove the `STORAGE BUCKETS` query and the leading spaces, run it with `psql -h /tmp -p 5544 -U postgres -d postgres -X -A -t -v ON_ERROR_STOP=1 -f snap.sql > scratch_snapshot.txt`; (4) split both files at the `=== SECTION ===` lines and diff section by section. Expected on 26 Oct: identical except storage policies, event triggers, `rls_auto_enable`, storage buckets, and the privilege letters of G15.

**Browser suites (restored 27 Oct 2026):** `scratch-db/browser/run_public.py`, `run_admin.py`, `run_gate.py` (+ `admin_test.py`, `mock_supabase.js`, `chart_stub.js`) use Playwright with Chromium against a **mocked** Supabase and read the pages from `/home/claude/ca-meetup-register`. **Chromium and Playwright are pre-installed in the chat sandbox: just run them. Do NOT run `playwright install`** (it produced nothing and was the cause of the earlier belief that Chromium could not be installed). Run: `cd scratch-db/browser && python3 run_public.py | tail -1`, same for `run_admin.py` and `run_gate.py` (run these two WITHOUT `python3 -I`: they import `admin_test.py` from their own folder). **Result on 27 Oct 2026: public 101, admin 47, gate 9, all pass.** They prove the pages call the right functions with the right values and show the right text, not that the real database answers like the scratch copy. **When you change wording, update the matching `check(...)` texts in `run_public.py`.** **Since 28 Oct 2026: public 101, admin 73, gate 35.** The gate suite loads `admin/index.html` (the scanner is a tab there) and covers a gate account and an admin account; run admin and gate WITHOUT `-I` (they import `admin_test.py`) and delete the generated `__pycache__` before committing. **A seventh script, `run_pagefx.py` (30 Oct 2026, 26 checks), tests the motion on the other screens and the payment-screen change.** **A sixth script, `run_homefx.py` (30 Oct 2026, 38 checks), tests the Home motion** (entrance timing, particles behind the cards, ripple, row flash, desktop-only effects, reduced motion, clean unmount). **A fifth script, `run_qrimage.py` (29 Oct 2026, 32 checks), tests the Share/Download QR picture** (see the top of this file; it needs the npm setup line there). **A fourth script, `run_startup.py` (added 29 Oct 2026, 12 checks), tests how the public page starts up** (Home drawn once, live values patched in place, scroll kept, and in later parts a held-back or failed library). It does not inject a fake Supabase before the page starts; the library comes through the network route so it can be delayed. Run it the same way (`python3 run_startup.py | tail -1`); `PAGE=/path/to/index.html` tests another copy. Screenshots of the staff page: route `admin/index.html` with the `MOCK` from `scratch-db/browser/admin_test.py` (`open_page`) and set the viewport to 390 x 844 for a phone; `reduced_motion='reduce'` avoids half-faded cards.

**Phone screenshots:** load `index.html` through a Playwright route with the `MOCK` block copied from `run_public.py`; use a browser context with viewport 390 x 844, `device_scale_factor` 2, `is_mobile`, `has_touch` and `reduced_motion='reduce'` (otherwise the scroll-reveal cards stay hidden in a full-page shot); set the screen with `S.step='...'; render()` and take a full-page screenshot. Google Fonts are not reachable from the sandbox, so shots use a fallback font.

**QR check (do this again if the QR drawing ever changes):** in a blank Playwright page load the real `qrcode-generator` (npm), run the page's own `drawQR` (the text between `const QRLOGO` and `function toast(` in `index.html`), export the canvas as PNG and decode it with OpenCV (`cv2.QRCodeDetector`), ZXing (`@zxing/library` in node) and jsQR (`jsqr` in node), at full size, 300 px, 200 px, blurred and JPEG q35, on several realistic UPI links (long payee name, long UPI ID, an amount like 12345). Include one deliberately oversized logo, which must fail, to prove the test can fail. The scripts lived in the chat's scratch folder and are not in the repo; rewrite them from this description.

**The pattern for new SQL:** generate it from the real function text in the snapshot (`gen_r2_0X.py` extract it and patch only the needed lines, asserting each patch applies exactly once) so nothing else drifts; write the tests first as attacks; then do a **deliberate-mistake check** (copy the SQL, break one rule, confirm the suite fails; a green run alone proves little). After the owner runs it: paste it into `sql/changes.sql`, run the snapshot workflow, compare. A ready example of the mistake check: `scratch-db/mutate_r2_12.py` breaks `r2_12` in 16 ways, runs `test_r2_12.py` against each (that suite reads the SQL file named in the environment variable `R12`) and prints CAUGHT, SURVIVED or BROKEN for each.

---

## 10. HOW TO WORK WITH THIS OWNER

- Plain language, short steps, no jargon; they are a beginner. Give step-by-step instructions. Since 27 Oct 2026 Claude normally pushes a branch itself (section 10); when a file has to go through the GitHub web editor, give a **complete file**, never partial edits. Ask before changing behaviour they decided; record decisions in `PROJECT_NOTES.md`. State assumptions plainly.
- Never put secrets, keys, real phone numbers or UPI IDs in files (the repo is public). Never ask for the Supabase service-role key or the database password. The publishable key and project URL in the pages are safe by design.
- **Delivery (since 27 Oct 2026):** SQL goes into the Supabase SQL editor (tell them where to click and what "Success" looks like; send long SQL as a file). **Page and document changes: Claude has push access to the repo** (the owner attached it with the `add_repo` tool and access `push`; a fresh chat may have to do that again, then clone into `/home/claude/ca-meetup-register`). **Claude works on a NEW branch from the latest `main`, runs the tests, pushes the branch and gives the owner the link `https://github.com/rameezmunirrr-gh/ca-meetup-register/pull/new/<branch>`. The owner presses Create pull request, then Merge pull request.** GitHub Pages redeploys in about a minute, then the owner hard-reloads. If the branch is not merged yet and the owner asks for a follow-up on the same screen, add a commit to the same branch. Claude never pushes to `main`. **A "Stop hook" may say a branch "has unpushed commits and no remote branch": every time so far this was a false alarm.** Check with `git ls-remote --heads origin <branch>`; if the hash equals `git rev-parse HEAD` it is pushed. Rule from the earlier sessions still stands: **SQL first, then publish the page.** (Fallback if the repo is not attached: complete files uploaded in the GitHub web editor, files not folders; the trash-can icon on a GitHub file page DELETES the file.)
- Safety over speed. Credits matter to the owner: batch tool calls, avoid re-reading big files, finish a step and record it.
- Say plainly what was NOT verified after every task.

---

## 11. THE NEXT SESSION'S TASK LIST (in order, with "done when")

1. ~~Ask the section-1 questions.~~ **Done 26 Oct 2026** (answers in section 1).
2. ~~Bring `PROJECT_NOTES.md` up to date.~~ **Done 26 Oct 2026** (commit `b53fee7`, verified identical to what Claude sent). Keep it true after each task.
3. **Further modification** of the app as the owner asks (this is the current stage; the owner says the app is not ready for launch). For each change: read the current files, work on a branch, run all three browser suites, say what was not verified, update the notes and this file. **Done on the public page by 27 Oct 2026:** second restyle, reworded text (including transfers and About), phone layout, payment QR logo. **Not looked at yet:** the wording and phone layout of Admin and Gate (the owner said "public page only, as of now"); the About page content (waiting for the owner).
4. ~~Restore browser testing.~~ **Done 27 Oct 2026** (101 / 47 / 9 pass then, 101 / 73 / 35 now; method in section 9).
5. Small housekeeping when convenient: fix G17, optionally G15, delete merged branches, write a real `README.md`.
5b. **First real-account tests of the staff page (new, 28 Oct 2026):** a real gate login and the real camera on a phone, the 2-minute undo with a gate account, and an admin undo after 2 minutes; then take a new snapshot (section 8.4; `r2_12` is already in `sql/changes.sql`). (`test_r2_12` was written on 29 Oct 2026.)
6. **Pre-launch checks with the owner** (section 1, question 3; `PROJECT_NOTES.md` section 11), then opening registration when the owner decides. Done when each item is confirmed in Admin → Settings and the Actions tab shows green ticks.
6b. **New 9 Nov 2026:** recover or reconstruct `sql/r2_17_contacts.sql` (see the 9 Nov block); then re-run the database and browser suites, rebuild the test database if needed, and record the new counts here and in `PROJECT_NOTES.md` section 10. Done when the counts are written down and every failure is either fixed or listed as a known failure.
6c. **New 9 Nov 2026:** the owner has an idea to track who downloaded tickets and when. Agreed design, not built yet: an admin-only table `ticket_downloads` (ticket, booking, time, format), a public function `log_ticket_download` that requires Booking ID plus phone like `lookup_tickets`, a call to it from `downloadTicket` and `downloadAll` in `index.html`, and admin screens (a Downloaded tag, a Not downloaded yet filter, a CSV column). It records the press of Download, not that the file was saved. Ask the owner before building.

7. **After the event:** section 8.1 item 5.

After each task: update `PROJECT_NOTES.md` (changelog + status) and this file's state lines, and say what was not verified.

---

## 12. GLOSSARY

- **Seller / transferor:** the ticket holder giving up the seat. **Buyer / transferee:** the person receiving it.
- **Code:** 6 characters the seller gets; whoever has it can open the Transfer Form.
- **Call tick:** the admin's confirmation that they phoned the number registered on the original ticket; the real identity check, required before Transfer.
- **Transfer (button):** `admin_transfer_approve`, the swap.
- **Retired ticket:** the seller's ticket after transfer (`transferred_out_at` set); its number is never reused.
- **Transfer booking:** the buyer's new Booking ID (`kind = 'transfer'`), no seat until approved.
- **Held now / return due / to pay out:** panel terms in `admin_transfer_money()`.
- **Snapshot:** the nightly dump of the real database structure in `sql/schema_snapshot.txt`; the truth for rebuilding the test copy.
- **Piece N:** one SQL file of Release 2 (`r2_0N_*.sql`).

---

## APPENDIX A. ERROR CODES PER FUNCTION (regenerated 26 Oct 2026 from the live snapshot `b86a59c`; "File" = the latest `sql/` file that defines the function)  **Patched 9 Nov 2026 from the snapshot of 9 Nov:** rows added for `admin_approve_bookings`, `admin_preview_approval`, `admin_set_contacts`, the message and prize functions and `gate_undo_checkin`; rows changed for `admit_ticket` and `submit_booking`.

| Function | File | Style | Codes |
|---|---|---|---|
| `admin_approve_bookings` | r2_18_bulk_approve | raises | NOT_ALLOWED, NO_BOOKINGS, NUMBERS_CHANGED, TOO_MANY |
| `admin_assign_messages` | r2_13_game_messages | raises | DUPLICATE_TICKET, INVALID_PAIRS, MESSAGE_NOT_FOUND, NOT_ALLOWED, TICKET_NOT_FOUND, TOO_MANY |
| `admin_clear_client_ips` | r2_05_cleanup_and_ip | raises | NOT_ALLOWED |
| `admin_clear_messages` | r2_13_game_messages | raises | NOT_ALLOWED, NOT_FOUND |
| `admin_clear_prizes` | r2_14_game_prizes | raises | NOT_ALLOWED |
| `admin_delete_message` | r2_13_game_messages | raises | NOT_ALLOWED, NOT_FOUND |
| `admin_ip_flags` | r2_05_cleanup_and_ip | raises | NOT_ALLOWED |
| `admin_payment_alert` | Release 1 (see changes.sql) | raises | NOT_ALLOWED |
| `admin_preview_approval` | r2_18_bulk_approve | raises | NOT_ALLOWED, TOO_MANY |
| `admin_registration_status` | Release 1 (see changes.sql) | raises | NOT_ALLOWED |
| `admin_save_message` | r2_13_game_messages | raises | INVALID_MESSAGE, INVALID_NAME, NAME_TAKEN, NOT_ALLOWED, NOT_FOUND |
| `admin_set_ask_email` | r2_10_email_switch | raises | INVALID_VALUE, NOT_ALLOWED |
| `admin_set_ask_feedback` | r2_11_feedback | raises | INVALID_VALUE, NOT_ALLOWED |
| `admin_set_contacts` | r2_17 (file lost; see the 9 Nov block) | raises | CONTACT_INCOMPLETE, FIRST_CONTACT_REQUIRED, INVALID_CONTACT_NAME, INVALID_WHATSAPP, NOT_ALLOWED |
| `admin_set_event` | Release 1 (see changes.sql) | raises | INVALID_EVENT, NOT_ALLOWED |
| `admin_set_payment_info` | Release 1 (see changes.sql) | raises | INVALID_PAYEE, INVALID_UPI, INVALID_WHATSAPP, NOT_ALLOWED |
| `admin_set_prizes` | r2_14_game_prizes | raises | DUPLICATE_TICKET, INVALID_MESSAGE, INVALID_NAME, INVALID_PAIRS, NOT_ALLOWED, TICKET_NOT_FOUND, TOO_MANY |
| `admin_set_show_about` | r2_09_about_link | raises | INVALID_VALUE, NOT_ALLOWED |
| `admin_set_show_messages` | r2_13_game_messages | raises | INVALID_VALUE, NOT_ALLOWED |
| `admin_set_transfer_settings` | r2_06_transfer_settings | raises | INVALID_CUTOFF, INVALID_HOURS, INVALID_THRESHOLD, NOT_ALLOWED, PAYMENT_INFO_MISSING |
| `admin_transfer_approve` | r2_10_email_switch | raises | BUYER_BOOKING_INVALID, CALL_NOT_CONFIRMED, INVALID_TRANSFER, NOT_ALLOWED, NOT_PENDING, NO_BUYER, PAYMENT_NOT_VERIFIED, SELLER_ALREADY_TRANSFERRED, SELLER_CHECKED_IN, SELLER_TICKET_INVALID |
| `admin_transfer_confirm_call` | r2_03_private_transfer | raises | INVALID_TRANSFER, NOT_ALLOWED, NOT_PENDING |
| `admin_transfer_extend_code` | r2_04_public_via_code | raises | INVALID_HOURS, INVALID_TRANSFER, NOT_ACTIVE, NOT_ALLOWED |
| `admin_transfer_mark_paid` | r2_04_public_via_code | raises | ALREADY_PAID, INVALID_REFERENCE, INVALID_TRANSFER, NOT_ALLOWED, NOT_DONE |
| `admin_transfer_mark_returned` | r2_04_public_via_code | raises | ALREADY_RETURNED, INVALID_REFERENCE, INVALID_TRANSFER, NOT_ALLOWED, NO_RETURN_DUE |
| `admin_transfer_money` | r2_04_public_via_code | raises | NOT_ALLOWED |
| `admin_transfer_reject` | r2_04_public_via_code | raises | INVALID_NOTE, INVALID_TRANSFER, NOT_ALLOWED, NOT_PENDING |
| `admin_transfer_request_payment` | r2_04_public_via_code | raises | ALREADY_REQUESTED, CALL_NOT_CONFIRMED, INVALID_TRANSFER, NOT_ALLOWED, NOT_PENDING, NOT_PUBLIC |
| `admin_transfer_verify_payment` | r2_04_public_via_code | raises | ALREADY_VERIFIED, INVALID_AMOUNT, INVALID_TRANSFER, NOT_ALLOWED, NOT_PENDING, NOT_SUBMITTED |
| `admin_update_settings` | Release 1 (see changes.sql) | raises | INVALID_PAUSE_TIMES, NOT_ALLOWED |
| `admit_ticket` | r2_16_gate_no_approve | raises | ADMIN_ONLY, NOT_ALLOWED |
| `gate_undo_checkin` | r2_12_gate_undo | raises | NOT_ALLOWED, UNDO_EXPIRED |
| `get_event_info` | Release 1 (see changes.sql) | (returns {found:false} or data) |  |
| `get_payment_info` | Release 1 (see changes.sql) | (returns {found:false} or data) |  |
| `get_public_status` | Release 1 (see changes.sql) | (returns {found:false} or data) |  |
| `get_site_flags` | r2_11_feedback | (returns {found:false} or data) |  |
| `get_transfer_info` | r2_06_transfer_settings | (returns {found:false} or data) |  |
| `lookup_tickets` | r2_04_public_via_code | (returns {found:false} or data) |  |
| `private_sell` | r2_08_coordinator_transfer | returns {ok:false,error} | ALREADY_CHECKED_IN, ALREADY_PENDING, ALREADY_TRANSFERRED, CUTOFF_PASSED, MISMATCH, NOT_CONFIRMED, TRANSFERS_CLOSED, TRY_AGAIN |
| `public_sell` | r2_08_coordinator_transfer | returns {ok:false,error} | ALREADY_CHECKED_IN, ALREADY_PENDING, ALREADY_TRANSFERRED, CUTOFF_PASSED, INVALID_UPI, MISMATCH, NOT_CONFIRMED, TRANSFERS_CLOSED, TRY_AGAIN |
| `registration_heartbeat` | Release 1 (see changes.sql) | raises | INVALID_DATA |
| `save_scan` | Release 1 (see changes.sql) | raises | NOT_ALLOWED |
| `set_booking_status` | r2_03_private_transfer | raises | INVALID_STATUS, NOT_ALLOWED, USE_TRANSFER_TOOLS |
| `set_coordinator` | r2_08_coordinator_transfer | raises | ALREADY_TRANSFERRED, INVALID_TICKET, NOT_ALLOWED |
| `submit_booking` | 2 Nov occupation change (changes.sql only) | raises | INVALID_DATA, INVALID_FOOD, INVALID_GROUP_SIZE, INVALID_LOCATION, INVALID_NAME, INVALID_OCCUPATION, INVALID_OCCUPATION_DETAIL, INVALID_PHONE, NOT_ENOUGH_SPOTS, REGISTRATION_CLOSED, SCREENSHOT_MISSING |
| `submit_feedback` | r2_11_feedback | returns {ok:false,error} | BOOKING_NOT_FOUND, EMPTY_FEEDBACK, FEEDBACK_OFF, INVALID_COMMENT, INVALID_RATING |
| `transfer_cancel` | r2_03_private_transfer | returns {ok:false,error} | CONTACT_ADMIN, MISMATCH, NOTHING_TO_CANCEL |
| `transfer_open` | r2_03_private_transfer | returns {ok:false,error} | CUTOFF_PASSED, INVALID_CODE, NOT_AVAILABLE, TRANSFERS_CLOSED |
| `transfer_pay` | r2_04_public_via_code | returns {ok:false,error} | ALREADY_SUBMITTED, MISMATCH, NOT_ACTIVE, PAYMENT_NOT_REQUESTED, SCREENSHOT_MISSING, TRANSFERS_CLOSED |
| `transfer_status` | r2_04_public_via_code | (returns {found:false} or data) |  |
| `transfer_submit` | r2_10_email_switch | returns {ok:false,error} | CUTOFF_PASSED, INVALID_ATTENDANCE, INVALID_CODE, INVALID_CONSENT, INVALID_DATA, INVALID_EMAIL, INVALID_FOOD, INVALID_LOCATION, INVALID_NAME, INVALID_PHONE, NOT_AVAILABLE, TRANSFERS_CLOSED, TRY_AGAIN |
| `undo_checkin` | Release 1 (see changes.sql) | raises | INVALID_TICKET, NOT_ALLOWED |

`raises` = the call fails and the exception text is the code; `returns` = the call succeeds and the answer is `{ok:false, error:CODE}` (so the page has one shape). Changes since the 23 Oct version: `COORDINATOR` is gone from `private_sell` and `public_sell` (coordinators may sell, r2_08); `set_coordinator` can raise `ALREADY_TRANSFERRED`; new `FEEDBACK_OFF`, `INVALID_RATING`, `INVALID_COMMENT`, `EMPTY_FEEDBACK`, `BOOKING_NOT_FOUND` (feedback), `INVALID_VALUE` (the three switches), `PAYMENT_INFO_MISSING` (cannot switch transfers on without UPI ID, payee name and WhatsApp number).

Codes with no obvious reading: `MISMATCH` (any wrong detail, never says which), `TRY_AGAIN` (two requests collided; retry), `CONTACT_ADMIN` (only an admin can end it now), `NOT_ACTIVE`/`NOT_PENDING` (wrong stage), `USE_TRANSFER_TOOLS` (do not verify a transfer booking in the Bookings tab), `PAYMENT_NOT_VERIFIED`, `CALL_NOT_CONFIRMED`, `SELLER_CHECKED_IN` (the seller already entered the hall). `admit_ticket` answers with `{result: ok | already_scanned | invalid | cancelled | pending | rejected | ...}`; for `cancelled` it includes `name`, `label` and `old_label`.

---

## APPENDIX B. REAL RESPONSES CAPTURED FROM THE TEST DATABASE (fake data)

The first group was captured on 23 Oct 2026; no test since r2_08 to r2_11 contradicts those shapes (all 675 checks pass). The last group (26 Oct) shows the functions added after that.

### lookup_tickets(booking_id, phone)  -- a registered person (paid)
{
 "kind": "registration",
 "found": true,
 "status": "paid",
 "tickets": [
  {
   "food": "Veg",
   "kind": "guest",
   "name": "Asha",
   "label": "E26-001",
   "secret": "d81f2d69d726",
   "coord_no": null,
   "location": "In Bengaluru",
   "ticket_no": 1,
   "attendance": "Surely",
   "transferred": false
  }
 ],
 "booking_code": "1140548D",
 "people_count": 2,
 "amount_expected": 500
}

### lookup_tickets  -- wrong details (every failure looks exactly like this)
{
 "found": false
}

### private_sell(booking_id, ticket, phone)
{
 "ok": true,
 "code": "67Y659",
 "hours": 2,
 "expires_at": "2026-10-23T13:22:05.44071+00:00",
 "ticket_label": "E26-001"
}

### private_sell -- wrong details
{
 "ok": false,
 "error": "MISMATCH"
}

### transfer_status(booking_id, phone)  -- seller, code active
{
 "found": true,
 "transfers": [
  {
   "code": "67Y659",
   "mode": "private",
   "payout": null,
   "status": "code_active",
   "buyer_name": null,
   "created_at": "2026-10-23T11:22:05.44071+00:00",
   "expires_at": "2026-10-23T13:22:05.44071+00:00",
   "ticket_label": "E26-001",
   "amount_to_receive": null
  }
 ]
}

### transfer_open(code)  -- buyer types the code
{
 "ok": true,
 "food": null,
 "mode": "private",
 "expires_at": "2026-10-23T13:22:05.44071+00:00",
 "food_locked": false,
 "seller_name": "Asha"
}

### transfer_open  -- wrong / expired / used code
{
 "ok": false,
 "error": "INVALID_CODE"
}

### transfer_submit(code, submission_id, buyer json)
{
 "ok": true,
 "food": "Veg",
 "mode": "private",
 "status": "pending",
 "seller_name": "Asha",
 "booking_code": "C6157147"
}

### lookup_tickets -- the buyer's NEW Booking ID, private transfer pending
{
 "kind": "transfer",
 "name": "Dan Buyer",
 "found": true,
 "status": "pending",
 "tickets": [],
 "transfer": {
  "type": "private",
  "state": "pending",
  "amount_due": null
 },
 "booking_code": "C6157147",
 "people_count": 1,
 "amount_expected": 0
}

### transfer_status -- seller after the buyer applied
{
 "found": true,
 "transfers": [
  {
   "code": null,
   "mode": "private",
   "payout": null,
   "status": "pending_admin",
   "buyer_name": "Dan Buyer",
   "created_at": "2026-10-23T11:22:05.44071+00:00",
   "expires_at": null,
   "ticket_label": "E26-001",
   "amount_to_receive": null
  }
 ]
}

### admin_transfer_approve(transfer_id)  -- THE Transfer button
{
 "new_label": "E26-004",
 "old_label": "E26-001",
 "booking_code": "C6157147"
}

### lookup_tickets -- the buyer after approval (has the ticket and QR secret)
{
 "kind": "transfer",
 "found": true,
 "status": "paid",
 "tickets": [
  {
   "food": "Veg",
   "kind": "guest",
   "name": "Dan Buyer",
   "label": "E26-004",
   "secret": "ebfebf318391",
   "coord_no": null,
   "location": "In Bengaluru",
   "ticket_no": 4,
   "attendance": "Surely",
   "transferred": false
  }
 ],
 "booking_code": "C6157147",
 "people_count": 1,
 "amount_expected": 0
}

### lookup_tickets -- the SELLER after the transfer (ticket shown as transferred, no secret)
{
 "kind": "registration",
 "found": true,
 "status": "paid",
 "tickets": [
  {
   "food": "Veg",
   "kind": "guest",
   "name": "Asha",
   "label": "E26-001",
   "secret": null,
   "coord_no": null,
   "location": "In Bengaluru",
   "ticket_no": 1,
   "attendance": "Surely",
   "transferred": true
  }
 ],
 "booking_code": "1140548D",
 "people_count": 2,
 "amount_expected": 500
}

### public_sell(booking_id, ticket, phone, payout_upi)
{
 "ok": true,
 "code": "H96NNF",
 "mode": "public",
 "hours": 2,
 "expires_at": "2026-10-23T13:22:05.462617+00:00",
 "ticket_label": "E26-002"
}

### admin_transfer_request_payment(transfer_id)
{
 "amount_due": 250
}

### lookup_tickets -- public buyer, payment due
{
 "kind": "transfer",
 "name": "Eve Buyer",
 "found": true,
 "status": "pending",
 "tickets": [],
 "transfer": {
  "type": "public",
  "state": "payment_due",
  "amount_due": 250
 },
 "booking_code": "43A1C79F",
 "people_count": 1,
 "amount_expected": 0
}

### transfer_pay(booking_id, phone, submission_id, screenshot_path)
{
 "ok": true,
 "amount_due": 250
}

### admin_transfer_money()  -- the money panel (230 verified, waiting for Transfer)
{
 "held_now": 230,
 "paid_out": {
  "count": 0,
  "amount": 0
 },
 "returned": {
  "count": 0,
  "amount": 0
 },
 "return_due": {
  "count": 0,
  "amount": 0
 },
 "to_pay_out": {
  "count": 0,
  "amount": 0
 },
 "awaiting_payment": {
  "count": 0,
  "amount": 0
 },
 "awaiting_verification": {
  "count": 0,
  "amount": 0
 },
 "verified_waiting_transfer": {
  "count": 1,
  "amount": 230
 }
}

### transfer_status -- public seller after Transfer (to be paid 230)
{
 "found": true,
 "transfers": [
  {
   "code": null,
   "mode": "public",
   "payout": "to_be_paid",
   "status": "done",
   "buyer_name": "Eve Buyer",
   "created_at": "2026-10-23T11:22:05.462617+00:00",
   "expires_at": null,
   "ticket_label": "E26-002",
   "amount_to_receive": 230
  }
 ]
}

### admin_ip_flags()  (threshold lowered to 2 for the example)
{
 "ips": [],
 "threshold": 2,
 "by_booking": {}
}

### admin function error shape (raised exception text, e.g. approving twice)
 ('err', 'NOT_PENDING')

### get_site_flags()  (26 Oct 2026; the three switches, visitors may read it)
{ "ask_email": true, "show_about": true, "ask_feedback": true }

### get_transfer_info()  (26 Oct 2026, scratch data with transfers switched on)
{ "open": true, "ask_price": 250, "cutoff_at": null, "code_hours": 2, "food_locked": false, "cutoff_passed": false, "server_now": "2026-10-26T11:19:55+00:00" }

### submit_feedback(booking_code, rating, comment)
{ "ok": true }
(only a comment or only a rating is fine; neither gives { "ok": false, "error": "EMPTY_FEEDBACK" }; an unknown Booking ID gives BOOKING_NOT_FOUND; with the switch off, FEEDBACK_OFF)
