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
def open_page(p, database, tab=None):
    b = p.chromium.launch(); pg = b.new_page(viewport={'width':1300,'height':900}); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    pg.route('**/*', lambda r: (r.fulfill(body=HTML, content_type='text/html') if r.request.url.endswith('/admin/test.html')
        else r.fulfill(body='/*stub*/', content_type='text/javascript') if r.request.url.endswith('.js') or '/npm/' in r.request.url
        else r.fulfill(status=204, body='')))
    pg.add_init_script('window.__DB='+json.dumps(database)+';'); pg.add_init_script(MOCK); pg.add_init_script(CH); pg.add_init_script(DLG_BOT)
    pg.goto('https://example.test/admin/test.html'); pg.wait_for_selector('.tabs')
    if tab: pg.click(f'button[data-tab="{tab}"]'); pg.wait_for_timeout(100)
    return b, pg, errs
