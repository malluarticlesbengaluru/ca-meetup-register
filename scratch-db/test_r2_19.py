# test_r2_19.py - database tests for sql/r2_19_ticket_downloads.sql (ticket page views and downloads)
import os
os.environ['PGOPTIONS'] = '-c check_function_bodies=off'   # the scratch build creates SQL functions in file order
from lib import *
import uuid, subprocess, json, os, re
R219 = os.environ.get('R219', '/home/claude/sql/r2_19_ticket_downloads.sql')
t = T()
def psql_file(path):
    r = subprocess.run(["psql","-h","/tmp","-p","5544","-q","-d","postgres","-U","postgres","-v","ON_ERROR_STOP=1","-f",path], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)
def mkstaff(nm, role):
    u = uuid.uuid4(); sql("insert into auth.users (id,email) values (%s,%s)", (str(u), nm+'@test')); sql("insert into staff (user_id,name,role) values (%s,%s,%s)", (str(u), nm, role)); return u
def booking(people):
    sid = uuid.uuid4(); path = f'{sid}.jpg'
    sql("insert into storage.objects values ('payment-proofs', %s)", (path,))
    ppl = [dict(name=n, phone=p, loc='In Bengaluru', food='Veg', occ='Student', occ_detail='Test college') for n,p in people]
    r = call('anon', "select submit_booking(%s,%s::jsonb,%s)", (str(sid), json.dumps(ppl), path)); assert r[0]=='ok', r
    row = sql("select id, booking_code from bookings order by created_at desc limit 1")[0]
    return str(row[0]), row[1]
def paid(bid, admin): r = call('authenticated', "select set_booking_status(%s,'paid')", (bid,), uid=admin); assert r[0]=='ok', r
def label(phone): return sql("select _ticket_label(kind,ticket_no,coord_no) from tickets where phone=%s", (phone,))[0][0]
def log(code, phone, action, tk=None, role='anon'): return call(role, "select log_ticket_activity(%s,%s,%s,%s::text[])", (code, phone, action, tk))
def rows(): return sql("select count(*) from ticket_activity")[0][0]
def fnmd5(n): return sql("select md5(pg_get_functiondef(p.oid)) from pg_proc p where p.proname=%s and p.pronamespace='public'::regnamespace order by 1", (n,))
def setup(sqlfile=R219):
    fresh(); a = mkstaff('Admin One','admin'); g = mkstaff('Gate One','gate')
    sql("update settings set is_open=true, deadline=now()+interval '30 days', cap=150, price_per_head=250, pause_enabled=false, upi_id='test@upi', payee_name='Test', whatsapp_number='919999999999' where id=1")
    A, ca = booking([('Asha','9000000001'),('Ben','9000000002')]); paid(A, a)
    B, cb = booking([('Carl','9000000003')]); paid(B, a)
    P, cp = booking([('Pia','9000000004')])          # stays pending
    return a, g, ca, cb, cp
admin, gate, ca, cb, cp = setup()
KEEP = ['lookup_tickets','_ticket_label','set_booking_status','submit_booking','is_admin']
before = {n: fnmd5(n) for n in KEEP}
lA, lB, lAsha = label('9000000001'), label('9000000003'), label('9000000001')

# 0 the guard: if lookup_tickets is not what we expect, stop and change nothing
sql("create or replace function public.lookup_tickets(p_code text, p_phone text) returns jsonb language sql as $$ select '{}'::jsonb $$")
rc, out = psql_file(R219)
t.check("0.1 guard stops when lookup_tickets was changed", rc != 0 and 'r2_19 STOPPED' in out, out[-300:])
t.check("0.2 ...and creates nothing", sql("select to_regclass('public.ticket_activity') is null")[0][0] and sql("select to_regprocedure('public.log_ticket_activity(text,text,text,text[])') is null")[0][0])
admin, gate, ca, cb, cp = setup()           # rebuild the real database
lAsha, lBen, lCarl = label('9000000001'), label('9000000002'), label('9000000003')
before = {n: fnmd5(n) for n in KEEP}

# 1 the file runs, twice, nothing else changes
rc, out = psql_file(R219); t.check("1.1 file runs cleanly", rc == 0 and 'checks passed' in out, out[-500:])
rc2, out2 = psql_file(R219); t.check("1.2 second run is safe", rc2 == 0, out2[-500:])
for n, b in before.items(): t.check(f"1.3 {n} byte-for-byte unchanged", fnmd5(n) == b)
for fn, exp in [('log_ticket_activity(text,text,text,text[])', {'anon': True, 'authenticated': True}), ('admin_ticket_activity()', {'anon': False, 'authenticated': True})]:
    for role, e in exp.items(): t.check(f"1.4 {fn} {role} execute = {e}", sql("select has_function_privilege(%s,%s::regprocedure,'execute')", (role, 'public.'+fn))[0][0] == e)
    t.check(f"1.5 {fn} not open to PUBLIC", not sql("select exists (select 1 from information_schema.routine_privileges where routine_name=%s and grantee='PUBLIC')", (fn.split('(')[0],))[0][0])
for role in ['anon', 'authenticated']:
    t.check(f"1.6 {role} has no insert/update/delete on the table", not sql("select has_table_privilege(%s,'public.ticket_activity','insert') or has_table_privilege(%s,'public.ticket_activity','update') or has_table_privilege(%s,'public.ticket_activity','delete')", (role,role,role))[0][0])
t.check("1.7 row level security is on", sql("select relrowsecurity from pg_class where oid='public.ticket_activity'::regclass")[0][0])

# 2 attacks first: nothing may be written
n0 = rows()
attacks = [("wrong phone", (ca, '9999999999', 'jpg', [lAsha])),
           ("Ben's phone for Asha's ticket", (ca, '9000000002', 'jpg', [lAsha])),
           ("other booking's ticket with my credentials", (ca, '9000000001', 'jpg', [lCarl])),
           ("wrong booking id", ('ZZZZZZZZ', '9000000001', 'jpg', [lAsha])),
           ("unpaid booking", (cp, '9000000004', 'jpg', None)),
           ("unpaid booking view", (cp, '9000000004', 'view', None)),
           ("unknown action", (ca, '9000000001', 'hack', [lAsha])),
           ("empty action", (ca, '9000000001', '', None)),
           ("null action", (ca, '9000000001', None, None)),
           ("null everything", (None, None, None, None)),
           ("short phone", (ca, '90000', 'jpg', None)),
           ("letters as phone", (ca, 'abcdefghij', 'jpg', None)),
           ("11 labels", (ca, '9000000001', 'jpg', [lAsha]*11)),
           ("sql text as label", (ca, '9000000001', 'jpg', ["x' or true --"]))]
for name, args in attacks:
    r = log(*args); t.check(f"2.1 attack '{name}': no error and nothing written", r[0] == 'ok' and rows() == n0 and r[1][0][0].get('logged') == 0, str(r))
sql("update tickets set transferred_out_at = now() where phone='9000000002'")
r = log(ca, '9000000002', 'jpg', [lBen]); t.check("2.2 transferred-away ticket: nothing written", r[0]=='ok' and rows()==n0, str(r))
r = log(ca, '9000000002', 'view', None); t.check("2.3 transferred-away ticket view: nothing written", r[0]=='ok' and rows()==n0, str(r))
sql("update tickets set transferred_out_at = null where phone='9000000002'")
sql("update bookings set status='rejected' where booking_code=%s", (ca,))
r = log(ca, '9000000001', 'jpg', [lAsha]); r2 = log(ca, '9000000001', 'view', None)
t.check("2.3b numbered but rejected booking (jpg and view): nothing written", r[0]=='ok' and r2[0]=='ok' and rows()==n0, str((r, r2)))
sql("update bookings set status='paid' where booking_code=%s", (ca,))
# direct table access
for role in ['anon', 'authenticated']:
    for q in ["insert into ticket_activity (ticket_id, action) select id, 'jpg' from tickets limit 1", "update ticket_activity set action='pdf'", "delete from ticket_activity"]:
        r = call(role, q, uid=gate if role == 'authenticated' else None); t.check(f"2.4 {role} direct write refused: {q[:22]}", r[0] == 'err' and rows() == n0, str(r))
t.check("2.5 anon cannot read the table", call('anon', "select * from ticket_activity")[0] == 'err')
t.check("2.6 anon cannot call the admin summary", call('anon', "select admin_ticket_activity()")[0] == 'err')
t.check("2.7 gate account refused by the admin summary", 'NOT_ALLOWED' in str(call('authenticated', "select admin_ticket_activity()", uid=gate)))

# 3 the good paths
r = log(ca, '9000000001', 'jpg', [lAsha]); t.check("3.1 one jpg download logged", r[0]=='ok' and r[1][0][0]['logged']==1 and rows()==1, str(r))
t.check("3.2 it belongs to Asha's ticket only", sql("select count(*) from ticket_activity a join tickets k on k.id=a.ticket_id where k.phone='9000000001' and a.action='jpg'")[0][0]==1)
r = log(ca.lower().replace('0','o'), '90000 00001', 'pdf', [lAsha]); t.check("3.3 lower-case code and spaced phone are accepted like in lookup", r[0]=='ok' and r[1][0][0]['logged']==1, str(r))
r = log(ca, '9000000001', 'jpg', [lAsha]); t.check("3.4 each click is its own row (count goes up)", rows()==3, str(rows()))
r = log(ca, '9000000001', 'all-pdf', None); t.check("3.5 all-pdf with no labels logs every ticket of that phone", r[1][0][0]['logged']==1, str(r))
r = log(cb, '9000000003', 'view', None); r2 = log(cb, '9000000003', 'view', None)
t.check("3.6 a view is logged once, a repeat within 10 minutes is not", r[1][0][0]['logged']==1 and r2[1][0][0]['logged']==0, str((r, r2)))
sql("update ticket_activity set created_at = now() - interval '11 minutes' where action='view'")
r = log(cb, '9000000003', 'view', None); t.check("3.7 after 10 minutes a new view is logged", r[1][0][0]['logged']==1, str(r))
# summary for the staff page
s = call('authenticated', "select admin_ticket_activity()", uid=admin); data = s[1][0][0] if s[0]=='ok' else []
asha = sql("select id from tickets where phone='9000000001'")[0][0]; carl = sql("select id from tickets where phone='9000000003'")[0][0]
da = [x for x in data if x['ticket_id']==str(asha)]; dc = [x for x in data if x['ticket_id']==str(carl)]
t.check("3.8 admin summary: Asha has 4 downloads, last format all-pdf, no views", len(da)==1 and da[0]['downloads']==4 and da[0]['last_format']=='all-pdf' and da[0]['views']==0, str(da))
t.check("3.9 admin summary: Carl has 2 views and no downloads", len(dc)==1 and dc[0]['views']==2 and dc[0]['downloads']==0 and dc[0]['last_download'] is None, str(dc))
t.check("3.10 admin can read the table, gate cannot", call('authenticated',"select count(*) from ticket_activity",uid=admin)[1][0][0]>=6 and call('authenticated',"select count(*) from ticket_activity",uid=gate)[1][0][0]==0)
t.check("3.11 no phone number is stored anywhere in the table", sql("select count(*) from information_schema.columns where table_name='ticket_activity' and column_name ~ 'phone|code|secret'")[0][0]==0)
sql("delete from tickets where phone='9000000003'"); t.check("3.12 deleting a ticket removes its rows (no orphans)", sql("select count(*) from ticket_activity a where not exists (select 1 from tickets k where k.id=a.ticket_id)")[0][0]==0)
for n, b in before.items(): t.check(f"3.13 {n} still unchanged after use", fnmd5(n) == b)

# 4 deliberate-mistake check: break the file on purpose; the tests above must notice
src = open(R219, encoding='utf-8').read()
muts = {"transferred check removed": src.replace("      and k.transferred_out_at is null\n", ""),
        "paid check removed": src.replace("or b.status <> 'paid'", ""),
        "phone check removed": src.replace("where k.booking_id = b.id and k.phone = ph", "where k.booking_id = b.id")}
for name, m in muts.items():
    assert m != src, name
    open('/tmp/r219_mut.sql', 'w', encoding='utf-8').write(m)
    a2, g2, ca2, cb2, cp2 = setup(); psql_file('/tmp/r219_mut.sql')
    bad = False
    sql("update tickets set transferred_out_at = now() where phone='9000000002'")
    lab = {p: label(p) for p in ['9000000001','9000000002']}
    log(ca2, '9000000002', 'jpg', [lab['9000000002']]); bad |= rows() > 0
    sql("delete from ticket_activity"); sql("update tickets set transferred_out_at = null where phone='9000000002'")
    log(cp2, '9000000004', 'jpg', None); bad |= rows() > 0
    sql("delete from ticket_activity"); log(ca2, '9000000002', 'jpg', [lab['9000000001']]); bad |= rows() > 0
    sql("delete from ticket_activity"); sql("update bookings set status='rejected' where booking_code=%s", (ca2,)); log(ca2, '9000000001', 'jpg', [lab['9000000001']]); bad |= rows() > 0
    t.check(f"4.1 deliberate mistake '{name}' is caught by the attack tests", bad)
t.report("test_r2_19")
