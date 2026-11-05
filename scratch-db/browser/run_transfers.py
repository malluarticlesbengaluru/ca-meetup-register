from admin_test import *
# Browser suite for the Transfers screen (Step 5 of the admin redesign): count tiles that jump to sections, money panel at the bottom, tables that become small cards on a phone.
# Run:  cd scratch-db/browser && python3 run_transfers.py | tail -1
def phone(p, database, w=390, h=850):
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': w, 'height': h}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.route('**/*', lambda r: (r.fulfill(body=HTML, content_type='text/html') if r.request.url.endswith('/admin/test.html') else r.fulfill(body='/*stub*/', content_type='text/javascript') if r.request.url.endswith('.js') or '/npm/' in r.request.url else r.fulfill(status=204, body='')))
    pg.add_init_script('window.__DB=' + json.dumps(database) + ';'); pg.add_init_script(MOCK); pg.add_init_script(CH); pg.add_init_script(DLG_BOT)
    pg.goto('https://example.test/admin/test.html'); pg.wait_for_selector('#v'); return b, pg, errs
with sync_playwright() as p:
    b, pg, errs = open_page(p, db(), 'transfers')
    t = pg.inner_text('.tsum')
    check('T1 four count tiles: waiting 1, codes 1, to pay sellers 1, to return 0', pg.evaluate("[...document.querySelectorAll('.tsum button b')].map(x=>x.textContent).join(',')") == '1,1,1,0', t)
    check('T2 tiles with something to do are highlighted, the empty one is not', pg.evaluate("[...document.querySelectorAll('.tsum button')].map(x=>x.classList.contains('hot')).join(',')") == 'true,false,true,false')
    check('T3 the first thing on the page after the tiles is "Waiting for you"; the money panel is at the bottom', pg.evaluate("(()=>{const a=document.querySelector('#tsec-wait').getBoundingClientRect().top,m=document.querySelector('details.mny').getBoundingClientRect().top;return a<m})()"))
    pg.evaluate("window.scrollTo(0,0)"); pg.click('[data-tjump="tsec-pay"]'); pg.wait_for_timeout(700)
    check('T4 tapping "To pay sellers" scrolls to that section', pg.evaluate("Math.abs(document.querySelector('#tsec-pay').getBoundingClientRect().top)<200 && scrollY>0"), pg.evaluate("[scrollY,document.querySelector('#tsec-pay').getBoundingClientRect().top]"))
    check('T5 the money panel is in a collapsible section, open because money is waiting, and still shows the figures', pg.evaluate("document.querySelector('details.mny').open") and '₹230' in pg.inner_text('details.mny') and 'Held by you right now' in pg.inner_text('details.mny'))
    check('T6 Transfer / Reject buttons are still there for the waiting transfer', pg.query_selector('[data-tact="approve"]') is not None and pg.query_selector('[data-tact="reject"]') is not None)
    check('T7 no email on the Transfers page', 'eve@example.com' not in pg.inner_text('#v') and '@example.com' not in pg.inner_text('#v'))
    check('T8 no page errors', not errs, errs); b.close()
    # nothing waiting: tiles show zero and nothing is highlighted
    quiet = db(tables=dict(transfers=[])); b, pg, errs = open_page(p, quiet, 'transfers')
    check('T9 with no transfers all tiles are 0 and none is highlighted', pg.evaluate("[...document.querySelectorAll('.tsum button b')].map(x=>x.textContent).join(',')") == '0,0,0,0' and pg.query_selector('.tsum .hot') is None); b.close()
    # phone
    b, pg, errs = phone(p, db()); go_tab(pg, 'transfers'); pg.wait_for_timeout(200)
    check('T10 phone: tiles are two across and nothing scrolls sideways', pg.evaluate("(()=>{const a=[...document.querySelectorAll('.tsum button')].map(x=>Math.round(x.getBoundingClientRect().top));return a[0]===a[1]&&a[2]===a[3]&&a[2]>a[0]&&document.documentElement.scrollWidth<=innerWidth+1})()"))
    check('T11 phone: the codes table became labelled small cards (header row hidden, every cell labelled)', pg.evaluate("(()=>{const t=document.querySelector('table.rt');return getComputedStyle(t.rows[0]).display==='none'&&[...t.rows[1].cells].every(c=>c.dataset.l)})()"))
    check('T12 phone: Extend and Cancel code are still tappable', pg.is_visible('[data-tact="extend"]') and pg.is_visible('[data-tact="reject"] >> nth=-1'))
    check('T13 phone: no page errors', not errs, errs); b.close()
    # feedback uses the same layout
    fb = [dict(id='f1', booking_id='b1', rating=5, comment='Cannot wait!', updated_at='2026-10-25T10:00:00Z')]
    b, pg, errs = phone(p, db(tables=dict(booking_feedback=fb))); go_tab(pg, 'feedback'); pg.wait_for_timeout(200)
    check('T14 phone: Feedback rows are labelled small cards too, with no sideways scroll', pg.evaluate("(()=>{const t=document.querySelector('table.rt');return !!t&&[...t.rows[1].cells].every(c=>c.dataset.l)&&document.documentElement.scrollWidth<=innerWidth+1})()"), pg.inner_text('#v')[:150])
    check('T15 phone: the comment text is shown', 'Cannot wait!' in pg.inner_text('#v')); b.close()
print(f"{sum(results)} passed, {len(results)-sum(results)} failed")
