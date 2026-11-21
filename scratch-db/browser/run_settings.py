from admin_test import *
# Browser suite for Settings, Scan and Feedback screens (Step 6 of the admin redesign): sticky section bar, Indian-style dates, no repeated title.
# Run:  cd scratch-db/browser && python3 run_settings.py | tail -1
FB = [dict(id='f1', booking_id='b1', rating=5, comment='Cannot wait!', updated_at='2026-10-25T10:00:00Z')]
def phone(p, database, w=390, h=800):
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': w, 'height': h}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.route('**/*', lambda r: (r.fulfill(body=HTML, content_type='text/html') if r.request.url.endswith('/admin/test.html') else r.fulfill(body='/*stub*/', content_type='text/javascript') if r.request.url.endswith('.js') or '/npm/' in r.request.url else r.fulfill(status=204, body='')))
    pg.add_init_script('window.__DB=' + json.dumps(database) + ';'); pg.add_init_script(MOCK); pg.add_init_script(CH); pg.add_init_script(DLG_BOT)
    pg.goto('https://example.test/admin/test.html'); pg.wait_for_selector('#v'); return b, pg, errs
with sync_playwright() as p:
    # phone: the section bar (chips) stays under the top bar and jumps to a card
    b, pg, errs = (lambda r: (go_tab(r[1], 'settings'), r)[1])(phone(p, db())); pg.wait_for_timeout(200)
    pg.evaluate("window.scrollTo(0,1500)"); pg.wait_for_timeout(200)
    r = pg.evaluate("(()=>{const n=document.querySelector('#snav').getBoundingClientRect(),t=document.querySelector('#top').getBoundingClientRect();return [Math.round(n.top-t.bottom),n.bottom>0&&n.top<innerHeight]})()")
    check('S1 phone: the section bar stays in view right under the top bar while scrolling', r[1] and abs(r[0]) <= 2, r)
    cid = pg.evaluate("[...document.querySelectorAll('#snav .chip')].find(c=>c.textContent==='Transfers').dataset.jump")
    pg.click(f'#snav [data-jump="{cid}"]'); pg.wait_for_timeout(900)
    r = pg.evaluate("(id=>{const c=document.getElementById(id).getBoundingClientRect(),n=document.querySelector('#snav').getBoundingClientRect();return [Math.round(c.top-n.bottom)]})", cid)
    check('S2 phone: jumping to a section leaves its title visible, not hidden behind the bars', r[0] >= -2 and 'Ticket transfers' in pg.inner_text('#' + cid), r)
    check('S3 phone: no page errors', not errs, errs); b.close()
    # laptop: the side menu stays in view while scrolling and switches the group
    b, pg, errs = open_page(p, db(), 'settings'); pg.wait_for_timeout(200)
    pg.click('#sside [data-sg="log"]'); pg.evaluate("window.scrollTo(0,1500)"); pg.wait_for_timeout(200)
    r = pg.evaluate("(()=>{const n=document.querySelector('#sside').getBoundingClientRect();return n.bottom>0&&n.top<innerHeight})()")
    check('S1 laptop: the side menu stays in view while scrolling', r, r)
    pg.click('#sside [data-sg="transfers"]'); pg.wait_for_timeout(200)
    check('S2 laptop: choosing Transfers shows the Ticket transfers card, from the top', 'Ticket transfers' in pg.inner_text('.spane.on') and pg.evaluate("scrollY") == 0, pg.evaluate("scrollY"))
    check('S3 laptop: no page errors', not errs, errs); b.close()
    b, pg, errs = open_page(p, db(tables=dict(booking_feedback=FB)), 'feedback')
    t = pg.inner_text('#v')
    check('S4 Feedback dates are in the Indian style (25 Oct, 3:30 pm), not 10/25/2026', '25 Oct' in t and '10/25/2026' not in t, t[:200]); b.close()
    b, pg, errs = open_page(p, db(), 'scan')
    check('S5 Scan page does not repeat its title inside the card, and still has its buttons', pg.inner_text('#v').count('Scan screenshots') == 0 and pg.query_selector('#scan') is not None, pg.inner_text('#v')[:120])
    check('S6 the page header still says Scan screenshots', 'Scan screenshots' in pg.inner_text('.page, #app')); b.close()
print(f"{sum(results)} passed, {len(results)-sum(results)} failed")
