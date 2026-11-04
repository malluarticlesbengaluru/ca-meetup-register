import json
from playwright.sync_api import sync_playwright
HTML = open('/home/claude/ca-meetup-register/index.html', encoding='utf-8').read()
res=[]
def check(n,c,d=''): res.append(bool(c)); print(('  PASS  ' if c else '  FAIL  ')+n+('' if c else '  '+str(d)[:300]))
MOCK = r'''
(function(){
 const calls = window.__CALLS = [], R = window.__R = {};
 const ok = d => ({data:d,error:null});
 const rpcs = {
  get_event_info:()=>ok({event_at:'2026-11-22T08:30:00Z',venue:'Savoury Business Hotel, Madiwala'}),
  get_payment_info:()=>ok({upi_id:'org@upi',payee_name:'Org',whatsapp:'919999999999'}),
  get_public_status:()=>ok({accepting:true,spots_left:100,price_per_head:250,max_group:5,deadline:'2026-10-31T18:29:59Z',server_now:new Date().toISOString(),closed_reason:null}),
  registration_heartbeat:()=>ok({accepting:true,spots_left:100,price_per_head:250,max_group:5,deadline:'2026-10-31T18:29:59Z',server_now:new Date().toISOString()}),
  submit_booking:()=>ok({booking_code:'AB12CD34',status:'pending',amount_expected:250,tickets:[{name:'Zed',food:'Veg'}]}),
 };
 const client = {
  auth:{},
  rpc: async (name,args)=>{ calls.push({name,args}); const h = R[name] || rpcs[name];
     if(!h) return {data:null,error:{message:'function '+name+' does not exist'}};
     if(typeof h==='function'){ try{ return h(args) }catch(e){ return {data:null,error:{message:String(e)}} } } return ok(h) },
  storage:{from:()=>({upload: async (path)=>{calls.push({name:'UPLOAD',args:{path}});return {data:{},error:null}}})}
 };
 window.supabase = {createClient:()=>client};
 window.__ok = ok;
})();
'''
def page(p, rpc_js='', w=420):
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':w,'height':900}); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e)))
    def handler(r):
        u = r.request.url
        if u.endswith('/test.html'): r.fulfill(body=HTML, content_type='text/html')
        elif 'home-fx.js' in u or 'page-fx.js' in u:   # the REAL motion scripts run in these tests too (entrance, ripple), as on the live page
            r.fulfill(path='/home/claude/ca-meetup-register/assets/' + u.split('/assets/')[1].split('?')[0], content_type='text/javascript')
        elif u.endswith('.js') or '/npm/' in u: r.fulfill(body='window.qrcode=function(){return {addData(){},make(){},getModuleCount(){return 21},isDark(){return false}}};', content_type='text/javascript')
        else: r.fulfill(status=204, body='')
    pg.route('**/*', handler)
    pg.add_init_script(MOCK)
    if rpc_js: pg.add_init_script("document.addEventListener('DOMContentLoaded',()=>{});"+rpc_js)
    pg.goto('https://example.test/test.html'); pg.wait_for_selector('#app h1'); return b,pg,errs
calls=lambda pg:pg.evaluate('window.__CALLS')
def last(pg,name): 
    c=[x for x in calls(pg) if x['name']==name]; return c[-1] if c else None
LOOK = {
 'paid': {'found':True,'kind':'registration','booking_code':'AB12CD34','status':'paid','people_count':2,'amount_expected':500,'tickets':[
    {'name':'Asha','food':'Veg','label':'E26-001','secret':'a'*12,'transferred':True,'kind':'guest','ticket_no':1,'coord_no':None,'location':'x','attendance':'y'},
    {'name':'Ben','food':'Non-veg','label':'E26-002','secret':'b'*12,'transferred':False,'kind':'guest','ticket_no':2,'coord_no':None,'location':'x','attendance':'y'}]},
}
# ---- Browser checks for the "fixed switches" change (Nov 2026): email is never asked, About link is always on, Feedback is always on.
# (The older run_public.py is out of date with the live registration form and is not used for this.)
# Run: cd scratch-db/browser && python3 run_public_fixed.py | tail -1
OLDFLAGS = "window.__R.get_site_flags={show_about:false,ask_email:true,ask_feedback:false};"
with sync_playwright() as p:
    for label, flags in [('flags all the old way round', OLDFLAGS), ('flags missing (old database)', "window.__R.get_site_flags=()=>({data:null,error:{message:'nope'}});")]:
        b,pg,errs=page(p,flags); pg.wait_for_timeout(300)
        check(f'About link is shown ({label})', pg.query_selector('#go-about') is not None)
        pg.click('#go-register'); pg.wait_for_selector('#n0')
        check(f'registration form has no email box ({label})', pg.query_selector('#e0') is None and 'mail' not in pg.inner_text('#app').lower())
        b.close()
    BUY = (OLDFLAGS+"window.__R.get_transfer_info={open:true,cutoff_passed:false,food_locked:false};"
           "window.__R.transfer_open=a=>({data:{ok:true,mode:'private',seller_name:'Ben',expires_at:'2030-01-01T00:00:00Z',food_locked:false,food:null},error:null});"
           "window.__R.transfer_submit=a=>({data:{ok:true,mode:'private',booking_code:'C6157147',status:'pending'},error:null});")
    b,pg,errs=page(p,BUY); pg.wait_for_timeout(300); pg.click('#go-tickets'); pg.wait_for_selector('#go-xmenu'); pg.click('#go-xmenu'); pg.click('[data-xgo="private-buy"]'); pg.wait_for_selector('#xb_c')
    pg.fill('#xb_c','67Y659'); pg.click('#xopen'); pg.wait_for_selector('#xf_n')
    check('transfer buyer form has no email box or email note', pg.query_selector('#xf_e') is None and 'mail' not in pg.inner_text('#app').lower(), pg.inner_text('#app')[:300])
    pg.fill('#xf_n','Dan Buyer'); pg.fill('#xf_p','9000000004'); pg.click('input[name="x_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="x_att"][value="Surely"]',force=True); pg.click('input[name="x_food"][value="Veg"]',force=True); pg.check('#xf_ok'); pg.click('#xsubmit'); pg.wait_for_selector('#copyxid')
    ts=last(pg,'transfer_submit'); check('the transfer is sent with an empty email and no page errors', ts and ts['args']['p_buyer']['email']=='' and not errs, (ts,errs)); b.close()
    b,pg,errs=page(p,OLDFLAGS+"window.__R.submit_feedback=a=>({data:{ok:true},error:null});"); pg.wait_for_timeout(300); pg.click('#go-register'); pg.wait_for_selector('#n0')
    pg.fill('#n0','Zed'); pg.fill('#t0','9876543210'); pg.click('input[name="p0_occ"]',force=True); pg.fill('#od0','ABC & Co.'); pg.click('input[name="p0_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="p0_food"][value="Veg"]',force=True)
    pg.click('#review'); pg.click('#topay'); pg.wait_for_selector('#shot',state='attached')
    pg.set_input_files('#shot',{'name':'s.png','mimeType':'image/png','buffer':bytes.fromhex('89504e470d0a1a0a')+b'x'*50}); pg.evaluate("window.compress=async f=>new Blob(['x'],{type:'image/jpeg'})")
    pg.click('#submit'); pg.wait_for_selector('#fb_c', timeout=5000)
    check('the feedback box is on the done page even though the old flag says off', pg.query_selector('#fbsend') is not None and not errs, errs); b.close()
print(f"{sum(res)} passed, {len(res)-sum(res)} failed")
