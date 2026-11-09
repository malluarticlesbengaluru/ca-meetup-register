# run_activity.py - browser checks for r2_19: the public ticket page records "page opened" and Download presses; the staff page shows them.
# Run: cd scratch-db/browser && python3 run_activity.py | tail -1
# Part 1 uses the public-page helpers of run_public_fixed.py (everything above its own checks). Part 2 uses admin_test.py.
import json, re
src = open('run_public_fixed.py', encoding='utf-8').read().split('# ---- Browser checks')[0]
exec(src)
from admin_test import db as adb, open_page as aopen, go_tab, TICKETS, BOOKINGS, SETTINGS
import admin_test
from playwright.sync_api import sync_playwright
pub_res = res
def logs(pg): return [x['args'] for x in calls(pg) if x['name'] == 'log_ticket_activity']
def open_ticket(pg):
    pg.evaluate("window.__R.lookup_tickets=()=>window.__ok(%s);0" % json.dumps(LOOK['paid']))
    pg.evaluate("S.step='tickets';S.tk.q='AB12CD34';S.tk.phone='9000000002';doSearch()"); pg.wait_for_timeout(300)
    n0 = len(logs(pg)); pg.evaluate("viewTickets()")
    pg.wait_for_function("S.cv&&S.cv[0]", timeout=8000); pg.wait_for_timeout(200); return n0
def dl(pg, js):
    with pg.expect_download(timeout=8000) as d: pg.evaluate(js)
    return d.value.suggested_filename
with sync_playwright() as p:
    for mode in ['database updated', 'database one step behind (function missing)', 'logging fails with an error']:
        b, pg, errs = page(p)
        if mode == 'database updated': pg.evaluate("window.__R.log_ticket_activity=()=>window.__ok({ok:true,logged:1});0")
        if mode.startswith('logging'): pg.evaluate("window.__R.log_ticket_activity=()=>{throw new Error('boom')};0")
        n0 = open_ticket(pg)
        check(f'[{mode}] searching alone logs nothing (only opening the ticket page does)', n0 == 0, logs(pg))
        v = logs(pg)
        check(f'[{mode}] opening the ticket page logs one "view" for the live ticket only (transferred Asha left out)', len(v) == 1 and v[0] == {'p_code': 'AB12CD34', 'p_phone': '9000000002', 'p_action': 'view', 'p_tickets': ['E26-002']}, v)
        f1 = dl(pg, "downloadTicket('jpg',0)")
        check(f'[{mode}] Download JPG still saves the file', f1 == 'Ehsaas26-E26-002-Ben.jpg', f1)
        f2 = dl(pg, "downloadTicket('pdf',0)")
        check(f'[{mode}] Download PDF still saves the file', f2 == 'Ehsaas26-E26-002-Ben.pdf', f2)
        f3 = dl(pg, "downloadAll('pdf')")
        check(f'[{mode}] Download all as PDF still saves the file', f3.endswith('-tickets.pdf'), f3)
        f4 = dl(pg, "downloadAll('jpg')")
        check(f'[{mode}] Download all as JPG still saves the file', f4 == 'Ehsaas26-E26-002-Ben.jpg', f4)
        acts = [(x['p_action'], x['p_tickets']) for x in logs(pg)[1:]]
        check(f'[{mode}] each press is logged with the right action and ticket', acts == [('jpg', ['E26-002']), ('pdf', ['E26-002']), ('all-pdf', ['E26-002']), ('jpg', ['E26-002'])], acts)
        check(f'[{mode}] every log call carries the Booking ID and phone and nothing else', all(set(x) == {'p_code', 'p_phone', 'p_action', 'p_tickets'} for x in logs(pg)))
        check(f'[{mode}] no page errors', not errs, errs); b.close()
pub = res[:]; res.clear()

# ---------------- staff page ----------------
ACT = [dict(ticket_id='t2', views=3, last_view='2026-11-09T12:00:00Z', downloads=2, last_download='2026-11-09T12:30:00Z', last_format='pdf'),
       dict(ticket_id='t3', views=1, last_view='2026-11-09T13:00:00Z', downloads=0, last_download=None, last_format=None),
       dict(ticket_id='t1', views=1, last_view='2026-11-09T13:00:00Z', downloads=1, last_download='2026-11-09T13:05:00Z', last_format='jpg')]  # t1 was transferred away: must not count
def rows(pg): return pg.query_selector_all('#tbl tbody tr')
def names(pg): return [r.query_selector_all('td')[1].inner_text() for r in rows(pg)]
with sync_playwright() as p:
    d = adb(rpc=dict(admin_ticket_activity=ACT))
    b, pg, errs = aopen(p, d)
    t = pg.inner_text('#v')
    check('S1 Today has a "Tickets downloaded" card: 1 of 3, 2 opened the page (the transferred ticket is not counted)', 'Tickets downloaded' in t and re.search(r'Tickets downloaded\s*1\s*of 3 · 2 opened the page', t), t[:400])
    pg.click('[data-sheet="list:downloaded"]'); pg.wait_for_timeout(250); s = pg.inner_text('.sheet')
    check('S2 the card opens a list: Ben under Downloaded, Carl and Dan under Not downloaded yet, with the honest note', 'Downloaded (1)' in s and 'Not downloaded yet (2)' in s and 'not whether the file was saved' in s, s[:500])
    pg.keyboard.press('Escape'); pg.wait_for_timeout(150)
    go_tab(pg, 'people'); pc = pg.inner_text('#pchips')
    check('S3 People has a "Not downloaded yet" chip with 2', 'Not downloaded yet 2' in pc, pc)
    ben = [r for r in rows(pg) if 'Ben' in r.inner_text()][0].inner_text(); carl = [r for r in rows(pg) if 'Carl' in r.inner_text()][0].inner_text()
    check('S4 Ben shows a Downloaded tag with the time and the count; Carl shows none', 'Downloaded' in ben and '×2' in ben and 'Downloaded' not in carl, (ben, carl))
    pg.click('[data-pchip="nodl"]'); pg.wait_for_timeout(150)
    check('S5 the chip lists only people not downloaded (Carl, Dan) and is marked on', sorted(x.split('\n')[0].strip() for x in names(pg)) == ['Carl', 'Dan'] and pg.get_attribute('[data-pchip="nodl"]', 'aria-pressed') == 'true', names(pg))
    pg.click('[data-pchip="all"]'); pg.wait_for_timeout(150)
    check('S6 Everyone clears it', len(rows(pg)) == 3)
    pg.click('[data-pview="cards"]'); pg.wait_for_timeout(200)
    check('S7 the card layout shows the tag too', 'Downloaded' in pg.inner_text('#tbl .pc:has-text("Ben")') and 'Downloaded' not in pg.inner_text('#tbl .pc:has-text("Carl")'))
    pg.click('[data-pview="table"]'); pg.wait_for_timeout(200)
    pg.click('#tbl tbody tr:has-text("Ben") .lk'); pg.wait_for_timeout(250); s = pg.inner_text('.sheet')
    check("S8 Ben's sheet: page opened 3 times, downloaded 2 times, last format PDF", 'opened 3 times' in s and '2 times' in s and 'PDF' in s, s)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(150)
    pg.click('#tbl tbody tr:has-text("Carl") .lk'); pg.wait_for_timeout(250); s = pg.inner_text('.sheet')
    check("S9 Carl's sheet: page opened 1 time, downloaded: not yet", 'opened 1 time' in s and 'not yet' in s, s)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(150)
    pg.evaluate("window.__B=[];const o=URL.createObjectURL;URL.createObjectURL=b=>{window.__B.push(b);return o(b)};0")
    pg.evaluate("csv()"); pg.wait_for_timeout(300); txt = pg.evaluate("window.__B.length?window.__B[0].text():''")
    lines = txt.lstrip('\ufeff').split('\r\n')
    check('S10 the CSV has the new columns', 'Downloaded (times)' in lines[0] and 'Last downloaded' in lines[0] and 'Ticket page opened (times)' in lines[0], lines[0])
    check('S11 the CSV row for Ben has 3 opens and 2 downloads; Carl has 1 open and 0 downloads', any('"Ben"' in l and '"3"' in l and '"2"' in l and '"pdf"' in l for l in lines) and any('"Carl"' in l and '"1"' in l and '"0"' in l for l in lines), lines)
    check('S12 no page errors (database updated)', not errs, errs); b.close()
    for label, rpc in [('database one step behind (function missing)', {}), ('a gate account (NOT_ALLOWED)', dict(admin_ticket_activity='NOT_ALLOWED'))]:
        b, pg, errs = aopen(p, adb(rpc=rpc))
        t = pg.inner_text('#v'); go_tab(pg, 'people')
        check(f'S13 [{label}] no card, no chip, no tag, nothing broken', 'Tickets downloaded' not in t and 'Not downloaded' not in pg.inner_text('#pchips') and 'Downloaded' not in pg.inner_text('#tbl') and len(rows(pg)) == 3, pg.inner_text('#pchips'))
        pg.evaluate("window.__B=[];const o=URL.createObjectURL;URL.createObjectURL=b=>{window.__B.push(b);return o(b)};0"); pg.evaluate("csv()"); pg.wait_for_timeout(300)
        h = pg.evaluate("window.__B.length?window.__B[0].text():''").lstrip('\ufeff').split('\r\n')[0]
        check(f'S14 [{label}] the CSV is exactly as before', 'Downloaded' not in h and h.startswith('"Ticket No."'), h)
        check(f'S15 [{label}] no page errors', not errs, errs); b.close()
allr = pub + res
print(f'run_activity: {sum(allr)} passed, {len(allr) - sum(allr)} failed')
