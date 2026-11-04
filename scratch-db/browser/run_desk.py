from admin_test import *
# Browser suite for the payment review desk (Step 3 of the admin redesign): queue, screenshot beside details, Paid / Reject advance, keyboard, back gesture, phone.
# Run:  cd scratch-db/browser && python3 run_desk.py | tail -1
def world(n):
    B = [bk(i, status='pending') for i in range(10, 10 + n)]
    T = [mk(100 + i, booking_id=f'b{10+i}', name=f'Pend{i}') for i in range(n)]
    for i, b in enumerate(B): b['created_at'] = f'2026-10-2{i}T10:00:00Z'
    return dict(bookings=BOOKINGS + B, tickets=TICKETS + T)
HOOK = """(()=>{const o=db.rpc;db.rpc=(n,a)=>{if(n==='set_booking_status'){const b=window.__DB.tables.bookings.find(x=>x.id===a.p_booking);if(b)b.status=a.p_status}return o(n,a)}})()"""
def desk_page(p, n=3, w=1300, h=900):
    d = db(tables=world(n)); d['rpc']['set_booking_status'] = None; b, pg, errs = open_page(p, d); pg.set_viewport_size({'width': w, 'height': h}); pg.evaluate(HOOK); go_tab(pg, 'bookings'); return b, pg, errs
def shown(pg): return pg.inner_text('#desk .dk-i').split('\n')[1] if pg.query_selector('#desk') else None
def sets(pg): return [c['args'] for c in pg.evaluate('window.__CALLS') if c['name'] == 'set_booking_status']
with sync_playwright() as p:
    b, pg, errs = desk_page(p)
    check('D1 Payments has a "Review payments (3)" button', 'Review payments (3)' in pg.inner_text('#v'))
    pg.click('[data-dk="open"]'); pg.wait_for_selector('#desk img')
    t = pg.inner_text('#desk')
    check('D2 the desk opens on the OLDEST waiting booking, with the counter and the screenshot', '1 of 3 waiting' in t and 'CODE00010' in t and pg.query_selector('#desk img') is not None, t[:200])
    check('D3 the screenshot and the details are side by side on a laptop', pg.evaluate("(()=>{const a=document.querySelector('#dkimg').getBoundingClientRect(),c=document.querySelector('.dk-i').getBoundingClientRect();return a.right<=c.left+2&&Math.abs(a.top-c.top)<4})()"))
    check('D4 the details show the people, the amount and Paid / Reject buttons', 'Pend0' in t and '₹250' in t and pg.query_selector('[data-dk="paid"]') and pg.query_selector('[data-dk="reject"]'))
    pg.click('[data-dk="skip"]'); pg.wait_for_timeout(100); check('D5 Skip goes to the next one and nothing is sent', 'CODE00011' in pg.inner_text('#desk') and not sets(pg))
    pg.click('[data-dk="prev"]'); pg.wait_for_timeout(100); check('D6 Back returns to the previous one', 'CODE00010' in pg.inner_text('#desk'))
    pg.click('[data-dk="paid"]'); pg.wait_for_timeout(500)
    s = sets(pg); t = pg.inner_text('#desk')
    check('D7 Paid sends the right booking and status, with no question asked', s and s[-1] == {'p_booking': 'b10', 'p_status': 'paid'}, s)
    check('D8 ...and moves straight to the next one: "1 of 2 waiting · 1 done"', 'CODE00011' in t and '1 of 2 waiting' in t and '1 done' in t, t[:160])
    dlg_msgs(pg); auto(pg, False); pg.keyboard.press('r'); pg.wait_for_timeout(500)
    check('D9 R asks first, naming the booking', 'CODE00011' in ' '.join(dlg_msgs(pg)))
    check('D10 Cancel leaves it pending and still on screen', len(sets(pg)) == 1 and 'CODE00011' in pg.inner_text('#desk'))
    auto(pg, True); pg.keyboard.press('r'); pg.wait_for_timeout(700)
    s = sets(pg); check('D11 confirming Reject sends rejected for that booking', s[-1] == {'p_booking': 'b11', 'p_status': 'rejected'}, s)
    check('D12 the last one is shown ("1 of 1 waiting · 2 done")', 'CODE00012' in pg.inner_text('#desk') and '1 of 1 waiting' in pg.inner_text('#desk'))
    check('D13 with one left, Skip and Back are switched off', pg.is_disabled('[data-dk="skip"]') and pg.is_disabled('[data-dk="prev"]'))
    pg.click('#desk img'); check('D14 tapping the screenshot zooms it', pg.evaluate("document.querySelector('#desk img').classList.contains('z')"))
    pg.keyboard.press('p'); pg.wait_for_timeout(600)
    check('D15 after the last one the desk closes by itself with "All caught up"', pg.query_selector('#desk') is None and 'All caught up' in pg.inner_text('#toasts') and not pg.evaluate("document.body.classList.contains('deskopen')"), pg.inner_text('#toasts'))
    check('D16 the Payments list behind it shows nothing pending and the button is gone', 'Review payments' not in pg.inner_text('#v'))
    check('D17 no page errors', not errs, errs); b.close()
    # back gesture, Escape, typing safety
    b, pg, errs = desk_page(p)
    pg.click('[data-dk="open"]'); pg.wait_for_selector('#desk'); pg.go_back(); pg.wait_for_timeout(250)
    check('D18 the phone back gesture closes the desk and stays on Payments', pg.query_selector('#desk') is None and on_tab(pg, 'bookings') and not sets(pg))
    pg.click('[data-dk="open"]'); pg.wait_for_selector('#desk'); pg.keyboard.press('Escape'); pg.wait_for_timeout(250)
    check('D19 Escape closes the desk', pg.query_selector('#desk') is None)
    pg.click('[data-dk="open"]'); pg.wait_for_selector('#desk'); pg.keyboard.press('Escape'); pg.wait_for_timeout(250)
    pg.click('[data-dk="open"]') if pg.query_selector('[data-dk="open"]') else go_tab(pg, 'bookings')
    check('D21 no page errors', not errs, errs); b.close()
    # browser shortcuts such as Ctrl+R (reload) must not be taken for "Reject"
    b, pg, errs = desk_page(p); pg.click('[data-dk="open"]'); pg.wait_for_selector('#desk')
    pg.keyboard.press('Control+r'); pg.wait_for_timeout(300)
    check('D22 Ctrl+R does not trigger Reject', pg.query_selector('.dlg') is None and not sets(pg)); b.close()
    # phone
    b, pg, errs = desk_page(p, w=390, h=800)
    pg.click('[data-dk="open"]'); pg.wait_for_selector('#desk img')
    r = pg.evaluate("(()=>{const f=document.querySelector('.dk-f').getBoundingClientRect(),i=document.querySelector('#dkimg').getBoundingClientRect();return [f.bottom<=innerHeight+1,f.top>i.top,document.documentElement.scrollWidth<=innerWidth+1,document.querySelector('#desk').getBoundingClientRect().height>=innerHeight-1]})()")
    check('D23 phone: action buttons stay on screen under the screenshot, no sideways scroll, desk covers the bottom bar', all(r), r)
    pg.click('[data-dk="paid"]'); pg.wait_for_timeout(500); check('D24 phone: Paid works and advances', sets(pg) and '1 of 2' in pg.inner_text('#desk'))
    check('D25 no page errors on phone', not errs, errs); b.close()
    # a failed save keeps you where you are
    b, pg, errs = desk_page(p); pg.evaluate("window.__DB.rpc.set_booking_status='permission denied'")
    pg.click('[data-dk="open"]'); pg.wait_for_selector('#desk img'); pg.click('[data-dk="paid"]'); pg.wait_for_timeout(400)
    check('D26 a failed save says so, stays on the same booking, and the buttons work again', 'Failed' in pg.inner_text('#toasts') and 'CODE00010' in pg.inner_text('#desk') and '1 of 3' in pg.inner_text('#desk')); b.close()
print(f"{sum(results)} passed, {len(results)-sum(results)} failed")
