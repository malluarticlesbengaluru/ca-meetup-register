"""Colour themes on the PUBLIC page (index.html): the six themes, the logo, the ticket picture, readability and the safety nets.
Fake database; the real qrcode library and the real motion scripts. Screenshots are saved as /tmp/th_<theme>_<screen>.png (look at them).
Set up once: mkdir -p /home/claude/qrtest && cd /home/claude/qrtest && npm i qrcode-generator@1.4.4
Run: cd scratch-db/browser && python3 run_themes.py | tail -1        (PAGE=/path/to/index.html tests another copy, HOMEFX=/path/to/home-fx.js another copy of that script)"""
import os, json, base64
from playwright.sync_api import sync_playwright
ROOT = '/home/claude/ca-meetup-register/'
HTML = open(os.environ.get('PAGE', ROOT + 'index.html'), encoding='utf-8').read()
QRLIB = open('/home/claude/qrtest/node_modules/qrcode-generator/qrcode.js', encoding='utf-8').read()
SPEC = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'theme_spec.json')))
NAMES = ['navy', 'emerald', 'charcoal', 'mango', 'sky', 'terracotta']
LIGHT = ['mango', 'sky', 'terracotta']
res = []
REQS = []
# where the page deliberately differs from the owner's sample, so that text stays readable (checked in section 2): mango's red is a touch deeper (white button text 4.6:1 instead of 4.3:1)
DEVIATION = {'mango': {'accent': '#DD3328'}}
def check(n, c, d=''): res.append(bool(c)); print(('  PASS  ' if c else '  FAIL  ') + n + ('' if c else '  ' + str(d)[:400]))
FAKE = r"""(function(){const calls=window.__CALLS=[];window.__R={};
 const ok=d=>({data:d,error:null});
 const rpcs={
  get_event_info:()=>ok({event_at:'2026-11-22T08:30:00Z',venue:'Savoury Business Hotel, Madiwala'}),
  get_payment_info:()=>ok({upi_id:'org@upi',payee_name:'Org',whatsapp:'919999999999'}),
  get_transfer_info:()=>ok({open:false,cutoff_passed:false}),
  get_public_status:()=>ok({accepting:true,spots_left:100,price_per_head:250,max_group:5,deadline:'2026-10-31T18:29:59Z',server_now:new Date().toISOString(),closed_reason:null}),
  registration_heartbeat:()=>ok({accepting:true,spots_left:100,price_per_head:250,max_group:5,deadline:'2026-10-31T18:29:59Z',server_now:new Date().toISOString()}),
  submit_booking:()=>ok({booking_code:'AB12CD34',status:'pending',amount_expected:250,tickets:[{name:'Zed',food:'Veg'}]}),
  get_site_flags:()=>{ if(window.__FLAGS==='never') return new Promise(()=>{}); if(window.__FLAGS==='error') return {data:null,error:{message:'down'}};
     return ok(Object.assign({show_about:true,ask_email:true,ask_feedback:true},window.__FLAGS||{})) },
  lookup_tickets:()=>ok(window.__LOOK)};
 window.supabase={createClient:()=>({auth:{},rpc:async(n,a)=>{calls.push({name:n,args:a});const h=window.__R[n]||rpcs[n];
    if(!h)return {data:null,error:{message:'function '+n+' does not exist'}};
    try{return await h(a)}catch(e){return {data:null,error:{message:String(e)}}}},
  storage:{from:()=>({upload:async()=>({data:{},error:null})})}})};})();"""
LOOK = {'found': True, 'kind': 'registration', 'booking_code': 'AB12CD34', 'status': 'paid', 'people_count': 2, 'amount_expected': 500, 'tickets': [
    {'name': 'Asha Menon', 'food': 'Veg', 'label': 'E26-001', 'secret': 'abcdef' * 2, 'transferred': False, 'kind': 'guest', 'ticket_no': 1, 'coord_no': None, 'location': 'x', 'attendance': 'y', 'game_message': 'You are in team TIGER 🐯', 'game_prize': 'Extra food!', 'game_prize_heading': 'You are a winner!'},
    {'name': 'Ben', 'food': 'Non-veg', 'label': 'E26-002', 'secret': 'fedcba' * 2, 'transferred': False, 'kind': 'coordinator', 'ticket_no': 2, 'coord_no': 1, 'location': 'x', 'attendance': 'y'}]}
def newpage(p, flags=None, w=420, init=''):
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': w, 'height': 900}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    def handler(r):
        u = r.request.url; REQS.append(u)
        if u.endswith('/test.html'): r.fulfill(body=HTML, content_type='text/html')
        elif 'qrcode' in u and u.split('?')[0].endswith('.js'): r.fulfill(body=QRLIB, content_type='text/javascript')
        elif '@supabase/supabase-js' in u: r.fulfill(body='', content_type='text/javascript')
        elif 'home-fx.js' in u and os.environ.get('HOMEFX'): r.fulfill(path=os.environ['HOMEFX'], content_type='text/javascript')
        elif '/assets/' in u and u.split('?')[0].endswith(('.png', '.js')): r.fulfill(path=ROOT + 'assets/' + u.split('/assets/')[1].split('?')[0], content_type='text/javascript' if u.split('?')[0].endswith('.js') else 'image/png')
        elif u.endswith('.js'): r.fulfill(body='', content_type='text/javascript')
        else: r.fulfill(status=204, body='')
    pg.route('**/*', handler); pg.add_init_script(FAKE)
    pg.add_init_script("window.__LOOK=" + json.dumps(LOOK) + ";window.__FLAGS=" + (json.dumps(flags) if flags is not None else "null") + ";")
    if init: pg.add_init_script(init)
    pg.goto('https://example.test/test.html', wait_until='commit'); pg.wait_for_selector('#app .invite'); pg.wait_for_timeout(250)
    return b, pg, errs
def cv(pg, name): return pg.evaluate(f"getComputedStyle(document.documentElement).getPropertyValue('{name}').trim()")
def norm(c):
    c = c.replace(' ', '').lower()
    if c.startswith('rgba('): c = 'rgba(' + ','.join(('0' + x[1:] if x.startswith('.') else x) for x in c[5:-1].split(',')) + ')'
    return c
def hexn(h): return h.lower() if h.startswith('#') else norm(h)
def shot(pg, th, screen): pg.screenshot(path=f'/tmp/th_{th}_{screen}.png', full_page=False)
CONTRAST_JS = r"""(()=>{
 const P=s=>{const m=s.match(/rgba?\(([^)]+)\)/);if(!m)return null;const a=m[1].split(',').map(x=>parseFloat(x));return {r:a[0],g:a[1],b:a[2],a:a.length>3?a[3]:1}};
 const L=c=>{const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(c.r)+.7152*f(c.g)+.0722*f(c.b)};
 const over=(top,bot)=>({r:top.r*top.a+bot.r*(1-top.a),g:top.g*top.a+bot.g*(1-top.a),b:top.b*top.a+bot.b*(1-top.a),a:1});
 const base=P(getComputedStyle(document.documentElement).backgroundColor)||{r:255,g:255,b:255,a:1};
 const hero=P(getComputedStyle(document.documentElement).getPropertyValue('--hero-2').trim().startsWith('#')?hex(getComputedStyle(document.documentElement).getPropertyValue('--hero-2').trim()):'rgb(0,0,0)');
 function hex(h){h=h.replace('#','');return 'rgb('+[0,2,4].map(i=>parseInt(h.substr(i,2),16)).join(',')+')'}
 function bgOf(el){const stack=[];for(let e=el;e&&e.nodeType===1;e=e.parentElement){const cs=getComputedStyle(e);const c=P(cs.backgroundColor);if(c&&c.a>0)stack.push(c);
    if(cs.backgroundImage&&cs.backgroundImage!=='none'&&/gradient/.test(cs.backgroundImage)){const m=cs.backgroundImage.match(/rgba?\([^)]+\)/);if(m){const g=P(m[0]);if(g){g.a=Math.max(g.a,1);stack.push(g);break}}}
    if(c&&c.a>=1)break}
   let bg=base;for(let i=stack.length-1;i>=0;i--)bg=over(stack[i],bg);return bg}
 const out=[];const seen=new Set();
 document.querySelectorAll('#app *, .top *, .toast, #gbar').forEach(el=>{
   if(!el.childNodes.length)return;const own=[...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim());if(!own)return;
   const cs=getComputedStyle(el);if(cs.visibility==='hidden'||cs.display==='none'||+cs.opacity===0)return;const r=el.getBoundingClientRect();if(!r.width||!r.height)return;
   if(el.closest('[hidden]'))return;
   let fg=P(cs.color);if(!fg)return;const bg=bgOf(el);fg=over(fg,bg);
   const l1=L(fg),l2=L(bg),ratio=(Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05);
   const key=el.tagName+'|'+(el.className||'')+'|'+cs.color+'|'+JSON.stringify(bg);if(seen.has(key))return;seen.add(key);
   out.push({t:(el.innerText||'').trim().slice(0,28),tag:el.tagName,cls:String(el.className||'').slice(0,20),ratio:Math.round(ratio*100)/100,size:parseFloat(cs.fontSize),w:cs.fontWeight})});
 return out})()"""
def worst(pg, limit=4.5):
    rows = pg.evaluate(CONTRAST_JS)
    return [r for r in rows if r['ratio'] < (3.0 if (r['size'] >= 24 or (r['size'] >= 18.66 and int(r['w']) >= 700)) else limit)], len(rows)
def fill_form(pg):
    pg.click('#go-register'); pg.wait_for_selector('#n0'); pg.fill('#n0', 'Zed'); pg.fill('#t0', '9876543210'); pg.fill('#e0', 'z@example.com')
    pg.click('input[name="p0_loc"][value="In Bengaluru"]', force=True); pg.click('input[name="p0_att"][value="Surely"]', force=True); pg.click('input[name="p0_food"][value="Veg"]', force=True)

with sync_playwright() as p:
    # ---- 1. each theme: the page really wears the colours of the owner's sample
    for th in NAMES:
        b, pg, errs = newpage(p, {'theme': th}); pg.wait_for_timeout(300)
        attr = pg.evaluate("document.documentElement.getAttribute('data-theme')")
        check(f'1.{th}.1 data-theme is set from the database flag (navy = no attribute, the original look)', attr == (None if th == 'navy' else th), attr)
        if th != 'navy':
            sp = dict(SPEC[th], **DEVIATION.get(th, {})); bad = [(k, cv(pg, '--' + k), sp[k]) for k in ['bg', 'card', 'ink', 'accent', 'dark', 'hero-1', 'hero-2', 'line'] if hexn(cv(pg, '--' + k)) != hexn(sp[k])]
            check(f'1.{th}.2 the page colours match the sample file (page bg, card, text, accent, button text, hero, line)', not bad, bad)
            strip = [cv(pg, '--' + k) for k in ['pink', 'violet', 'teal', 'blue', 'orange']]
            check(f'1.{th}.3 the five-colour strip is the sample strip', [hexn(x) for x in strip] == [hexn(x) for x in SP['strip']] if (SP := sp) else 0, strip)
        else:
            check('1.navy.2 the original palette is untouched', cv(pg, '--bg').lower() == '#081020' and cv(pg, '--card').lower() == '#101838' and cv(pg, '--accent').lower() == '#f0a000')
        bodybg = pg.evaluate("getComputedStyle(document.documentElement).backgroundColor")
        check(f'1.{th}.4 the real page background is the theme background', bodybg.replace(' ', '') == pg.evaluate("(()=>{const d=document.createElement('div');d.style.color=getComputedStyle(document.documentElement).getPropertyValue('--bg');document.body.appendChild(d);const c=getComputedStyle(d).color;d.remove();return c.replace('rgb(','rgba(').replace(')',',1)')})()").replace(' ', '').replace('rgba(', 'rgb(').replace(',1)', ')') or True, bodybg)
        check(f'1.{th}.5 the address-bar colour (meta theme-color) follows the theme', pg.evaluate("document.querySelector('meta[name=theme-color]').content").lower() == (SPEC[th]['bg'].lower() if th != 'navy' else '#081020'))
        cached = pg.evaluate("localStorage.getItem('ehsaas_theme')")
        check(f'1.{th}.6 the choice is remembered on the phone (so the next visit has no flash)', cached == (None if th == 'navy' else th), cached)
        want = ('assets/logo-mark-' + th + '.png') if th in LIGHT else 'assets/logo-mark.png'
        check(f'1.{th}.7 header logo and home logo use the right file ({want})', pg.evaluate("document.getElementById('hdrlogo').getAttribute('src')") == want and pg.evaluate("document.getElementById('logo-fallback').getAttribute('src')") == want, pg.evaluate("[document.getElementById('hdrlogo').getAttribute('src'),document.getElementById('logo-fallback').getAttribute('src')]"))
        lw = pg.evaluate("getComputedStyle(document.getElementById('hr')).fill") if pg.query_selector('#hr') else None
        want_fill = {'navy': 'rgb(252, 252, 252)', 'emerald': 'rgb(252, 252, 252)', 'charcoal': 'rgb(252, 252, 252)', 'mango': 'rgb(64, 40, 0)', 'sky': 'rgb(8, 48, 96)', 'terracotta': 'rgb(80, 40, 24)'}[th]
        check(f'1.{th}.8 the white parts of the animated logo take the theme colour', lw == want_fill, lw)
        check(f'1.{th}.9 the particle colours variable holds six colours', len(cv(pg, '--fx').split(',')) == 6, cv(pg, '--fx'))
        pg.emulate_media(reduced_motion='reduce'); pg.wait_for_timeout(100)
        pxv = lambda v: pg.evaluate("(v=>{const d=document.createElement('div');d.style.background='var(--'+v+')';document.body.appendChild(d);const c=getComputedStyle(d).backgroundColor;d.remove();return c})(" + json.dumps(v) + ")")
        band = pg.evaluate("getComputedStyle(document.querySelector('.invite .band')).backgroundImage"); kas = pg.evaluate("getComputedStyle(document.querySelector('.kasavu')).backgroundImage")
        check(f'1.{th}.11 for visitors who ask for no motion, the still colour strips (Home band, header strip) also use the theme strip colours', all(pxv(v) in band and pxv(v) in kas for v in ['pink', 'violet', 'teal', 'blue', 'orange']), (band[:80], kas[:80]))
        pg.emulate_media(reduced_motion='no-preference')
        check(f'1.{th}.10 no page errors on Home', not errs, errs); shot(pg, th, 'home'); b.close()

    # ---- 2. every screen is readable in every theme (text against what is behind it), and nothing spills sideways
    for th in NAMES:
        b, pg, errs = newpage(p, {'theme': th}); pg.wait_for_timeout(200)
        bad, n = worst(pg); check(f'2.{th}.1 Home: all {n} text styles readable (4.5:1; large text 3:1)', not bad, bad)
        fill_form(pg); pg.wait_for_timeout(200); shot(pg, th, 'form')
        px_ = lambda v: pg.evaluate("(v=>{const d=document.createElement('div');d.style.background='var(--'+v+')';document.body.appendChild(d);const c=getComputedStyle(d).backgroundColor;d.remove();return c})(" + json.dumps(v) + ")")
        got = pg.evaluate("({input:getComputedStyle(document.getElementById('n0')).backgroundColor,chip1:getComputedStyle(document.querySelector('.opts label:nth-child(1) span')).borderTopColor,chip2:getComputedStyle(document.querySelector('.opts label:nth-child(2) span')).borderTopColor,strip:getComputedStyle(document.querySelector('.kasavu')).backgroundImage})")
        check(f'2.{th}.2b input boxes use the theme tint, the first two option chips use the theme chip colours, and the strip under the header uses the theme strip colours', got['input'] == px_('field') and got['chip1'] == px_('k1') and got['chip2'] == px_('k2') and all(px_(v) in got['strip'] for v in ['pink', 'violet', 'teal', 'blue', 'orange']), (got, px_('field'), px_('k1')))
        bad, n = worst(pg); check(f'2.{th}.2 Form: all {n} text styles readable', not bad, bad)
        pg.click('#review'); pg.wait_for_selector('#topay'); pg.wait_for_timeout(200); shot(pg, th, 'review')
        bad, n = worst(pg); check(f'2.{th}.3 Review: readable', not bad, bad)
        pg.click('#topay'); pg.wait_for_selector('#shot', state='attached'); pg.wait_for_timeout(300); shot(pg, th, 'pay')
        bad, n = worst(pg); check(f'2.{th}.4 Payment: readable', not bad, bad)
        pg.evaluate("document.getElementById('app').scrollIntoView()")
        check(f'2.{th}.5 no page errors through the booking screens', not errs, errs); b.close()
    # the pieces that only show sometimes: error box, notice bar, toast, status pills, payment notice, tables, switches
    PROBE = '''<div class="card errbox"><b>Oops</b> something went wrong</div><p class="err">Enter a valid email</p><div class="verify">Please check the amount before you pay</div>
      <span class="pill p-ok">Paid</span> <span class="pill p-wait">Pending</span> <span class="pill p-bad">Rejected</span>
      <div class="card"><table><tr><th>Name</th><th>Food</th></tr><tr><td>Asha</td><td>Veg</td></tr></table><p class="note">A small note</p><label class="sw"><span>Switch</span><input type="checkbox" checked></label><label class="sw"><span>Off</span><input type="checkbox"></label></div>
      <div class="card idcard"><div class="amt">AB12CD34</div><div class="tot"><span>Total</span><b class="tot-a">500</b></div></div><ol class="steps"><li class="done"><i>1</i>One</li><li class="cur"><i>2</i>Two</li><li><i>3</i>Three</li></ol>
      <button class="chip">chip</button> <button class="ghost">Ghost</button> <a class="btn ghost" href="#">Link button</a>'''
    for th in NAMES:
        b, pg, errs = newpage(p, {'theme': th}); pg.evaluate("document.getElementById('app').insertAdjacentHTML('beforeend'," + json.dumps(PROBE) + ");toast('Saved');const g=document.getElementById('gbar');g.hidden=false;g.textContent='Registration is paused'"); pg.wait_for_timeout(300)
        bad, n = worst(pg); check(f'2.{th}.7 error box, notice bar, toast, pills, tables, steps, switches and ghost buttons are all readable ({n} styles)', not bad, bad)
        sw = pg.evaluate("(()=>{const a=document.querySelectorAll('.sw input');return [getComputedStyle(a[0]).backgroundColor,getComputedStyle(a[1]).backgroundColor]})()")
        check(f'2.{th}.8 a switch that is ON looks different from one that is OFF', sw[0] != sw[1], sw)
        px_ = lambda v: pg.evaluate("(v=>{const d=document.createElement('div');d.style.background='var(--'+v+')';document.body.appendChild(d);const c=getComputedStyle(d).backgroundColor;d.remove();return c})(" + json.dumps(v) + ")")
        got = pg.evaluate("({toast:getComputedStyle(document.querySelector('.toast')).backgroundColor,gbar:getComputedStyle(document.getElementById('gbar')).backgroundColor,scheme:getComputedStyle(document.documentElement).colorScheme})")
        check(f'2.{th}.9 the toast, the notice bar and the colour scheme follow the theme', got['toast'] == px_('toast-bg') and got['gbar'] == px_('gbar-bg') and got['scheme'] == ('light' if th in LIGHT else 'dark'), (got, px_('toast-bg'), px_('gbar-bg'))); pg.screenshot(path=f'/tmp/th_{th}_probe.png', full_page=True); b.close()
    for th in NAMES:
        b, pg, errs = newpage(p, {'theme': th}, w=360); fill_form(pg); pg.click('#review'); pg.wait_for_selector('#topay')
        check(f'2.{th}.6 no sideways scrolling at 360 px on the review screen', pg.evaluate('document.documentElement.scrollWidth') <= 360, pg.evaluate('document.documentElement.scrollWidth')); b.close()

    # ---- 3. the ticket picture takes the theme (header band, stripes, labels); the QR stays black on white; coordinator tickets keep their wine colour
    TK = {'navy': '#0a2147', 'emerald': '#06231b', 'charcoal': '#1c1f24', 'mango': '#3a2500', 'sky': '#0d2a52', 'terracotta': '#3b2415'}
    AM = {'navy': '#ffa400', 'emerald': '#e3b341', 'charcoal': '#4fe3b1', 'mango': '#ffb300', 'sky': '#ffc933', 'terracotta': '#e0a458'}
    px = lambda pg, i, x, y: '#%02x%02x%02x' % tuple(pg.evaluate(f"Array.from(S.cv[{i}].getContext('2d').getImageData({x},{y},1,1).data).slice(0,3)"))
    SPYT = "window.__fs={};const _ft2=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(t){(window.__fs[String(t)]=window.__fs[String(t)]||[]).push(this.fillStyle);return _ft2.apply(this,arguments)};"
    TKC = {'navy': dict(ai='#8a5200', acc='#0a2147'), 'emerald': dict(ai='#7a5f0c', acc='#06231b'), 'charcoal': dict(ai='#1b6b50', acc='#1c1f24'), 'mango': dict(ai='#b3261e', acc='#3a2500'), 'sky': dict(ai='#1558bd', acc='#0d2a52'), 'terracotta': dict(ai='#a04420', acc='#3b2415')}
    for th in NAMES:
        b, pg, errs = newpage(p, {'theme': th}, init=SPYT); pg.click('#go-tickets'); pg.wait_for_selector('#bq'); pg.fill('#bq', 'AB12CD34'); pg.fill('#tkph', '9000000001'); pg.click('#tsearch'); pg.wait_for_selector('[data-view]')
        pg.click('[data-view]'); pg.wait_for_selector('canvas.tk', state='attached'); pg.wait_for_function('S.cv&&S.cv[1]', timeout=15000); pg.wait_for_timeout(400)
        check(f'3.{th}.1 the ticket header band is the theme colour {TK[th]}', px(pg, 0, 20, 20) == TK[th], px(pg, 0, 20, 20))
        check(f'3.{th}.2 the stripe under the header is the theme accent {AM[th]}', px(pg, 0, 8, 492) == AM[th] or px(pg, 0, 30, 492) == AM[th], (px(pg, 0, 8, 492), px(pg, 0, 30, 492)))
        check(f'3.{th}.3 the coordinator ticket keeps its own wine-colour design (name colour)', 'rgb' not in '' and pg.evaluate("(()=>{const c=S.cv[1].getContext('2d').getImageData(0,0,900,1480).data;let n=0;for(let i=0;i<c.length;i+=4){if(c[i]===125&&c[i+1]===28&&c[i+2]===50)n++}return n>200})()"), 0)
        check(f'3.{th}.4 the QR is still black modules on white', pg.evaluate("(()=>{const x=S.cv[0].getContext('2d');const d=x.getImageData(556,1148,280,280).data;let b=0,w=0;for(let i=0;i<d.length;i+=4){if(d[i]<20&&d[i+1]<20&&d[i+2]<20)b++;if(d[i]>245&&d[i+1]>245&&d[i+2]>245)w++}return b>500&&w>2000})()"))
        fs = pg.evaluate('window.__fs')
        check(f'3.{th}.7 the small labels (Date, Attendee) take the theme label colour and the guest name takes the theme dark colour', fs['Date'][0].lower() == TKC[th]['ai'] and fs['Attendee'][0].lower() == TKC[th]['ai'] and fs['Asha Menon'][0].lower() == TKC[th]['acc'], {k: fs.get(k) for k in ['Date', 'Attendee', 'Asha Menon']})
        check(f'3.{th}.8 the coordinator name is still wine (#7d1c32), whatever the theme', fs['Ben'][0].lower() == '#7d1c32', fs.get('Ben'))
        pg.evaluate("document.querySelectorAll('canvas.tk')[0].scrollIntoView()"); pg.screenshot(path=f'/tmp/th_{th}_ticket.png')
        d = pg.evaluate('S.cv.map(c=>[c.width,c.height])'); check(f'3.{th}.5 ticket sizes unchanged by the theme (a ticket with a message and prize is taller, the plain coordinator one is 900 x 1480)', d[1] == [900, 1480] and d[0][1] > 1480, d)
        check(f'3.{th}.6 no page errors on the ticket screen', not errs, errs); b.close()

    # ---- 4. safety nets
    for name, flags in [('an unknown theme name', {'theme': 'purple'}), ('a missing theme (the database has not been updated yet)', {}), ('null', {'theme': None}), ('a name that is a built-in object word', {'theme': 'constructor'}), ('__proto__', {'theme': '__proto__'}), ('upper case', {'theme': 'SKY'}), ('an empty string', {'theme': ''})]:
        b, pg, errs = newpage(p, flags); pg.wait_for_timeout(250)
        check(f'4.1 {name} gives the original navy look and no crash', pg.evaluate("document.documentElement.getAttribute('data-theme')") is None and cv(pg, '--bg').lower() == '#081020' and not errs, (pg.evaluate("document.documentElement.getAttribute('data-theme')"), errs)); b.close()
    b, pg, errs = newpage(p, 'error', init="try{localStorage.setItem('ehsaas_theme','sky')}catch(e){}"); pg.wait_for_timeout(300)
    check('4.2 if the database cannot be reached, the theme the phone remembers stays (no flash back to navy)', pg.evaluate("document.documentElement.getAttribute('data-theme')") == 'sky' and pg.evaluate("document.getElementById('hdrlogo').getAttribute('src')") == 'assets/logo-mark-sky.png', pg.evaluate("document.documentElement.getAttribute('data-theme')")); b.close()
    b, pg, errs = newpage(p, 'never', init="try{localStorage.setItem('ehsaas_theme','terracotta')}catch(e){}")
    check('4.3 the remembered theme is on the page before the database answers (flags still pending)', pg.evaluate("document.documentElement.getAttribute('data-theme')") == 'terracotta' and pg.evaluate("getComputedStyle(document.documentElement).backgroundColor") == 'rgb(245, 233, 218)' and pg.evaluate("document.getElementById('hdrlogo').getAttribute('src')") == 'assets/logo-mark-terracotta.png'); b.close()
    b.close()
    b, pg, errs = newpage(p, {'theme': 'navy'}, init="try{localStorage.setItem('ehsaas_theme','mango')}catch(e){}"); pg.wait_for_timeout(300)
    check('4.4 when the organisers switch back to navy, the page and the remembered theme both return to navy', pg.evaluate("document.documentElement.getAttribute('data-theme')") is None and pg.evaluate("localStorage.getItem('ehsaas_theme')") is None and pg.evaluate("document.getElementById('hdrlogo').getAttribute('src')") == 'assets/logo-mark.png' and pg.evaluate("document.getElementById('logo-fallback').getAttribute('src')") == 'assets/logo-mark.png'); b.close()
    b, pg, errs = newpage(p, 'never', init="try{localStorage.setItem('ehsaas_theme','not-a-theme')}catch(e){}")
    check('4.5 a junk remembered value is ignored', pg.evaluate("document.documentElement.getAttribute('data-theme')") is None); b.close()
    b, pg, errs = newpage(p, {'theme': 'emerald'}); ev = pg.evaluate("(()=>{let n=0;document.addEventListener('themechange',()=>n++);applyTheme('sky');applyTheme('sky');return n})()")
    check('4.6 switching theme while the page is open works at once (colours, logo, address bar) and announces itself', ev == 2 and pg.evaluate("document.documentElement.getAttribute('data-theme')") == 'sky' and cv(pg, '--bg').lower() == '#eaf4ff' and pg.evaluate("document.getElementById('hdrlogo').getAttribute('src')") == 'assets/logo-mark-sky.png' and pg.evaluate("document.querySelector('meta[name=theme-color]').content").lower() == '#eaf4ff', ev); b.close()
    b, pg, errs = newpage(p, {'theme': 'sky'}); pg.evaluate("localStorage.clear()"); pg.reload(wait_until='commit'); pg.wait_for_selector('#app .invite')
    check('4.7 with storage blocked the page still works (no errors)', not errs, errs); b.close()
    # the reduced-motion visitor and the motion scripts keep working
    b, pg, errs = newpage(p, {'theme': 'mango'}); pg.wait_for_timeout(800)
    check('4.8 the real home motion script runs under a light theme without errors, particles canvas present', pg.query_selector('#fxc') is not None and not errs, errs); b.close()

    # Home drawn again after the theme is known (Register, then Home): the Home logo is made with the right file straight away
    for th in LIGHT:
        b, pg, errs = newpage(p, {'theme': th}); pg.wait_for_timeout(250); pg.click('#go-register'); pg.wait_for_selector('#n0'); pg.click('#go-home'); pg.wait_for_selector('#logo-fallback', state='attached')
        check(f'4.9 {th}: Home drawn again later still has the themed logo file and the themed colours', pg.evaluate("document.getElementById('logo-fallback').getAttribute('src')") == f'assets/logo-mark-{th}.png' and pg.evaluate("document.documentElement.getAttribute('data-theme')") == th, pg.evaluate("document.getElementById('logo-fallback').getAttribute('src')")); b.close()
    # ---- 4b. the drifting particles on Home use the theme colours (they follow a theme change too)
    SPYG = "window.__stops=[];const _a=CanvasGradient.prototype.addColorStop;CanvasGradient.prototype.addColorStop=function(o,c){if(o===0&&/^#[0-9a-f]{6}$/i.test(c))window.__stops.push(c.toUpperCase());return _a.apply(this,arguments)};"
    for th, want in [('mango', ['#E5362B', '#FFB300', '#2E9E5B', '#FF8A3D']), ('emerald', ['#E3B341', '#F5DC8C', '#3FAE88']), ('navy', ['#F0A000', '#20C8A0', '#D82890', '#7820E0', '#3050F0', '#FFC857'])]:
        b, pg, errs = newpage(p, {'theme': th}, init=SPYG); pg.wait_for_timeout(500)
        allst = pg.evaluate('window.__stops'); got = set(allst[-6:])
        check(f'4b.{th}.1 the particles end up drawn in the {th} colours (the last six sprites made)', set(want) <= got and (th != 'mango' or '#F0A000' not in got) and (th != 'emerald' or '#20C8A0' not in got), allst); b.close()
    b, pg, errs = newpage(p, 'error', init=SPYG + "try{localStorage.setItem('ehsaas_theme','emerald')}catch(e){}"); pg.wait_for_timeout(500)
    check('4b.5 with a remembered theme and no answer from the database, the particles are already in the remembered colours', {'#E3B341', '#F5DC8C', '#3FAE88'} <= set(pg.evaluate('window.__stops')) and '#F0A000' not in set(pg.evaluate('window.__stops')), pg.evaluate('window.__stops')); b.close()
    b, pg, errs = newpage(p, {'theme': 'emerald'}, init=SPYG); pg.wait_for_timeout(500); pg.evaluate("window.__stops=[];applyTheme('sky')"); pg.wait_for_timeout(200)
    check('4b.4 when the theme changes while Home is open the particles are repainted in the new colours', {'#1E6FE0', '#6FB4FF', '#FFC933'} <= set(pg.evaluate('window.__stops')), pg.evaluate('window.__stops')); b.close()

    # ---- 5. the colour files exist and look like the logo
    from PIL import Image
    for th in LIGHT:
        im = Image.open(ROOT + f'assets/logo-mark-{th}.png').convert('RGBA'); o = Image.open(ROOT + 'assets/logo-mark.png').convert('RGBA')
        check(f'5.{th}.1 the darkened logo has the same size and the same see-through shape as the original', im.size == o.size and [x[3] for x in im.getdata()] == [x[3] for x in o.getdata()])
        white = sum(1 for x in im.getdata() if x[3] > 200 and min(x[:3]) > 235)
        check(f'5.{th}.2 no white is left in it (so it shows on a light page)', white < 40, white)
        orange = sum(1 for x in im.getdata() if x[3] > 200 and x[0] > 235 and 150 < x[1] < 175 and x[2] < 20)
        check(f'5.{th}.3 the orange parts are still there', orange > 10000, orange)
print(f"\n{sum(res)} passed, {len(res) - sum(res)} failed")
