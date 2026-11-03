"""Browser suite for the redesigned Home page (index.html + assets/home-fx.js), Nov 2026.
Mocked Supabase, headless Chromium. Run:  cd scratch-db/browser && python3 run_home.py | tail -1      (no -I needed)
Set PAGE=/path/to/other/index.html to test a different copy (used by the deliberate-mistake checks at the bottom)."""
import os, json, mimetypes
from playwright.sync_api import sync_playwright
ROOT = '/home/claude/ca-meetup-register/'
PAGE = os.environ.get('PAGE', ROOT + 'index.html')
HTML = open(PAGE, encoding='utf-8').read()
res = []
def check(n, c, d=''): res.append(bool(c)); print(('  PASS  ' if c else '  FAIL  ') + n + ('' if c else '  ' + str(d)[:300]))

MOCK = r'''
(function(){
 const calls=window.__CALLS=[],R=window.__R={};const ok=d=>({data:d,error:null});
 const st=()=>ok(Object.assign({accepting:true,spots_left:12,price_per_head:250,max_group:5,deadline:new Date(Date.now()+5*86400e3+3*3600e3).toISOString(),server_now:new Date().toISOString(),closed_reason:null},window.__ST||{}));
 const rpcs={get_event_info:()=>ok({event_at:new Date(Date.now()+20*86400e3+5*3600e3).toISOString(),venue:'Bloom Creative Zone, Haralur'}),
   get_payment_info:()=>ok({upi_id:'org@upi',payee_name:'Org',whatsapp:'919999999999'}),get_site_flags:()=>ok(Object.assign({show_about:false,ask_email:true,ask_feedback:true},window.__FL||{})),
   get_public_status:st,registration_heartbeat:st};
 const client={auth:{},rpc:async(n,a)=>{calls.push({name:n,args:a});const h=R[n]||rpcs[n];if(!h)return{data:null,error:{message:'nope '+n}};return typeof h==='function'?h(a):ok(h)},
   storage:{from:()=>({upload:async()=>({data:{},error:null})})}};
 window.supabase={createClient:()=>client};
})();'''

def page(p, w=390, h=844, extra='', mine=False, reduced=False, nofx=False):
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': w, 'height': h}, reduced_motion='reduce' if reduced else 'no-preference')
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    def handler(r):
        u = r.request.url
        if u.endswith('/test.html'): r.fulfill(body=HTML, content_type='text/html')
        elif '/assets/' in u:
            name = u.split('/assets/')[1].split('?')[0]; f = ROOT + 'assets/' + name
            if nofx and name == 'home-fx.js': r.fulfill(status=404, body='')
            elif os.path.exists(f): r.fulfill(path=f, content_type=mimetypes.guess_type(f)[0] or 'application/octet-stream')
            else: r.fulfill(status=404, body='')
        elif u.endswith('.js') or '/npm/' in u: r.fulfill(body='window.qrcode=function(){return {addData(){},make(){},getModuleCount(){return 21},isDark(){return false}}};', content_type='text/javascript')
        else: r.fulfill(status=204, body='')
    pg.route('**/*', handler); pg.add_init_script(MOCK + extra)
    if mine: pg.add_init_script("localStorage.setItem('mm_mine',JSON.stringify(['AB12CD34']))")
    pg.goto('https://example.test/test.html'); pg.wait_for_selector('.home h1'); pg.wait_for_timeout(600)
    return b, pg, errs
T = lambda pg, s: pg.evaluate("s=>{const e=document.querySelector(s);return e?e.textContent.trim():null}", s)
calls = lambda pg: [c['name'] for c in pg.evaluate('window.__CALLS')]

with sync_playwright() as p:
    # ===== 1. a new visitor, phone width
    b, pg, errs = page(p)
    check('Home draws with no script errors', not errs, errs)
    check('motion script mounted (html.fx on, one canvas)', pg.evaluate("document.documentElement.classList.contains('fx')") and pg.evaluate('HomeFX.info().mounted') and pg.evaluate('HomeFX.info().canvases') == 1)
    check('hero and join buttons carry the LIVE price', T(pg, '#hero-register') == 'Register · ₹250' and T(pg, '#go-register') == 'Register · ₹250', (T(pg, '#hero-register'), T(pg, '#go-register')))
    check('second button says View my ticket; Register-another stays hidden', T(pg, '#go-tickets') == 'View my ticket' and pg.evaluate("document.getElementById('hero-tickets').hidden"))
    check('each button id is used once on Home', all(pg.evaluate(f"document.querySelectorAll('#{k}').length") == 1 for k in ['hero-register', 'hero-tickets', 'go-register', 'go-tickets', 'home-fab', 'home-cal', 'home-map', 'home-poster']))
    check('Home asked for the live status (price and spots come from the database)', 'get_public_status' in calls(pg), calls(pg))
    check('venue and date follow the live event info', T(pg, '[data-ev=v]') == 'Bloom Creative Zone, Haralur' and pg.evaluate("document.getElementById('home-map').href").startswith('https://www.google.com/maps/'))
    check('calendar link points at Google Calendar with the live date', 'calendar.google.com' in pg.evaluate("document.getElementById('home-cal').href"))
    pg.wait_for_timeout(1500)
    check('spots: both lines are live (data-to is 12) and the hero one has counted down to 12', pg.evaluate("[...document.querySelectorAll('.fxspots b')].every(b=>b.dataset.to==='12')") and pg.evaluate("document.querySelector('.hhero .fxspots b').textContent") == '12')
    pg.evaluate("document.getElementById('home-join').scrollIntoView({block:'center'})"); pg.wait_for_timeout(2200)
    check('spots: the join-card line counts down to 12 once it is scrolled into view', pg.evaluate("[...document.querySelectorAll('.fxspots:not(.nosp)')].filter(x=>/Only 12 spots left/.test(x.textContent)).length") == 2, pg.evaluate("[...document.querySelectorAll('.fxspots')].map(x=>x.textContent)"))
    pg.evaluate('window.scrollTo(0,0)')
    cd = pg.evaluate("[...document.querySelectorAll('.fxbig b')].map(x=>+x.textContent)")
    check('meetup countdown shows about 20 days 4 hours', cd[0] == 20 and cd[1] in (4, 5), cd)
    check('registration countdown shows about 5 days', pg.evaluate("document.querySelector('.fxreg').hidden") is False and pg.evaluate("document.querySelectorAll('.fxreg b')[0].textContent") == '05')
    pg.wait_for_timeout(2200); cd2 = pg.evaluate("[...document.querySelectorAll('.fxbig b')].map(x=>+x.textContent)")
    check('the seconds tick', cd2[3] != cd[3], (cd, cd2))
    check('no sideways scrolling at phone width', pg.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
    # buttons route correctly
    pg.click('#hero-register'); pg.wait_for_selector('#n0')
    check('Register (hero) opens the form', pg.query_selector('#n0') is not None)
    pg.click('#go-home'); pg.wait_for_selector('.home h1')
    check('Back to Home draws Home again, and the long hero entrance is not replayed', pg.evaluate("document.querySelector('.home').classList.contains('again')"))
    pg.click('#go-register'); pg.wait_for_selector('#n0'); check('Register (join card) opens the form', True)
    pg.click('#go-home'); pg.wait_for_selector('.home h1'); pg.click('#go-tickets'); pg.wait_for_selector('#bq')
    check('View my ticket opens Tickets', pg.query_selector('#bq') is not None)
    pg.wait_for_timeout(2300)
    check('confetti from the Register button cleans itself up (no canvas left behind)', pg.evaluate("document.querySelectorAll('canvas.fxconf').length") == 0)
    b.close()

    # ===== 2. a returning visitor (booking ID saved on the device)
    b, pg, errs = page(p, mine=True)
    check('returning: main buttons say View my ticket; the second says Register another booking', T(pg, '#hero-register') == 'View my ticket' and T(pg, '#go-register') == 'View my ticket' and T(pg, '#go-tickets') == 'Register another booking', (T(pg, '#hero-register'), T(pg, '#go-tickets')))
    check('returning: hero shows the Register-another button', pg.evaluate("!document.getElementById('hero-tickets').hidden"))
    check('returning: the saved-on-this-device note is shown', 'saved on this device' in pg.inner_text('#home-join'))
    check('returning: price refresh does not overwrite View my ticket', T(pg, '#hero-register') == 'View my ticket')
    pg.click('#hero-register'); pg.wait_for_selector('#bq'); check('returning: main button opens Tickets', True)
    pg.click('#go-home'); pg.wait_for_selector('.home h1'); pg.click('#go-register'); pg.wait_for_selector('#bq'); check('returning: join-card main button opens Tickets', True)
    pg.click('#go-home'); pg.wait_for_selector('.home h1'); pg.click('#go-tickets'); pg.wait_for_selector('#n0'); check('returning: Register another booking opens the form', True)
    pg.click('#go-home'); pg.wait_for_selector('.home h1'); pg.click('#hero-tickets'); pg.wait_for_selector('#n0'); check('returning: hero Register another opens the form', True)
    b.close()

    # ===== 3. spots rule, closed registration, full hall
    b, pg, errs = page(p, extra="window.__ST={spots_left:60};")
    check('60 spots left: the spots line is hidden (only 20 or fewer are announced)', pg.evaluate("[...document.querySelectorAll('.fxspots')].every(x=>x.classList.contains('nosp'))"))
    b.close()
    b, pg, errs = page(p, extra="window.__ST={spots_left:1};")
    pg.evaluate("document.getElementById('home-join').scrollIntoView({block:'center'})"); pg.wait_for_timeout(2200)
    check('1 spot left: singular wording on both lines', pg.evaluate("[...document.querySelectorAll('.fxspots:not(.nosp)')].filter(x=>/^Only 1 spot left$/.test(x.textContent.trim())).length") == 2, pg.evaluate("[...document.querySelectorAll('.fxspots')].map(x=>x.className+'|'+x.textContent)"))
    b.close()
    b, pg, errs = page(p, extra="window.__ST={accepting:false,spots_left:0,closed_reason:'full'};")
    check('hall full: "All spots are taken" is shown', pg.evaluate("[...document.querySelectorAll('.fxspots:not(.nosp)')].every(x=>/All spots are taken/.test(x.textContent))"))
    check('registration closed: the registration countdown is hidden, the meetup countdown stays', pg.evaluate("document.querySelector('.fxreg').hidden") and pg.evaluate("!document.querySelector('.fxbig').closest('[hidden]')"))
    b.close()
    b, pg, errs = page(p, extra="window.__R.get_public_status=()=>({data:null,error:{message:'down'}});")
    check('status call fails: Home still works, button says plain Register, no spots line, no registration countdown', T(pg, '#hero-register') == 'Register' and pg.evaluate("[...document.querySelectorAll('.fxspots')].every(x=>x.classList.contains('nosp'))") and pg.evaluate("document.querySelector('.fxreg').hidden") and not errs, (T(pg, '#hero-register'), errs))
    b.close()

    # ===== 4. About switch
    b, pg, errs = page(p, extra="window.__FL={show_about:true};")
    check('About switch ON: the About button appears and opens the About page', T(pg, '#go-about') == 'About us')
    pg.click('#go-about'); pg.wait_for_selector('#go-home'); check('About page opens', 'About' in pg.inner_text('#app'))
    b.close()
    b, pg, errs = page(p)
    check('About switch OFF: no About button', pg.query_selector('#go-about') is None)
    b.close()

    # ===== 5. poster zoom and the floating button
    b, pg, errs = page(p)
    pg.evaluate("document.getElementById('home-poster').scrollIntoView({block:'center'})"); pg.wait_for_timeout(1500)
    pg.click('#home-poster'); pg.wait_for_selector('.hlb'); pg.wait_for_timeout(700)
    check('tapping the poster opens the picture viewer', pg.query_selector('.hlb img') is not None)
    pg.click('.hlb'); pg.wait_for_timeout(700); check('tapping again closes it', pg.query_selector('.hlb') is None)
    pg.evaluate("window.scrollTo(0,900)"); pg.wait_for_timeout(500)
    check('floating Register button shows after the hero', pg.evaluate("document.getElementById('home-fab').classList.contains('show')"))
    pg.click('#home-fab'); pg.wait_for_timeout(1500)
    check('floating button scrolls to the join card without opening the form', pg.query_selector('#n0') is None and pg.evaluate("(()=>{const r=document.getElementById('home-join').getBoundingClientRect();return r.top<innerHeight&&r.bottom>0})()"))
    check('floating button hides while the join card is on screen', not pg.evaluate("document.getElementById('home-fab').classList.contains('show')"))
    b.close()

    # ===== 6. the Register screens are not touched by the Home motion styles
    b, pg, errs = page(p)
    pg.click('#hero-register'); pg.wait_for_selector('#n0'); pg.wait_for_timeout(500)
    check('form screen: cards are not hidden by the Home reveal rule', pg.evaluate("[...document.querySelectorAll('#app .card')].every(c=>getComputedStyle(c).opacity!=='0')"))
    check('form screen: no Home motion leftovers (canvas, progress line)', pg.evaluate("document.querySelectorAll('canvas.fxcanvas,.fxprog,.fxcue').length") == 0)
    b.close()
    # a short window, so the form's cards really are below the fold and the app's own scroll-reveal is armed
    b, pg, errs = page(p, h=420)
    pg.click('#hero-register'); pg.wait_for_selector('#n0'); pg.wait_for_timeout(500)
    tr = pg.evaluate("[...document.querySelectorAll('#app .card.rv:not(.in)')].map(c=>getComputedStyle(c).transform)")
    check('form screen: the app\'s own scroll-reveal is untouched (cards below the fold start 22px low, with no Home scaling)', len(tr) > 0 and all(x.startswith('matrix(1, 0, 0, 1, 0, ') and 15 < float(x.rstrip(')').split(',')[-1]) <= 22 for x in tr), tr)
    b.close()

    # ===== 7. reduced motion and a missing motion script
    b, pg, errs = page(p, reduced=True)
    check('reduced motion: no motion styles (html.fx off), no particles, but everything is visible', not pg.evaluate("document.documentElement.classList.contains('fx')") and pg.evaluate('HomeFX.info().canvases') == 0 and pg.evaluate("[...document.querySelectorAll('.home .rv')].every(e=>getComputedStyle(e).opacity==='1')"))
    check('reduced motion: countdowns still run', pg.evaluate("+document.querySelector('.fxbig b').textContent") == 20)
    check('reduced motion: spots shown without counting down', pg.evaluate("[...document.querySelectorAll('.fxspots b')].every(b=>b.textContent==='12')"), pg.evaluate("[...document.querySelectorAll('.fxspots b')].map(b=>b.textContent)"))
    b.close()
    b, pg, errs = page(p, nofx=True)
    check('motion script fails to load: Home still shows everything, with no countdown stuck at 00', not errs and pg.evaluate("[...document.querySelectorAll('.home .rv')].every(e=>getComputedStyle(e).opacity==='1')") and pg.evaluate("document.querySelector('.fxcdwrap').hidden"), errs)
    pg.click('#hero-register'); pg.wait_for_selector('#n0'); check('motion script fails to load: Register still works', True)
    b.close()

    # ===== 8. desktop
    b, pg, errs = page(p, w=1280, h=800)
    check('desktop: no errors, no sideways scroll, 26 particles', not errs and pg.evaluate('document.documentElement.scrollWidth<=innerWidth+1') and pg.evaluate('HomeFX.info().particles') == 26, errs)
    b.close()

n = len(res); print(f'\n{sum(res)} of {n} checks passed'); raise SystemExit(0 if all(res) else 1)
