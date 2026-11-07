from admin_test import *
# Browser suite for Group D: approve payments with a confirmation (tick bookings, preview of ticket numbers, Yes / Cancel).
# Run:  cd scratch-db/browser && python3 run_approve.py | tail -1
def world():
    B = [bk(10, status='pending'), bk(11, status='pending'), bk(12, status='pending', n=2, amt=500), bk(13, status='rejected'), bk(14, status='pending')]
    T = [mk(100, booking_id='b10', name='Pend0'), mk(101, booking_id='b11', name='Pend1'), mk(102, booking_id='b12', name='Pend2a'), mk(103, booking_id='b12', name='Pend2b'), mk(104, booking_id='b13', name='Rej'), mk(105, booking_id='b14', name='Pend4')]
    for i, b in enumerate(B): b['created_at'] = f'2026-10-2{i}T10:00:00Z'
    return dict(bookings=BOOKINGS + B, tickets=TICKETS + T)
def page(p, w=1300, h=900):
    d = db(tables=world()); d['rpc']['set_booking_status'] = None
    b, pg, errs = open_page(p, d); pg.set_viewport_size({'width': w, 'height': h})
    pg.evaluate("(()=>{const o=db.rpc;db.rpc=(n,a)=>{if(n==='set_booking_status'){const b=window.__DB.tables.bookings.find(x=>x.id===a.p_booking);if(b)b.status=a.p_status}return o(n,a)}})()")
    go_tab(pg, 'bookings'); return b, pg, errs
def appr(pg): return [c['args'] for c in pg.evaluate('window.__CALLS') if c['name'] == 'admin_approve_bookings']
def sets(pg): return [c['args'] for c in pg.evaluate('window.__CALLS') if c['name'] == 'set_booking_status']
def tick(pg, *ids):
    for i in ids: pg.click(f'[data-sel="{i}"]')
def toasts(pg): return pg.inner_text('#toasts') if pg.query_selector('#toasts') else ''
with sync_playwright() as p:
    b, pg, errs = page(p)
    check('A1 only pending bookings have a tick box (4 pending, none on paid or rejected)', len(pg.query_selector_all('[data-sel]')) == 4 and not pg.query_selector('.bk.st-paid [data-sel]') and not pg.query_selector('.bk.st-rejected [data-sel]'))
    check('A2 no Approve button until something is ticked', not pg.query_selector('[data-approve]') and pg.query_selector('[data-selall]') is not None)
    tick(pg, 'b10', 'b11')
    check('A3 ticking two shows "Approve (2)" without redrawing the list', 'Approve (2)' in pg.inner_text('#selbar'))
    pg.click('[data-selall]'); check('A4 "Select all pending" ticks all 4: "Approve (4)"', 'Approve (4)' in pg.inner_text('#selbar') and len(pg.query_selector_all('[data-sel]:checked')) == 4)
    pg.click('[data-selclear]'); check('A5 Clear unticks everything', not pg.query_selector('[data-approve]') and not pg.query_selector_all('[data-sel]:checked'))
    # confirmation screen
    tick(pg, 'b12', 'b10'); dlg_msgs(pg); auto(pg, False); pg.click('[data-approve]'); pg.wait_for_timeout(900)
    m = ' '.join(dlg_msgs(pg))
    check('A6 the confirmation says N bookings, people and the total', 'This will approve the payments of 2 bookings (3 people, ₹750 total)' in m, m[:200])
    check('A7 it lists each booking with names, people, amount and the ticket numbers in the order they will be given (oldest first)', m.index('CODE00010') < m.index('CODE00012') and 'Pend0 E26-040' in m and 'Pend2a E26-041, Pend2b E26-042' in m and '2 people' in m and '₹500' in m, m)
    check('A8 it has the grey bank-statement line', 'Check these against your bank statement before approving.' in m)
    check('A9 no typing needed: no input in the dialog; buttons are "Yes, approve" and "Cancel"', 'Yes, approve' in m and 'Cancel' in m)
    check('A10 Cancel approves nothing, nothing changes, the ticks stay', not appr(pg) and not sets(pg) and 'Approve (2)' in pg.inner_text('#selbar') and pg.evaluate("window.__DB.tables.bookings.find(x=>x.id==='b10').status") == 'pending')
    auto(pg, True); pg.click('[data-approve]'); pg.wait_for_timeout(900)
    a = appr(pg)
    check('A11 Yes sends the ids oldest first plus the number the preview started from', a and a[-1] == {'p_ids': ['b10', 'b12'], 'p_expected_next': 40}, a)
    check('A12 it says "2 bookings approved"', '2 bookings approved' in toasts(pg), toasts(pg))
    check('A13 the list updated: both are Paid, no tick boxes left on them, selection cleared', not pg.query_selector('.bk[data-bid="b10"] [data-sel]') and 'paid' in pg.inner_text('.bk[data-bid="b10"]') and not pg.query_selector('[data-approve]'))
    check('A14 the tickets really got the numbers shown (40, 41, 42)', pg.evaluate("['t100','t102','t103'].map(i=>window.__DB.tables.tickets.find(t=>t.id===i).ticket_no).join()") == '40,41,42')
    check('A15 no page errors', not errs, errs); b.close()
    # single booking
    b, pg, errs = page(p); dlg_msgs(pg); auto(pg, False); pg.click('.bk[data-bid="b10"] [data-st="paid"]'); pg.wait_for_timeout(900); m = ' '.join(dlg_msgs(pg))
    check('A16 a single Paid uses the same confirmation with one row and the ticket number', 'This will approve the payment of Pend0, ₹250. Ticket E26-040.' in m and 'CODE00010' in m and 'Check these against your bank statement' in m, m)
    check('A17 Cancel on a single Paid sends nothing', not appr(pg) and not sets(pg))
    auto(pg, True); pg.click('.bk[data-bid="b10"] [data-st="paid"]'); pg.wait_for_timeout(900)
    check('A18 Yes approves just that one: "1 booking approved"', appr(pg) and appr(pg)[-1]['p_ids'] == ['b10'] and '1 booking approved' in toasts(pg), toasts(pg))
    # Reject and other buttons stay as they were
    auto(pg, True); pg.click('.bk[data-bid="b11"] [data-st="rejected"]'); pg.wait_for_timeout(700)
    check('A19 Reject is unchanged: set_booking_status rejected, no approval call', sets(pg) and sets(pg)[-1] == {'p_booking': 'b11', 'p_status': 'rejected'} and len(appr(pg)) == 1)
    dlg_msgs(pg); auto(pg, True); pg.click('.bk[data-bid="b13"] [data-st="paid"]'); pg.wait_for_timeout(700)
    check('A20 a REJECTED booking marked Paid keeps the old direct path (not part of this change)', sets(pg)[-1] == {'p_booking': 'b13', 'p_status': 'paid'} and len(appr(pg)) == 1 and not dlg_msgs(pg))
    check('A21 no page errors', not errs, errs); b.close()
    # numbers changed in between: nothing approved
    b, pg, errs = page(p); pg.evaluate("window.__DB.rpc.admin_approve_bookings='NUMBERS_CHANGED'"); tick(pg, 'b10', 'b11'); auto(pg, True); pg.click('[data-approve]'); pg.wait_for_timeout(900)
    check('A22 numbers changed: "Numbers changed. Nothing approved. Please review again."', 'Numbers changed. Nothing approved. Please review again.' in toasts(pg), toasts(pg))
    check('A23 ...and both are still pending, with Approve still offered', pg.evaluate("window.__DB.tables.bookings.filter(x=>['b10','b11'].includes(x.id)&&x.status==='pending').length") == 2)
    pg.evaluate("window.__DB.rpc.admin_approve_bookings='permission denied'"); auto(pg, True); pg.click('[data-approve]'); pg.wait_for_timeout(900)
    check('A24 other errors show "Failed: ..." and approve nothing', 'Failed: permission denied' in toasts(pg) and pg.evaluate("window.__DB.tables.bookings.filter(x=>['b10','b11'].includes(x.id)&&x.status==='pending').length") == 2, toasts(pg)); b.close()
    # one booking changed before the confirmation opened (stale list)
    b, pg, errs = page(p); tick(pg, 'b10', 'b11', 'b12'); pg.evaluate("S.bookings=S.bookings.map(b=>({...b}));window.__DB.tables.bookings.find(x=>x.id==='b11').status='rejected'"); dlg_msgs(pg); auto(pg, True); pg.click('[data-approve]'); pg.wait_for_timeout(900); m = ' '.join(dlg_msgs(pg))
    check('A25 a booking no longer pending is left out of the confirmation and the screen says so', 'CODE00011' not in m and '1 booking is no longer pending and left out' in m and 'payments of 2 bookings' in m, m)
    a = appr(pg); check('A26 only the pending ones are sent, numbers unchanged', a and a[-1]['p_ids'] == ['b10', 'b12'], a); b.close()
    # one booking changed AFTER the confirmation opened (between preview and Yes)
    b, pg, errs = page(p); tick(pg, 'b10', 'b11', 'b12'); pg.click('[data-approve]'); pg.wait_for_selector('.dlg')
    pg.evaluate("window.__DB.tables.bookings.find(x=>x.id==='b11').status='rejected'"); pg.click('[data-dlg="yes"]'); pg.wait_for_timeout(900)
    check('A27 skipped one is reported and the rest are approved', '2 bookings approved' in toasts(pg) and '1 skipped' in toasts(pg), toasts(pg))
    check('A28 numbers that moved are named (Check the list)', 'differ' in toasts(pg) and 'CODE00012' in toasts(pg), toasts(pg)); b.close()
    # everything already changed
    b, pg, errs = page(p); tick(pg, 'b10'); pg.evaluate("S.bookings=S.bookings.map(b=>({...b}));window.__DB.tables.bookings.find(x=>x.id==='b10').status='rejected'"); auto(pg, True); pg.click('[data-approve]'); pg.wait_for_timeout(900)
    check('A29 nothing left to approve: says so, no dialog, no approval call', 'Nothing to approve' in toasts(pg) and not appr(pg), toasts(pg)); b.close()
    # phone
    b, pg, errs = page(p, 390, 760); tick(pg, 'b10', 'b11', 'b12', 'b14'); pg.click('[data-approve]'); pg.wait_for_selector('.dlg'); pg.wait_for_timeout(900)
    r = pg.evaluate("(()=>{const x=document.querySelector('.dlg');if(!x)return null;const r=x.getBoundingClientRect(),a=x.querySelector('[data-dlg=yes]').getBoundingClientRect();return [r.bottom<=innerHeight+1,a.bottom<=innerHeight+1,document.documentElement.scrollWidth<=innerWidth+1]})()")
    check('A30 phone: the dialog and its Yes button fit on screen with no sideways scroll', r and all(r), r)
    check('A31 no page errors on phone', not errs, errs); pg.click('[data-dlg="no"]'); b.close()
print(f"{sum(results)} passed, {len(results)-sum(results)} failed")
