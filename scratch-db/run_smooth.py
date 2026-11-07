from admin_test import *
# Browser suite for the "smoothness engine" of the staff page (Step 1 of the admin redesign, Nov 2026):
#   in-app dialogs (and the back gesture), reloading only what changed, the screen updating in place (scroll, open panels, typed text kept),
#   the progress bar and the double-tap guard, stacked toasts, the tab bar, auto-refresh, and the error path.
# Run:  cd scratch-db/browser && python3 run_smooth.py | tail -1

def small(p, database, w=390, h=800):
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': w, 'height': h}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.route('**/*', lambda r: (r.fulfill(body=HTML, content_type='text/html') if r.request.url.endswith('/admin/test.html')
        else r.fulfill(body='/*stub*/', content_type='text/javascript') if r.request.url.endswith('.js') or '/npm/' in r.request.url else r.fulfill(status=204, body='')))
    pg.add_init_script('window.__DB=' + json.dumps(database) + ';'); pg.add_init_script(MOCK); pg.add_init_script(CH); pg.add_init_script(DLG_BOT)
    pg.goto('https://example.test/admin/test.html'); pg.wait_for_selector('#v'); return b, pg, errs

def calls(pg, name=None): return [x for x in pg.evaluate('window.__CALLS||[]') if name is None or x['name'] == name]
def dlg(pg): return pg.query_selector('.dlg') is not None
def tab_on(pg, t): return pg.query_selector(f'button[data-tab="{t}"][aria-current="page"]') is not None

def pending_world(n=1):
    """n pending bookings with one person each (plus the standard sample data)"""
    B = [bk(i, status='pending') for i in range(10, 10 + n)]
    T = [mk(100 + i, booking_id=f'b{10+i}', name=f'Pend{i}') for i in range(n)]
    return dict(bookings=BOOKINGS + B, tickets=TICKETS + T)

with sync_playwright() as p:
    # ================= 1. in-app dialogs
    d = db(); d['rpc']['set_coordinator'] = {'label': 'E26-001C'}
    b, pg, errs = open_page(p, d, 'people'); MK = '[data-co="make"][data-t="t2"]'
    pg.click(MK); pg.wait_for_timeout(100)
    t = pg.inner_text('.dlg') if dlg(pg) else ''
    check('1.1 Make coordinator opens an in-page dialog (not a browser box) with a clear title', dlg(pg) and 'Make Ben a coordinator?' in t and pg.get_attribute('.dlg-bg .dlg', 'role') == 'alertdialog', t)
    check('1.2 the dialog explains the consequence in plain words', 'guest number' in t and 'E26-002' in t, t)
    check('1.3 nothing is sent to the database while the dialog is open', not calls(pg, 'set_coordinator'))
    pg.click('.dlg [data-dlg="no"]'); pg.wait_for_timeout(150)
    check('1.4 Cancel closes it and still sends nothing', not dlg(pg) and not calls(pg, 'set_coordinator'))
    pg.click(MK); pg.wait_for_timeout(100); pg.keyboard.press('Escape'); pg.wait_for_timeout(150)
    check('1.5 Escape cancels', not dlg(pg) and not calls(pg, 'set_coordinator'))
    pg.click(MK); pg.wait_for_timeout(100); pg.mouse.click(4, 4); pg.wait_for_timeout(150)
    check('1.6 a tap outside the dialog cancels', not dlg(pg) and not calls(pg, 'set_coordinator'))
    pg.click(MK); pg.wait_for_timeout(100); pg.keyboard.press('Enter'); pg.wait_for_timeout(300)
    c = calls(pg, 'set_coordinator')
    check('1.7 Enter confirms: the database gets the right ticket and p_make = true', c and c[-1]['args'] == {'p_ticket_id': 't2', 'p_make': True} and not dlg(pg), c)
    check('1.8 the toast confirms the result', 'is now E26-001C' in pg.inner_text('#toasts'), pg.inner_text('#toasts') if pg.query_selector('#toasts') else 'no toasts')
    check('1.9 no page errors', not errs, errs); b.close()

    # the back gesture closes the dialog and the dialog leaves no stray history step behind
    b, pg, errs = open_page(p, d := db(), None)
    pg.click('button[data-tab="people"]'); pg.wait_for_timeout(100); pg.click('[data-co="make"][data-t="t2"]'); pg.wait_for_timeout(100)
    pg.go_back(); pg.wait_for_timeout(200)
    check('1.10 back gesture with a dialog open closes the dialog only: still on People, nothing sent', not dlg(pg) and tab_on(pg, 'people') and not calls(pg, 'set_coordinator'))
    pg.go_back(); pg.wait_for_timeout(200)
    check('1.11 the next back goes to the previous tab (Overview): the dialog left no extra step', tab_on(pg, 'overview'))
    pg.go_forward(); pg.wait_for_timeout(200)
    pg.click('[data-co="make"][data-t="t2"]'); pg.wait_for_timeout(100); pg.click('.dlg [data-dlg="no"]'); pg.wait_for_timeout(250)
    pg.go_back(); pg.wait_for_timeout(200)
    check('1.12 closing a dialog with its Cancel button leaves no extra history step either', tab_on(pg, 'overview'), pg.evaluate('S.tab'))
    check('1.13 no page errors with history', not errs, errs); b.close()

    # a dialog over an open sheet: back closes the dialog first, the sheet stays
    b, pg, errs = open_page(p, db(), 'people')
    pg.evaluate("openSheet('person','t2')"); pg.wait_for_timeout(100)
    pg.evaluate("document.querySelector('[data-co=\"make\"][data-t=\"t2\"]').click()"); pg.wait_for_timeout(100)
    check('1.14 dialog opens over a sheet', dlg(pg) and pg.query_selector('#sheetbg') is not None)
    pg.go_back(); pg.wait_for_timeout(200)
    check('1.15 back closes the dialog and the sheet is still open', not dlg(pg) and pg.query_selector('#sheetbg') is not None and 'Ben' in pg.inner_text('#sheetbg .sh-h h2'))
    b.close()

    # dialogs with a text box (replace the old browser prompt)
    d = db(); d['rpc']['admin_transfer_extend_code'] = None; d['rpc']['admin_transfer_reject'] = None
    b, pg, errs = open_page(p, d, 'transfers')
    pg.click('[data-tact="extend"][data-id="x2"]'); pg.wait_for_timeout(100)
    check('1.16 Extend asks for hours in a number box, prefilled with 24', dlg(pg) and pg.input_value('.dlg input') == '24' and pg.get_attribute('.dlg input', 'type') == 'number' and 'Extend this code' in pg.inner_text('.dlg'))
    pg.fill('.dlg input', '12'); pg.click('.dlg [data-dlg="yes"]'); pg.wait_for_timeout(300)
    c = calls(pg, 'admin_transfer_extend_code')
    check('1.17 the typed hours are sent as a number', c and c[-1]['args'] == {'p_transfer': 'x2', 'p_hours': 12}, c)
    pg.click('[data-tact="reject"][data-id="x2"]'); pg.wait_for_timeout(100)
    check('1.18 Cancel code asks for an optional note, as a destructive (red) dialog', dlg(pg) and 'Cancel this code?' in pg.inner_text('.dlg') and pg.query_selector('.dlg.danger') is not None)
    pg.click('.dlg [data-dlg="no"]'); pg.wait_for_timeout(150)
    check('1.19 Cancel on the note box sends nothing (null, not an empty note)', not calls(pg, 'admin_transfer_reject'))
    pg.click('[data-tact="reject"][data-id="x2"]'); pg.wait_for_timeout(100); pg.fill('.dlg input', 'duplicate'); pg.keyboard.press('Enter'); pg.wait_for_timeout(300)
    c = calls(pg, 'admin_transfer_reject')
    check('1.20 the typed note is sent', c and c[-1]['args'] == {'p_transfer': 'x2', 'p_note': 'duplicate'}, c)
    pg.click('[data-tact="reject"][data-id="x2"]'); pg.wait_for_timeout(100); pg.click('.dlg [data-dlg="yes"]'); pg.wait_for_timeout(300)
    c = calls(pg, 'admin_transfer_reject')
    check('1.21 an empty note is allowed and is sent as no note', len(c) == 2 and c[-1]['args']['p_note'] is None, c)
    check('1.22 no page errors with prompts', not errs, errs); b.close()

    # destructive dialogs start on Cancel, so a stray Enter cannot delete anything
    b, pg, errs = open_page(p, db(), 'settings')
    pg.click('#ipclear'); pg.wait_for_timeout(100)
    check('1.23 a destructive dialog is red and its focus starts on Cancel', pg.query_selector('.dlg.danger') is not None and pg.evaluate("document.activeElement.dataset.dlg") == 'no')
    pg.keyboard.press('Enter'); pg.wait_for_timeout(200)
    check('1.24 Enter on Cancel cancels: nothing deleted', not dlg(pg) and not calls(pg, 'admin_clear_client_ips'))
    pg.click('#pchange'); pg.fill('#pupi', 'new@upi'); pg.click('#psave'); pg.wait_for_timeout(100)
    t = pg.inner_text('.dlg') if dlg(pg) else ''
    check('1.25 changing payment details shows old and new values in a red dialog', 'Change the payment details?' in t and 'a@b' in t and 'new@upi' in t and pg.query_selector('.dlg.danger') is not None, t)
    pg.click('.dlg [data-dlg="no"]'); pg.wait_for_timeout(150)
    check('1.26 Cancel keeps the fields open for editing and saves nothing', not calls(pg, 'admin_set_payment_info') and pg.input_value('#pupi') == 'new@upi')
    b.close()

    # ================= 2. only what changed is read again
    d = db(tables=pending_world()); d['rpc']['set_booking_status'] = None
    b, pg, errs = open_page(p, d, 'bookings')
    pg.evaluate('window.__READS.length=0;window.__CALLS.length=0'); auto(pg, True); pg.click('[data-st="paid"] >> nth=0'); pg.wait_for_timeout(700)
    reads = set(pg.evaluate('window.__READS')); cn = {x['name'] for x in calls(pg)}
    check('2.1 marking Paid re-reads bookings, tickets, scans and settings', {'bookings', 'tickets', 'screenshot_scans', 'settings'} <= reads, reads)
    check('2.2 ...and does NOT re-read transfers, emails, feedback, messages or the log', not (reads & {'transfers', 'transfer_buyers', 'ticket_emails', 'booking_feedback', 'game_messages', 'ticket_messages', 'settings_log', 'ticket_prizes'}), reads)
    check('2.3 ...it refreshes the registration banner and the repeat-address flags, but not the transfer money', {'admin_approve_bookings', 'admin_registration_status', 'admin_ip_flags'} <= cn and 'admin_transfer_money' not in cn, cn)
    pg.evaluate('window.__READS.length=0;window.__CALLS.length=0'); pg.click('[data-refresh]:visible'); pg.wait_for_timeout(400)
    reads = set(pg.evaluate('window.__READS'))
    check('2.4 the Refresh button still reads everything', {'bookings', 'tickets', 'screenshot_scans', 'settings', 'settings_log', 'booking_feedback', 'transfers', 'transfer_buyers', 'game_messages', 'ticket_messages'} <= reads and 'ticket_emails' not in reads, reads)
    check('2.5 no page errors', not errs, errs); b.close()

    # reading in parallel: with a slow database the whole reload takes about one wait, not twelve
    d = db(); b, pg, errs = open_page(p, d)
    pg.evaluate('window.__DB.delay=300'); t0 = pg.evaluate('Date.now()'); pg.evaluate('sync()'); pg.wait_for_timeout(50)
    t1 = pg.evaluate('(async()=>{const a=performance.now();await sync();return performance.now()-a})()')
    check('2.6 a full reload with 300 ms per database function takes well under 1.5 s (parts are read at the same time)', t1 < 1500, t1); b.close()

    # ================= 3. the screen is updated in place
    d = db(tables=pending_world(40)); d['rpc']['set_booking_status'] = None
    b, pg, errs = open_page(p, d, 'bookings')
    pg.evaluate("document.querySelector('#top').dataset.keep='1';document.querySelector('#rail').dataset.keep='1'")
    pg.evaluate('window.scrollTo(0,900)'); pg.wait_for_timeout(100); y0 = pg.evaluate('scrollY')
    auto(pg, True); pg.evaluate("document.querySelectorAll('.bk')[8].querySelector('[data-st=paid]').click()"); pg.wait_for_timeout(700)
    y1 = pg.evaluate('scrollY')
    check('3.1 the page is long enough for the test (scrolled down)', y0 >= 800, y0)
    check('3.2 marking Paid keeps the scroll position', abs(y1 - y0) <= 2, (y0, y1))
    check('3.3 the top bar and the side menu are updated in place, not rebuilt', pg.evaluate("document.querySelector('#top').dataset.keep") == '1' and pg.evaluate("document.querySelector('#rail').dataset.keep") == '1')
    check('3.4 a booking card is still there after the redraw', pg.evaluate("document.querySelectorAll('.bk').length") >= 40, pg.evaluate("document.querySelectorAll('.bk').length"))
    b.close()

    # open filter panel and typed text survive an action
    d = db(); d['rpc']['set_coordinator'] = {'label': 'E26-001C'}
    b, pg, errs = open_page(p, d, 'people')
    pg.click('.flt summary'); check('3.5 the filter panel is open', pg.evaluate("document.querySelector('.flt').open"))
    pg.click('[data-co="make"][data-t="t2"]'); pg.wait_for_timeout(100); pg.click('.dlg [data-dlg="yes"]'); pg.wait_for_timeout(400)
    check('3.6 the filter panel is still open after an action redraws the list', pg.evaluate("document.querySelector('.flt').open"))
    b.close()

    d = db(); d['tables']['settings'] = dict(d['tables']['settings'], show_about=True); d['rpc']['admin_set_event'] = None; d['rpc']['admin_update_settings'] = None
    b, pg, errs = open_page(p, d, 'settings')
    pg.fill('#sprice', '999'); pg.fill('#thours', '99'); pg.fill('#svenue', 'Typed Hall')
    pg.click('#evsave'); pg.wait_for_timeout(400)
    check('3.7 saving one card does not wipe what was typed in another (price)', pg.input_value('#sprice') == '999', pg.input_value('#sprice'))
    check('3.8 ...nor another card (transfer hours) ...', pg.input_value('#thours') == '99')
    check('3.9 ...and the venue just saved is still shown', pg.input_value('#svenue') == 'Typed Hall')
    check('3.10 and the save itself worked', calls(pg, 'admin_set_event') and 'Event details saved' in pg.inner_text('#toasts'), pg.inner_text('#toasts'))
    pg.click('#ssave'); pg.wait_for_timeout(400)
    check('3.11 saving Registration settings sends the typed price', calls(pg, 'admin_update_settings')[-1]['args']['p_price'] == 999, calls(pg, 'admin_update_settings'))
    check('3.12 ...and keeps what was typed in other cards', pg.input_value('#thours') == '99')
    pg.click('#pchange'); pg.fill('#pupi', 'zzz@bank'); pg.click('#pcancel'); pg.wait_for_timeout(200)
    check('3.13 pressing Cancel on payment details still puts the saved value back', pg.input_value('#pupi') == 'a@b', pg.input_value('#pupi'))
    check('3.14 no page errors on Settings', not errs, errs); b.close()

    # the number inside a button counts as the button (it used to be ignored)
    b, pg, errs = open_page(p, db(), 'bookings')
    pg.click('.chip[data-chip="paid"] span'); pg.wait_for_timeout(100)
    check('3.15 tapping the count inside a status chip selects that status', pg.evaluate('S.f.pay') == 'paid' and pg.query_selector('.chip[data-chip="paid"].on') is not None)
    b.close()

    # ================= 4. progress and double taps
    d = db(tables=pending_world()); d['rpc']['set_booking_status'] = None
    b, pg, errs = open_page(p, d, 'bookings'); pg.evaluate('window.__DB.delay=500')
    auto(pg, True); pg.evaluate("(()=>{const b=document.querySelector('[data-st=paid]');b.click();b.click();b.click()})()"); pg.wait_for_timeout(120)
    check('4.1 while the database works, the page shows it (progress bar on)', pg.evaluate("document.body.classList.contains('working')"))
    check('4.2 ...and the button is locked', pg.evaluate("document.querySelector('[data-st=paid]').dataset.run") == '1')
    pg.wait_for_timeout(2800)
    check('4.3 three quick taps send the change only once', len(calls(pg, 'admin_approve_bookings')) == 1, calls(pg, 'admin_approve_bookings'))
    check('4.4 afterwards the progress bar is off', not pg.evaluate("document.body.classList.contains('working')"))
    b.close()

    # an error never leaves a button stuck
    d = db(tables=pending_world()); d['rpc']['set_booking_status'] = None
    b, pg, errs = open_page(p, d, 'bookings')
    pg.evaluate("(()=>{window.__rpc0=db.rpc;db.rpc=()=>{throw new Error('network down')}})()")
    pg.click('[data-st="paid"] >> nth=0'); pg.wait_for_timeout(300)
    check('4.5 an unexpected failure shows a plain message instead of nothing', 'Something went wrong' in pg.inner_text('#toasts') and 'network down' in pg.inner_text('#toasts'), pg.inner_text('#toasts') if pg.query_selector('#toasts') else 'no toast')
    check('4.6 ...and the button is usable again', pg.evaluate("document.querySelector('[data-st=paid]').dataset.run") is None)
    b.close()

    # ================= 5. toasts, tab bar, sheets
    b, pg, errs = open_page(p, db())
    pg.evaluate("toast('first',5000);toast('second',5000)"); pg.wait_for_timeout(100)
    check('5.1 two toasts at once are stacked, both readable', pg.evaluate("document.querySelectorAll('#toasts .toast').length") == 2 and pg.get_attribute('#toasts', 'aria-live') == 'polite')
    pg.evaluate("openSheet('person','t2')"); pg.wait_for_timeout(100)
    first = pg.evaluate("document.querySelector('.sheet').classList.contains('still')")
    pg.evaluate("renderSheet()"); again = pg.evaluate("document.querySelector('.sheet').classList.contains('still')")
    check('5.2 a sheet slides in once; drawing it again does not replay the slide (and keeps its scroll)', first is False and again is True, (first, again))
    b.close()

    b, pg, errs = small(p, db())
    check('5.3 on a phone the menu is a bottom bar and the side menu is hidden', pg.is_visible('#bnav') and not pg.is_visible('#rail'))
    pg.click('#bnav button[data-tab="people"]'); pg.wait_for_timeout(150)
    check('5.4 tapping a bottom-bar item opens it and marks it as the open one', tab_on(pg, 'people') and pg.query_selector('#bnav [aria-current="page"][data-tab="people"]') is not None)
    check('5.5 no sideways scrolling at 390 px', pg.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'))
    pg.click('#bnav button[data-tab="overview"]'); pg.evaluate('window.scrollTo(0,300)'); pg.click('#bnav button[data-tab="overview"][aria-current="page"]'); pg.wait_for_timeout(100)
    check('5.6 tapping the open item again scrolls to the top', pg.evaluate('scrollY') == 0)
    b.close()

    # ================= 6. sign out and in builds the screen again; gate staff unaffected
    b, pg, errs = open_page(p, db())
    pg.click('[data-logout]:visible'); pg.wait_for_timeout(150)
    check('6.1 signing out shows the login', pg.query_selector('#login') is not None and pg.query_selector('#rail button') is None)
    pg.fill('#em', 'a@b.c'); pg.fill('#pw', 'x'); pg.click('#login'); pg.wait_for_timeout(400)
    check('6.2 signing in again builds the header and tabs again', pg.query_selector('#top') is not None and pg.query_selector('#rail button') is not None and 'Admin One' in pg.inner_text('#rail'), pg.inner_text('#app')[:100])
    check('6.3 no page errors on sign out / in', not errs, errs); b.close()

    # ================= 7. data stays fresh without pressing Refresh
    NEW = "{id:'b9',booking_code:'CODE0009',status:'pending',kind:'registration',amount_expected:250,people_count:1,created_at:'2026-10-20T10:00:00Z',screenshot_path:'p9.jpg'}"
    VIS = "Object.defineProperty(document,'visibilityState',{get:()=>window.__vs,configurable:true});window.__vs='visible'"
    def leave_and_return(pg, minutes_away):
        pg.evaluate("window.__vs='hidden';document.dispatchEvent(new Event('visibilitychange'))")
        pg.evaluate(f"window.__off=(window.__off||0)+{int(minutes_away*60000)};window.__vs='visible';document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(600)
    b, pg, errs = open_page(p, db(), 'bookings'); pg.evaluate(VIS)
    pg.evaluate(f"window.__DB.tables.bookings=window.__DB.tables.bookings.concat([{NEW}])")
    leave_and_return(pg, 0.1)
    check('7.1 coming back after only a few seconds does not reload', 'CODE0009' not in pg.inner_text('#tbl'))
    leave_and_return(pg, 2)
    check('7.2 coming back after a while shows a booking added meanwhile, without pressing Refresh', 'CODE0009' in pg.inner_text('#tbl'), pg.inner_text('#tbl')[:100])
    pg.evaluate("window.scrollTo(0,0)"); pg.fill('#q', 'CODE'); pg.focus('#q')
    pg.evaluate(f"window.__DB.tables.bookings=window.__DB.tables.bookings.concat([{NEW.replace('b9','b8').replace('CODE0009','CODE0008')}])")
    leave_and_return(pg, 2)
    check('7.3 while you are typing in a box the data is refreshed but the screen is not redrawn under your fingers', pg.input_value('#q') == 'CODE' and pg.evaluate("S.bookings.some(b=>b.booking_code==='CODE0008')") and 'CODE0008' not in pg.inner_text('#tbl'), pg.inner_text('#tbl')[:80])
    pg.evaluate("document.activeElement.blur()"); pg.click('[data-refresh]:visible'); pg.wait_for_timeout(300)
    check('7.4 pressing Refresh then shows it', 'CODE0008' in pg.inner_text('#tbl'))
    check('7.5 no page errors', not errs, errs); b.close()

    d = db(); b, pg, errs = open_page(p, d, 'settings'); pg.evaluate(VIS)
    pg.fill('#sprice', '777'); pg.evaluate("document.activeElement.blur()")
    pg.evaluate("window.__DB.tables.settings=Object.assign({},window.__DB.tables.settings,{cap:222})")
    leave_and_return(pg, 2)
    check('7.6 on Settings an automatic refresh brings the new cap but keeps an unsaved price you typed', pg.input_value('#scap') == '222' and pg.input_value('#sprice') == '777', (pg.input_value('#scap'), pg.input_value('#sprice')))
    b.close()

    # a failed background refresh must not show a red error message
    b, pg, errs = open_page(p, db(), 'bookings'); pg.evaluate(VIS)
    pg.evaluate("window.__DB.tables.bookings={error:'network problem'}"); leave_and_return(pg, 2)
    check('7.7 a failed automatic refresh stays silent and keeps the screen', 'Could not load' not in pg.inner_text('#app') and 'CODE0001' in pg.inner_text('#tbl'), pg.inner_text('#app')[:120])
    pg.click('[data-refresh]:visible'); pg.wait_for_timeout(300)
    check('7.8 a failed manual Refresh does say so', 'Could not load data' in pg.inner_text('#app'))
    pg.evaluate("window.__DB.tables.bookings=[]"); b.close()

    # an open dialog blocks automatic redraws
    d = db(); d['rpc']['set_coordinator'] = {'label': 'E26-001C'}
    b, pg, errs = open_page(p, d, 'people'); pg.evaluate(VIS)
    pg.click('[data-co="make"][data-t="t2"]'); pg.wait_for_timeout(100)
    pg.evaluate(f"window.__DB.tables.bookings=window.__DB.tables.bookings.concat([{NEW}])"); leave_and_return(pg, 2)
    check('7.9 an open dialog is never closed by an automatic refresh', dlg(pg))
    b.close()

print(f'{sum(results)} passed, {len(results)-sum(results)} failed')
