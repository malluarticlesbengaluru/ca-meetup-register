"""Touch checks for Home (Nov 2026): a finger on the Date/Venue cards must not lift or ripple them; no venue pill in the hero; Sponsored by line in the footer.
Run: cd scratch-db/browser && python3 run_home_touch.py | tail -1"""
import os,sys,mimetypes
sys.argv=['x']
from playwright.sync_api import sync_playwright
ROOT=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..'))+'/'
HTML=open(ROOT+'index.html',encoding='utf-8').read()
src=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'run_home.py'),encoding='utf-8').read()
MOCK=src.split("MOCK = r'''")[1].split("'''")[0]
res=[]
def check(n,c,d=''):
    res.append(bool(c));print(('  PASS  ' if c else '  FAIL  ')+n+('' if c else '  '+str(d)[:300]))
def mk(p,touch,sponsor='',video=False):
    b=p.chromium.launch();ctx=b.new_context(viewport={'width':390,'height':844},has_touch=touch,is_mobile=touch)
    pg=ctx.new_page();errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    def hd(r):
        u=r.request.url
        if u.endswith('/test.html'):r.fulfill(body=__import__('re').sub(r'const SPONSOR=\{[^}]*\}','const SPONSOR={src:"assets/sponsorfolder.jpg",name:"%s",logo:"%s",video:"assets/sponsor-video.mp4"}'%(sponsor,'assets/sponsor-logo.png' if sponsor else ''),HTML),content_type='text/html')
        elif u.split('?')[0].endswith('/assets/sponsor-video.mp4') and video:r.fulfill(path='/tmp/spv.webm',content_type='video/webm')
        elif '/assets/' in u:
            f=ROOT+'assets/'+u.split('/assets/')[1].split('?')[0]
            r.fulfill(path=f,content_type=mimetypes.guess_type(f)[0] or 'application/octet-stream') if os.path.exists(f) else r.fulfill(status=404,body='')
        elif u.endswith('.js') or '/npm/' in u:r.fulfill(body='window.qrcode=function(){return {addData(){},make(){},getModuleCount(){return 21},isDark(){return false}}};',content_type='text/javascript')
        else:r.fulfill(status=204,body='')
    pg.route('**/*',hd);pg.add_init_script(MOCK)
    pg.goto('https://example.test/test.html');pg.wait_for_selector('.home h1');pg.wait_for_timeout(3500)
    return b,pg,errs
with sync_playwright() as p:
    b,pg,errs=mk(p,True,'Eagles Institute of Management')
    check('no venue pill in the hero',pg.evaluate("document.querySelectorAll('.hhero .hfacts').length")==0 and pg.evaluate("!document.querySelector('.hhero').innerText.includes('Bloom')"))
    check('venue still shown in the Venue card',pg.evaluate("document.querySelector('#home-map').innerText.includes('Bloom')"))
    for id in ['home-cal','home-map']:
        pg.evaluate("id=>document.getElementById(id).scrollIntoView({block:'center'})",id);pg.wait_for_timeout(1200)
        box=pg.evaluate("id=>{const r=document.getElementById(id).getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2,r.height,r.width]}",id)
        cdp=pg.context.new_cdp_session(pg)
        cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':box[0],'y':box[1]}]});pg.wait_for_timeout(400)
        st=pg.evaluate("id=>{const e=document.getElementById(id),c=getComputedStyle(e),r=e.getBoundingClientRect();return {t:c.transform,sc:c.scale,h:r.height,w:r.width,rip:e.querySelectorAll('.fxr').length}}",id)
        cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
        check(f'{id}: finger down does not lift, scale or ripple the card',st['t'] in('none','matrix(1, 0, 0, 1, 0, 0)') and st['sc'] in('none','1') and abs(st['h']-box[2])<0.6 and abs(st['w']-box[3])<0.6 and st['rip']==0,st)
    pg.evaluate("window.scrollTo(0,document.body.scrollHeight)");pg.wait_for_timeout(1500)
    t=pg.evaluate("document.querySelector('.hfoot').innerText")
    check('footer: brand line then Co-sponsored by line (not Sponsored by)',t.index('Mallu Articles')<t.index('Co-sponsored by Eagles Institute of Management') and 'Co-sponsored' in t and t.replace('Co-sponsored','').find('Sponsored by')<0,t)
    pg.screenshot(path='/tmp/h_footer.png')
    check('sponsor logo drawn under the line, loaded, and not wider than the screen',pg.evaluate("(()=>{const i=document.querySelector('.hfoot .hspons img');return !!i&&i.naturalWidth>0&&i.getBoundingClientRect().width<=220&&i.getBoundingClientRect().top>document.querySelector('.hfoot .hspons span').getBoundingClientRect().top})()"))
    pg.screenshot(path='/tmp/h_footer2.png')
    check('no script errors',not errs,errs);b.close()
    b,pg,errs=mk(p,True,'')
    check('no sponsor name or logo set: no empty Co-sponsored by line',pg.evaluate("!document.querySelector('.hfoot').innerText.includes('ponsored')"));b.close()
    # co-sponsor card: wording, and the optional video
    b,pg,errs=mk(p,True,'Eagles Institute of Management',video=True)
    card=pg.evaluate("document.querySelector('#home-sponsor').innerText")
    check('card says co-sponsor, not sponsor',('OUR CO-SPONSOR' in card.upper()) and ('as the co-sponsor of Ehsaas' in card) and ('is sponsoring' not in card),card[:200])
    pg.evaluate("document.getElementById('home-sp-video').scrollIntoView({block:'center'})");pg.wait_for_timeout(1500)
    v=pg.evaluate("(()=>{const v=document.getElementById('home-sp-video');return v?{ctl:v.controls,pi:v.playsInline,auto:v.autoplay,w:v.getBoundingClientRect().width,rs:v.readyState,err:!!v.error,fig:!!document.getElementById('home-sp-vfig')}:null})()")
    check('video is in the card with controls, plays inline, does not autoplay, fits the screen and loaded',v and v['ctl'] and v['pi'] and not v['auto'] and 0<v['w']<=390 and v['rs']>=1 and not v['err'],v)
    pg.evaluate("document.getElementById('home-sp-video').play().catch(()=>{})");pg.wait_for_timeout(500)
    playing=pg.evaluate("!document.getElementById('home-sp-video').paused")
    pg.evaluate("window.scrollTo(0,0)");pg.wait_for_timeout(1500)
    check('video stops by itself when scrolled out of view',playing and pg.evaluate("document.getElementById('home-sp-video').paused"),playing)
    check('no script errors with the video',not errs,errs);b.close()
    b,pg,errs=mk(p,True,'Eagles Institute of Management',video=False)   # the file is not there yet
    pg.wait_for_timeout(800)
    check('video file missing: the video is left out, the rest of the card stays',pg.evaluate("!document.getElementById('home-sp-video')&&!document.getElementById('home-sp-vfig')&&document.querySelector('#home-sponsor h2')!==null"))
    check('no script errors without the video file',not errs,errs);b.close()
    b,pg,errs=mk(p,False,'Eagles Institute of Management')   # mouse still gets the ripple/lift
    pg.evaluate("document.getElementById('home-cal').scrollIntoView({block:'center'})");pg.wait_for_timeout(1000)
    bx=pg.locator('#home-cal').bounding_box();h0=bx['height'];pg.mouse.move(bx['x']+50,bx['y']+50);pg.mouse.down();pg.wait_for_timeout(150)
    n=pg.evaluate("document.querySelectorAll('#home-cal .fxr').length");h1=pg.evaluate("document.getElementById('home-cal').getBoundingClientRect().height");pg.mouse.up()
    check('mouse: the card keeps its height while the ripple plays',abs(h1-h0)<0.6,(h0,h1))
    check('mouse: ripple is kept',n==1,n);b.close()
print(sum(res),'of',len(res),'checks passed')
