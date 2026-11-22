from admin_test import *
# Browser suite for the Attendee space card in Admin > Settings > Event day (r2_32): shown, saved, switched, and absent-safe.
# Run:  cd scratch-db/browser && python3 run_attendee_space.py | tail -1
MB = 1048576
SUM = dict(shared=False, pool_bytes=75*1024*MB, cap_bytes=500*MB, used_bytes=3*1024*MB, photo_bytes=2*1024*MB, video_bytes=1024*MB, present=140, per_person_bytes=500*MB, accounts=[2*1024*MB, 1024*MB, 0, 0])
def calls(pg, name): return [x for x in pg.evaluate('window.__CALLS||[]') if x['name'] == name]
with sync_playwright() as p:
    d = db(rpc=dict(admin_attendee_summary=SUM, admin_set_attendee_space=None))
    b, pg, errs = open_page(p, d, 'settings'); pg.wait_for_timeout(300)
    pg.click('#sside [data-sg="event"]'); pg.wait_for_timeout(300)
    t = pg.inner_text('#attcard')
    check('A1 card shows the switch OFF, the 75 GB pool and the 500 MB cap', not pg.is_checked('#atsh') and pg.input_value('#atpool') == '75' and pg.input_value('#atcap') == '500', t[:200])
    check('A2 it shows use of the pool and what each Storj account holds', '3.00 GB used of 75.00 GB' in t and 'account 1 (public photos) 2.00 GB' in t and 'account 3 (new) 0.0 MB' in t and 'account 4 (new) 0.0 MB' in t, t)
    check('A3 right-now line: 140 present, each up to 500 MB (75 GB / 140 = 548, cap 500)', '140 people are marked Present' in t and '500 MB' in pg.inner_text('#atprev'), pg.inner_text('#atprev'))
    pg.fill('#atpool', '40'); pg.wait_for_timeout(100)
    check('A4 changing the pool updates the line (40 GB / 140 = 292 MB)', '292 MB' in pg.inner_text('#atprev'), pg.inner_text('#atprev'))
    pg.click('#atsave'); pg.wait_for_timeout(400)
    c = calls(pg, 'admin_set_attendee_space')
    check('A5 Save sends pool 40960 MB and cap 500 and not the switch', c and c[-1]['args'] == {'p_pool_mb': 40960, 'p_cap_mb': 500}, c)
    pg.click('#atsh'); pg.wait_for_timeout(400)
    c = calls(pg, 'admin_set_attendee_space')
    check('A6 the switch sends only p_shared true', c and c[-1]['args'] == {'p_shared': True}, c)
    check('A7 no page errors', not errs, errs); b.close()
    b, pg, errs = open_page(p, db(), 'settings'); pg.wait_for_timeout(300)
    pg.click('#sside [data-sg="event"]'); pg.wait_for_timeout(300)
    check('A8 database not updated yet: card says so, the Photos and Videos cards still load, no errors', 'r2_32 has not been run' in pg.inner_text('#attcard') and pg.query_selector('#photocard') is not None and not errs, (pg.inner_text('#attcard'), errs)); b.close()
    d = db(rpc=dict(admin_attendee_summary=dict(SUM, shared=True), admin_set_attendee_space='NOT_ALLOWED'))
    b, pg, errs = open_page(p, d, 'settings'); pg.wait_for_timeout(300); pg.click('#sside [data-sg="event"]')
    check('A9 ON: the text says photos and videos share one space; switch is ticked', pg.is_checked('#atsh') and 'ON: every attendee has one amount' in pg.inner_text('#attcard'))
    pg.click('#atsh'); pg.wait_for_timeout(400)
    check('A10 a refused change shows a message and puts the switch back', pg.is_checked('#atsh') and pg.inner_text('#toasts').strip() != '', pg.inner_text('#toasts')); b.close()
print(f"{sum(results)} passed, {len(results)-sum(results)} failed")
