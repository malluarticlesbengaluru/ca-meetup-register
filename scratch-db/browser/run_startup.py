"""Startup behaviour of the public page (index.html): does Home draw early, stay put, and survive a slow or failed library?
Separate from run_public.py on purpose, because run_public.py injects a fake Supabase before the page starts and so cannot test
"what happens while the library is still downloading". Here the libraries come through the network route and can be held back.
Run:  cd scratch-db/browser && python3 run_startup.py | tail -1      (no -I needed; reads ../../index.html)
Set PAGE=/path/to/other/index.html to test a different copy."""
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = '/home/claude/ca-meetup-register/'
HTML = open(os.environ.get('PAGE', ROOT + 'index.html'), encoding='utf-8').read()
res = []
def check(n, c, d=''): res.append(bool(c)); print(('  PASS  ' if c else '  FAIL  ') + n + ('' if c else '  ' + str(d)[:300]))

CLIENT_JS = r'''
(function(){
 const cfg = window.__CFG || {}, calls = window.__CALLS = window.__CALLS || [];
 const ok = d => ({data:d,error:null}), wait = ms => new Promise(r=>setTimeout(r,ms));
 const status = () => ok({accepting:true,spots_left:100,price_per_head:250,max_group:5,deadline:'2026-10-31T18:29:59Z',server_now:new Date().toISOString(),closed_reason:null});
 const rpcs = {
  get_event_info:()=>ok({event_at:'2026-11-22T08:30:00Z',venue:'Test Hall, Indiranagar'}),
  get_payment_info:()=>ok({upi_id:'org@upi',payee_name:'Org',whatsapp:'919999999999'}),
  get_site_flags:()=>ok({show_about:!!cfg.about,ask_email:true,ask_feedback:true}),
  get_public_status:status, registration_heartbeat:status,
 };
 const client = {auth:{},
  rpc: async (name,args)=>{ calls.push({name,args}); await wait((cfg.delay||{})[name]||0); const h=rpcs[name];
     return h ? h(args) : {data:null,error:{message:'function '+name+' does not exist'}} },
  storage:{from:()=>({upload: async (path)=>{calls.push({name:'UPLOAD',args:{path}});return {data:{},error:null}}})}};
 window.supabase = {createClient:()=>client};
})();
'''
QR_JS = 'window.qrcode=function(){return {addData(){},make(){},getModuleCount(){return 21},isDark(){return false}}};'
COUNT_JS = ("document.addEventListener('animationstart',e=>{const t=e.target;if(e.animationName==='rise'&&t&&t.classList&&t.classList.contains('invite'))"
            "window.__invite=(window.__invite||0)+1},true);")

def make(p, html=None, preloaded=True, cfg=None, sb='ok', qr='ok', w=420, h=900):
    """preloaded=True: a fake Supabase exists before the page starts (like run_public.py).
       preloaded=False: the fake library arrives through the network route like the real one, so it can be held back (sb='hold'),
       made to fail (sb='fail') or delivered (sb='ok'). qr works the same way for the QR library."""
    html = HTML if html is None else html
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': w, 'height': h}); errs = []; held = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    def handler(r):
        u = r.request.url
        if u.endswith('/test.html'): r.fulfill(body=html, content_type='text/html')
        elif '@supabase/supabase-js' in u:
            if preloaded: r.fulfill(body='', content_type='text/javascript')
            elif sb == 'hold': held.append(('sb', r))
            elif sb == 'fail': r.abort()
            else: r.fulfill(body=CLIENT_JS, content_type='text/javascript')
        elif 'qrcode' in u and u.split('?')[0].endswith('.js'):
            if qr == 'hold': held.append(('qr', r))
            elif qr == 'fail': r.abort()
            else: r.fulfill(body=QR_JS, content_type='text/javascript')
        else: r.fulfill(status=204, body='')
    pg.route('**/*', handler)
    import json
    pg.add_init_script('window.__CFG=' + json.dumps(cfg or {}) + ';' + COUNT_JS + (CLIENT_JS if preloaded else ''))
    def release(kind):
        for k, r in list(held):
            if k == kind:
                r.fulfill(body=CLIENT_JS if k == 'sb' else QR_JS, content_type='text/javascript'); held.remove((k, r))
    pg.goto('https://example.test/test.html', wait_until='commit')   # not 'load': a held background script delays that event on purpose
    return b, pg, errs, release

LIVE = 'Test Hall, Indiranagar'
def dd(pg): return pg.evaluate("[...document.querySelectorAll('#app .when dd')].map(e=>e.textContent)")

with sync_playwright() as p:
    # ===== A. Home is drawn once and live values are patched in (no rebuild, no second fade-in, no jump)
    def scenario_a(html=None, about=True):
        b, pg, errs, rel = make(p, html=html, cfg={'about': about, 'delay': {'get_event_info': 600, 'get_site_flags': 1000, 'get_payment_info': 300}}, h=380)
        pg.wait_for_selector('#app .invite')
        first = dd(pg)
        pg.evaluate("document.querySelector('.invite').__m=1; document.getElementById('logo').__m=1; window.scrollTo(0,40)")
        s0 = pg.evaluate("window.scrollY"); tall = pg.evaluate("document.documentElement.scrollHeight>window.innerHeight")
        pg.wait_for_function("document.querySelectorAll('.when dd')[2].textContent.includes('Test Hall')", timeout=5000)
        if about: pg.wait_for_function("!!document.getElementById('go-about')", timeout=5000)
        else: pg.wait_for_timeout(1300)
        pg.wait_for_timeout(500)   # time for any extra (unwanted) redraw to show up
        m = pg.evaluate("""({same:!!(document.querySelector('.invite')||{}).__m, logo:!!(document.getElementById('logo')||{}).__m,
            fades:window.__invite||0, y:window.scrollY, about:document.querySelectorAll('#go-about').length,
            order:(()=>{const a=document.getElementById('go-about'),t=document.getElementById('go-tickets');return !!(a&&t&&t.nextElementSibling===a)})()})""")
        out = dict(first=first, now=dd(pg), s0=s0, tall=tall, errs=errs, **m); b.close(); return out
    a = scenario_a()
    check('A1 Home is drawn before any live answer arrives (it starts with the built-in text)', a['first'] and LIVE not in a['first'][2], a['first'])
    check('A2 the live date, time and venue appear on the same card', 'Sunday, 22 November 2026' in a['now'][0] and '2:00 PM' in a['now'][1] and a['now'][2] == LIVE, a['now'])
    check('A3 the card is the SAME element afterwards (not rebuilt)', a['same'])
    check('A4 the logo element is the same one too (its animation is not restarted)', a['logo'])
    check('A5 the card fades in exactly once', a['fades'] == 1, a['fades'])
    check('A6 the page is tall enough to scroll in this test (so A7 means something)', a['tall'] and a['s0'] > 0, (a['tall'], a['s0']))
    check('A7 the scroll position is kept when live values arrive (no jump to the top)', a['y'] == a['s0'], (a['y'], a['s0']))
    check('A8 the About button appears once, right after Tickets, when the switch is on', a['about'] == 1 and a['order'], a)
    check('A9 no script errors during startup', not a['errs'], a['errs'])
    a2 = scenario_a(about=False)
    check('A10 with the About switch off, no About button ever appears', a2['about'] == 0 and a2['same'] and a2['fades'] == 1, a2)

    # ===== A-control: the OLD behaviour (redraw the whole card) must be detected by the same checks
    BAD = HTML.replace('if(S.step==="home")refreshHome()', 'if(S.step==="home")render()')
    check('control: the broken copy really differs (two places changed)', BAD != HTML and HTML.count('if(S.step==="home")refreshHome()') == 2)
    ab = scenario_a(html=BAD)
    check('control: redrawing the card is DETECTED (card replaced, extra fade-ins, page jumps)', (not ab['same']) and ab['fades'] > 1 and ab['y'] != ab['s0'], (ab['same'], ab['fades'], ab['y'], ab['s0']))

    # ===== B. Home is drawn without waiting for the Supabase and QR libraries
    MARK = "document.querySelector('.invite').__m=1"
    FIRST_H1 = "document.querySelector('#app h1')&&document.querySelector('#app h1').textContent"
    def early_tap(html=None):
        """Library held back: Home must already be there; then tap Register early; then deliver the library."""
        b, pg, errs, rel = make(p, html=html, preloaded=False, sb='hold', cfg={'about': True})
        pg.wait_for_selector('#app .invite')
        o = dict(lib=pg.evaluate("typeof window.supabase"), dd=dd(pg), cta=pg.evaluate("!!document.getElementById('go-register')"))
        pg.click('#go-register')
        try: pg.wait_for_function(FIRST_H1 + ".includes('Loading')", timeout=3000); o['loading'] = True
        except Exception: o['loading'] = False
        rel('sb')
        try: pg.wait_for_selector('#n0', timeout=6000); o['form'] = True
        except Exception: o['form'] = False; o['h1'] = pg.evaluate(FIRST_H1)
        o['errs'] = errs; b.close(); return o
    e = early_tap()
    check('B1 Home is on screen while the Supabase library has NOT arrived (library absent, built-in text, Register button ready)', e['lib'] == 'undefined' and e['cta'] and e['dd'] and LIVE not in e['dd'][2], e)
    check('B2 tapping Register before the library arrives shows Loading, then the form once it arrives', e['loading'] and e['form'], e)
    check('B3 no script errors on that path', not e['errs'], e['errs'])
    BAD_NOWAIT = HTML.replace('if(!sbClient){await sbReady;', 'if(!sbClient){')
    check('control: the copy that does not wait for the library really differs', BAD_NOWAIT != HTML)
    e2 = early_tap(BAD_NOWAIT)
    check('control: not waiting for the library is DETECTED (the early tap fails)', not (e2['loading'] and e2['form']), e2)

    def after_release(wait_ms, html=None, about=True):
        b, pg, errs, rel = make(p, html=html, preloaded=False, sb='hold', cfg={'about': about})
        pg.wait_for_selector('#app .invite'); pg.evaluate(MARK)
        pg.wait_for_timeout(wait_ms); rel('sb')
        try: pg.wait_for_function("document.querySelectorAll('.when dd')[2].textContent.includes('Test Hall')", timeout=6000); live = True
        except Exception: live = False
        pg.wait_for_timeout(500)
        o = pg.evaluate("({same:!!(document.querySelector('.invite')||{}).__m,fades:window.__invite||0,about:document.querySelectorAll('#go-about').length})")
        o.update(live=live, errs=errs); b.close(); return o
    f = after_release(300)
    check('B4 when the library arrives, the live date/venue appear and the About button shows (same card, one fade-in)', f['live'] and f['same'] and f['fades'] == 1 and f['about'] == 1, f)
    s = after_release(3500)
    check('B5 a SLOW library (3.5 s, longer than the 2.5 s event limit) still gets the live date/venue onto Home', s['live'] and s['same'] and s['fades'] == 1, s)
    BAD_LIMIT = HTML.replace('if(Date.now()-evAt<30000||!await sbGet())return;', 'if(Date.now()-evAt<30000)return;')
    check('control: the copy with the old time limit really differs', BAD_LIMIT != HTML)
    s2 = after_release(3500, html=BAD_LIMIT)
    check('control: counting the library download inside the 2.5 s limit is DETECTED (live date lost)', not s2['live'], s2)

    # library that fails to load: the same error screen as before, no crash
    b, pg, errs, rel = make(p, preloaded=False, sb='fail')
    pg.wait_for_selector('#app .invite'); pg.click('#go-register')
    try: pg.wait_for_function(FIRST_H1 + ".includes(\"couldn't load\")", timeout=6000); shown = True
    except Exception: shown = False
    check('B6 if the Supabase library fails to load, Home still draws and Register leads to the "couldn\'t load" screen', shown, pg.evaluate(FIRST_H1))
    check('B7 ... without script errors', not errs, errs); b.close()

    # QR library held back: the pay screen and the tickets wait for it, then draw
    PAYSTATE = ("S.status={price_per_head:250,max_group:5,accepting:true,deadline:'2026-10-31T18:29:59Z'};S.n=1;S.pay={upi:'org@upi',payee:'Org',wa:'919999999999'};"
                "S.payLoading=false;S.payFail=false;S.step='pay';render();")
    def qr_case(html=None):
        b, pg, errs, rel = make(p, html=html, preloaded=True, qr='hold')
        pg.wait_for_selector('#app .invite')
        try: pg.evaluate(PAYSTATE)
        except Exception as ex: errs.append('ReferenceError' if 'qrcode is not defined' in str(ex) else str(ex)[:150])   # the broken copy throws right here
        pg.wait_for_timeout(300)
        before = pg.evaluate("({lib:typeof qrcode,w:(document.getElementById('qr')||{}).width})")
        rel('qr'); pg.wait_for_timeout(500)
        after = pg.evaluate("({lib:typeof qrcode,w:(document.getElementById('qr')||{}).width})")
        o = dict(before=before, after=after, errs=list(errs)); b.close(); return o
    q = qr_case()
    check('B8 pay screen before the QR library arrives: nothing drawn and no error; after it arrives the QR is drawn', q['before']['lib'] == 'undefined' and q['before']['w'] != 232 and q['after']['w'] == 232 and not q['errs'], q)
    BAD_QR = HTML.replace('const whenQR=f=>typeof qrcode==="function"?f():qrReady.then(()=>{if(typeof qrcode==="function")f()});', 'const whenQR=f=>f();')
    check('control: the copy that draws the QR without waiting really differs', BAD_QR != HTML)
    q2 = qr_case(BAD_QR)
    check('control: drawing the QR before its library exists is DETECTED (script error, nothing drawn)', q2['errs'] or q2['after']['w'] != 232, q2)

    def tickets_case(html=None):
        b, pg, errs, rel = make(p, html=html, preloaded=True, qr='hold')
        pg.wait_for_selector('#app .invite')
        pg.evaluate("S.cur={booking_code:'AB12CD34',status:'paid',kind:'registration',tickets:[{name:'Asha',food:'Veg',label:'E26-001',secret:'a'.repeat(12),transferred:false,kind:'guest',ticket_no:1,coord_no:null,location:'x',attendance:'y'}]};S.step='ticket';render();")
        pg.wait_for_timeout(600)
        before = pg.evaluate("(S.cv||[]).length")
        rel('qr'); pg.wait_for_timeout(1200)
        o = dict(before=before, after=pg.evaluate("(S.cv||[]).length"), errs=list(errs)); b.close(); return o
    t1 = tickets_case()
    check('B9 tickets wait for the QR library, then are drawn', t1['before'] == 0 and t1['after'] == 1 and not t1['errs'], t1)
    BAD_TK = HTML.replace('await loadLogo();await qrReady;', 'await loadLogo();')
    check('control: the copy whose tickets do not wait for the QR library really differs', BAD_TK != HTML)
    t2 = tickets_case(BAD_TK)
    check('control: tickets drawn before the QR library exists are DETECTED (never drawn)', t2['after'] != 1, t2)

n = len(res); bad = res.count(False)
print(f"{n - bad} passed, {bad} failed")
sys.exit(1 if bad else 0)
