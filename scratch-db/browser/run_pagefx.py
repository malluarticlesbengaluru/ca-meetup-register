"""Tests for the motion on every public screen except Home (assets/page-fx.js + the CSS in index.html), and for the payment-screen change:
the scroll-reveal ("a card appears only when you swipe to it") is OFF on the two payment screens, so the next card is never hidden.
Run:  cd scratch-db/browser && python3 run_pagefx.py | tail -1      (PAGE=/path/index.html, FX=/path/page-fx.js test other copies)"""
import os, sys, subprocess
from playwright.sync_api import sync_playwright
ROOT = '/home/claude/ca-meetup-register/'
HTML = open(os.environ.get('PAGE', ROOT + 'index.html'), encoding='utf-8').read()
FX = open(os.environ.get('FX', ROOT + 'assets/page-fx.js'), encoding='utf-8').read()
res = []
def check(n, c, d=''): res.append(bool(c)); print(('  PASS  ' if c else '  FAIL  ') + n + ('' if c else '  ' + str(d)[:300]))
FAKE_SB = "window.supabase={createClient:()=>({auth:{},rpc:async()=>({data:null,error:{message:'x'}}),storage:{from:()=>({upload:async()=>({data:{},error:null})})}})};"
QR = "window.qrcode=function(){return {addData(){},make(){},getModuleCount(){return 21},isDark(){return false}}};"
PAYSTATE = ("S.status={price_per_head:250,max_group:5,accepting:true,deadline:'2026-10-31T18:29:59Z'};S.n=3;S.pay={upi:'org@upi',payee:'Mallu Articles',wa:'919999999999'};"
            "S.payLoading=false;S.payFail=false;")

def new_page(p, html=None, fx=None, hfx=None, reduced=False, w=390, h=844):
    b = p.chromium.launch(); ctx = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=True, has_touch=True, reduced_motion='reduce' if reduced else 'no-preference')
    pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    H = HTML if html is None else html; F = FX if fx is None else fx
    def hd(r):
        u = r.request.url
        if u.endswith('/test.html'): r.fulfill(body=H, content_type='text/html')
        elif '@supabase' in u: r.fulfill(body=FAKE_SB, content_type='text/javascript')
        elif 'qrcode' in u and u.split('?')[0].endswith('.js'): r.fulfill(body=QR, content_type='text/javascript')
        elif 'page-fx.js' in u: r.fulfill(body=F, content_type='text/javascript')
        elif '/assets/' in u and u.split('?')[0].endswith('.png'): r.fulfill(path=ROOT + 'assets/' + u.split('/assets/')[1].split('?')[0])
        else: r.fulfill(status=204, body='')
    pg.route('**/*', hd); pg.goto('https://example.test/test.html', wait_until='commit'); pg.wait_for_selector('#app .invite'); pg.wait_for_timeout(1500)
    return b, pg, errs
def show(pg, step, extra=''): pg.evaluate(PAYSTATE + extra + f"S.step='{step}';render();")
WAAPI = "document.getAnimations().filter(a=>a.constructor.name==='Animation'&&a.effect&&a.effect.target&&a.effect.target.closest&&a.effect.target.closest('#app')).length"
CARDS = "(()=>{const c=[...document.querySelectorAll('#app .card')];return {n:c.length,rv:c.filter(e=>e.classList.contains('rv')).length,minOp:Math.min(...c.map(e=>+getComputedStyle(e).opacity)),tops:c.map(e=>Math.round(e.getBoundingClientRect().top+scrollY))}})()"

with sync_playwright() as p:
    # ---------- the payment screens ----------
    b, pg, errs = new_page(p)
    check('Z0 the new scripts really are loaded (so these checks mean something)', pg.evaluate("typeof PageFX") == 'object')
    show(pg, 'pay'); c0 = pg.evaluate(CARDS)
    check('PAY1 payment screen: no card is held back by the scroll-reveal (none has the hidden class), right away', c0['n'] >= 2 and c0['rv'] == 0, c0)
    pg.wait_for_timeout(1000); c1 = pg.evaluate(CARDS)
    check('PAY2 ... and after the short entrance every card, including "Upload your payment screenshot", is fully visible without scrolling', c1['minOp'] >= 0.99 and c1['rv'] == 0, c1)
    check('PAY3 the screenshot card is the second card, below the QR card (so scrolling down reaches it)', c1['n'] == 2 and c1['tops'][1] > c1['tops'][0], c1)
    show(pg, 'tpay', "S.xp={amount:500,code:'AB12CD34',ph:'9000000001',busy:false,err:'',file:null,sid:'x'};"); pg.wait_for_timeout(900); c2 = pg.evaluate(CARDS)
    check('PAY4 the transfer payment screen (also a QR page) behaves the same: no hidden card', c2['n'] >= 2 and c2['rv'] == 0 and c2['minOp'] >= 0.99, c2)
    # everything else keeps the scroll-reveal exactly as before
    show(pg, 'form', "S.n=5;setN(5);"); c3 = pg.evaluate(CARDS)
    check('KEEP1 the registration form (5 people) still holds back the cards below the fold, as before', c3['n'] >= 5 and c3['rv'] >= 1, c3)
    check('PAY5 no script errors', not errs, errs)

    # ---------- the short entrance, only when a screen changes ----------
    show(pg, 'summary'); pg.wait_for_timeout(80)
    a1 = pg.evaluate(WAAPI); pg.wait_for_timeout(1000)
    st = pg.evaluate("(()=>{const e=[...document.querySelectorAll('#app > *')].filter(x=>!x.classList.contains('rv'));return {n:e.length,bad:e.filter(x=>+getComputedStyle(x).opacity<.99||getComputedStyle(x).transform!=='none').length}})()")
    check('ENT1 changing to another screen plays a short entrance', a1 >= 3, a1)
    check('ENT2 ... which has finished within a second, leaving everything fully visible and in place', st['n'] >= 3 and st['bad'] == 0, st)
    pg.evaluate("render()"); pg.wait_for_timeout(60); a2 = pg.evaluate(WAAPI)
    check('ENT3 redrawing the SAME screen (typing, an error message, a chosen file) does not replay it', a2 == 0, a2)
    pg.evaluate("S.payLoading=true;S.step='pay';render()"); pg.wait_for_timeout(1000)
    pg.evaluate("S.payLoading=false;render()"); pg.wait_for_timeout(80); a3 = pg.evaluate(WAAPI)
    check('ENT4 the payment screen that first says "Loading the payment details" and then shows its cards: the cards do get their entrance when they arrive', a3 >= 2, a3)
    pg.evaluate("S.step='loading';render()"); pg.wait_for_timeout(60); a4 = pg.evaluate(WAAPI)
    check('ENT5 the brief "Loading…" screen is not animated', a4 == 0, a4)
    # ---------- ripple on every button, exactly one ----------
    show(pg, 'summary'); pg.wait_for_timeout(900)
    r1 = pg.evaluate("""(()=>{const b=document.querySelector('#app button'),r=b.getBoundingClientRect();
      b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:r.left+20,clientY:r.top+10,pointerType:'touch'}));return [b.id,b.querySelectorAll('.fxr').length]})()""")
    pg.wait_for_timeout(1200); r2 = pg.evaluate("document.querySelectorAll('.fxr').length")
    check('RIP1 pressing any button (here on the review screen) makes one soft ripple, removed afterwards', r1[1] == 1 and r2 == 0, (r1, r2))
    pg.evaluate("S.step='home';render()"); pg.wait_for_timeout(300)
    r3 = pg.evaluate("""(()=>{const b=document.getElementById('go-register'),r=b.getBoundingClientRect();
      b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:r.left+20,clientY:r.top+10,pointerType:'touch'}));return b.querySelectorAll('.fxr').length})()""")
    check('RIP2 on Home exactly ONE ripple (not two: Home and the page-wide script do not both add one)', r3 == 1, r3)
    pg.evaluate("S.step='summary';render()"); pg.wait_for_timeout(900)
    dis = pg.evaluate("""(()=>{const b=document.querySelector('#app button');b.disabled=true;const r=b.getBoundingClientRect();
      b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:r.left+5,clientY:r.top+5}));return b.querySelectorAll('.fxr').length})()""")
    check('RIP3 a disabled button makes no ripple', dis == 0, dis)
    css = pg.evaluate("""(()=>{const b=document.querySelector('#app button'),k=document.querySelector('.kasavu');return {tr:getComputedStyle(b).transitionProperty,ov:getComputedStyle(b).overflow,pos:getComputedStyle(b).position,band:getComputedStyle(k).animationName+'|'+getComputedStyle(k).animationDuration}})()""")
    check('CSS1 every button can press in (scale transition) and clips its ripple', 'scale' in css['tr'] and css['ov'] == 'hidden' and css['pos'] == 'relative', css)
    check('CSS2 the thin colour stripe under the header flows slowly (16 s), like the Home bands', css['band'] == 'fxFlow|16s', css)
    check('ALL no script errors', not errs, errs); b.close()

    # ---------- reduced motion ----------
    b, pg, errs = new_page(p, reduced=True); show(pg, 'summary'); pg.wait_for_timeout(60)
    rm = pg.evaluate(WAAPI)
    pg.evaluate("""(()=>{const b=document.querySelector('#app button'),r=b.getBoundingClientRect();b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:r.left+20,clientY:r.top+10}))})()""")
    rip = pg.evaluate("document.querySelectorAll('.fxr').length"); kb = pg.evaluate("getComputedStyle(document.querySelector('.kasavu')).animationName")
    show(pg, 'pay'); c = pg.evaluate(CARDS)
    check('RM1 reduced motion: no entrance, no ripple, the stripe is still, and the payment cards are all visible at once', rm == 0 and rip == 0 and kb == 'none' and c['rv'] == 0 and c['minOp'] == 1, (rm, rip, kb, c))
    check('RM2 reduced motion: no script errors', not errs, errs); b.close()

    # ---------- deliberate mistakes ----------
    def mut(src, old, new):
        assert src.count(old) == 1, (old[:60], src.count(old)); return src.replace(old, new)
    # a) the scroll-reveal is back on the payment screens (the thing the owner asked to remove)
    BAD = mut(HTML, 'if(S.step==="pay"||S.step==="tpay")return;   /* the payment screens', 'if(false)return;   /* the payment screens')
    b, pg, errs = new_page(p, html=BAD); show(pg, 'pay'); pg.wait_for_timeout(900); cb = pg.evaluate(CARDS); b.close()
    check('control: bringing the scroll-reveal back on the payment screen is DETECTED (a card is hidden)', cb['rv'] > 0 or cb['minOp'] < .99, cb)
    # b) the entrance replays on every redraw
    BAD2 = mut(FX, 'fresh=step!==prevStep||(cards&&!prevCards);', 'fresh=true;')
    b, pg, errs = new_page(p, fx=BAD2); show(pg, 'summary'); pg.wait_for_timeout(1000); pg.evaluate("render()"); pg.wait_for_timeout(60); ra = pg.evaluate(WAAPI); b.close()
    check('control: an entrance that replays on every redraw is DETECTED', ra != 0, ra)
    # c) two ripples on Home (the old Home script still adds its own)
    import subprocess
    old_home = subprocess.run(['git', '-C', ROOT, 'show', '4ea94b7:assets/home-fx.js'], capture_output=True, text=True).stdout
    check('control: the old home-fx.js (with its own ripple) was found in git history', 'press ripple on the big buttons' in old_home)
    b, pg, errs = new_page(p, hfx=old_home)
    rr = pg.evaluate("""(()=>{const b=document.getElementById('go-register'),r=b.getBoundingClientRect();
      b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:r.left+20,clientY:r.top+10,pointerType:'touch'}));return b.querySelectorAll('.fxr').length})()"""); b.close()
    check('control: two ripples on one press are DETECTED', rr != 1, rr)
    # d) ripple on a disabled button
    BAD4 = mut(FX, 'if(!b||b.disabled||b.getAttribute("aria-disabled")==="true")return;', 'if(!b)return;')
    b, pg, errs = new_page(p, fx=BAD4); show(pg, 'summary'); pg.wait_for_timeout(900)
    d4 = pg.evaluate("""(()=>{const b=document.querySelector('#app button');b.disabled=true;const r=b.getBoundingClientRect();b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:r.left+5,clientY:r.top+5}));return b.querySelectorAll('.fxr').length})()"""); b.close()
    check('control: a ripple on a disabled button is DETECTED', d4 != 0, d4)
    # e) motion ignoring reduced-motion
    BAD5 = mut(FX, 'if(RM.matches||!fresh||step==="home"||step==="loading")return;', 'if(!fresh||step==="home"||step==="loading")return;')
    b, pg, errs = new_page(p, fx=BAD5, reduced=True); show(pg, 'summary'); pg.wait_for_timeout(60); e5 = pg.evaluate(WAAPI); b.close()
    check('control: an entrance that ignores "reduce motion" is DETECTED', e5 != 0, e5)

n = len(res); bad = res.count(False)
print(f"{n - bad} passed, {bad} failed")
sys.exit(1 if bad else 0)
