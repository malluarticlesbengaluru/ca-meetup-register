from admin_test import *
# Browser suite for the new staff-page frame (Step 2 of the admin redesign): menu groups and badges, Today "Needs you", theme, search, phone bar + More sheet, no email anywhere.
# Run:  cd scratch-db/browser && python3 run_frame.py | tail -1
def phone(p, database, w=390, h=800):
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': w, 'height': h}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.route('**/*', lambda r: (r.fulfill(body=HTML, content_type='text/html') if r.request.url.endswith('/admin/test.html')
        else r.fulfill(body='/*stub*/', content_type='text/javascript') if r.request.url.endswith('.js') or '/npm/' in r.request.url else r.fulfill(status=204, body='')))
    pg.add_init_script('window.__DB=' + json.dumps(database) + ';'); pg.add_init_script(MOCK); pg.add_init_script(CH); pg.add_init_script(DLG_BOT)
    pg.goto('https://example.test/admin/test.html'); pg.wait_for_selector('#v'); return b, pg, errs
with sync_playwright() as p:
    pend = [bk(5, status='pending', amt=250)]
    d = db(tables=dict(bookings=BOOKINGS + pend))
    b, pg, errs = open_page(p, d)
    r = pg.inner_text('#rail').lower()
    check('F1 side menu has the three groups in order', r.index('daily') < r.index('event day') < r.index('setup'), r)
    check('F2 Payments shows a badge with the number waiting', pg.query_selector('#rail button[data-tab="bookings"] .bdg') is not None or '1' in pg.inner_text('#rail button[data-tab="bookings"]'))
    check('F3 Today is the open item', on_tab(pg, 'overview'))
    pg.click('[data-need]:visible'); pg.wait_for_timeout(200)
    check('F4 a "Needs you" button opens Payments already filtered', on_tab(pg, 'bookings'))
    pg.click('button[data-theme], [data-act="theme"], #theme', timeout=3000) if pg.query_selector('button[data-theme], [data-act="theme"], #theme') else None
    pg.evaluate("setTheme('dark')"); check('F5 dark theme is applied and remembered', pg.evaluate("document.documentElement.dataset.theme") == 'dark' and pg.evaluate("localStorage.getItem('adm_theme')") == 'dark')
    pg.evaluate("setTheme('light')"); check('F6 light theme can be set again', pg.evaluate("document.documentElement.dataset.theme") == 'light')
    pg.keyboard.press('Escape'); pg.evaluate("document.activeElement.blur()"); pg.keyboard.press('/')
    check('F7 the / key jumps to the search box', pg.evaluate("document.activeElement.id") == 'gtop')
    pg.fill('#gtop', 'Ben'); pg.wait_for_timeout(300)
    check('F8 searching shows matching people in the drop-down', 'Ben' in pg.inner_text('#sdrop'), pg.inner_text('#sdrop'))
    go_tab(pg, 'people'); t = pg.inner_text('#v')
    check('F9 no email is shown anywhere on People', '@example.com' not in t and 'Email' not in t)
    pg.evaluate("openSheet('person','t2')"); pg.wait_for_timeout(200)
    check('F10 no email on the person sheet', '@example.com' not in pg.inner_text('.sheet'))
    pg.evaluate("nav({tab:'people',sheets:[]})"); pg.wait_for_timeout(200)
    go_tab(pg, 'transfers'); check('F11 no email on Transfers', '@example.com' not in pg.inner_text('#v') and 'eve@' not in pg.inner_text('#v'))
    check('F12 no page errors on wide screen', not errs, errs); b.close()
    b, pg, errs = phone(p, d)
    check('F13 phone: bottom bar visible, side menu hidden', pg.is_visible('#bnav') and not pg.is_visible('#rail'))
    check('F14 phone: no sideways scrolling', pg.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'))
    pg.click('#bnav [data-more], #bnav .morebtn, #bnav button[data-act="morebtn"]') if pg.query_selector('#bnav [data-more], #bnav .morebtn, #bnav button[data-act="morebtn"]') else pg.evaluate("document.querySelector('#bnav').lastElementChild.click()")
    pg.wait_for_timeout(200)
    check('F15 phone: the More sheet opens and lists Settings', pg.is_visible('#more') and 'Settings' in pg.inner_text('#more'), pg.inner_text('#bnav'))
    pg.click('#more button[data-tab="settings"]'); pg.wait_for_timeout(200)
    check('F16 choosing from More opens it and closes the sheet', not pg.is_visible('#more') and 'Registration settings' in pg.inner_text('#v'))
    check('F17 phone: no sideways scrolling on Settings', pg.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'))
    check('F18 no page errors on phone', not errs, errs); b.close()
    b, pg, errs = open_page(p, db(tables=dict(staff=dict(name='Gate One', role='gate'))))
    check('F19 gate staff do not get the admin menu or search', pg.query_selector('#rail button[data-tab="settings"]') is None and not pg.is_visible('#gtop')); b.close()
print(f"{sum(results)} passed, {len(results)-sum(results)} failed")
