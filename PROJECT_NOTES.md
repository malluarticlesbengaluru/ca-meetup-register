# Ehsaas'26 Registration App: Project Notes

> **4 Nov 2026 cleanup of the public Home (owner request):** `assets/home-fx.js`, `assets/logo-fluid.js` and the stray root `akhina-a-r.jpg` were deleted, together with the old Home design's CSS (about 20 KB, all of it dead since the BURGUNDY `.bhome` Home: nothing renders `.home` or `#logo`) and the browser suite `scratch-db/browser/run_homefx.py`. Any other mention of `home-fx.js` or `logo-fluid.js` in this file or the handover describes the old design. The Home pop-up on scroll now lives in `homeMount()` in `index.html` (each section follows whichever is further along: a timed pop from the moment it enters the screen, or its scroll position). `run_home.py`, `run_home_touch.py` and `run_public.py` still test the OLD Home and fail on the current one; they need rewriting for `.bhome`.

> **NEW SESSION? READ `HANDOVER_NEXT_SESSION.md` FIRST** (state of each environment, the transfer case scenario by scenario, API reference, error codes, how to rebuild the test setup). This file is the decision log and the description of the design.

Last updated: 28 Oct 2026. **Release 2 is LIVE** (applied 25 Oct) with the later pieces `r2_08` to `r2_11`, the three on/off switches, and (27 Oct) a second restyle, reworded text, a phone-first layout and the logo on the payment QR for the **public pages**. **27 to 28 Oct: the staff side was rebuilt** (PRs #20 to #28, all merged by the owner): a green dark theme matching the public look, cards and previews instead of wide tables, linked data (tap a number, name or Booking ID to see what is behind it), the **gate scanner merged into the admin page** (one login, one page), a new gate result flow with an admitted list and an **Undo** (gate staff for 2 minutes, admins any time; `sql/r2_12_gate_undo.sql`, applied by the owner on 28 Oct). The app is **not ready for launch**: the owner is still modifying it. Registration is switched on **for testing only**, there is **test data only**, and **transfers are off** (owner, 26 Oct 2026).

**This repo is public.** Never put passwords, the Supabase service role key, database connection strings, UPI IDs, phone numbers or email addresses in this file or anywhere else in the repo. (The Supabase URL and the *publishable* key inside the HTML pages are safe by design.)

---

## 0. For Claude: read this first

**About the owner**
- The owner is a **beginner building this alone** (a friend will later get the admin dashboard). Explain everything **step by step in plain language**. Avoid jargon, or explain it in one line. The owner treats Claude as the **instructor**: lead, and say exactly what to click.
- Everything is done in the browser (GitHub web editor and Supabase SQL editor). Installing software on the owner's computer is allowed if really needed, but has never been needed.
- Times are India time (Asia/Calcutta, UTC+05:30). Credits matter to the owner: batch tool calls, avoid re-reading big files, finish a step and record it.

**How work is done (since 26 Oct 2026)**
- **Since 27 Oct 2026 Claude has push access to the repo** (the owner attached it to the chat). Claude works on a **new branch from the latest `main`**, runs the tests, pushes the branch and gives the owner the link `https://github.com/rameezmunirrr-gh/ca-meetup-register/pull/new/<branch>`; the owner presses **Create pull request, then Merge pull request**. GitHub Pages redeploys in about a minute, then the page needs a hard reload (Ctrl+Shift+R). Claude never pushes to `main`. A "Stop hook" that says a branch has unpushed commits is a false alarm: check with `git ls-remote --heads origin <branch>`. Full detail: `HANDOVER_NEXT_SESSION.md` section 10. (Between 26 and 27 Oct Claude had no repo connection and gave complete files for the owner to upload.)
- **If files are ever uploaded by hand: upload files, never folders** (a dragged folder once mixed files into the wrong place). **Warn the owner that the trash-can icon on a GitHub file page deletes the file** (it happened once, on 14 Oct 2026, and was restored from a saved copy).
- **Database changes:** in the **Supabase SQL editor**; send long SQL as a file and say what "Success" looks like. **Run the SQL first, then publish the page** (the pages cope with the database being one step behind, not the other way round).
- **Check your work before handing it over.** Rebuild the test database (handover section 9) and run the database suites and the three browser suites (public 101, admin 73, gate 35; Chromium is pre-installed in the sandbox). Do a deliberate-mistake check for any rule about money or security. **Say plainly what was NOT verified** after every task.
- **Work order set by the owner:** structure and safety first, looks last. The looks are now done. On 26 Oct 2026 the owner said: there is no deadline pressure on Claude (the 31 Oct deadline is not to be considered for now); focus on accurate, high-quality, working results without wasting time, credits or effort.
- **Ask before changing behaviour.** When the owner says "don't change anything yet, just note it", only record it (section 12) and do not edit code.

**Staying accurate**
- **Read the current files** before suggesting changes. From a shell with internet (verified 26 Oct 2026): `git clone https://github.com/rameezmunirrr-gh/ca-meetup-register.git` works, and `curl` on `https://raw.githubusercontent.com/rameezmunirrr-gh/ca-meetup-register/main/<path>?nocache=<number>` returns the exact text. The web-fetch tool can return an **old cached copy** of a GitHub page (on 26 Oct it showed 49 commits when the real number was 175), so do not trust it for the current state.
- **Source of truth:** `sql/schema_snapshot.txt` (the actual database structure, nightly) beats the SQL files and tests, which beat `HANDOVER_NEXT_SESSION.md`, which beats this file. If they disagree, say so to the owner. `sql/changes.sql` is a hand-kept history that may have gaps.
- Settings values and data are **not** in the snapshot. Read them in Admin, Settings, and ask the owner.
- Every time SQL is run in Supabase, remind the owner to **paste it into `sql/changes.sql`** (only statements that change something, with a date comment), run **Actions, Database Snapshot, Run workflow**, and compare the snapshot with the test copy. At the end of a session, offer to **update this file and the handover**.
- Respect the "Decisions not to undo" in section 9.

---

## 1. What this is

A custom registration, payment-verification, ticket-transfer and entry app for **Ehsaas'26**, a Malayalee CA meet-up in Bengaluru.

- **Organiser:** Mallu Articles Bengaluru. It began as a WhatsApp group started by 3 people who struggled with articleship, interviews and preparation. It guides CA, CMA and ACCA students and trainees coming to Bengaluru from Kerala with articleship vacancies, application links and interview preparation. It has grown to 700+ members, and the meet-up (party, food, enjoyment, relief) is the first in a year.
- **Event:** Sunday 22 Nov 2026, 2 PM, Savoury Business Hotel, Madiwala, Bengaluru (the live values are in Admin, Settings, Event details).
- **Why not a Google Form:** custom look and feel, plus features a form can't do:
  - several people in one booking (up to 5)
  - automatic UPI QR (scan-only) with the amount calculated from group size
  - OCR scan of payment screenshots to help admins catch fake or reused proofs
  - automatic ticket generation (JPG/PDF with QR)
  - ticket lookup by Booking ID + phone, and **ticket transfers** (the hall is limited and there are no refunds, so a person who cannot come hands the seat to someone else; the organisers handle it by phone and the app makes it safe)
  - QR scanning at the gate, with live present/confirmed counts
  - admin controls (cap, price, deadline, open/close, daily pause, transfer settings, on/off switches)
- **Payment:** there is **no payment gateway** (no business account is involved). The UPI QR on the Pay screen is generated for the exact total (number of people times the price), and the participant can scan it, use **Share/Download QR** (then upload the screenshot of the QR inside their UPI app), or copy the UPI ID and pay to it. **Tapping the QR to open a UPI app was removed on 16 Oct 2026** (the apps refuse it). The participant enters the UPI PIN in their own app, then uploads a payment screenshot. The UPI ID, payee name and WhatsApp number are read from the database, not the page code. Organisers verify manually, helped by OCR.
- **Goal:** maximum simplicity for participants and coordinators, with as much automation as possible.

**Key numbers (last recorded values; the database is the truth, read them in Admin, Settings):**

| Item | Value |
|---|---|
| Cap (people, confirmed + pending) | 150 (last recorded 14 to 16 Oct 2026) |
| Price per person | ₹250 (last recorded); the final price is set by the budgeting team |
| Max group per booking | 5 |
| Registration deadline | 31 Oct 2026, 23:59:59 IST (owner, 26 Oct: not to be considered for now; it may move) |
| Registration opens | **Not fixed.** The owner will decide when the project is complete and will set all settings then. |
| Registration open flag | **ON for testing** (owner, 26 Oct 2026). Only the owner has the link. Only test data exists. No real person registers until the owner says the project is complete. |
| Transfers | **OFF** (owner, 26 Oct 2026) |
| Transfer code lifetime | 24 hours (owner's setting; the database default is 2 hours) |

---

## 2. People and access

About 30 coordinators in four teams: Games and Activity, Stage Program Planning, Venue and Food, Operations and Coordination. The owner heads Operations and Coordination (6 members).

| Role | Who | What they use |
|---|---|---|
| Budgeting | 2 members | Work out the per-person price, which is set in Admin, Settings |
| App building and Admin | The owner + 1 friend | Full admin dashboard |
| Gate scanning | 2 members | Gate scanner page only |

Intended rule: gate-scan access is requested by the person and must be approved by someone with admin access. **There is no request/approve screen yet** (section 12).

**Adding staff:** The owner and **one friend (app building and admin)** get logins early. **Everyone else** (gate members, any other admins, the other coordinators) is added manually **at the end**, once everything is ready and tested. **The gate members' logins have not been created or tested yet** (owner, 26 Oct 2026). The steps are the same for everyone:
1. Supabase, Authentication, Users, Add user (email and password, auto-confirm).
2. Copy the new user's **User UID**.
3. In the SQL editor: `insert into staff (user_id, name, role) values ('<UID>', '<Name>', '<role>');`

The database only accepts the role values **`admin`** and **`gate`**. **Always write the role explicitly: since 16 Oct 2026 the column has no default**, so an insert without a role is refused. To remove someone's access, **delete their row from `staff`** (do not delete their Supabase login: that fails if they have ever reviewed or scanned anything). How many rows `staff` has today is not recorded (it is not in the snapshot): ask the owner.

**Sign-ups in Supabase Auth must stay OFF.** This is a switch in Supabase (Authentication, in the sign-in settings): "Allow new users to sign up". If it were on, any stranger could create a login for themselves. With it off, only logins the owner creates by hand can exist. It was confirmed off on 14 Oct 2026 (manual linking and anonymous sign-ins off, email confirmation on) and **again by the owner on 26 Oct 2026**. Re-check it once more just before launch.

**Since 28 Oct 2026 everybody signs in on the one staff page (`/admin/`; `/gate/` forwards there).** A gate account sees only the Gate tab; an admin sees all tabs including Gate. Gate staff can undo an admission for 2 minutes, admins any time. Gate staff can read `tickets` and `bookings` but see **zero rows** of the emails, transfers, IP and feedback tables.

---

## 3. Architecture

- **No server and no build step.** Three static HTML pages hosted on **GitHub Pages** (public repo, free plan), talking directly to **Supabase** (free plan: Postgres database, Auth, Storage). Supabase project: `CA-meetup-2026`.
- Libraries from CDNs: supabase-js (pinned version), qrcode-generator, jsQR (gate camera), Chart.js (admin charts), tesseract.js (in-browser OCR, loaded only when scanning screenshots).
- **All data changes go through database functions** (`SECURITY DEFINER`). Tables are readable only by logged-in staff (row-level security). The public pages never read or write tables directly (they only call the public functions and upload to the storage bucket).
- **GitHub Actions** (both in `.github/workflows/`):
  - `supabase-keepalive.yml`: pings the `keepalive` table every 3 days so the free Supabase project doesn't pause. It uses GitHub secrets `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
  - `schema-snapshot.yml`: runs **every night at 2:00 AM India time** (and on demand from the Actions tab) and writes the database structure to `sql/schema_snapshot.txt`, committing only when something changed. It connects with a **read-only database user `snapshot_reader`** through the GitHub secret `SNAPSHOT_DB_URL` (session-pooler connection string). It does **not** capture data, the contents of the `staff` table, or dashboard settings. The commit history of that file works as a change log of the database. The snapshot is public because the repo is public (it shows structure and function code, never data or keys).
- Browser sessions: the admin and gate pages use persistent Supabase logins. **Signing out in one window signs the account out everywhere.** Requests made while logged out run as an anonymous visitor, which has no table access, so the dashboard shows **"Could not load data: permission denied for table bookings"**. The fix is a hard reload and signing in again (this appeared once on 14 Oct 2026 after a second private window was used; signing in again cleared it, and the most likely cause was the login ending). If it ever returns after a fresh sign-in, compare the table permissions with the `TABLE AND VIEW PERMISSIONS` section of `sql/schema_snapshot.txt` (each table should show `authenticated=r/postgres`).

---

## 4. Files in the repo

| Path | Purpose |
|---|---|
| `index.html` | Public page (about 80 KB). A `CONFIG` block at the top holds event text, ticket text and the Supabase URL and key. The UPI ID, payee name and WhatsApp number are **not** in the code: they come from the database (`get_payment_info`). See section 6. |
| `admin/index.html` | The **staff page** (about 112 KB): login for everyone, the admin dashboard (admins) AND the gate scanner (a **Gate** tab; gate staff see only that tab). See section 6. |
| `gate/index.html` | Only a **forwarder** (about 0.6 KB) to `../admin/#gate`, so old bookmarks keep working. The scanner itself lives in `admin/index.html` since 28 Oct 2026. |
| `assets/home-fx.js` | Motion for the Home page (letters, countdowns, reveal, particles, poster tilt, confetti). Loaded as `?v=3`: bump the number on every change. Rewritten 3 Nov 2026 for the new Home design. |
| `assets/` | Logo files: `logo-fluid.js` (animated logo, home page only; load it with `?v=N` and bump N on change), `logo-mark.png` (transparent), `icon-192.png`, `apple-touch-icon.png`, `og-image.jpg` (the WhatsApp link preview). No SVG exists yet. |
| `.github/workflows/supabase-keepalive.yml` | Keep-alive ping. |
| `.github/workflows/schema-snapshot.yml` | Nightly database structure snapshot. |
| `HANDOVER_NEXT_SESSION.md` | Handover for the next Claude session (state, transfers in detail, API, error codes, test environment, task list). |
| `PROJECT_NOTES.md` | This file. |
| `README.md` | Only the repo name for now (a real one is on the housekeeping list). |
| `sql/schema_snapshot.txt` | Automatic nightly export. Never edit by hand. |
| `sql/changes.sql` | A history of SQL run in Supabase, with date comments. **Not guaranteed complete.** Never treat it as the current state of the database. |
| `sql/r2_01` to `r2_06` (+ `r2_02b`, `r2_02c`), `r2_08` to `r2_11` | Release 2 backend pieces, **all applied live**. Kept because the tests build on them. `rollout_A_part1_APPLIED.sql` and `rollout_A_part2_APPLIED.sql` are the exact files run on 25 Oct. |
| `sql/r2_12_gate_undo.sql` | `gate_undo_checkin(p_id)`: any staff can undo an admission for **2 minutes** after it was made; admins can always undo; after 2 minutes a non-admin gets `UNDO_EXPIRED`. **Applied by the owner on 28 Oct 2026** (recorded in `changes.sql` on 28 Oct 2026, and **confirmed live**: the snapshot of 28 Oct 2026, 09:53 UTC, contains the function with execute rights for `authenticated` only). The page falls back to the older admin-only `undo_checkin` if this function is missing. |
| `sql/r2_13_game_messages.sql` | **Messages for the game activity** (written 30 Oct 2026, **run by the owner on 30 Oct 2026, recorded in `changes.sql`; snapshot still to be taken**). Tables `game_messages` (name, body up to 200 characters) and `ticket_messages` (one message per ticket, many tickets can share one), both readable by admins only; switch `settings.show_messages` (default OFF); admin functions `admin_set_show_messages`, `admin_save_message`, `admin_delete_message`, `admin_assign_messages(jsonb [{t,m}], all or nothing, max 1000)`, `admin_clear_messages(message, tickets)`; a trigger copies the message to a ticket created by a transfer; changes are written to the Settings log (area `messages`); `lookup_tickets` returns `game_message` only while the switch is ON, for a paid booking and a ticket not transferred away. Tests: `scratch-db/test_r2_13.py` (88) and `mutate_r2_13.py` (44 of 44 caught). |
| `sql/r2_07_cleanup_test_data.sql` | Deletes ALL bookings, tickets, emails, transfers, IP records, scans and sessions, restarts numbering at 1 and switches transfers off; keeps staff, settings and the settings log. **Refuses to run while registration is open.** Run once on 25 Oct. Never run it again after real bookings exist. |
| `sql/archive/`, `scratch-db/archive/` | Abandoned designs. **Never apply.** |
| `sql/README.md` | The owner's guide to the sql folder (manual export queries are now optional because of the snapshot). |
| `scratch-db/` | The test setup: `build.py`, `lib.py`, the generators `gen_r2_*.py`, the ten database suites `test_r2_*.py`, and `browser/` (the three page suites with a mocked Supabase). Not part of the live system. How to rebuild it: handover section 9. |

---

## 5. Database (Supabase, `public` schema)

The live structure is `sql/schema_snapshot.txt` (checked on 26 Oct 2026: 13 tables, the `report` view, 64 functions of which 19 are internal helpers). Everything below is a summary; read the snapshot for exact columns and function source.

### Tables
- **`settings`** (one row, `id = 1`): `cap`, `price_per_head`, `max_group` (1 to 5), `deadline`, `is_open`, `closed_at` (when registration was last switched off by hand), `pause_enabled`, `pause_close_time`, `pause_open_time` (daily pause, India time), `grace_minutes` (10, fixed), `next_ticket`, `next_coord` (counters for the next guest and coordinator number), `event_at`, `venue`, `upi_id`, `payee_name`, `whatsapp_number` (null until the admin enters them), the transfer settings (`transfers_open`, `transfer_cutoff_at`, `transfer_food_locked`, `private_code_hours`, `ip_flag_threshold`) and the three switches `show_about`, `ask_email`, `ask_feedback` (all default ON). `max_resale_price` still exists but nothing uses it.
- **`settings_log`**: one row per setting, staff or transfer step (`at`, `changed_by`, `who`, `area`, `field`, `old_value`, `new_value`). Admin read only. Never holds phones, emails, UPI IDs or QR secrets. Not cleared by the cleanup.
- **`bookings`**: one row per payment. `booking_code` (8 hex characters, unique), `submission_id` (unique, prevents double submits), `people_count` (1 to 5), `amount_expected`, `status` (`pending` / `paid` / `rejected`), `screenshot_path`, `reviewed_by`, `reviewed_at`, `reviewed_via` (`admin` or `gate`), `created_at`, **`kind`** (`registration` or `transfer`; a transfer booking is a buyer's booking with amount 0, no screenshot and no ticket until approved, and never counts as a seat or income).
- **`tickets`**: one row per person (**no email column**). `booking_id`, `ticket_no` (unique, the guest number), `coord_no`, `kind` (`guest` / `coordinator`), `secret` (12 hex characters, goes in the QR), `orig_secret`, `prev_coord_no`, `prev_coord_secret`, `name`, `phone` (exactly 10 digits), `location`, `attendance`, `food`, `checked_in_at`, `checked_in_by`, `marked_by`, `marked_at`, `reg_seq`, `created_at`, **`transferred_out_at`** (set on the seller's ticket after a transfer; the row stays and its number is retired forever; **every count of people must ignore rows where this is set**) and **`transferred_from`** (on the buyer's ticket: the seller's ticket; the gate follows these links).
- **`ticket_emails`** (`ticket_id`, `email`): admin read only. Filled by `submit_booking` and by the Transfer step. When the Email switch is OFF nothing is asked or stored; emails already collected stay.
- **`transfers`**: one sale of one seat. `kind` (`private` / `public`), `status` (`code_active`, `pending_admin`, `done`, `rejected`, `withdrawn`, `replaced`), the 6-character `code` and its expiry, the seller snapshot, the admin's call tick, and for public transfers the payout UPI, `amount_due`, the payment steps, `amount_received`, the seller payout and the return fields. Admin read only. Only one open transfer (`code_active` or `pending_admin`) can exist per seat.
- **`transfer_buyers`**: the buyer's form (name, phone, email, location, attendance, food, consent, `booking_id`, status `active` / `done` / `rejected` / `released`). Admin read only.
- **`booking_ips`**: the visitor's IP per registration (flag only, never blocks). Admin read only. After the event, `admin_clear_client_ips()` deletes them.
- **`booking_feedback`**: optional feedback, one row per registration booking (rating 1 to 5 and/or a comment up to 1000 characters; sending again replaces it). Admin read only.
- **`screenshot_scans`**: one row per booking: `txn_ids`, `image_hash`, `read_ok`, `amounts`, `scanned_by`, `scanned_at`. Deleted with its booking.
- **`staff`**: `user_id` (linked to the login), `name`, `role` (`admin` or `gate` only).
- **`reg_sessions`**: one row per registration attempt in progress (no personal data), written only by `registration_heartbeat`; old rows are deleted automatically.
- **`keepalive`**: tiny table for the ping (readable by anon).
- The old marketplace transfer tables (`ticket_listings`, `ticket_interests`, `ticket_transfers`) and their functions were **dropped** in `r2_05`.

### Rules enforced by the database itself
- Unique: `bookings.booking_code`, `bookings.submission_id`, `tickets.ticket_no`, `tickets.coord_no` and `tickets.prev_coord_no` (where not null), one open transfer per seat, and a code unique among active codes.
- Check rules on phone (10 digits), food (`Veg` / `Non-veg`), location (`In Bengaluru` / `Outside Bengaluru`), attendance (`Surely` / `Most probably`), booking status, group size 1 to 5, amount above 0, `reviewed_via`, staff role, and: a coordinator must have a `coord_no` and a guest must not.
- **A ticket cannot outlive its booking:** deleting a booking that still has tickets is blocked. Cleanup order is tickets first, then bookings (`r2_07` does this).
- Several columns (`reviewed_by`, `checked_in_by`, `marked_by`, `scanned_by`) point to the login in `auth.users`; deleting a login that has acted fails.
- The group-size limit of 5 is fixed in two places (`settings.max_group` and the `bookings.people_count` check). A bigger group size needs both changed.
- A transfer needs the admin's call tick (and, for public transfers, a verified payment); the seller's ticket must be paid, a guest or coordinator ticket, not checked in and not already transferred; the cap is never checked at Transfer.

### View
`report` (joins tickets and bookings, for manual exports; it also shows the email, `transferred_out_at` and `booking_kind`). Set to `security_invoker = true` so it follows the staff-only rules (emails are therefore visible to admins only). No page uses it.

### Functions
All write paths are `SECURITY DEFINER` functions, and every admin function checks `is_admin()` itself. Parameter names matter because the pages call them by name. **The full list with parameters is in `HANDOVER_NEXT_SESSION.md` section 7, and the error codes of every function are in its Appendix A.** Summary by group:

| Group | Functions | Who |
|---|---|---|
| Registration status | `get_public_status`, `registration_heartbeat` | public |
| Settings readable by visitors | `get_payment_info`, `get_event_info`, `get_site_flags` (the three switches), `get_transfer_info` | public |
| Booking and tickets | `submit_booking`, `lookup_tickets(booking id, phone)` (replaced `lookup_booking`), `submit_feedback` | public |
| Transfers, seller and buyer | `private_sell`, `public_sell`, `transfer_status`, `transfer_cancel`, `transfer_open`, `transfer_submit`, `transfer_pay` | public (they return `{ok:false, error}` for user mistakes) |
| Gate | `admit_ticket`, `save_scan`, `admin_registration_status`, `is_staff` | staff |
| Admin, bookings and people | `set_booking_status` (refuses transfer bookings), `set_coordinator`, `undo_checkin` | admin |
| Admin, settings | `admin_update_settings`, `admin_set_event`, `admin_set_payment_info`, `admin_payment_alert`, `admin_set_transfer_settings`, `admin_set_show_about`, `admin_set_ask_email`, `admin_set_ask_feedback` | admin |
| Admin, transfers | `admin_transfer_confirm_call`, `_extend_code`, `_request_payment`, `_verify_payment`, `_approve` (the Transfer button), `_reject`, `_mark_paid`, `_mark_returned`, `admin_transfer_money` | admin |
| Admin, IP flag | `admin_ip_flags`, `admin_clear_client_ips` | admin |
| Internal (execute rights only for the database owner) | `_assign_numbers`, `_booking_json`, `_client_ip`, `_find_seller_ticket`, `_tlog`, `_pause_info`, `_grace_until`, `_public_state`, and others (19 in all). `is_staff`, `is_admin` and `_ticket_label` are small helpers; `rls_auto_enable` is Supabase's own event trigger. | nobody |

### Security rules (row-level security)
- Any staff can select from `bookings`, `tickets`, `screenshot_scans` and `settings`. `settings_log`, `ticket_emails`, `transfers`, `transfer_buyers`, `booking_ips` and `booking_feedback` are readable by **admins only**. `staff` rows are readable by the person themselves or by admins. `keepalive` is readable by anon. **Nobody can write to tables directly.**
- `anon` (visitors) has no table access at all (except `keepalive`).

### Storage
Bucket `payment-proofs`. Anyone can upload (needed for the public form), but only staff can read, through short-lived signed links. The bucket has a **file size limit and image-only types**. Screenshots are named `<submission_id>.<jpg|png|webp>`. The public page compresses screenshots in the browser before uploading. SQL cannot delete stored files: empty the bucket by hand in the dashboard when cleaning test data.

---

## 6. Pages and core flows

Three static pages (the public page, the staff page, and a tiny forwarder at `gate/`); the first two are single HTML files with inline JavaScript and the Supabase client, drawing views as HTML strings. Only the public key is in them. Everything that changes data goes through database functions. Full page-by-page detail: `HANDOVER_NEXT_SESSION.md` section 4.

### Public page (`index.html`)
- **Look (27 Oct 2026, modelled on the owner's "Join the Event Team" page):** dark navy page `#081020`, navy hero gradient with two soft discs, dark cards `#101838` with an amber `#F0A000` top edge, amber buttons, five accent colours (pink, violet, teal, blue, orange) for the option chips, heading bars and a thin stripe under the header; font **Manrope** (Fraunces and Jost are still loaded because the ticket IMAGE is drawn with them and is unchanged); the Mallu Articles Bengaluru logo; a navy invitation card on Home. Dark only. Scroll animations (cards rise in, bars grow, chips pop) are switched off for reduced motion. **Phone first:** checked at 390 x 844. CSS variables `--brand` (blue) and `--accent` (amber) plus `--pink`, `--violet`, `--teal`, `--orange`. Admin and Gate keep Midnight Emerald (not changed).
- **On load** the page calls `get_site_flags()`; the About link, the Email boxes and the feedback questions follow the three switches (if the call fails, all behave as ON).
- **Home:** Register, Tickets, About (shows "Under construction" until the owner sends content) and, only when transfers are open and the cut-off has not passed, Transfer tickets.
- **Register:** the page asks `get_public_status`; if closed it shows why. The form takes 1 to 5 people (an "Include friends" switch reveals 2 to `max_group`; `max_group` shrinks as spots run out). Each person: name, 10-digit phone with a fixed +91 box, Email right after Phone (only when the Email switch is on), location, attendance, food. A pasted "+91 98765-43210" is cleaned to 10 digits.
  - **Daily pause and grace:** the page sends a heartbeat every 30 seconds while the form is open. If registration closes (daily pause or switched off by hand) while someone is filling the form, a yellow bar shows a 10:00 countdown and they can finish and submit. If they run out of time they see "Your 10 minutes are over" with a WhatsApp button (they should not pay again). New visitors during a pause see the reopen time. Within 2 hours before a pause the form shows a heads-up note.
- **Review, then Pay:** Review lists each person as a stacked card (name, phone, email, location, attending, food) with a "Total payable" line. Pay shows the exact total, a **UPI QR drawn in the page with the logo in a round patch in the centre** (error-correction level Q, 24% of the QR width, tested with three decoders and scanned by the owner in several UPI apps; the ticket QR has no logo; do not enlarge it or switch to level H without re-testing, handover 4.1 and 9), copy-UPI-ID, share/download QR, and the screenshot upload (compressed in the browser, then `submit_booking`).
- **Done:** the **Booking ID** (saved on the device), "Pending verification", then the optional "Share your thoughts" card (a 1 to 5 excitement rating and a comment box with a placeholder) when the Feedback switch is on, then the buttons (Go to Tickets, Contact the organisers, Register another booking, Home). There is no Name/Food table.
- **Resubmit rule:** the submission ID is the idempotency key of `submit_booking`. After a SUCCESSFUL booking the form and the ID are cleared; a FAILED send keeps the same ID on purpose (no duplicate bookings). A real bug here was fixed on 26 Oct.
- **Tickets:** needs **Booking ID + phone every time** (case, spaces and dashes in the ID are ignored; the letter O counts as zero). Saved Booking IDs appear as tap-to-fill chips; **the phone number is never stored on the device**. States: Pending verification, Not verified (rejected, with a contact button), Confirmed (paid) which opens **View Ticket**. A seller's active code, its expiry and a Cancel-code button also appear here.
- **Ticket:** each person gets a ticket drawn on a canvas (navy header with the logo, event details, name, food mark, **ticket number**, QR `E26-007|secret`). The Booking ID is **not** drawn on the ticket. Download as JPG or PDF per person, or all as one PDF. Guest badge amber; coordinator badge ivory with maroon accents and the word COORDINATOR. Transferred-out tickets show as transferred, with no QR.
- **Transfers:** the seller chooses private or public and **Sell** (Booking ID, ticket number, phone; public also a payout UPI ID or phone, and no price) and gets a 6-character code with its expiry. The buyer types the code under **"I want to buy"** (the code itself decides private or public), fills the Transfer Form (name, phone, email when the switch is on, location, attendance, food unless locked, consent) and gets a **new Booking ID**. A public buyer later sees **Pay ₹X** with a UPI QR and a screenshot upload on the Tickets page. Seller and buyer never see each other's phone, email, Booking ID or ticket number, only each other's **name**.
- **On the device:** only Booking IDs are remembered.

### Staff page (`admin/index.html`): admin dashboard and gate scanner in one page (rebuilt 27 to 28 Oct 2026)
One email-and-password login for everybody. **Admins** get the dashboard tabs; **gate staff** see only the Gate tab (counts, camera, Find a person, Admitted list; no amounts, emails or payment details). The roles are still just `admin` and `gate` in the `staff` table; the owner decided on 28 Oct 2026 to keep access as it is (a 0-to-3 access-level idea was dropped). **Look:** dark green "Midnight Emerald" rebuilt to match the public page (page `#04140F`, cards `#0A2219` with a coloured top edge, brand green `#2FD39B`, amber accent, font **Manrope**, rounded corners, tabs that scroll sideways and stay pinned on a phone). Designed for **phone and laptop equally**. The page still loads on a database that lacks a newer piece (it hides the tab or card instead of crashing). Counts are computed in the browser and **ignore retired tickets**; transfer bookings are hidden from Bookings and from the OCR queue.
- **Previews and the back gesture (28 Oct):** tapping a card, a name, a Booking ID or "and N others" opens a **preview sheet** (bottom sheet on a phone, side panel on a laptop) instead of changing tab. Every sheet and every tab change is a browser-history step, so the phone's back gesture closes the sheet or returns to the last tab with the scroll position. Sheets stack (card, person, booking, person) and **Back** unwinds them. Deeper links ("Open in People tab ›", "Open in Bookings tab ›") change tab, highlight the card, and back returns to the earlier place with the same sheet open. The header **Find** button opens a search sheet (name, phone, ticket or Booking ID) from any tab. Code: `nav`, `openSheet`, `gotoTab`, `pSheet`, `bSheet`, `lSheet`, `renderSheet`.
- **Overview:** six cards (Active tickets, Spots used with a progress bar, Pending, Expected total, Present at event, Coordinators). **Each card opens the list behind its number with the working** (for example "₹750 confirmed + ₹0 pending = ₹750", booking by booking). Three **full pie charts** (Food, Location, Attendance; Chart.js, percentage on each slice, an HTML legend, drawn at 2x sharpness) with a switch between Confirmed + Pending and **Confirmed only** (use this for final food and hall numbers). Pie slices are NOT yet tappable (the owner left that out on 28 Oct). The IP banner's network addresses open the bookings behind them. The registration status banner and the payment-details-changed banner are unchanged.
- **Bookings:** one **card** per registration booking (code, time, amount, status, people as links, OCR-read transaction ID, review flags with tappable booking codes, big Screenshot / Paid / Reject / Pending buttons). Status chips Pending / Paid / Rejected / All with counts, a search box, "Needs review only". Pending first, newest first.
- **People:** one **card** per person (tap-to-call phone, tap-to-mail email, location / attendance / food tags, booking-ID chip that opens the booking preview, Make / Remove coordinator, Present with Undo); a collapsible **Filters** panel (payment, food, location, attendance, **Present / Not present yet**, type, show transferred tickets); the shown and present counts; **Download Excel (CSV)** with an Email column; retired tickets dimmed as Transferred.
- **Gate tab (merged 28 Oct 2026):** live counters (Present / Confirmed, Veg, Non-veg; paid bookings only, retired tickets ignored; refreshed every 30 seconds while the tab is open); camera scan (jsQR) of `E26-007|<12 hex>` or `E26-001C|<12 hex>` (anything else shows NOT A TICKET); **Find a person** (at least 2 characters; tapping Open then Admit skips the QR checks; a retired ticket shows a Transferred pill, never an Admit button); the **Admitted (N)** list, latest first, with name, ticket, Booking ID and entry time, whose names open the same person / booking previews (a person's preview has an **Admit** button when they are not in yet). The camera turns **off when you leave the tab**. **Result screens no longer close by themselves** (ADMITTED, ALREADY SCANNED, PAYMENT PENDING with Approve and admit, PAYMENT REJECTED, TICKET CANCELLED, INVALID TICKET, COULDN'T CHECK): buttons **Next scan** (closes and starts the camera if it is off), **Home page** (closes and turns the camera off) and, on ADMITTED only, **Undo** (asks first, then calls `gate_undo_checkin`, falling back to `undo_checkin`). **Gate staff can undo for 2 minutes, admins any time**; after 2 minutes the page says "ask an admin" without calling the database. **Camera permission:** the button shows Asking, then Try again after a denial with plain steps (browsers decide whether the prompt returns; a page cannot force it) and the camera starts by itself if the permission is allowed later. The only functions the Gate tab calls are `admit_ticket` and the undo functions. Gate staff load only a few columns of `tickets` and `bookings`.
- **Transfers** (appears only once the database has the transfer tables; shows the number waiting): the money cards **each open the list of transfers that add up to the amount** (the list checks itself against the card and warns if they differ), seller and buyer names are previews, waiting transfers (call tick, Ask to pay, verify the amount received, **Transfer**, or Reject), active codes with Extend and Cancel, seller payouts, buyer returns, history.
- **Scan screenshots:** OCR runs in the admin's browser (nothing leaves the computer) and saves transaction IDs, an image hash and amounts; the three counts (not scanned, unreadable, scanned) open their booking lists.
- **Feedback** (appears only when the feedback table exists): answers with the average and a 1-to-5 split (the rating counts open the answers); "Name and N others" opens the booking and everyone in it; booking codes open the booking preview.
- **Settings:** a responsive grid of cards (one column on a phone) with a jump bar: Registration settings (open, daily pause, cap, price, deadline), Payment details (locked until **Change** is pressed; the other admin sees a banner for 7 days after a change), Event details, Ticket transfers, Repeat-registration flag (IP threshold), About link, Email box, Feedback questions, a "Before you open registration" checklist and the Settings log (permanent: nobody can clear it). A live status banner (open / paused / closed, and how many people are inside their grace minutes) refreshes every 15 seconds.

### Verification workflow
A participant submits; an admin opens Bookings, checks the screenshot and the flags, then marks **Paid** (numbers are assigned and the participant can download tickets) or **Rejected** (the participant sees "Not verified" with a contact button). For a transfer the admin phones the **seller's registered number** (the real identity check), ticks the box and presses **Transfer** (public transfers also need the verified payment first).

---

## 7. Ticket numbering (final rules, tested 14 Oct 2026)

**Core rule from the owner: a number touched by a person is never given to another person.** Each person keeps their guest number and their coordinator number for good. This protects entry control: a cancelled ticket can never be mistaken for a live one.

- Format: guests `E26-007`, coordinators `E26-001C`.
- **Numbers are given only when a booking becomes `paid`**, either by an admin or by gate approval. Within one booking, people are numbered in the order they were listed on the form. Across bookings, numbers follow the **order bookings were marked Paid**, not the order they registered.
- Only **guest tickets** get a guest number at payment. A coordinator who has no guest number yet does not get one when their booking is paid.
- Marking paid, then pending, then paid again does not change numbers. A rejected booking keeps its numbers on record (the gate shows PAYMENT REJECTED), and marking it paid again gives the same numbers back.
- **Making a guest a coordinator:**
  - First time: they get the next coordinator number (`next_coord`, then it increases) and a **new QR secret**. Their guest number (if any) stays on the row but is cancelled while they are a coordinator, and the guest QR secret is kept in `orig_secret`. Nobody else is renumbered.
  - If they were a coordinator before: they get **their own old coordinator number and QR back** (`prev_coord_no`, `prev_coord_secret`), not a new number.
- **Removing a coordinator:** their coordinator number is kept on them as `prev_coord_no` (cancelled, never given to anyone else), their guest number and original QR come back, or if they never had a guest number and the booking is paid, they get the next free guest number.
- **Gate behaviour:** scanning the old guest QR of a coordinator shows TICKET CANCELLED with the new number. Scanning a retired coordinator QR of someone who is a guest again shows TICKET CANCELLED with their current number. The person sees the new ticket after refreshing Tickets (the ticket page shows the tickets the database returns).
- **Gaps are expected** (rejected numbered bookings, cancelled guest numbers, retired coordinator numbers), and the highest number can exceed the cap. That is fine: **counts use active people, not numbers** (section 6, Overview).
- Two admins clicking Paid at the same moment is safe (the settings row is locked, and unique indexes refuse duplicate numbers).
- Counters (`next_ticket`, `next_coord`) are reset to 1 only by the pre-launch cleanup (`sql/r2_07_cleanup_test_data.sql`, section 11).
- **Transfers (Release 2):** a transfer gives the buyer the **next guest number** and a new QR secret, and retires the seller's number and QR for good (`tickets.transferred_out_at`). The buyer's ticket points back to the seller's with `transferred_from`. Coordinator tickets can be sold too: the buyer always becomes a normal guest, and both of the seller's numbers are retired. Details: `HANDOVER_NEXT_SESSION.md` section 3.

---

## 8. Cap and counting rules


- The cap counts **every person in a non-rejected booking**, confirmed or pending. Registration closes when this reaches the cap. Rejecting a booking frees its spots.
- Coordinators count toward the cap like everyone else. Making someone a coordinator does not change the total.
- The public page shows "Only N spots left" when 20 or fewer remain, and "All spots are taken" at the cap.
- The dashboard separates the two groups: **Active tickets** (confirmed) and **Pending**, so that active + pending = spots used. No waiting list exists or is needed.
- **Retired (transferred-out) tickets and transfer bookings never count** as people, seats or income. A transfer is a swap, so the cap is **not** checked when an admin presses Transfer, and the hall stays exactly as full as before.

### Daily pause and grace rules (added 14 Oct 2026)
- The master **Registration open** switch overrides everything. The daily pause only applies while it is on. The cap never gets grace. The **deadline gets the same 10-minute grace** (people mid-registration at the deadline can finish; nobody new can start).
- The pause is enforced in the database (`submit_booking`), not only on the page. Times are India time, the same every day until the deadline. Close and reopen cannot be equal. Overnight windows (23:00 to 00:30) and same-day windows (13:00 to 14:00) both work.
- **Grace:** 10 minutes (`grace_minutes`, fixed). A person counts as "mid-registration" if their form session started before the closing moment and was last seen within 10 minutes before it (so someone who left to pay in a UPI app still qualifies). People who open the form after closing time get nothing. Applies to the daily pause and to switching registration off by hand (`closed_at`).
- The cap still applies during grace (`NOT_ENOUGH_SPOTS`).
- If the reopen time after a pause would fall past the deadline, the page shows "deadline passed". The closing moment used for grace is the earliest of: switched off by hand (`closed_at`), pause start, deadline (`_close_moment`).
- The dashboard banner tells the admin when no one is mid-registration, i.e. when it is safe to check the bank balance.

---

## 9. Decisions not to undo

- A number touched by a person is never given to another person (guest and coordinator numbers both, and transferred-out numbers too).
- Numbers are given when a booking is paid, never at registration, and are never renumbered.
- Any staff member (not only admins) can approve a pending payment at the gate. This marks the whole booking paid.
- Everything that writes data goes through database functions, and the public never touches tables.
- Participants see no fraud or OCR information, only status.
- OCR runs in the admin's browser. No screenshot is sent to any outside service.
- No payment gateway (direct UPI with manual verification).
- Pending people hold spots (otherwise registrations could exceed the number of seats).
- Registration stays closed to real people until the owner says the project is complete.
- **Do not bring back the tap-to-pay (`upi://`) link** on the Pay screen. It was tried twice and the UPI apps refuse it (16 Oct 2026).
- The **Booking ID is not shown on the ticket image, the ticket page heading or the PDF file name**.
- **Ticket lookup is Booking ID + phone**; a Booking ID alone shows nothing. The phone is never stored on the device.
- **Transfers:** private transfers move no money through the organisers (settled between the two people); public transfers do (the buyer pays the organisers, who pay the seller exactly the amount received; if a public transfer fails after the buyer paid, the money is returned and recorded with a reference; normal registrations stay no-refund). The admin's phone call to the **seller's registered number** is the identity check for every transfer. One code flow serves both kinds. A transfer is a swap: the hall never gets bigger.
- **Owner decisions of 25 to 26 Oct 2026:** transfer codes last 24 hours (the admin can Extend up to 168 h); no extra spam protection beyond the IP flag, which never blocks; waiting transfers do not expire by themselves; **coordinators can transfer their ticket** (the buyer becomes a normal guest); there are **no free passes** (guests of honour enter without registration or gate checks, outside this app); seller and buyer see only each other's name; the text says the organisers "may call"; one "I want to buy" button (the code decides private or public); a received ticket can be sold on.
- **Emails are admin-only**, in their own table. Gate staff cannot read them.
- Transfers stay **off** until the owner switches them on in Admin, Settings (the database refuses while the UPI ID, payee name or WhatsApp number is missing).
- Work order: structure and safety first, looks last (the looks of the public pages are done).
- **The logo goes on the PAYMENT QR only**, in a circle in the centre, never on the ticket QR; level Q and about a quarter of the width at most (tested 27 Oct 2026; level H is worse). Scanning it must be re-tested if the QR drawing changes.
- **Public pages are phone first and dark only** (owner, 27 Oct 2026). **The staff page was restyled to match in green** and made phone-and-laptop friendly (owner, 27 to 28 Oct 2026).
- **Staff access stays `admin` and `gate`** (owner, 28 Oct 2026). A proposal for levels 0 to 3 (an Access tab, a clearable settings log) was reviewed and dropped. The settings log stays permanent and cannot be cleared.
- **One page for staff** (owner, 28 Oct 2026): the gate scanner is a tab of the admin page; one login for everybody; gate staff see only the Gate tab. `/gate/` just forwards.
- **Gate results never close by themselves.** The gate person chooses Next scan, Home page or Undo. **Undo: gate staff for 2 minutes, admins any time** (owner, 28 Oct 2026).
- **Detail views are previews first** (bottom sheet or side panel); only the clearly labelled "Open in ... tab" buttons change tab, and the back gesture must always return to where the person was (owner, 28 Oct 2026).

---

## 10. Testing

**Release 1 (14 Oct 2026):** a full numbering, check-in and counting test passed (five test bookings; registration and group limit; numbers following the order of Paid; gate approval, double scans and live counters; coordinators both ways, retired numbers never reused; rejecting and re-approving; undo check-in; the cap and a registration race; counts agreeing across Overview, People, CSV and gate). Two things it found were fixed in `admin/index.html`: "Present at event" now matches the gate, and "Active tickets" counts confirmed people only.

**Release 2 and later (26 Oct 2026, verified by the previous session):**
- **Database: 11 suites, 731 checks, all pass** (`scratch-db/test_r2_01` to `_06`, `_08` to `_12`: 62, 54, 153, 157, 77, 68, 36, 14, 26, 28, 56; the 56 of `test_r2_12` were added on 29 Oct 2026 and have their own mistake check, `mutate_r2_12.py`, 16 of 16 caught). They run on a scratch Postgres rebuilt from the repo, with attacks written first, and deliberate-mistake checks (a rule broken on purpose must make the suite fail; a green run alone proves little).
- **The live database equals the tested one:** every function body and execute right, all columns, constraints, indexes, views, row-level security and triggers are identical between the live snapshot and a scratch copy built from the pre-Release-2 snapshot plus `r2_01` to `r2_11`. Remaining differences are Supabase's own items (storage policies, event triggers, `rls_auto_enable`) and default privilege letters on a few older objects (gap G15).
- **Browser suites** (`scratch-db/browser/`, headless Chromium with a mocked Supabase): **re-run on 28 Oct 2026: public 101, admin 73, gate 35, all pass** (the gate suite now loads `admin/index.html`; it covers both a gate account and an admin account on the merged page, and the new previews, back gesture, undo and camera-retry flows; admin and gate runs must be done without `-I`). Chromium and Playwright are pre-installed in the chat sandbox (do not run `playwright install`); run `cd scratch-db/browser && python3 run_public.py | tail -1` (admin and gate the same, without `-I`). The public suite checks exact sentences, so update it with any wording change. A separate script, `run_startup.py` (29 Oct 2026), checks how the public page starts up (Home drawn once, live values patched in place); run it the same way. How to take phone screenshots and how to test the payment-QR logo: handover section 9.
- **Rehearsal on the real site (25 Oct, owner):** registration with email and +91; lookup by Booking ID + phone; private transfer; public transfer with screenshot, verify, transfer and payout; the reject path; the gate refused the old QR and showed retired tickets as Transferred. The real visitor IP showed in the stored header data, so the IP-header question is closed.
- **Never verified by anyone:** a complete real payment (real money moving and an admin matching it); the new screens on a wide range of phones (the owner checked the 25 Oct rehearsal and the 27 Oct QR on their own phone and several UPI apps); the transfer screens against the real database (transfers are off); the gate members' logins (and so the real 2-minute undo for a non-admin account, the real camera scan on the merged page, and the admin side of the undo rule); the new staff page on a real phone.

**Test lessons:** the cancelled-ticket messages only appear when a QR is scanned with the camera (not when a person is picked from search). Download each ticket *before* changing it if it will be scanned later. Confirm the cap and price are what the test expects before starting.

**Test environment:** Claude's container is wiped between chats, so the tools live in `scratch-db/`. How to rebuild it in about 10 minutes (including the pre-Release-2 base snapshot `161e7ed`, which must be used instead of the current snapshot), how the harness works, and how to compare the real database with the tested one: `HANDOVER_NEXT_SESSION.md` section 9.

---

## 11. Before registration opens

The owner will say when. When all work is done the owner fixes all settings. In order:

1. **Finish the remaining work** (section 12) and, if possible, restore and re-run the browser suites.
2. In **Admin, Settings, Payment details**, press Change and type the real UPI ID, payee name and organiser WhatsApp number (with country code). Do not copy them into the repo. Check the Settings log shows the change. (Transfers cannot be switched on without them.)
3. Budgeting team sets the **final price**. Confirm the cap, the deadline and the event date and venue. Set the daily pause if wanted, the transfer settings (cut-off time, code lifetime, food lock, IP threshold) and the three switches (About, Email, Feedback).
4. Do a small real test payment (for example ₹1) and scan it in two UPI apps (never verified by anyone yet).
5. **Delete all test data** (once, right before launch, after all testing). Switch **Registration open** OFF first (the cleanup refuses to run while it is on). In the Supabase SQL editor, run `sql/r2_07_cleanup_test_data.sql`, then **empty the `payment-proofs` bucket** in the Storage section of the dashboard (SQL cannot delete stored files). Check afterwards that all counts are 0, `staff` still has its rows, and `select next_ticket, next_coord from settings;` shows `1, 1`. **Never run it again after real bookings exist.**
6. In Supabase Authentication, **"Allow new users to sign up" is off** (section 2; confirmed off by the owner on 26 Oct 2026). Re-check it once more just before launch.
7. **Create the remaining organiser logins** (the two gate members and anyone else) as in section 2, then test each login, and check that gate users cannot open the admin page.
8. Check that the keepalive and snapshot workflows show green ticks in the Actions tab.
9. Turn **Registration open** on in Settings, and only then share the link. Turn **Transfers** on later, when the owner decides.
10. **After the event:** run `select admin_ip_flags();` once to review, then `select admin_clear_client_ips();` to delete every stored address. Decide what to do with emails, feedback comments and payment screenshots (nothing sends email yet; no retention rule exists).

---

## 12. Status and next steps

**Done (as of 26 Oct 2026):**
- Release 1: the three pages, the database, OCR scanning, coordinators, keep-alive, nightly snapshot, security hardening, payment details in Settings with a log and a 7-day banner, the daily pause with the 10-minute grace.
- **Release 2 (applied live 25 Oct):** ticket lookup by Booking ID + phone, an email per person (admin-only table), private and public ticket transfers through one code flow, the IP flag, and the Admin tools for all of it.
- **27 Oct 2026 (live, PRs #13 to #18):** second restyle of the public pages, reworded public text including the transfer screens and a "Coming soon" About page, phone-first layout (stacked Review), the Done screen reordered, and the logo on the payment QR.
- **27 to 28 Oct 2026 (live, PRs #19 to #28, one SQL file `r2_12`):** the staff page rebuilt in stages (theme, header and sticky tabs, Overview with full pies; Bookings cards with status chips and search; People cards with filters including Present; Settings grid with a jump bar), then **linked data** (preview sheets for people, bookings and the numbers behind every Overview and Transfers card, linked names and booking codes in flags, Feedback and Scan, a Find box, the back gesture), then the **gate flow** (results stay on screen, Next scan / Home page / Undo, an Admitted list with previews, camera retry, undo limits) and finally the **gate scanner merged into the staff page** (PR #28).
- **After Release 2 (live):** coordinators can transfer (`r2_08`); About link switch (`r2_09`); Email box switch (`r2_10`); optional feedback with a switch and an admin Feedback tab (`r2_11`); the resubmit bug fix; the restyle (public pages navy and amber with the logo, Admin and Gate "Midnight Emerald").

**Owner's situation (26 Oct 2026):** the app is still under modification and **not ready for launch**; registration is on for testing, test data only, transfers off; the gate logins are untested; all settings will be fixed at launch time.

**Next tasks (in order):**
1. Keep these documents true: both this file and `HANDOVER_NEXT_SESSION.md` were brought up to date on 27 Oct 2026; update them after each task.
2. Do whatever further modification the owner asks for. For each change: read the current files, work on a branch, run the tests (database and the three browser suites), say what was not verified, update the log.
3. ~~Restore browser testing.~~ **Done 27 Oct 2026** (101 / 47 / 9 then; now 101 / 73 / 35; the browser is pre-installed in the sandbox; handover section 9).
4. Housekeeping when convenient: fix G17 (two test files hardcode a folder), optionally G15 (revoke leftover default privileges on `keepalive` and `report`), delete the 12 merged branches on GitHub, write a real `README.md`.
5. The pre-launch checklist (section 11), then launch when the owner decides.
6. After the event: section 11, item 10.

**Open decisions and unknowns (ask the owner):** the real opening date and whether the deadline moves; whether transfers should pause during the daily pause (default: no); the About page content (text, reels as links, photos with permission; the page says "Coming soon" until then) and the logo as an **SVG**; whether the wording of the staff page needs a pass (its look and phone layout were rebuilt 27 to 28 Oct, but its text was only partly reworded); retention of emails, feedback comments and payment screenshots after the event.

**Known small gaps (none are blockers):**
- No in-app screen for gate staff to request access and for admins to approve (manual in Supabase).
- G9: `_ticket_label` can be called by anyone (pure formatting, harmless).
- G15: leftover Supabase default privileges (TRUNCATE, REFERENCES, TRIGGER) on a few older objects; not reachable through the API.
- Not re-checked since 14 Oct 2026: the cap can be set below the number already registered (harmless; new bookings just stop); the People table and the CSV may still show "Present" for people from rejected bookings (only the Overview card and the gate counters exclude them); booking-code lookups are not rate-limited (owner's decision for this size of event).
- Gate search cannot find a retired coordinator number by that number.
- The Overview pie slices do not open lists (left out by the owner); the Present card's "rejected: N" line and the Settings log rows are not tappable; the Settings log is not linked to bookings.
- The staff page's Find sheet and the Gate tab's Find list are two separate searches (the Gate tab keeps its own so gate staff only get gate-level data).
- `settings.max_resale_price` is unused.

---

## 13. Change log

- **13 Oct 2026:** Database reviewed from exports and all three HTML pages. Security hardening done (report view, helper functions, bucket limits). `undo_checkin` rewritten to work by ticket id. Project notes and `sql/README.md` created.
- **14 Oct 2026:** Nightly schema snapshot added (`schema-snapshot.yml`, read-only `snapshot_reader`). Numbering rule extended so coordinator numbers also stay with their person (`prev_coord_no`, `prev_coord_secret`, updated `set_coordinator` and `admit_ticket`). Full test passed. Overview changed (Active tickets, Spots used, Present). Admin page accidentally deleted on GitHub and restored from a saved copy with the Overview edits applied. Afternoon checks: helper functions locked, sign-ups off, cap 150, price 250, deadline correct, registration currently closed.
- **14 Oct 2026 (later):** Daily pause + 10-minute grace added: new `settings` columns, `reg_sessions` table, `registration_heartbeat`, `admin_registration_status`, updated `get_public_status`, `submit_booking` and `admin_update_settings`; pause options and live banner in Admin; countdown, paused message and heartbeat on the public page. Run `daily-pause.sql` first, then upload both pages.
- **14 Oct 2026 (end of day):** Decided that the owner and one friend (admin) get logins now, and everyone else is added at the end (section 2). Restyle direction agreed (section 12): public page light (ivory and green), gate and admin dark with one shared colour theme, "Midnight Emerald" (details in section 12). Explained to the owner how an admin is added (create the Supabase login, copy the User UID, insert a `staff` row with the role written explicitly).

- **16 Oct 2026 (Release 1, Part 3a):** Payment details moved from the page code into Settings (`upi_id`, `payee_name`, `whatsapp_number`; `get_payment_info`, `admin_set_payment_info`). The Pay screen loads them fresh when opened, re-checks every 30 seconds, and shows a notice if they change, plus loading/failed/not-set-up states. The QR is scan-only (amount filled in). **Tapping the QR to open a UPI app was tried twice on 16 Oct 2026 (with and without the amount) and removed**: PhonePe, Google Pay and BHIM all refuse payments started from a `upi://` link to a personal UPI ID, while scanning, Share/Download QR and paying to a copied UPI ID work. Do not bring the tap link back. The caption now says: scan the QR, or on this phone take a screenshot and upload it in the UPI app, or pay to the UPI ID. The screenshot box shows "File uploaded · Tap to view · Change" once a file is chosen (the page used to show "No file chosen" next to "Selected"). New `settings_log` table (admin read only; logs settings and staff changes, including ones made directly in Supabase as "database"); Admin shows the Settings log and a 7-day banner to the other admin when payment details change (`admin_payment_alert`). `staff.role` default removed. The Booking ID is no longer drawn on the ticket image, the ticket page heading or the PDF file name. Event date/venue SQL recorded in `sql/changes.sql`. Tests: 151 earlier checks + 49 new database checks, and browser tests of both pages passed. **Transfers stay OFF** (`transfers_open` false); the transfer screens and the hardening SQL (Part 3b) are Release 2. **Decision reversed:** the organisers now handle money for transfers (Public mode), so "never handles money" no longer applies to transfers.

- **16 Oct 2026 (review and audit):** Notes brought up to date with the repo: Release 1 added to Done, stale lines fixed. The transfer backend (tables and about 20 functions) was found already deployed but unused and switched off, and was audited from the schema snapshot: eight issues found, written up in section 12 (Release 2 audit). The owner set the work order: build Release 2, then test and risk-proof, then restyle only afterwards; no deadline pressure on Claude. The restyle of the gate, admin and ticket image is therefore postponed. Stale lines corrected in the same pass: the Pay description (no tap-to-pay, no Share-QR-opens-an-app), the ticket description (no Booking ID on the ticket), the missing Release 1 tables, columns and functions in section 5 and the Admin Settings description, and the known gap about unlimited Booking ID lookups. Decisions, a Release 2 test plan and the verified list of protections already in the database were added. Nothing was changed in code or in the database in this step.

- **17 to 24 Oct 2026 (Release 2 designed, built and tested; nothing applied yet):** The owner replaced the earlier marketplace plan with one simple design: ticket status by Booking ID + phone; **one code flow** for private and public transfers; a new Booking ID for every buyer; the admin's phone call to the seller as the final identity check; email, a fixed +91, an IP flag that never blocks. The old transfer backend (about 22 functions and 3 tables) was audited, found to have eight holes, and replaced (`r2_05` drops it). Written as `sql/r2_01` to `r2_06`, each with attack tests and deliberate-mistake checks. Emails were moved to the admin-only table `ticket_emails` (23 to 24 Oct). All three pages were rewritten. The long design, audit and open-item records of this period are in the git history of this file (commit `55c4176`, 25 Oct 2026) and in `HANDOVER_NEXT_SESSION.md` sections 3 and 6.
- **25 Oct 2026 (Release 2 applied live):** rollout with the owner in the safe order (snapshot, `r2_01` + `r2_02`, pages, `r2_02b` to `r2_06`, snapshot comparison identical, rehearsal on the real site). Test data cleaned with `r2_07` and the `payment-proofs` bucket emptied.
- **25 to 26 Oct 2026:** `r2_08` (coordinators can transfer), the amount-difference warning, About link (`r2_09`), the restyle with the logo (public pages navy, amber, ivory; Admin and Gate "Midnight Emerald"), the Email switch (`r2_10`) and Email right after Phone, optional feedback (`r2_11`), the resubmit fix, the "Name and N others" wording. Each was a pull request merged by the owner (12 in all); SQL was run first, then the PR merged.
- **26 Oct 2026 (new session):** the previous session's GitHub connection was removed; Claude now delivers complete files. All 10 database suites re-run (675 checks pass) and the live snapshot compared with the tested copy (identical apart from Supabase's own items). The handover was rewritten. The owner confirmed the situation: registration on for testing, test data only, transfers off, not ready for launch, gate logins untested; no deadline pressure. **This file was brought up to date** (sections 0, 1, 2, 4, 5, 6, 9, 10, 11, 12, 13); the old Release 2 design and audit sections were removed from it (kept in git history). Nothing was changed in the code or the database in this step. The owner uploaded this file (commit `b53fee7`, verified identical to what Claude sent) and confirmed in Supabase that sign-ups are off.
- **27 Oct 2026 (same session continued, PRs #13 to #18, no SQL):** the owner attached the repo with push access (Claude now pushes branches, the owner merges). Browser testing restored (public 101, admin 47, gate 9). Public pages restyled to the owner's "Join the Event Team" look (PR #13), the whole public text reworded and the phone layout fixed (the Review table was stacked, #14), the Done screen changed (Name/Food table removed, feedback below Pending verification, #15), the payment QR got the logo (#16) in a round patch (#17), and the transfer screens, error messages and About page were reworded (#18). Two sentences the old tests called "exact" were reworded (Request received; the details-mismatch message). The owner scanned the payment QR in several UPI apps: works. Admin and Gate were not touched.
- **27 to 28 Oct 2026 (PRs #19 to #28; SQL: `r2_12` only):** docs updated (#19). **Admin restyle** in stages: theme, header, sticky scrolling tabs, Overview cards and full pies (#20); Bookings cards with status chips and search (#21); People cards, collapsible filters, tap-to-call (#22); Settings grid with a jump bar (#23). **Linked data:** preview sheets and the back gesture, booking IDs and names as links, a Present / Not present filter (#24); every Overview and Transfers card opens its list with the working, linked names in Transfers, Feedback, Scan and flags, and a Find box (#25). **Gate flow:** results stay until chosen, Next scan / Home page / Undo, an Admitted list with previews, camera retry (#26); the 2-minute gate undo (#27, with `sql/r2_12_gate_undo.sql`, which the owner ran in Supabase on 28 Oct; recorded in `sql/changes.sql` the same day; a new snapshot is still to be taken: Actions, Database Snapshot, Run workflow). **Gate merged into the staff page:** one login, a Gate tab, gate staff see only the scanner, `/gate/` forwards (#28). Tests after each step: public 101, admin 73, gate 35. Not verified: a real gate account, a real camera scan on the merged page, the admin side of the undo rule, real phones.
- **29 Oct 2026 (tests only; no page, SQL or database change):** `scratch-db/test_r2_12.py` (56 checks for `gate_undo_checkin`: visitors and non-staff refused, gate inside and after 2 minutes, admin any time, wrong, empty and never-admitted ids, one ticket only, the old `undo_checkin` still admin-only, a same-instant race) and `scratch-db/mutate_r2_12.py` (16 deliberate mistakes, all caught). Database total: 11 suites, 731 checks. Browser suites re-run: public 101, admin 73, gate 35.
- **30 Oct 2026 (Messages part 1, database only; SQL file `r2_13` run by the owner on 30 Oct):** see the table row above. Part 2 (page: admin Messages tab, Settings switch, ticket display) follows in the next pull request. Older suites re-run with r2_13 on top: 04, 05, 06, 10, 11 and the r2_12 suite still pass; suites 03 and 09 could not be used for this (03 builds an old partial database that the final `lookup_tickets` does not fit; 09 has the known path problem G17).
- **31 Oct 2026 (Pick random people; SQL file `r2_14` RUN by the owner on 31 Oct 2026 and confirmed against the snapshot):** a separate message line per ticket with an editable heading (default 'You are a winner!', up to 60 characters), given to N randomly picked people in the admin Messages tab (secure random draw with a preview), shown on the public ticket as its own panel next to the team message only when it exists, under the same Show/Hide switch. Suites: `test_r2_14.py` 72 (`mutate_r2_14.py` 48 of 48), `run_messages.py` 111 (`mutate_messages_page.py` 49 of 49), `run_gamemsg.py` 37 (`mutate_gamemsg.py` 24 of 24); older suites unchanged (public 101, admin 73, gate 35, startup 29, pagefx 26, homefx 38, qrimage 32).
- **30 Oct 2026 (Messages part 2, the pages):** admin Messages tab, Settings card **Game messages**, People tag and one-person select; public ticket gets a panel "Your secret message" only when the database sends one (it sends one only while the switch is ON). Order for the owner: merge the database pull request, run `sql/r2_13_game_messages.sql` in Supabase, then merge the page pull request (the pages also work if merged first: the new parts simply stay hidden). Suites: `run_messages.py` 69, `run_gamemsg.py` 23, with `mutate_messages_page.py` (24 of 24) and `mutate_gamemsg.py` (11 of 11). One mutant was left out as equivalent in this browser (splitting emoji by code units: Chromium refuses to measure half an emoji as fitting, so the result is the same; `Array.from` stays as the safe choice).
- **30 Oct 2026 (snapshot compared):** the real database (snapshot of 30 Oct, 10:20 UTC) equals the tested scratch copy built from `r2_01` to `r2_13`: every function body and execute right, columns, constraints, indexes, policies on public tables, triggers; only the known Supabase-only differences remain (storage policies, event triggers, `rls_auto_enable`, extra privilege letters).
- **29 Oct 2026 (public page, part A of the speed work; no SQL):** the Home card is patched in place when live answers arrive (`refreshHome()`), instead of being rebuilt. Measured on the old page: the card faded in 4 times, the logo was replaced and the page jumped to the top. New script `scratch-db/browser/run_startup.py` (12 checks, with a deliberate-mistake control) covers it; the old page fails it, the new one passes. Suites: public 101, admin 73, gate 35, startup 12. Not checked: a real phone.
- **29 Oct 2026 (public page, part B of the speed work; no SQL; stacked on part A):** the Supabase and QR libraries load `async`, so Home is drawn at once instead of after both download. `db` became a wrapper that waits for the library; the pay screens and the ticket drawing wait for the QR library; the 2.5 s event limit now starts after the library arrives. Simulated slow network: Home visible after 4018 ms (old) versus 23 ms (new). `run_startup.py` now has 29 checks (each rule has a deliberate-mistake control); public 101, admin 73, gate 35. Not checked: real phones or networks, Safari on iPhone, the real Supabase library through the wrapper (the tests use a fake one), a real screenshot upload through the wrapper.
- **29 Oct 2026 (public page; no SQL):** the Share QR / Download QR picture now carries the amount, the payee and the UPI ID (`blobQR()` draws the page's QR 1:1 inside a larger picture). `scratch-db/browser/run_qrimage.py` (21 checks, real QR library, decoded with OpenCV, three mistake controls) shows it still scans. The QR on the page, `drawQR` and the ticket QR are unchanged. Not checked: scanning the shared picture in real UPI apps, how WhatsApp or the phone's share sheet shows it, Manrope in the picture (the sandbox used a fallback font).
- **29 Oct 2026 (public page; no SQL):** a warning note, "After you scan, check that the UPI ID shown in your app matches the UPI ID below", was added on both pay screens and inside the Share/Download picture, between the QR and the UPI ID (owner's request). `run_qrimage.py` now has 32 checks. Not checked: real phones; how the longer picture looks after WhatsApp's compression.
- **30 Oct 2026 (public page; no SQL):** calm Home motion (owner's chosen list; details in the handover): drifting discs, flowing bands, diamond pulse, ~1.2 s entrance once per visit, button ripple and press-in, staggered light sweeps every 8 s, a few background-only particles, row flash, and on desktop only a card tilt with glare and logo heads that follow the pointer. New `assets/home-fx.js?v=1` plus a CSS block in `index.html`; off for reduced motion. `run_homefx.py` 38 checks (6 mistake controls). Headless measurement: 59 to 60 frames per second at 6x slower CPU. Not checked: real phones, Safari on iPhone, feel.
- **30 Oct 2026 (public page; no SQL):** (a) payment screens (`pay`, `tpay`): the scroll-reveal is switched off so the next card ("Upload your payment screenshot") is always visible; all other screens unchanged. (b) `assets/page-fx.js?v=1`: a short entrance on every non-Home screen (only when the screen changes, not on redraws) and a button ripple on every button; CSS press-in and a flowing `.kasavu` stripe; reduced motion off. Ripple removed from `home-fx.js` (now `?v=2`). `run_pagefx.py` 26 checks; `run_public.py` now runs with the real motion scripts. Not checked: real phones.

---

---

## CHECKPOINT: end of the 26 to 28 Oct 2026 session (owner closed the session here)

**Added after the checkpoint, 29 Oct 2026: animated logo on the public home page** (written by the owner, reviewed by Claude). `assets/logo-fluid.js` draws the logo as inline SVG: two bodies merge through a "goo" blur, the heads bud out, and the grey centre is the overlap of the two bodies. It runs for about 3.4 s, then shows the crisp logo. It is used on the **home page only**, with scroll-squish and tap-to-replay turned off. The old PNG is the fallback (script error) and reduced-motion users see the finished logo with no motion. The script is loaded as `assets/logo-fluid.js?v=2`: **bump the number whenever the file changes**. `vHome()` holds `#logo-fallback` (PNG) and `#logo` (SVG); `render()` mounts it. The tuning numbers are in `TUNE` at the top of the script. Suites still pass (public 101, admin 73, gate 35). Not checked: real phones (older Android, iPhone Safari).

**State:** `main` is clean and equal to the remote; every pull request (#1 to #30) is merged; the three browser suites pass on `main` (public 101, admin 73, gate 35); `r2_12_gate_undo.sql` is live (confirmed in the snapshot of 28 Oct 2026) and recorded in `sql/changes.sql`. The app is still in **testing mode**: registration on for testing, test data only, transfers off, not ready for launch.

**Pending, in the order I would do it (nothing blocks anything else):**
1. **Real-account tests (the owner):** create a gate login, then on a phone: sign in at `/admin/` (only the Gate tab must show), scan a real ticket, Undo within 2 minutes (works) and after 2 minutes (says ask an admin), deny the camera and press Try again. Also an admin Undo after 2 minutes, and the staff page on real phones. Report what is odd and Claude fixes it.
2. ~~A database test suite for `r2_12`.~~ **Done 29 Oct 2026:** `scratch-db/test_r2_12.py` (56 checks) and `scratch-db/mutate_r2_12.py` (16 deliberate mistakes, all caught). It tests the SQL file, which equals the live function in the 28 Oct snapshot. Not covered: a real account on a real phone (item 1). Found, not changed: a wrong id, an empty id and a never-admitted ticket all raise `UNDO_EXPIRED`, and the function keeps no record of who undid what.
3. **About page content** from the owner (text, reels as links, photos with permission) and the logo as an SVG.
4. **Wording pass on the staff page** (its look and phone layout were rebuilt, its text only partly reworded).
5. **Housekeeping:** a real `README.md`; G15 and G17 (section 12); old merged branches (none are left on GitHub at the checkpoint).
6. **Left out on purpose, ask before building:** tappable Overview pie slices; tappable "rejected: N" on the Present card; the Settings log linked to bookings.
7. **Pre-launch checklist** (section 11) when the owner decides, then launch. After the event: section 11, item 10.

**Never verified by anyone:** a complete real payment; a real gate account (the real 2-minute undo, the real camera scan on the merged page); the admin side of the undo rule on a real account (the database rule itself, for gate and admin accounts, is tested on a scratch copy since 29 Oct 2026); the new staff page on a range of real phones; the transfer screens against the real database (transfers are off).

---

## ADMIN REDESIGN (Nov 2026): progress, branch `admin-step2-frame` (NOT pushed yet, owner asked to wait)

Plan in 7 steps: (1) smoothness engine, merged as PR #48; (2) new frame: side menu / bottom bar, top bar with search, light and dark, Today screen (**built, on the branch**); (3) payment review desk; (4) People and Gate; (5) Transfers and Messages; (6) Settings grouped, Scan, Feedback; (7) final pass and docs.

**Decisions of the owner (Step 2):** the About link is always on; Feedback is always on; the Email box is never asked and email is not shown anywhere (the only place it was asked was the transfer buyer form; the registration form already had none). So the switches were removed from Settings, and the Game messages card was removed (the Messages tab already has Show/Hide). The hand-ticked checklist is now an automatic "Launch readiness" card; the repeat-registration threshold is under a collapsed "Advanced"; "Delete all stored network addresses" is under "After the event".

**Order to roll out (important):** (1) run `sql/r2_15_fixed_switches.sql` in Supabase (sets show_about=true, ask_email=false, ask_feedback=true); (2) merge the pages. If the pages go first, the transfer form no longer sends an email while the database still demands one, and transfers would fail. After running it, paste it into `sql/changes.sql` and refresh `schema_snapshot.txt`.

**Tests on the branch:** `run_admin.py` 69, `run_gate.py` 35, `run_messages.py` 111, `run_smooth.py` 71, new `run_frame.py` 19 (menu, badges, Needs-you buttons, theme, search, phone bar and More sheet, no email), new `run_public_fixed.py` 7 (About always shown, no email box, feedback always on; fails on the old page). **`run_public.py` is out of date** with the live registration form (it still expects an attendance question and an email box) and was already failing before this work; it needs a rewrite, not used here. Note `run_public_fixed.py` needs `qrcode-generator` in `/home/claude/qrtest` only for the older suite.

**Not verified:** a real phone, a real database, the SQL on the live database, light/dark on real devices.

**Step 3 (payment review desk), branch `admin-step3-review`, built on top of step 2, not pushed:** Payments page has "Review payments (N)". It opens a full-screen desk: oldest waiting booking first, screenshot beside the details (stacked on a phone), Paid / Reject / Skip / Back, keys P, R, right and left arrows, Escape; Reject asks first, Paid does not; after each decision it moves to the next and closes with "All caught up". The phone back gesture closes it. No background refresh while it is open. Tests: `run_desk.py` (25 checks, 4 of 5 deliberate mistakes caught; the fifth was an equivalent change). Not verified: real screenshots from the real storage bucket, a real phone.

**Step 4 (People and Gate), branch `admin-step4-people-gate`, from `main` after PR #49, not pushed:** People has quick chips (Everyone, Present, Not here yet, Payment pending, Coordinators, with counts) and a Table / Cards switch (table by default on a laptop, cards on a phone; the choice is remembered in the browser under `adm_pview`). Names open the person sheet. Gate has a progress bar of people present and a second list, "Not here yet", with phone numbers and an Open button. The scan overlay and admit/undo rules are unchanged. Tests: `run_people.py` (26 checks, 5 deliberate mistakes all caught); older suites updated to find rows in either layout. Not verified: a real phone, the real camera scan.

**Step 5 (Transfers and Messages), branch `admin-step5-transfers-messages`, stacked on the unpushed step 4 branch:** Transfers opens with four count tiles (Waiting for you, Active codes, To pay sellers, To return to buyers) that jump to their section; the "Transfer money" panel moved to a collapsible section at the bottom (open when money is waiting); the tables on Transfers and Feedback become small labelled cards on a phone (`table.rt`, labels added by `stackTbl`). Messages page unchanged apart from "1 person" wording. Tests: `run_transfers.py` (15 checks, 5 deliberate mistakes all caught). Not verified: a real phone with real transfers.

---

## 14. Never share

Supabase **service role key**, database password, the `snapshot_reader` password or connection string, staff passwords, or anything from the Supabase dashboard's secret key section. The publishable key in the pages is safe by design.
