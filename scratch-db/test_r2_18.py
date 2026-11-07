# test_r2_18.py - database tests for sql/r2_18_bulk_approve.sql (approve several payments after a preview)
from lib import *
import uuid, subprocess, json, os
R218 = os.environ.get('R218', '/home/claude/sql/r2_18_bulk_approve.sql')
t = T()
def psql_file(path):
    r = subprocess.run(["psql","-h","/tmp","-p","5544","-q","-d","postgres","-U","postgres","-v","ON_ERROR_STOP=1","-f",path], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)
def mkstaff(nm, role):
    u = uuid.uuid4(); sql("insert into auth.users (id,email) values (%s,%s)", (str(u), nm+'@test')); sql("insert into staff (user_id,name,role) values (%s,%s,%s)", (str(u), nm, role)); return u
def pending(names):
    sid = uuid.uuid4(); path = f'{sid}.jpg'
    sql("insert into storage.objects values ('payment-proofs', %s)", (path,))
    people = [dict(name=n, phone=str(9100000000+abs(hash(n))%99999999), email=f'{n.lower()}@example.com', loc='In Bengaluru', att='Surely', food='Veg', occ='Student', occ_detail='Test college') for n in names]
    r = call('anon', "select submit_booking(%s,%s::jsonb,%s)", (str(sid), json.dumps(people), path)); assert r[0]=='ok', r
    return str(sql("select id from bookings order by created_at desc limit 1")[0][0])
def prev(uid, ids, role='authenticated'): return call(role, "select admin_preview_approval(%s::uuid[])", (ids,), uid=uid)
def appr(uid, ids, nxt=None, role='authenticated'): return call(role, "select admin_approve_bookings(%s::uuid[], %s)", (ids, nxt), uid=uid)
def nums(bid): return [r[0] for r in sql("select ticket_no from tickets where booking_id=%s order by reg_seq", (bid,))]
def state(bid): return sql("select status, reviewed_via, reviewed_by is not null, reviewed_at is not null from bookings where id=%s", (bid,))[0]
def fnmd5(n): return sql("select md5(pg_get_functiondef(p.oid)) from pg_proc p where p.proname=%s and p.pronamespace='public'::regnamespace order by 1", (n,))
def setup():
    fresh(); a = mkstaff('Admin One','admin'); g = mkstaff('Gate One','gate')
    sql("update settings set is_open=true, deadline=now()+interval '30 days', cap=150, price_per_head=250, pause_enabled=false, upi_id='test@upi', payee_name='Test', whatsapp_number='919999999999' where id=1")
    return a, g
KEEP = ['set_booking_status','_assign_numbers','admit_ticket','is_admin','get_payment_info','_close_open_transfers']
admin, gate = setup()
before = {n: fnmd5(n) for n in KEEP}
t.check("0.1 admit_ticket carries the r2_16 rule before", 'ADMIN_ONLY' in sql("select pg_get_functiondef('public.admit_ticket(integer,text,boolean,boolean,uuid)'::regprocedure)")[0][0])

# 1 file runs, twice, nothing else changes
rc, out = psql_file(R218); t.check("1.1 file runs cleanly", rc==0 and 'checks passed' in out, out[-500:])
rc2, out2 = psql_file(R218); t.check("1.2 second run is safe", rc2==0, out2[-500:])
for n,b in before.items(): t.check(f"1.3 {n} byte-for-byte unchanged", fnmd5(n)==b)
t.check("1.4 r2_16 text still in admit_ticket", 'ADMIN_ONLY' in sql("select pg_get_functiondef('public.admit_ticket(integer,text,boolean,boolean,uuid)'::regprocedure)")[0][0])
for fn in ['admin_preview_approval(uuid[])','admin_approve_bookings(uuid[],integer)']:
    for role,exp in [('anon',False),('authenticated',True),('public',False)]:
        if role=='public': v = sql("select exists (select 1 from information_schema.routine_privileges where routine_name=%s and grantee='PUBLIC')", (fn.split('(')[0],))[0][0]; t.check(f"1.5 {fn} not granted to PUBLIC", v==False)
        else: t.check(f"1.5 {fn} {role} execute = {exp}", sql("select has_function_privilege(%s,%s::regprocedure,'execute')", (role,'public.'+fn))[0][0]==exp)

# 2 file STOPS if live set_booking_status differs
fresh(); a2 = mkstaff('A','admin')
sql("select 1")
d = sql("select pg_get_functiondef('public.set_booking_status(uuid,text)'::regprocedure)")[0][0]
sql(d.replace("reviewed_via = 'admin'", "reviewed_via = 'admin' /*changed*/", 1).replace("update bookings set status = p_status, reviewed_by = auth.uid(), reviewed_at = now(), reviewed_via = 'admin' /*changed*/", "update bookings set status = p_status, reviewed_by = auth.uid(), reviewed_at = now(), reviewed_via = 'gate'", 1))
rc, out = psql_file(R218)
t.check("2.1 changed live function makes the file STOP", rc!=0 and 'r2_18 STOPPED' in out, out[-300:])
t.check("2.2 and no new function was created", sql("select count(*) from pg_proc where proname in ('admin_preview_approval','admin_approve_bookings')")[0][0]==0)

# 3 behaviour
admin, gate = setup(); rc,_ = psql_file(R218); assert rc==0
P = [pending([f'P{i}a', f'P{i}b'][:1+(i%2)]) for i in range(6)]   # 1,2,1,2,1,2 people
t.check("3.1 anon refused preview", prev(None, P[:1], 'anon')[0]=='err')
t.check("3.2 gate refused preview", prev(gate, P[:1])[0]=='err' and 'NOT_ALLOWED' in prev(gate, P[:1])[1])
t.check("3.3 gate refused approve", 'NOT_ALLOWED' in appr(gate, P[:1])[1])
t.check("3.4 anon refused approve", appr(None, P[:1], None, 'anon')[0]=='err')
t.check("3.5 refused calls changed nothing", all(state(p)[0]=='pending' for p in P) and sql("select next_ticket from settings")[0][0]==1)
snap = sql("select count(*), coalesce(sum(ticket_no),0) from tickets")[0]
order = [P[3], P[0], P[2]]
pr = prev(admin, order); t.check("3.6 preview works", pr[0]=='ok', pr)
pj = pr[1][0][0]
t.check("3.7 preview changed nothing", sql("select count(*), coalesce(sum(ticket_no),0) from tickets")[0]==snap and all(state(p)[0]=='pending' for p in P) and sql("select next_ticket from settings")[0][0]==1)
t.check("3.8 preview shows given order and totals", [r['booking_id'] for r in pj['rows']]==order and pj['bookings']==3 and pj['people']==4 and pj['amount']==4*250, pj)
pred = [[p['ticket_no'] for p in r['people']] for r in pj['rows']]
t.check("3.9 preview numbers are 1..4 in order", pred==[[1,2],[3],[4]], pred)
ar = appr(admin, order, pj['next_ticket']); t.check("3.10 approve works", ar[0]=='ok', ar)
aj = ar[1][0][0]
act = [[p['ticket_no'] for p in r['people']] for r in aj['approved']]
t.check("3.11 actual numbers equal the preview", act==pred, (act,pred))
t.check("3.12 numbers are really on the tickets", [nums(p) for p in order]==pred)
t.check("3.13 state fields set", all(state(p)==('paid','admin',True,True) for p in order))
t.check("3.14 untouched bookings still pending", all(state(p)[0]=='pending' for p in (P[1],P[4],P[5])))
t.check("3.15 next_ticket moved on", sql("select next_ticket from settings")[0][0]==5)
# same end state as the old function
sql("select 1")
c1 = call('authenticated', "select set_booking_status(%s,'paid')", (P[1],), uid=admin); t.check("3.16 old function still works", c1[0]=='ok')
c2 = appr(admin, [P[4]]); t.check("3.17 new function on a single booking", c2[0]=='ok')
t.check("3.18 old and new leave the same kind of state", state(P[1])==state(P[4]) and nums(P[1])==[5,6] and nums(P[4])==[7], (state(P[1]),state(P[4]),nums(P[1]),nums(P[4])))
# no longer pending
sql("select 1"); call('authenticated', "select set_booking_status(%s,'rejected')", (P[5],), uid=admin)
r = prev(admin, [P[0], P[5]])[1][0][0]['rows']; t.check("3.19 preview marks non-pending as skipped", r[0]['reason']=='NOT_PENDING' and r[1]['reason']=='NOT_PENDING', r)
keep0 = nums(P[0]); q = [pending(['Q1']), P[0], pending(['Q2'])]
ar = appr(admin, q); aj = ar[1][0][0]
t.check("3.20 non-pending skipped and reported, others approved", [r['booking_id'] for r in aj['skipped']]==[P[0]] and aj['skipped'][0]['reason']=='NOT_PENDING' and aj['bookings']==2, aj)
t.check("3.21 skipped booking unchanged (numbers kept)", nums(P[0])==keep0 and keep0==[3], keep0)
t.check("3.22 rejected booking stays rejected via new function", appr(admin,[P[5]])[1][0][0]['skipped'][0]['reason']=='NOT_PENDING' and state(P[5])[0]=='rejected')
t.check("3.23 empty list refused", 'NO_BOOKINGS' in appr(admin, [])[1])
t.check("3.24 empty preview is harmless", prev(admin, [])[0]=='ok')
t.check("3.25 unknown id is skipped, not a crash", appr(admin,[str(uuid.uuid4())])[1][0][0]['skipped'][0]['reason']=='NOT_FOUND')
D = pending(['Dup']); n0 = sql("select next_ticket from settings")[0][0]
aj = appr(admin, [D, D, D])[1][0][0]
t.check("3.26 duplicate ids approve once", aj['bookings']==1 and nums(D)==[n0] and sql("select next_ticket from settings")[0][0]==n0+1, aj)
E = pending(['Guard']); n0 = sql("select next_ticket from settings")[0][0]
r = appr(admin, [E], n0+5); t.check("3.27 wrong expected number stops with NUMBERS_CHANGED", r[0]=='err' and 'NUMBERS_CHANGED' in r[1], r)
t.check("3.28 and approves nothing", state(E)[0]=='pending' and sql("select next_ticket from settings")[0][0]==n0)
t.check("3.29 right expected number works", appr(admin, [E], n0)[0]=='ok' and state(E)[0]=='paid')
# coordinator ticket gets no guest number, preview agrees
C = pending(['Cooa','Coob']); sql("update tickets set kind='coordinator', coord_no=1 where booking_id=%s and name='Cooa'", (C,))
pj = prev(admin,[C])[1][0][0]; aj = appr(admin,[C])[1][0][0]
pp = [p['ticket_no'] for p in pj['rows'][0]['people']]; ap = [p['ticket_no'] for p in aj['approved'][0]['people']]
t.check("3.30 coordinator ticket: preview equals actual", pp==ap and ap[0] is None and ap[1] is not None, (pp,ap))
# transfer bookings
T1 = pending(['Tr']); sql("update bookings set kind='transfer' where id=%s", (T1,))
aj = appr(admin,[T1])[1][0][0]; t.check("3.31 transfer booking skipped (USE_TRANSFER_TOOLS rule)", aj['skipped'][0]['reason']=='TRANSFER' and state(T1)[0]=='pending')
# gate still cannot approve at the gate (r2_16)
t.check("3.32 r2_16 still holds", 'ADMIN_ONLY' in sql("select pg_get_functiondef('public.admit_ticket(integer,text,boolean,boolean,uuid)'::regprocedure)")[0][0])
# all-or-nothing: an error half-way rolls everything back
F = [pending(['F1']), pending(['F2'])]; sql("alter table public.tickets add constraint boom check (ticket_no is distinct from 9999)") ; n0 = sql("select next_ticket from settings")[0][0]
sql("update settings set next_ticket=9999 where id=1")
r = appr(admin, F); t.check("3.33 error half-way rolls everything back", r[0]=='err' and all(state(f)[0]=='pending' for f in F), r)
t.report("r2_18 database tests")
