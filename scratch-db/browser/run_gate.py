import json
from playwright.sync_api import sync_playwright
import admin_test as A
HTML = open('/home/claude/ca-meetup-register/admin/index.html', encoding='utf-8').read()
res=[]
def check(n,c,d=''): res.append(bool(c)); print(('  PASS  ' if c else '  FAIL  ')+n+('' if c else '  '+str(d)[:200]))
def run(p, tickets, bookings, fail_col=False, rpc=None, init=None):
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':420,'height':900}); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.route('**/*', lambda r: (r.fulfill(body=HTML, content_type='text/html') if r.request.url.endswith('/admin/test.html') else r.fulfill(body='/*s*/', content_type='text/javascript') if r.request.url.endswith('.js') else r.fulfill(status=204, body='')))
    d=dict(tables=dict(staff=dict(name='Gate One',role='gate'), tickets=tickets, bookings=bookings), rpc=rpc or {})
    if fail_col: d['tables']['tickets']={'error':'column tickets.transferred_out_at does not exist'}
    pg.add_init_script('window.__DB='+json.dumps(d)+';'); pg.add_init_script(A.MOCK)
    if fail_col:  # first call fails, the retry (without the column) must succeed: emulate by switching the table after first read
        pg.add_init_script("(function(){let n=0;const o=window.__DB.tables;Object.defineProperty(o,'tickets',{get(){n++;return n===1?{error:'column tickets.transferred_out_at does not exist'}:window.__OLD},configurable:true})})();")
        pg.add_init_script('window.__OLD='+json.dumps(tickets)+';')
    if init: pg.add_init_script(init)
    pg.goto('https://example.test/admin/test.html'); pg.wait_for_selector('#counts'); pg.wait_for_timeout(200); return b,pg,errs
with sync_playwright() as p:
    T=A.TICKETS; B=A.BOOKINGS
    b,pg,errs=run(p,T,B)
    c=pg.inner_text('#counts').replace('\n',' ')
    check('gate: Present / Confirmed = 0 / 3 (retired Asha not counted)', '0 / 3' in c, c)
    check('gate: Veg 0 / 2 and Non-veg 0 / 1', '0 / 2' in c and '0 / 1' in c, c)
    pg.fill('#gfq','Asha'); t=pg.inner_text('#gres')
    check('gate: search finds the retired ticket and says Transferred', 'Transferred' in t and 'current ticket' in t, t)
    check('gate: retired ticket has NO Open/Admit button', pg.query_selector('#gres button') is None)
    pg.fill('#gfq','Dan'); check('gate: the buyer Dan can be opened', pg.query_selector('#gres button[data-pick]') is not None)
    check('look: staff page has the top bar with the Organiser label and no admin menu for gate staff', pg.is_visible('#top') and 'Organiser' in pg.inner_text('#top') and not pg.is_visible('#rail') and pg.query_selector('#gtop') is None)
    check('look: gate screen has no sideways scrolling at phone width', pg.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'))
    check('no page errors', not errs, errs); b.close()
    # ---- result screens stay until the gate person decides; Home page / Next scan / Undo; admitted list; camera retry
    CAM = "window.__GUM=0;navigator.mediaDevices=navigator.mediaDevices||{};navigator.mediaDevices.getUserMedia=function(){window.__GUM++;return Promise.reject(Object.assign(new Error('Permission denied'),{name:'NotAllowedError'}))};"
    OK = {'result':'ok','id':'t2','name':'Ben','label':'E26-002','food':'Non-veg','booking_code':'CODE0001','people_count':2,'kind':'guest'}
    TT = [dict(t) for t in T]; TT[1]['checked_in_at']='2026-10-26T10:15:00Z'; TT[2]['checked_in_at']='2026-10-26T11:40:00Z'
    b,pg,errs=run(p,TT,B,rpc=dict(admit_ticket=OK, undo_checkin=None),init=CAM)
    items = pg.inner_text('#admlist')
    check('admitted list shows names, times and booking IDs, latest first', 'Ben' in items and 'Carl' in items and 'CODE0001' in items and items.index('Carl') < items.index('Ben'), items)
    pg.click('#admlist .lk >> text=Carl'); check('tapping a name opens the person preview', 'Carl' in pg.inner_text('#sheetbg .sh-h h2') and 'CODE0002' in pg.inner_text('#sheetbg'))
    pg.click('#sheetbg .lk >> text=CODE0002'); check('tapping the booking ID shows the booking and its people', 'People in this booking' in pg.inner_text('#sheetbg') and 'Carl' in pg.inner_text('#sheetbg'))
    pg.go_back(); check('back gesture returns to the person', 'Carl' in pg.inner_text('#sheetbg .sh-h h2')); pg.go_back(); check('second back closes the preview', pg.query_selector('#sheetbg') is None)
    pg.fill('#gfq','Ben'); pg.click('#gres button[data-pick]'); pg.click('[data-act="admitpick"]')
    pg.wait_for_selector('.ov.g'); pg.wait_for_timeout(3500)
    check('ADMITTED stays on screen (no automatic close)', pg.query_selector('.ov.g') is not None)
    ov = pg.inner_text('.ov'); check('ADMITTED has Next scan, Home page and Undo', 'Next scan' in ov and 'Home page' in ov and 'Undo' in ov, ov)
    pg.click('[data-act="undo"]'); check('Undo asks first', 'UNDO ADMISSION?' in pg.inner_text('.ov'))
    pg.click('[data-act="keep"]'); check('No, keep admitted returns to the result', 'ADMITTED' in pg.inner_text('.ov'))
    pg.evaluate('S.ov.res._at=Date.now()-130000'); pg.click('[data-act="undo"]'); pg.click('[data-act="undo2"]')
    check('after 2 minutes a gate person cannot undo (needs an admin), no database call', 'more than 2 minutes' in pg.inner_text('.ov') and not [c for c in pg.evaluate('window.__CALLS.map(c=>c.name)') if 'undo' in c], pg.inner_text('.ov'))
    pg.evaluate('delete window.__DB.rpc.admit_ticket._at'); pg.click('[data-act="home"]'); pg.fill('#gfq','Ben'); pg.click('#gres button[data-pick]'); pg.click('[data-act="admitpick"]'); pg.wait_for_selector('.ov.g')
    pg.click('[data-act="undo"]'); pg.click('[data-act="undo2"]'); pg.wait_for_selector('.ov.n')
    calls = pg.evaluate('window.__CALLS.map(c=>c.name+":"+(c.args.p_id||""))')
    check('Undo calls the database with the ticket id (falls back to the admin function)', 'undo_checkin:t2' in calls, calls)
    check('screen says ADMISSION UNDONE', 'ADMISSION UNDONE' in pg.inner_text('.ov'))
    pg.click('[data-act="home"]'); check('Home page closes the result and keeps the camera off', pg.query_selector('.ov') is None and pg.evaluate('window.__GUM')==0)
    pg.click('#camtoggle'); pg.wait_for_timeout(200)
    check('camera denied: clear message, button says Try again', 'blocked' in pg.inner_text('#camoff') and pg.inner_text('#camtoggle')=='Try again', pg.inner_text('#camoff'))
    pg.click('#camtoggle'); pg.wait_for_timeout(200)
    check('Try again asks the browser again', pg.evaluate('window.__GUM')==2, pg.evaluate('window.__GUM'))
    pg.fill('#gfq','Ben'); pg.click('#gres button[data-pick]'); pg.click('[data-act="admitpick"]'); pg.wait_for_selector('.ov.g'); pg.click('[data-act="next"]'); pg.wait_for_timeout(200)
    check('Next scan closes the result and starts the camera', pg.query_selector('.ov') is None and pg.evaluate('window.__GUM')==3, pg.evaluate('window.__GUM'))
    check('no page errors in the new gate flow', not errs, errs); b.close()
    # undo refused for non-admins: shows a plain message
    b,pg,errs=run(p,TT,B,rpc=dict(admit_ticket=OK, gate_undo_checkin='NOT_ALLOWED'))
    pg.fill('#gfq','Ben'); pg.click('#gres button[data-pick]'); pg.click('[data-act="admitpick"]'); pg.wait_for_selector('.ov.g'); pg.click('[data-act="undo"]'); pg.click('[data-act="undo2"]'); pg.wait_for_selector('.ov.r')
    check('non-admin undo refused: "Only an admin can undo this"', 'Only an admin' in pg.inner_text('.ov'), pg.inner_text('.ov')); b.close()
    # ---- merged page: what each role sees
    b,pg,errs=run(p,T,B)
    tabs = pg.query_selector_all('#rail button, #bnav button')
    check('gate staff see only the scanner: no admin tabs, no Bookings/People/Settings', not tabs and pg.query_selector('#counts') is not None and 'Settings' not in pg.inner_text('#app'), pg.inner_text('#app')[:200])
    pg.evaluate("document.querySelector('#admlist')"); 
    check('gate staff have no Find/Dashboard shortcut to admin things', pg.query_selector('#gtop') is None and pg.query_selector('a[href*="admin"]') is None)
    b.close()
    b,pg,errs=A.open_page(p, A.db())
    check('admin: Gate is a tab, and the old "Gate scanner" link is gone', pg.query_selector('button[data-tab="gate"]') is not None and pg.query_selector('a[href*="gate"]') is None)
    A.go_tab(pg,'gate'); check('admin: Gate tab shows the counts, camera card, find and admitted list', all(pg.query_selector(x) is not None for x in ['#counts','#camtoggle','#gfq','#admlist']))
    pg.fill('#gfq','Ben'); check('admin: find works inside the Gate tab', 'Ben' in pg.inner_text('#gres'))
    pg.click('button[data-tab="people"]'); check('admin: other tabs still work after visiting Gate', pg.query_selector('#tbl .pc') is not None)
    check('no page errors for admin on the merged page', not errs, errs); b.close()
    # the old address just forwards
    old = open('/home/claude/ca-meetup-register/gate/index.html', encoding='utf-8').read()
    check('old /gate/ address forwards to the staff page Gate tab', '../admin/#gate' in old and 'supabase' not in old)
    # database not updated yet: the first query fails on the missing column, the page must fall back
    old=[{k:v for k,v in t.items() if k!='transferred_out_at'} for t in T[1:3]]
    b,pg,errs=run(p,old,B[:2],fail_col=True); c=pg.inner_text('#counts').replace('\n',' ')
    check('gate on an old database: still loads and counts (0 / 2)', '0 / 2' in c and not errs, (c, errs)); b.close()
print(sum(res),'passed,',len(res)-sum(res),'failed')
