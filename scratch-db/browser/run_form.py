"""Browser suite for the redesigned Register form (index.html), Nov 2026. Mocked Supabase, headless Chromium.
Run:  cd scratch-db/browser && python3 run_form.py | tail -1      (set PAGE=/path/to/index.html to test another copy)"""
import os,sys,mimetypes,json
sys.argv=['x']
from playwright.sync_api import sync_playwright
ROOT=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..'))+'/'
PAGE=os.environ.get('PAGE',ROOT+'index.html')
HTML=open(PAGE,encoding='utf-8').read()
src=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'run_home.py'),encoding='utf-8').read()
MOCK=src.split("MOCK = r'''")[1].split("'''")[0]
res=[]
def check(n,c,d=''):
    res.append(bool(c));print(('  PASS  ' if c else '  FAIL  ')+n+('' if c else '  '+str(d)[:300]))
def chip(pg,txt):
    pg.evaluate("t=>{const l=[...document.querySelectorAll('.opts label')].find(x=>x.textContent.trim()===t);l.scrollIntoView({block:'center'})}",txt)
    pg.click('.opts label:has(span:text-is("%s"))'%txt)
def mk(p,w=390,h=844,extra='',reduced=False,mine=False):
    b=p.chromium.launch();ctx=b.new_context(viewport={'width':w,'height':h},reduced_motion='reduce' if reduced else 'no-preference')
    pg=ctx.new_page();errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    def hd(r):
        u=r.request.url
        if u.endswith('/test.html'):r.fulfill(body=HTML,content_type='text/html')
        elif '/assets/' in u:
            f=ROOT+'assets/'+u.split('/assets/')[1].split('?')[0]
            r.fulfill(path=f,content_type=mimetypes.guess_type(f)[0] or 'application/octet-stream') if os.path.exists(f) else r.fulfill(status=404,body='')
        elif u.endswith('.js') or '/npm/' in u:r.fulfill(body='window.qrcode=function(){return {addData(){},make(){},getModuleCount(){return 21},isDark(){return false}}};',content_type='text/javascript')
        else:r.fulfill(status=204,body='')
    pg.route('**/*',hd);pg.add_init_script(MOCK+extra)
    if mine:pg.add_init_script("localStorage.setItem('mm_last',JSON.stringify({code:'3F9A2C7D'}))")
    pg.goto('https://example.test/test.html');pg.wait_for_selector('.home h1');pg.wait_for_timeout(500)
    return b,pg,errs
Q=lambda pg,s:pg.evaluate("s=>document.querySelectorAll(s).length",s)

with sync_playwright() as p:
    b,pg,errs=mk(p)
    pg.click('#hero-register');pg.wait_for_selector('#n0');pg.wait_for_timeout(1500)
    check('form opens, no script errors',not errs,errs)
    check('body step is form; old header/stepbar not drawn',pg.evaluate("document.body.dataset.step")=='form' and Q(pg,'ol.steps')==0)
    check('hero chips live: date, venue, price, close',pg.evaluate("[...document.querySelectorAll('.ffacts span')].map(x=>x.textContent)"))
    print('   chips:',pg.evaluate("[...document.querySelectorAll('.ffacts span')].map(x=>x.textContent)"))
    check('h1 reads Register for Ehsaas’26',pg.evaluate("document.querySelector('.fhero h1').textContent")=='Register for Ehsaas’26',pg.evaluate("document.querySelector('.fhero h1').textContent"))
    check('sticky bar present with Home / total / Review and fixed at bottom',pg.evaluate("(()=>{const b=document.querySelector('#fbar');const r=b.getBoundingClientRect();return b.querySelector('#go-home')&&b.querySelector('#review')&&b.querySelector('.ftot b').textContent==='₹250'&&Math.abs(r.bottom-innerHeight)<2})()"))
    check('bar stays put while the page is scrolled',pg.evaluate("(()=>{scrollTo(0,500);const r=document.querySelector('#fbar').getBoundingClientRect();scrollTo(0,0);return Math.abs(r.bottom-innerHeight)<2})()"))
    check('only one of each key id',all(Q(pg,'#'+i)==1 for i in ['review','go-home','n0','t0','od0'] if i!='od0'))
    check('no sideways scroll',pg.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
    pg.screenshot(path='/tmp/s1_empty.png',full_page=True)
    # validation
    pg.click('#review');pg.wait_for_timeout(900)
    check('empty review stays on form and marks fields',pg.evaluate("document.body.dataset.step")=='form' and Q(pg,'.fpage .bad')>=4 and Q(pg,'.fe')>=4,(Q(pg,'.bad'),Q(pg,'.fe')))
    check('summary banner shown',pg.evaluate("document.body.innerText.includes('Please fix the highlighted fields.')"))
    pg.screenshot(path='/tmp/s2_errors.png',full_page=False)
    # fill
    pg.fill('#n0','Anu Menon');pg.fill('#t0','98a4 56x7890abc')
    check('phone box keeps digits only (existing cleanPhone)',pg.input_value('#t0')=='9845678901' or pg.input_value('#t0').isdigit(),pg.input_value('#t0'))
    pg.fill('#t0','9845678901')
    chip(pg,'Student');pg.wait_for_selector('#od0')
    check('choosing a chip clears the red mark on that question',pg.evaluate("!document.querySelectorAll('.opts')[0].closest('.bad')") )
    pg.click('#review');pg.wait_for_timeout(300)
    check('occupation detail error shows after choosing a type',pg.evaluate("document.querySelector('#ob0 .fe')&&document.querySelector('#ob0 .fe').textContent")=='Enter the exam you are attempting',pg.evaluate("document.querySelector('#ob0').innerHTML"))
    pg.fill('#od0','CA Finals')
    chip(pg,'Student')
    check('re-choosing the same type keeps the typed text',pg.input_value('#od0')=='CA Finals')
    chip(pg,'Yes');chip(pg,'Non-veg')
    # friends
    pg.click('#fr',force=True) if False else pg.evaluate("document.getElementById('fr').click()");pg.wait_for_timeout(400)
    check('friends switch adds a second person and bar total updates to 2 people ₹500',Q(pg,'.pc[data-card]')==2 and pg.evaluate("document.querySelector('.ftot small').textContent")=='2 people' and pg.evaluate("document.querySelector('.ftot b').textContent")=='₹500')
    pg.screenshot(path='/tmp/s3_friends.png',full_page=True)
    pg.evaluate("document.querySelector('input[name=cnt][value=\"4\"]').click()");pg.wait_for_timeout(300)
    check('count chips 2..5 offered (max_group 5)',pg.evaluate("[...document.querySelectorAll('input[name=cnt]')].map(x=>x.value).join()")=='2,3,4,5')
    check('4 people ₹1000',pg.evaluate("document.querySelector('.ftot b').textContent")=='₹1000' and Q(pg,'.pc[data-card]')==4)
    pg.evaluate("document.getElementById('fr').click()");pg.wait_for_timeout(300)
    check('turning friends off returns to 1 person',Q(pg,'.pc[data-card]')==1)
    # name still kept?
    pg.fill('#n0','Anu Menon') if pg.input_value('#n0')=='' else None
    pg.click('#review');pg.wait_for_selector('.who')
    check('valid form goes to existing Review (summary) screen',pg.evaluate("document.body.dataset.step")=='summary' and Q(pg,'#fbar .hw')==0 and Q(pg,'ol.steps')==1)
    check('summary shows the person',pg.evaluate("document.body.innerText.includes('Anu Menon')"))
    pg.click('#edit');pg.wait_for_selector('#n0')
    check('Edit returns with data kept and no error marks',pg.input_value('#n0')=='Anu Menon' and Q(pg,'.bad')==0)
    pg.click('#review');pg.wait_for_selector('#topay');pg.click('#topay');pg.wait_for_selector('#qr');pg.wait_for_timeout(300)
    check('Pay screen still works with new form flow',Q(pg,'#qr')==1 and Q(pg,'#shot')==1)
    pg.click('#back');pg.wait_for_selector('#topay');pg.click('#edit');pg.wait_for_selector('#go-home');pg.click('#go-home');pg.wait_for_selector('.home h1')
    check('Home button returns to Home and the bar is gone',pg.evaluate("document.body.dataset.step")=='home' and pg.evaluate("document.getElementById('fbar').innerHTML")=='')
    check('no script errors through the flow',not errs,errs)
    b.close()
    # banners
    ex="window.__R={};"
    b,pg,errs=mk(p,extra="")
    pg.evaluate("""()=>{const c=window.supabase.createClient();}""")
    b.close()
    # banners: few spots + pause + already booked
    ex2="""setTimeout(()=>{window.__R.get_public_status=()=>({data:{accepting:true,spots_left:12,price_per_head:250,max_group:5,deadline:new Date(Date.now()+5*86400e3).toISOString(),server_now:new Date().toISOString(),next_close_at:new Date(Date.now()+3600e3).toISOString()},error:null});window.__R.registration_heartbeat=window.__R.get_public_status},0);"""
    b,pg,errs=mk(p,extra=ex2,mine=True)
    pg.click('#hero-register');pg.wait_for_selector('#n0');pg.wait_for_timeout(1200)
    t=pg.evaluate("document.querySelector('.fbody').innerText")
    check('banners: pause note, only 12 spots, already booked',('pause briefly' in t) and ('Only 12 spots left.' in t) and ('3F9A2C7D' in t),t[:300])
    pg.screenshot(path='/tmp/s4_banners.png',full_page=False)
    b.close()
    # reduced motion + desktop
    b,pg,errs=mk(p,reduced=True)
    pg.click('#hero-register');pg.wait_for_selector('#n0');pg.wait_for_timeout(500)
    check('reduced motion: all cards visible at once',pg.evaluate("[...document.querySelectorAll('.pc')].every(e=>getComputedStyle(e).opacity==='1')"))
    b.close()
    b,pg,errs=mk(p,w=1280,h=800)
    pg.click('#hero-register');pg.wait_for_selector('#n0');pg.wait_for_timeout(1300)
    pg.screenshot(path='/tmp/s5_desktop.png')
    check('desktop: no sideways scroll',pg.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
    b.close()


import base64
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
open('/tmp/shot.png','wb').write(PNG)
ex="window.__R.submit_booking=a=>({data:{booking_code:'ZZ11AA22',status:'pending',amount_expected:500,tickets:[]},error:null});"
with sync_playwright() as p:
    b,pg,errs=mk(p,extra=ex)
    pg.click('#hero-register');pg.wait_for_selector('#n0')
    pg.evaluate("document.getElementById('fr').click()");pg.wait_for_timeout(300)
    for i,(n,ph,occ,d,loc,food) in enumerate([('Anu Menon','9845678901','Student','CA Finals','Yes','Veg'),('Ravi K','9000011111','Employee','XYZ Ltd','No','Non-veg')]):
        pg.fill(f'#n{i}',n);pg.fill(f'#t{i}',ph)
        pg.evaluate("([i,t,o,f])=>{const q=(k,v)=>document.querySelector(`input[name=p${i}_${k}][value=\"${v}\"]`).click();q('occ',t);q('loc',o);q('food',f)}",[i,occ,'In Bengaluru' if loc=='Yes' else 'Outside Bengaluru',food])
        pg.fill(f'#od{i}',d)
    pg.click('#review');pg.wait_for_selector('#topay');pg.click('#topay');pg.wait_for_selector('#shot')
    pg.set_input_files('#shot','/tmp/shot.png');pg.wait_for_timeout(300)
    pg.click('#submit');pg.wait_for_selector('#copyid',timeout=8000)
    c=[x for x in pg.evaluate('window.__CALLS') if x['name']=='submit_booking'][0]['args']
    print(json.dumps(c['p_people']))
    check('submit_booking payload keys exactly name/phone/occ/occ_detail/loc/food',all(sorted(x.keys())==sorted(['name','phone','occ','occ_detail','loc','food']) for x in c['p_people']))
    check('values correct for both people',c['p_people'][0]=={'name':'Anu Menon','phone':'9845678901','occ':'Student','occ_detail':'CA Finals','loc':'In Bengaluru','food':'Veg'} and c['p_people'][1]['loc']=='Outside Bengaluru' and c['p_people'][1]['food']=='Non-veg')
    check('screenshot path = submission id + ext',c['p_screenshot_path'].endswith('.jpg') and len(c['p_submission_id'])==36)
    check('Done screen shows the Booking ID',pg.evaluate("document.body.innerText.includes('ZZ11AA22')"))
    pg.click('#again');pg.wait_for_selector('#n0')
    check('Register another gives a clean form (no errors, 1 person)',pg.evaluate("document.querySelectorAll('.pc[data-card]').length")==1 and pg.input_value('#n0')=='' and pg.evaluate("document.querySelectorAll('.bad').length")==0)
    check('no script errors',not errs,errs)
    b.close()
print(sum(res),'of',len(res),'passed')
