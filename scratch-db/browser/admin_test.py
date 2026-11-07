import json, sys
from playwright.sync_api import sync_playwright
import os
HTML = open(os.environ.get('ADMIN_HTML', '/home/claude/ca-meetup-register/admin/index.html'), encoding='utf-8').read()
MOCK = open('mock_supabase.js').read(); CH = open('chart_stub.js').read()
results = []
# The page now shows its own dialogs (not the browser's confirm/prompt). This small bot answers the NEXT dialog the page shows:
#   auto(pg)              -> press OK          auto(pg, False) -> press Cancel        auto(pg, True, value='x') -> type x, press OK
#   dlg_msgs(pg)          -> the texts of the dialogs answered since the last call
DLG_BOT = r"""
(function(){
  window.__DLGQ=[];window.__DLGMSG=[];
  const go=()=>{const d=document.querySelector('.dlg');if(!d||d.dataset.bot)return;const q=window.__DLGQ.shift();if(!q)return;d.dataset.bot='1';
    window.__DLGMSG.push(d.innerText);const i=d.querySelector('input');if(i&&q.value!=null)i.value=q.value;
    setTimeout(()=>d.querySelector('[data-dlg="'+(q.accept?'yes':'no')+'"]').click(),0)};
  new MutationObserver(go).observe(document,{childList:true,subtree:true});
  const n=Date.now.bind(Date);Date.now=()=>n()+(window.__off||0);   // tests can move the clock forward with window.__off
})();
"""
def go_tab(pg, t):
    """open a section like a person would: tap its menu button if one is on screen (side menu or bottom bar), otherwise go there directly (Scan screenshots, and the sections under More on a phone)"""
    el = pg.query_selector(f'button[data-tab="{t}"]:visible')
    if el: el.click()
    else: pg.evaluate("t=>nav({tab:t,sheets:[]})", t)
    pg.wait_for_timeout(100)
def on_tab(pg, t): return pg.query_selector(f'button[data-tab="{t}"][aria-current="page"]') is not None
def auto(pg, accept=True, value=None): pg.evaluate('(q)=>window.__DLGQ.push(q)', dict(accept=accept, value=value))
def dlg_msgs(pg): return pg.evaluate('(()=>{const m=window.__DLGMSG;window.__DLGMSG=[];return m})()')
def check(name, cond, detail=''):
    results.append(bool(cond)); print(('  PASS  ' if cond else '  FAIL  ')+name+('' if cond else '  '+str(detail)[:200]))

def mk(n, **kw):
    d = dict(id=f't{n}', ticket_no=None, coord_no=None, kind='guest', name=f'P{n}', phone=f'90000000{n:02d}', food='Veg', location='In Bengaluru',
             attendance='Surely', booking_id='b1', checked_in_at=None, reg_seq=n, transferred_out_at=None, prev_coord_no=None); d.update(kw); return d
def bk(i, status='paid', kind='registration', amt=250, n=1): return dict(id=f'b{i}', booking_code=f'CODE000{i}', status=status, kind=kind, amount_expected=amt, people_count=n, created_at='2026-10-20T10:00:00Z', screenshot_path=f'p{i}.jpg')
SETTINGS = dict(id=1, cap=150, price_per_head=250, deadline='2026-10-31T18:29:59Z', is_open=True, pause_enabled=False, pause_close_time='23:00:00', pause_open_time='00:00:00',
  event_at='2026-11-22T08:30:00Z', venue='Hotel', upi_id='a@b', payee_name='X', whatsapp_number='919999999999', next_coord=1,
  transfers_open=True, transfer_cutoff_at=None, transfer_food_locked=False, private_code_hours=2, ip_flag_threshold=5)
# Asha (t1, E26-001) transferred to Dan (t4, E26-004, new booking b3 kind transfer, amount 0). Ben (t2) and Carl (t3) normal.
TICKETS = [mk(1,ticket_no=1,name='Asha',transferred_out_at='2026-10-22T10:00:00Z'), mk(2,ticket_no=2,name='Ben',food='Non-veg'), mk(3,ticket_no=3,name='Carl',booking_id='b2'), mk(4,ticket_no=4,name='Dan',booking_id='b3',transferred_from='t1')]
BOOKINGS = [bk(1,n=2,amt=500), bk(2), bk(3,kind='transfer',amt=0)]
TRANSFERS = [
 dict(id='x1',kind='private',ticket_id='t2',booking_id='b1',seller_name='Ben',seller_phone='9000000002',status='pending_admin',code=None,code_expires_at=None,seller_call_confirmed_at=None,created_at='2026-10-24T08:00:00Z',updated_at='2026-10-24T08:00:00Z',seller_upi=None,return_due=False),
 dict(id='x2',kind='public',ticket_id='t3',booking_id='b2',seller_name='Carl',seller_phone='9000000003',status='code_active',code='ABC234',code_expires_at='2026-10-23T08:00:00Z',seller_upi='carl@upi',created_at='2026-10-22T08:00:00Z',updated_at='2026-10-22T08:00:00Z',return_due=False),
 dict(id='x3',kind='public',ticket_id='t1',booking_id='b1',seller_name='Asha',seller_phone='9000000001',status='done',seller_upi='asha@upi',amount_received=230,seller_paid_at=None,return_due=False,decided_at='2026-10-22T10:00:00Z',created_at='2026-10-21T08:00:00Z',updated_at='2026-10-22T10:00:00Z'),
]
BUYERS = [dict(id='y1',transfer_id='x1',name='Eve Buyer',phone='9000000009',email='eve@example.com',location='In Bengaluru',attendance='Surely',food='Veg',status='active',created_at='2026-10-24T08:00:00Z'),
          dict(id='y3',transfer_id='x3',name='Dan',phone='9000000004',email='dan@example.com',location='In Bengaluru',attendance='Surely',food='Veg',status='done',created_at='2026-10-21T09:00:00Z')]
MONEY = {k:{'count':0,'amount':0} for k in ['awaiting_payment','awaiting_verification','verified_waiting_transfer','to_pay_out','paid_out','return_due','returned']}; MONEY['to_pay_out']={'count':1,'amount':230}; MONEY['held_now']=230
def db(**over):
    d = dict(tables=dict(staff=dict(name='Admin One',role='admin'), bookings=BOOKINGS, tickets=TICKETS, screenshot_scans=[], settings=SETTINGS, settings_log=[], ticket_emails=[{'ticket_id':t['id'],'email':t['name'].lower()+'@example.com'} for t in TICKETS],
                         transfers=TRANSFERS, transfer_buyers=BUYERS),
             rpc=dict(admin_registration_status={'accepting':True,'grace_count':0}, admin_payment_alert=None, admin_transfer_money=MONEY, admin_ip_flags={'threshold':5,'ips':[],'by_booking':{}}))
    for k,v in over.items():
        if k=='tables': d['tables'].update(v)
        elif k=='rpc': d['rpc'].update(v)
    return d
# Group D: the mock answers admin_preview_approval / admin_approve_bookings from the fake tables (same rules as sql/r2_18_bulk_approve.sql).
# A string set in window.__DB.rpc[name] still makes that call fail with that text; window.__NEXT is the next free ticket number.
APPROVE_HOOK = r"""(()=>{const o=db.rpc;window.__NEXT=window.__NEXT||40;const T=()=>window.__DB.tables;
const plan=(ids,commit)=>{let nx=window.__NEXT;const seen=new Set(),rows=[];
 for(const id of ids){if(seen.has(id))continue;seen.add(id);const b=T().bookings.find(x=>x.id===id);
  if(!b){rows.push({booking_id:id,ok:false,reason:'NOT_FOUND'});continue}
  if(b.kind==='transfer'){rows.push({booking_id:id,booking_code:b.booking_code,ok:false,reason:'TRANSFER'});continue}
  if(b.status!=='pending'){rows.push({booking_id:id,booking_code:b.booking_code,ok:false,reason:'NOT_PENDING',status:b.status});continue}
  const ppl=T().tickets.filter(t=>t.booking_id===id).sort((a,c)=>a.reg_seq-c.reg_seq).map(t=>{let n=t.ticket_no;if(t.kind==='guest'&&n==null){n=nx++;if(commit)t.ticket_no=n}return t.kind==='guest'?{name:t.name,ticket_no:n}:{name:t.name,ticket_no:n,kind:t.kind}});
  if(commit)b.status='paid';
  rows.push({booking_id:id,booking_code:b.booking_code,ok:true,people_count:b.people_count,amount:b.amount_expected,people:ppl})}
 if(commit)window.__NEXT=nx;return rows};
const tot=rows=>{const k=rows.filter(r=>r.ok);return{bookings:k.length,people:k.reduce((a,r)=>a+r.people_count,0),amount:k.reduce((a,r)=>a+r.amount,0)}};
db.rpc=async(n,a)=>{if(n!=='admin_preview_approval'&&n!=='admin_approve_bookings')return o(n,a);
 const r=await o(n,a);if(r.error&&!/does not exist/.test(r.error.message))return r;
 if(n==='admin_preview_approval'){const rows=plan(a.p_ids,false);return{data:{rows,next_ticket:window.__NEXT,...tot(rows)},error:null}}
 if(a.p_expected_next!=null&&a.p_expected_next!==window.__NEXT)return{data:null,error:{message:'NUMBERS_CHANGED'}};
 const rows=plan(a.p_ids,true);return{data:{approved:rows.filter(r=>r.ok),skipped:rows.filter(r=>!r.ok),...tot(rows)},error:null}}})()"""
def open_page(p, database, tab=None):
    b = p.chromium.launch(); pg = b.new_page(viewport={'width':1300,'height':900}); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    pg.route('**/*', lambda r: (r.fulfill(body=HTML, content_type='text/html') if r.request.url.endswith('/admin/test.html')
        else r.fulfill(body='/*stub*/', content_type='text/javascript') if r.request.url.endswith('.js') or '/npm/' in r.request.url
        else r.fulfill(status=204, body='')))
    pg.add_init_script('window.__DB='+json.dumps(database)+';'); pg.add_init_script(MOCK); pg.add_init_script(CH); pg.add_init_script(DLG_BOT)
    pg.goto('https://example.test/admin/test.html'); pg.wait_for_selector('#v'); pg.evaluate(APPROVE_HOOK)
    if tab: go_tab(pg, tab)
    return b, pg, errs
