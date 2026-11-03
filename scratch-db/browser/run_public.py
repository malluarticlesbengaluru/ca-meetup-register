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
with sync_playwright() as p:
    # ===== 1. registration form: +91 prefix, email, payload
    b,pg,errs=page(p); pg.click('#go-register'); pg.wait_for_selector('#n0')
    check('form has a fixed +91 box next to the phone field', pg.inner_text('.pf span')=='+91' and pg.query_selector('#t0').get_attribute('class')=='ph')
    check('form order: Email comes right after Phone number', pg.evaluate("(()=>{const ids=[...document.querySelectorAll('#app input[type=text],#app input[type=tel]')].map(e=>e.id);return ids.indexOf('t0')+1===ids.indexOf('e0')})()"))
    check('form has an email field with the reason line', pg.query_selector('#e0') is not None and 'Only the organisers can see this' in pg.inner_text('#app'))
    pg.fill('#n0','Zed'); pg.fill('#t0','+91 98765-43210abc'); check('a pasted "+91 98765-43210abc" becomes exactly the 10 digits 9876543210', pg.input_value('#t0')=='9876543210', pg.input_value('#t0'))
    pg.fill('#t0','09876543210'); check('a pasted 0-prefixed number loses the 0', pg.input_value('#t0')=='9876543210', pg.input_value('#t0'))
    pg.fill('#t0','98765432109999'); check('extra digits are cut to 10', pg.input_value('#t0')=='9876543210', pg.input_value('#t0'))
    pg.fill('#t0','9876543210'); pg.click('input[name="p0_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="p0_att"][value="Surely"]',force=True); pg.click('input[name="p0_food"][value="Veg"]',force=True)
    pg.click('#review'); check('missing email blocks Review', 'Enter a valid email address' in pg.inner_text('#app'), pg.inner_text('#app')[:200])
    pg.fill('#e0','not-an-email'); pg.click('#review'); check('bad email blocks Review', 'valid email' in pg.inner_text('#app'))
    pg.fill('#e0','  Zed@Example.COM '); pg.click('#review'); check('good email reaches the summary, shown with +91 phone', 'Check your details' in pg.inner_text('#app') and '+91 9876543210' in pg.inner_text('#app') and 'Zed@Example.COM' in pg.inner_text('#app'), pg.inner_text('#app')[:300])
    pg.click('#topay'); pg.wait_for_selector('#shot',state='attached')
    pg.set_input_files('#shot',{'name':'s.png','mimeType':'image/png','buffer':bytes.fromhex('89504e470d0a1a0a')+b'x'*50})
    pg.evaluate("window.compress=async f=>new Blob(['x'],{type:'image/jpeg'})")
    pg.click('#submit'); pg.wait_for_timeout(400)
    sb=last(pg,'submit_booking'); check('submit_booking sends email (trimmed, lower-case) and 10-digit phone', sb and sb['args']['p_people'][0]['email']=='zed@example.com' and sb['args']['p_people'][0]['phone']=='9876543210', sb)
    check('done page asks for Booking ID + phone to get tickets', 'enter your Booking ID and phone number' in pg.inner_text('#app'))
    check('no page errors in registration', not errs, errs); 
    # ===== 2. tickets from the done page: Booking ID prefilled, phone EMPTY
    pg.click('#go-tickets'); pg.wait_for_selector('#bq')
    check('Tickets: Booking ID prefilled after registration, phone empty', pg.input_value('#bq')=='AB12CD34' and pg.input_value('#tkph')=='')
    b.close()
    # ===== 3. Tickets page: history chips only fill, never fetch; lookup needs the phone
    b,pg,errs=page(p); pg.evaluate("localStorage.setItem('mm_mine',JSON.stringify(['AB12CD34','11112222']))"); pg.click('#go-tickets'); pg.wait_for_selector('#bq'); pg.wait_for_timeout(300)
    check('opening Tickets does NOT fetch any booking automatically', not [x for x in calls(pg) if x['name'] in('lookup_tickets','lookup_booking')], calls(pg))
    check('saved Booking IDs are shown as chips', pg.query_selector_all('.chip').__len__()==2)
    pg.click('.chip >> nth=0'); check('tapping a chip fills the Booking ID but not the phone', pg.input_value('#bq')=='AB12CD34' and pg.input_value('#tkph')=='' )
    check('still no lookup after the chip tap', not [x for x in calls(pg) if x['name']=='lookup_tickets'])
    pg.click('#tsearch'); pg.wait_for_timeout(200)
    check('Check with no phone gives the generic message and makes NO server call', "We couldn't find a booking with these details" in pg.inner_text('#app') and not last(pg,'lookup_tickets'))
    pg.fill('#tkph','9876543210'); pg.fill('#bq','AB12CD34'); pg.click('#tsearch'); pg.wait_for_timeout(200)
    check('the phone number is never written to localStorage', pg.evaluate("Object.values(localStorage).every(v=>!/[0-9]{10}/.test(v))") and pg.evaluate("Object.values(sessionStorage).every(v=>!/[0-9]{10}/.test(v))"), pg.evaluate("JSON.stringify(localStorage)"))
    b.close()
    # ===== 4. found / not found
    b,pg,errs=page(p); pg.evaluate("window.__R.lookup_tickets=a=>({data:a.p_phone==='9000000002'?"+json.dumps(LOOK['paid'])+":{found:false},error:null});window.__R.get_transfer_info={open:true,cutoff_passed:false,food_locked:False,code_hours:2,ask_price:250};".replace('False','false')); pg.click('#go-tickets'); pg.wait_for_selector('#bq')
    pg.fill('#bq','ab12-cd34'); pg.fill('#tkph','9111111111'); pg.click('#tsearch'); pg.wait_for_timeout(300)
    check('wrong phone: one generic message (never says which part was wrong)', "We couldn't find a booking with these details" in pg.inner_text('#app') and 'wrong' not in pg.inner_text('#app').lower().split("couldn't find a booking")[1][:200])
    lk=last(pg,'lookup_tickets'); check('lookup sends the normalised ID and the 10 digits', lk['args']=={'p_code':'AB12CD34','p_phone':'9111111111'}, lk)
    pg.fill('#tkph','9000000002'); pg.click('#tsearch'); pg.wait_for_timeout(300); t=pg.inner_text('#app')
    check('right phone: booking shows Confirmed and both people', 'Confirmed' in t and 'Asha' in t and 'Ben' in t)
    check('retired ticket shown as Transferred (and has no QR in the view)', 'Transferred' in t)
    check('Transfer a ticket button appears when transfers are open', pg.query_selector('[data-xstart]') is not None)
    pg.click('[data-view]'); pg.wait_for_selector('canvas.tk',state='attached'); check('View Ticket draws only the live ticket (1 canvas)', len(pg.query_selector_all('canvas.tk'))==1)
    pg.click('#back-tickets'); pg.wait_for_selector('#tkph'); check('Back to Tickets keeps the result', 'Ben' in pg.inner_text('#app'))
    check('no page errors in tickets', not errs, errs); b.close()
    # ===== 5. transfers closed => no entry points
    b,pg,errs=page(p); pg.evaluate("window.__R.get_transfer_info={open:false,cutoff_passed:false};window.__R.lookup_tickets=()=>({data:"+json.dumps(LOOK['paid'])+",error:null})"); pg.click('#go-tickets'); pg.wait_for_selector('#bq'); pg.wait_for_timeout(300)
    check('transfers OFF: no Transfer tickets button on Tickets', 'Transfer tickets' not in pg.inner_text('#app'))
    pg.fill('#bq','AB12CD34'); pg.fill('#tkph','9000000002'); pg.click('#tsearch'); pg.wait_for_timeout(300)
    check('transfers OFF: no Transfer a ticket button on the booking', pg.query_selector('[data-xstart]') is None)
    b.close()
    # ===== 6. seller flow (private)
    SELL = "window.__R.get_transfer_info={open:true,cutoff_passed:false,food_locked:false};window.__R.private_sell=a=>({data:a.p_phone==='9000000002'&&a.p_ticket.toUpperCase()==='E26-002'?{ok:true,code:'67Y659',hours:2,expires_at:new Date(Date.now()+7200000).toISOString(),ticket_label:'E26-002'}:{ok:false,error:'MISMATCH'},error:null});window.__R.public_sell=a=>({data:{ok:true,mode:'public',code:'H96NNF',hours:2,expires_at:new Date(Date.now()+7200000).toISOString(),ticket_label:'E26-002'},error:null});"
    b,pg,errs=page(p,SELL); pg.click('#go-tickets'); pg.wait_for_selector('#go-xmenu'); pg.click('#go-xmenu'); pg.wait_for_selector('[data-xgo="private-sell"]')
    check('menu offers Private sell, Public sell and ONE buy button (the code decides the mode)', all(pg.query_selector(f'[data-xgo="{k}"]') for k in ['private-sell','private-buy','public-sell']) and not pg.query_selector('[data-xgo="public-buy"]') and len(pg.query_selector_all('[data-xgo$="-buy"]'))==1)
    pg.click('[data-xgo="private-sell"]'); pg.wait_for_selector('#xs_c')
    pg.fill('#xs_c','AB12CD34'); pg.fill('#xs_t','E26-009'); pg.fill('#xs_p','9000000002'); pg.click('#xsell'); pg.wait_for_timeout(300)
    check('wrong details: the exact mismatch sentence, nothing else revealed', "The details don't match" in pg.inner_text('#app'), pg.inner_text('#app')[:300])
    check('form keeps what was typed', pg.input_value('#xs_c')=='AB12CD34')
    pg.fill('#xs_t','e26-002'); pg.click('#xsell'); pg.wait_for_selector('#copycode'); t=pg.inner_text('#app')
    check('right details: the code and its expiry are shown', '67Y659' in t and 'Valid until' in t)
    check('private text tells the seller to give the code to the buyer', 'Give this code to the person taking your seat' in t)
    ps=last(pg,'private_sell'); check('private_sell got the 10-digit phone and ID', ps['args']['p_phone']=='9000000002' and ps['args']['p_booking_code']=='AB12CD34', ps)
    pg.click('#go-tickets'); b.close()
    # public sell needs UPI
    b,pg,errs=page(p,SELL); pg.click('#go-tickets'); pg.wait_for_selector('#go-xmenu'); pg.click('#go-xmenu'); pg.click('[data-xgo="public-sell"]'); pg.wait_for_selector('#xs_u')
    check('seller form hints that coordinators type their E26-001C style number', 'E26-001C' in (pg.get_attribute('#xs_t','placeholder') or ''))
    pg.fill('#xs_c','AB12CD34'); pg.fill('#xs_t','E26-002'); pg.fill('#xs_p','9000000002'); pg.click('#xsell'); pg.wait_for_timeout(200)
    check('public sell without a payout UPI is stopped before any server call', 'fill in all the fields' in pg.inner_text('#app') and not last(pg,'public_sell'))
    pg.fill('#xs_u','asha@okbank'); pg.click('#xsell'); pg.wait_for_selector('#copycode'); ps=last(pg,'public_sell')
    check('public_sell sends the payout UPI', ps['args'].get('p_upi')=='asha@okbank', ps); check('public text tells the seller the organisers find a buyer', 'find a buyer' in pg.inner_text('#app')); check('wording: organisers MAY call (never "will call")', 'may call your registered number' in pg.inner_text('#app') and 'will call' not in pg.inner_text('#app')); b.close()
    # ===== 7. buyer flow
    BUY = ("window.__R.get_transfer_info={open:true,cutoff_passed:false,food_locked:false};"
           "window.__R.transfer_open=a=>({data:a.p_code==='67Y659'?{ok:true,mode:'private',seller_name:'Ben',expires_at:'2030-01-01T00:00:00Z',food_locked:window.__LOCK||false,food:window.__LOCK?'Non-veg':null}:{ok:false,error:'INVALID_CODE'},error:null});"
           "window.__R.transfer_submit=a=>({data:{ok:true,mode:'private',booking_code:'C6157147',status:'pending'},error:null});")
    b,pg,errs=page(p,BUY); pg.click('#go-tickets'); pg.wait_for_selector('#go-xmenu'); pg.click('#go-xmenu'); pg.click('[data-xgo="private-buy"]'); pg.wait_for_selector('#xb_c')
    pg.fill('#xb_c','zzzzzz'); pg.click('#xopen'); pg.wait_for_timeout(300); check('wrong code: plain "not valid" message', "This code isn't valid" in pg.inner_text('#app'), pg.inner_text('#app')[:200])
    pg.fill('#xb_c','67y 659'); pg.click('#xopen'); pg.wait_for_selector('#xf_n'); t=pg.inner_text('#app')
    check('right code (typed with a space, lower-case): form opens with the seller NAME only', 'taking over Ben' in t and 'Transfer details' in t)
    check('private form text: money is between the two people', 'payment between me and the seller is our own arrangement' in t)
    check('buyer form has +91, email, location, attendance, food and a consent tick', all(pg.query_selector(x) for x in ['.pf span','#xf_e','#xf_ok','input[name="x_loc"]','input[name="x_att"]','input[name="x_food"]']))
    pg.click('#xsubmit'); pg.wait_for_timeout(200); check('empty form: lists what is missing, no server call', 'enter your name' in pg.inner_text('#app') and not last(pg,'transfer_submit'))
    pg.fill('#xf_n','Dan Buyer'); pg.fill('#xf_p','9000000004'); pg.fill('#xf_e','Dan@Example.com'); pg.click('input[name="x_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="x_att"][value="Surely"]',force=True); pg.click('input[name="x_food"][value="Veg"]',force=True)
    pg.click('#xsubmit'); pg.wait_for_timeout(200); check('consent tick is required', 'tick the box' in pg.inner_text('#app') and not last(pg,'transfer_submit'))
    pg.check('#xf_ok'); pg.click('#xsubmit'); pg.wait_for_selector('#copyxid'); t=pg.inner_text('#app'); ts=last(pg,'transfer_submit')
    check('submit sends code, a submission id and the clean buyer details', ts['args']['p_code']=='67Y659' and len(ts['args']['p_submission_id'])==36 and ts['args']['p_buyer']['email']=='Dan@Example.com'.strip() and ts['args']['p_buyer']['phone']=='9000000004' and ts['args']['p_buyer']['consent']=='true', ts)
    check('done: new Booking ID, pending, the exact organisers message, no ticket yet', 'C6157147' in t and 'The organisers have been notified of your request and will take the next steps shortly.' in t and "You won't have a ticket or a seat until the transfer is complete" in t)
    check('done: Contact the organisers button present', 'Contact the organisers' in t)
    check('booking ID saved to this device for the chips', 'C6157147' in pg.evaluate("localStorage.getItem('mm_mine')"))
    check('no page errors in buyer flow', not errs, errs); b.close()
    # food lock
    b,pg,errs=page(p,BUY+"window.__LOCK=true;"); pg.click('#go-tickets'); pg.wait_for_selector('#go-xmenu'); pg.click('#go-xmenu'); pg.click('[data-xgo="private-buy"]'); pg.fill('#xb_c','67Y659'); pg.click('#xopen'); pg.wait_for_selector('#xf_n')
    check('food locked: no food choice, the seller food is stated', pg.query_selector('input[name="x_food"]') is None and 'Non-veg' in pg.inner_text('#app'))
    pg.fill('#xf_n','Dan'); pg.fill('#xf_p','9000000004'); pg.fill('#xf_e','d@e.com'); pg.click('input[name="x_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="x_att"][value="Surely"]',force=True); pg.check('#xf_ok'); pg.click('#xsubmit'); pg.wait_for_selector('#copyxid')
    check('food locked: page sends no food of its own', last(pg,'transfer_submit')['args']['p_buyer']['food']=='', last(pg,'transfer_submit')); b.close()
    # retry of the same form reuses the same submission id; a different code gets a new one
    b,pg,errs=page(p,BUY+"window.__N=0;window.__R.transfer_submit=a=>(++window.__N===1?{data:null,error:{message:'Failed to fetch'}}:{data:{ok:true,mode:'private',booking_code:'C6157147',status:'pending'},error:null});"); pg.click('#go-tickets'); pg.wait_for_selector('#go-xmenu'); pg.click('#go-xmenu'); pg.click('[data-xgo="private-buy"]'); pg.fill('#xb_c','67Y659'); pg.click('#xopen'); pg.wait_for_selector('#xf_n')
    pg.fill('#xf_n','Dan'); pg.fill('#xf_p','9000000004'); pg.fill('#xf_e','d@e.com'); pg.click('input[name="x_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="x_att"][value="Surely"]',force=True); pg.click('input[name="x_food"][value="Veg"]',force=True); pg.check('#xf_ok')
    pg.click('#xsubmit'); pg.wait_for_timeout(300); check('network failure: a friendly message, the form is kept', "We couldn't reach the server" in pg.inner_text('#app') and pg.input_value('#xf_n')=='Dan')
    pg.click('#xsubmit'); pg.wait_for_selector('#copyxid'); sids=[c['args']['p_submission_id'] for c in calls(pg) if c['name']=='transfer_submit']
    check('the retry reuses the SAME submission id (no duplicate request)', len(sids)==2 and sids[0]==sids[1], sids); b.close()
    # ===== 8. buyer pays (public) from the Tickets page
    PAY = ("window.__R.get_transfer_info={open:true,cutoff_passed:false};window.__R.lookup_tickets=()=>({data:{found:true,kind:'transfer',booking_code:'C6157147',status:'pending',people_count:1,amount_expected:0,name:'Eve',tickets:[],transfer:{type:'public',state:window.__ST||'payment_due',amount_due:250}},error:null});"
           "window.__R.transfer_pay=a=>({data:{ok:true,amount_due:250},error:null});")
    b,pg,errs=page(p,PAY); pg.click('#go-tickets'); pg.wait_for_selector('#bq'); pg.fill('#bq','C6157147'); pg.fill('#tkph','9000000009'); pg.click('#tsearch'); pg.wait_for_selector('[data-tpay]')
    check('payment_due: shows the amount and a Pay button', 'Payment needed' in pg.inner_text('#app') and 'Pay ₹250' in pg.inner_text('#app'))
    pg.click('[data-tpay]'); pg.wait_for_selector('#tshot',state='attached'); check('pay screen shows ₹250, the UPI ID and a screenshot box', '₹250' in pg.inner_text('#app') and 'org@upi' in pg.inner_text('#app'))
    pg.click('#tp-submit'); pg.wait_for_timeout(200); check('submitting with no screenshot is stopped', 'Upload your payment screenshot' in pg.inner_text('#app') and not last(pg,'transfer_pay'))
    pg.evaluate("window.compress=async f=>new Blob(['x'],{type:'image/jpeg'})"); pg.set_input_files('#tshot',{'name':'s.png','mimeType':'image/png','buffer':b'x'*60}); pg.wait_for_timeout(100)
    pg.evaluate("window.__ST='payment_submitted'"); pg.click('#tp-submit'); pg.wait_for_timeout(500); tp=last(pg,'transfer_pay'); up=[c for c in calls(pg) if c['name']=='UPLOAD']
    check('upload goes to <submission id>.jpg and transfer_pay gets the same path', up and tp and tp['args']['p_screenshot_path']==up[-1]['args']['path'] and tp['args']['p_screenshot_path'].startswith(tp['args']['p_submission_id']), (up,tp))
    check('after paying, the Tickets page re-checks and shows the new state', 'Payment submitted' in pg.inner_text('#app'), pg.inner_text('#app')[:300])
    check('no page errors in payment flow', not errs, errs); b.close()
    # every transfer-booking state reads correctly
    for st,txt in [('pending','Pending verification'),('payment_verified','Payment verified'),('rejected','Not approved'),('return_due','refund due'),('returned','Payment returned')]:
        b,pg,errs=page(p,PAY+f"window.__ST='{st}';"); pg.click('#go-tickets'); pg.wait_for_selector('#bq'); pg.fill('#bq','C6157147'); pg.fill('#tkph','9000000009'); pg.click('#tsearch'); pg.wait_for_timeout(300)
        check(f'buyer state {st}: shows "{txt}" and no Pay button', txt in pg.inner_text('#app') and pg.query_selector('[data-tpay]') is None, pg.inner_text('#app')[:200]); b.close()
    # approved transfer: buyer sees the ticket
    DONE = "window.__R.get_transfer_info={open:true};window.__R.lookup_tickets=()=>({data:{found:true,kind:'transfer',booking_code:'C6157147',status:'paid',people_count:1,amount_expected:0,tickets:[{name:'Dan',food:'Veg',label:'E26-004',secret:'c'.repeat(12),transferred:false,kind:'guest'}]},error:null});"
    b,pg,errs=page(p,DONE); pg.click('#go-tickets'); pg.wait_for_selector('#bq'); pg.fill('#bq','C6157147'); pg.fill('#tkph','9000000004'); pg.click('#tsearch'); pg.wait_for_selector('[data-view]')
    check('completed transfer: buyer sees Confirmed with a View Ticket button', 'Your transfer is complete' in pg.inner_text('#app')); pg.click('[data-view]'); pg.wait_for_selector('canvas.tk',state='attached'); check('ticket canvas drawn for the buyer', len(pg.query_selector_all('canvas.tk'))==1); b.close()
    # ===== 9. seller sees and can cancel their code; mobile width has no sideways scroll
    ST = ("window.__R.get_transfer_info={open:true};window.__R.lookup_tickets=()=>({data:"+json.dumps(LOOK['paid'])+",error:null});window.__R.transfer_status=()=>({data:{found:true,transfers:[{ticket_label:'E26-002',mode:'private',status:'code_active',code:'67Y659',expires_at:new Date(Date.now()+3600000).toISOString(),buyer_name:null}]},error:null});window.__R.transfer_cancel=a=>({data:{ok:true},error:null});")
    b,pg,errs=page(p,ST); pg.click('#go-tickets'); pg.wait_for_selector('#bq'); pg.fill('#bq','AB12CD34'); pg.fill('#tkph','9000000002'); pg.click('#tsearch'); pg.wait_for_selector('[data-xcancel]'); t=pg.inner_text('#app')
    check('seller sees the active code on the Tickets page', '67Y659' in t and 'Code active' in t)
    pg.once('dialog',lambda d:d.accept()); pg.click('[data-xcancel]'); pg.wait_for_timeout(300); tc=last(pg,'transfer_cancel')
    check('cancel sends Booking ID, ticket label and phone', tc and tc['args']=={'p_booking_code':'AB12CD34','p_ticket':'E26-002','p_phone':'9000000002'}, tc)
    for step in ['tickets']:
        sw=pg.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'); check('no sideways scrolling at phone width (Tickets)', sw)
    b.close()
    # ===== About link (admin switch)
    b,pg,errs=page(p); pg.wait_for_timeout(300)
    check('About: no link when the database does not know the switch yet', pg.query_selector('#go-about') is None); b.close()
    b,pg,errs=page(p,"window.__R.get_site_flags={show_about:false};"); pg.wait_for_timeout(300)
    check('About: switched OFF in Admin, no link on the home page', pg.query_selector('#go-about') is None); b.close()
    b,pg,errs=page(p,"window.__R.get_site_flags={show_about:true};"); pg.wait_for_selector('#go-about')
    check('About: switched ON, the link shows the organiser name', 'About Mallu Articles Bengaluru' in pg.inner_text('#go-about'))
    pg.click('#go-about'); pg.wait_for_selector('#go-home'); ta=pg.inner_text('#app')
    check('About: opens a page that says Coming soon', 'Coming soon' in ta and not errs, (ta, errs))
    check('About: sideways scroll never happens at phone width', pg.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'))
    pg.click('#go-home'); pg.wait_for_selector('#go-register'); check('About: Home button goes back to the home page', pg.query_selector('#go-about') is not None); b.close()
    # ===== Email switch OFF
    b,pg,errs=page(p,"window.__R.get_site_flags={show_about:true,ask_email:false};"); pg.wait_for_timeout(300); pg.click('#go-register'); pg.wait_for_selector('#n0')
    check('email OFF: the registration form has no Email box or email note', pg.query_selector('#e0') is None and 'Only the organisers can see it' not in pg.inner_text('#app'))
    pg.fill('#n0','Zed'); pg.fill('#t0','9876543210'); pg.click('input[name="p0_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="p0_att"][value="Surely"]',force=True); pg.click('input[name="p0_food"][value="Veg"]',force=True)
    pg.click('#review'); check('email OFF: Review works without any email', 'Check your details' in pg.inner_text('#app') and 'valid email' not in pg.inner_text('#app'), pg.inner_text('#app')[:200])
    pg.click('#topay'); pg.wait_for_selector('#shot',state='attached')
    pg.set_input_files('#shot',{'name':'s.png','mimeType':'image/png','buffer':bytes.fromhex('89504e470d0a1a0a')+b'x'*50})
    pg.evaluate("window.compress=async f=>new Blob(['x'],{type:'image/jpeg'})")
    pg.click('#submit'); pg.wait_for_timeout(400); sb=last(pg,'submit_booking')
    check('email OFF: submit_booking sends an empty email', sb and sb['args']['p_people'][0]['email']=='' and not errs, (sb, errs)); b.close()
    BUY2 = ("window.__R.get_site_flags={show_about:true,ask_email:false};window.__R.get_transfer_info={open:true,cutoff_passed:false,food_locked:false};"
            "window.__R.transfer_open=a=>({data:{ok:true,mode:'private',seller_name:'Ben',expires_at:'2030-01-01T00:00:00Z',food_locked:false,food:null},error:null});"
            "window.__R.transfer_submit=a=>({data:{ok:true,mode:'private',booking_code:'C6157147',status:'pending'},error:null});")
    b,pg,errs=page(p,BUY2); pg.wait_for_timeout(300); pg.click('#go-tickets'); pg.wait_for_selector('#go-xmenu'); pg.click('#go-xmenu'); pg.click('[data-xgo="private-buy"]'); pg.wait_for_selector('#xb_c')
    pg.fill('#xb_c','67Y659'); pg.click('#xopen'); pg.wait_for_selector('#xf_n')
    check('email OFF: the buyer form has no Email box or email note', pg.query_selector('#xf_e') is None and 'Only the organisers can see your email' not in pg.inner_text('#app'))
    pg.fill('#xf_n','Dan'); pg.fill('#xf_p','9000000004'); pg.click('input[name="x_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="x_att"][value="Surely"]',force=True); pg.click('input[name="x_food"][value="Veg"]',force=True); pg.check('#xf_ok'); pg.click('#xsubmit'); pg.wait_for_selector('#copyxid')
    ts=last(pg,'transfer_submit'); check('email OFF: the transfer is sent with an empty email', ts and ts['args']['p_buyer']['email']=='' and not errs, (ts, errs)); b.close()
    b,pg,errs=page(p,"window.__R.get_site_flags={show_about:true,ask_email:true};"); pg.wait_for_timeout(300); pg.click('#go-register'); pg.wait_for_selector('#n0')
    check('email ON (flag true): the Email box is shown', pg.query_selector('#e0') is not None); b.close()
    # ===== Feedback on the Booking ID page
    def done_page(flags):
        b,pg,errs=page(p,"window.__R.get_site_flags="+flags+";"+"window.__R.submit_feedback=a=>({data:{ok:true},error:null});"); pg.wait_for_timeout(300); pg.click('#go-register'); pg.wait_for_selector('#n0')
        pg.fill('#n0','Zed'); pg.fill('#t0','9876543210'); pg.fill('#e0','z@e.com') if pg.query_selector('#e0') else None
        pg.click('input[name="p0_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="p0_att"][value="Surely"]',force=True); pg.click('input[name="p0_food"][value="Veg"]',force=True)
        pg.click('#review'); pg.click('#topay'); pg.wait_for_selector('#shot',state='attached')
        pg.set_input_files('#shot',{'name':'s.png','mimeType':'image/png','buffer':bytes.fromhex('89504e470d0a1a0a')+b'x'*50})
        pg.evaluate("window.compress=async f=>new Blob(['x'],{type:'image/jpeg'})")
        pg.click('#submit'); pg.wait_for_selector('#copyid'); return b,pg,errs
    b,pg,errs=done_page("{show_about:true,ask_email:true,ask_feedback:true}"); t=pg.inner_text('#app')
    check('feedback ON: Booking ID page shows both questions', 'How excited are you for' in t and 'Please share a few words about the program' in t and len(pg.query_selector_all('input[name="fb_r"]'))==5, t[:400])
    pg.click('#fbsend'); pg.wait_for_timeout(100); check('feedback: sending nothing is stopped with a message, no server call', 'Please pick a number' in pg.inner_text('#app') and not last(pg,'submit_feedback'))
    pg.click('input[name="fb_r"][value="4"]',force=True); pg.fill('#fb_c','More snacks please'); pg.click('#fbsend'); pg.wait_for_selector('text=Thank you!')
    f=last(pg,'submit_feedback'); check('feedback: sends booking ID, rating 4 and the comment', f and f['args']=={'p_booking_code':'AB12CD34','p_rating':4,'p_comment':'More snacks please'} and not errs, (f, errs))
    check('feedback: after sending the questions are replaced by a thank-you', pg.query_selector('#fbsend') is None); b.close()
    b,pg,errs=done_page("{show_about:true,ask_email:true,ask_feedback:true}"); pg.fill('#fb_c','Only words'); pg.click('#fbsend'); pg.wait_for_selector('text=Thank you!'); f=last(pg,'submit_feedback')
    check('feedback: comment only is sent with rating null', f['args']['p_rating'] is None and f['args']['p_comment']=='Only words', f); b.close()
    b,pg,errs=done_page("{show_about:true,ask_email:true,ask_feedback:false}")
    check('feedback OFF: no questions on the Booking ID page', 'Tell us how excited' not in pg.inner_text('#app') and pg.query_selector('#fbsend') is None); b.close()
    b,pg,errs=done_page("{show_about:true,ask_email:true}")
    check('feedback flag unknown (database not updated yet): no questions, no crash', pg.query_selector('#fbsend') is None and not errs); b.close()
    # ===== a finished booking leaves no old data behind (the reused Booking ID bug)
    b,pg,errs=done_page("{show_about:true,ask_email:true,ask_feedback:false}"); sid1=last(pg,'submit_booking')['args']['p_submission_id']
    pg.click('#go-home'); pg.wait_for_selector('#go-register'); pg.click('#go-register'); pg.wait_for_selector('#n0')
    check('after a booking, Home then Register opens an EMPTY form', pg.input_value('#n0')=='' and pg.input_value('#t0')=='' and pg.input_value('#e0')=='' and not pg.is_checked('input[name="p0_loc"][value="In Bengaluru"]',) )
    check('after a booking, the old screenshot is forgotten', pg.query_selector('#shot') is None or 'File uploaded' not in pg.inner_text('#app'))
    pg.fill('#n0','Amy'); pg.fill('#t0','9876500001'); pg.fill('#e0','a@e.com')
    pg.click('input[name="p0_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="p0_att"][value="Surely"]',force=True); pg.click('input[name="p0_food"][value="Veg"]',force=True)
    pg.click('#review'); pg.click('#topay'); pg.wait_for_selector('#shot',state='attached')
    pg.set_input_files('#shot',{'name':'s2.png','mimeType':'image/png','buffer':bytes.fromhex('89504e470d0a1a0a')+b'y'*50})
    pg.evaluate("window.compress=async f=>new Blob(['y'],{type:'image/jpeg'})")
    pg.click('#submit'); pg.wait_for_selector('#copyid'); calls2=[c for c in calls(pg) if c['name']=='submit_booking']
    check('the second booking uses a NEW submission ID and its own details', len(calls2)==2 and calls2[1]['args']['p_submission_id']!=sid1 and calls2[1]['args']['p_people'][0]['name']=='Amy', calls2); b.close()
    b,pg,errs=done_page("{show_about:true,ask_email:true,ask_feedback:false}"); pg.click('#again'); pg.wait_for_selector('#n0'); check('"Register another booking" still gives an empty form', pg.input_value('#n0')==''); b.close()
    # a failed send keeps the same ID so a re-tap can never create a duplicate
    b,pg,errs=page(p,"window.__N=0;window.__R.submit_booking=a=>(++window.__N===1?{data:null,error:{message:'network down'}}:{data:{booking_code:'AB12CD34',status:'pending',amount_expected:250,tickets:[{name:'Zed',food:'Veg'}]},error:null});"); pg.wait_for_timeout(300); pg.click('#go-register'); pg.wait_for_selector('#n0')
    pg.fill('#n0','Zed'); pg.fill('#t0','9876543210'); pg.fill('#e0','z@e.com'); pg.click('input[name="p0_loc"][value="In Bengaluru"]',force=True); pg.click('input[name="p0_att"][value="Surely"]',force=True); pg.click('input[name="p0_food"][value="Veg"]',force=True)
    pg.click('#review'); pg.click('#topay'); pg.wait_for_selector('#shot',state='attached'); pg.set_input_files('#shot',{'name':'s.png','mimeType':'image/png','buffer':bytes.fromhex('89504e470d0a1a0a')+b'x'*50}); pg.evaluate("window.compress=async f=>new Blob(['x'],{type:'image/jpeg'})")
    pg.click('#submit'); pg.wait_for_selector('text=Tapping again will not create a duplicate'); pg.click('#submit'); pg.wait_for_selector('#copyid'); c3=[c for c in calls(pg) if c['name']=='submit_booking']
    check('after a failed send, the retry keeps the same submission ID (no duplicate)', len(c3)==2 and c3[0]['args']['p_submission_id']==c3[1]['args']['p_submission_id'], c3); b.close()
    # ===== look and feel (logo, header, share preview, phone width)
    b,pg,errs=page(p,"window.__R.get_site_flags={show_about:true};",w=360); pg.wait_for_timeout(300)
    check('look: home has no top bar (removed 3 Nov 2026), the big heading with a coloured year, and the old slim header is hidden', pg.query_selector('.home .hhead') is None and pg.inner_text('.home h1').replace('\u2019',"'")=="Ehsaas'26" and pg.query_selector('.home h1 em') is not None and not pg.is_visible('.top'))
    check('home: live date, time and venue (from the database) fill the tap cards, and there is no separate event summary', pg.query_selector('#home-summary') is None and 'Sunday, 22 November 2026' in pg.inner_text('#home-cal') and '2:00 PM' in pg.inner_text('#home-cal') and 'Savoury Business Hotel' in pg.inner_text('#home-map'))
    check('home: Add to calendar uses the live start time (08:30 UTC) and Open in Maps the live venue', 'dates=20261122T083000Z/20261122T113000Z' in pg.get_attribute('#home-cal','href') and 'Savoury%20Business%20Hotel' in pg.get_attribute('#home-map','href') and pg.get_attribute('#home-cal','target')=='_blank' and pg.get_attribute('#home-map','rel')=='noopener')
    check('home: the floating Register button is always there and scrolls to the Ready-to-join box without opening the form', pg.is_visible('#home-fab') and pg.evaluate("(async()=>{window.scrollTo(0,0);document.getElementById('home-fab').click();await new Promise(r=>setTimeout(r,1200));const r=document.getElementById('home-join').getBoundingClientRect();return r.top<innerHeight&&r.bottom>0&&!!document.getElementById('go-register')&&document.querySelector('#n0')===null})()"))
    check('home: every card is revealed after scrolling through (nothing stays hidden)', pg.evaluate("(async()=>{for(let y=0;y<4000;y+=300){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,60))}await new Promise(r=>setTimeout(r,700));return [...document.querySelectorAll('.home .rv')].every(e=>e.classList.contains('in'))})()"))
    check('home: the sponsor card is always shown; with no poster file only the poster part is left out (no broken picture)', pg.query_selector('#home-sponsor') is not None and 'Thank you for the support' in pg.inner_text('#home-sponsor') and pg.query_selector('#home-sp-img') is None)
    check('home: no tapping-finger animation on the cards', pg.query_selector('.hhand') is None and 'Tap to add to calendar' in pg.inner_text('#home-cal') and 'Tap to open in Google Maps' in pg.inner_text('#home-map'))
    check('home: tapping the poster opens a full-screen view and tapping again closes it', (pg.click('#home-poster') or True) and pg.query_selector('.hlb img') is not None and (pg.click('.hlb') or True) and pg.query_selector('.hlb') is None)
    check('look: home at 360 px wide has no sideways scrolling', pg.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'))
    check('home: Register now, Ticket Status and About (when switched on) are all there, each id used once (the floating button has its own id)', all(pg.evaluate(f"document.querySelectorAll('#{k}').length")==1 for k in ('go-register','go-tickets','go-about','home-fab')))
    pg.click('#go-register'); pg.wait_for_selector('#n0'); pg.wait_for_timeout(200)
    check('look: other pages show the slim header with the logo', pg.is_visible('.top') and pg.query_selector('.top img') is not None)
    check('look: form at 360 px wide has no sideways scrolling', pg.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'))
    html=pg.content()
    check('look: share preview (og:image) and browser icon are set', 'og:image' in html and 'assets/og-image.jpg' in html and 'rel="icon"' in html and 'apple-touch-icon' in html)
    check('look: the page never mentions the old green theme colours', '#0e5a43' not in html.lower() and 'Cormorant' not in html)
    b.close()
print(sum(res),'passed,',len(res)-sum(res),'failed')
