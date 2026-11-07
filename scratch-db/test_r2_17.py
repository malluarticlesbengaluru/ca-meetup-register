# test_r2_17.py - database tests for sql/r2_17_contacts.sql (three organiser contacts)
# Run from scratch-db with the private test Postgres: python3 test_r2_17.py
from lib import *
import uuid, subprocess, json, os
R217 = os.environ.get('R217', '/home/claude/sql/r2_17_contacts.sql')
t = T()
def psql_file(path):
    r = subprocess.run(["psql","-h","/tmp","-p","5544","-q","-d","postgres","-U","postgres","-v","ON_ERROR_STOP=1","-f",path], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)
def mkstaff(nm, role):
    u = uuid.uuid4(); sql("insert into auth.users (id,email) values (%s,%s)", (str(u), nm+'@test')); sql("insert into staff (user_id,name,role) values (%s,%s,%s)", (str(u), nm, role)); return u
def setup():
    fresh()
    return mkstaff('Admin One','admin'), mkstaff('Admin Two','admin'), mkstaff('Gate One','gate')
def setc(uid, *a, role='authenticated'):
    ph = ', '.join(['%s']*len(a)); return call(role, f"select admin_set_contacts({ph})", a, uid=uid)
def err(r, w): return r[0]=='err' and w in r[1]
def info(): return sql("select get_payment_info()")[0][0]
def srow(): return sql("select upi_id, payee_name, whatsapp_number, contact1_name, contact2_name, contact2_number, contact3_name, contact3_number from settings where id=1")[0]

admin, admin2, gate = setup()
sql("update settings set upi_id='org@upi', payee_name='Org', whatsapp_number='919999999999' where id=1")
snap = {n: sql("select md5(pg_get_functiondef(p.oid)) from pg_proc p where p.proname=%s and p.pronamespace='public'::regnamespace order by 1", (n,)) for n in ['admin_set_payment_info','admin_set_transfer_settings','admit_ticket','set_booking_status','_assign_numbers']}

# 1. the file runs, and runs twice
rc, out = psql_file(R217)
t.check("1.1 r2_17 runs cleanly on the 5 Nov schema", rc==0, out[-600:])
t.check("1.2 first run says applied (both functions)", 'get_payment_info applied' in out and 'admin_payment_alert applied' in out, out[-600:])
snap_after_1 = srow()
rc2, out2 = psql_file(R217)
t.check("1.3 second run is safe and says already applied", rc2==0 and 'get_payment_info already applied' in out2 and 'admin_payment_alert already applied' in out2, out2[-600:])
t.check("1.4 second run changed no data", srow()==snap_after_1)
t.check("1.5 existing data kept (UPI, payee, contact 1 number)", srow()[:3]==('org@upi','Org','919999999999'), srow())
for n, before in snap.items():
    after = sql("select md5(pg_get_functiondef(p.oid)) from pg_proc p where p.proname=%s and p.pronamespace='public'::regnamespace order by 1", (n,))
    t.check(f"1.6 function {n} is byte-for-byte unchanged", after==before)

# 2. the guard stops without changing anything when the live function differs
fresh()
admin, admin2, gate = mkstaff('Admin One','admin'), mkstaff('Admin Two','admin'), mkstaff('Gate One','gate')
sql("create or replace function public.get_payment_info() returns jsonb language sql stable security definer set search_path to 'public' as $$ select jsonb_build_object('upi_id', upi_id) from settings where id = 1 $$")
rc3, out3 = psql_file(R217)
t.check("2.1 changed get_payment_info: file STOPS with an error", rc3!=0 and 'r2_17 STOPPED' in out3, out3[-400:])
cols = sql("select count(*) from information_schema.columns where table_name='settings' and column_name ~ '^contact'")[0][0]
t.check("2.2 ...and nothing was changed (no new columns, no new function)", cols==0 and sql("select count(*) from pg_proc where proname='admin_set_contacts'")[0][0]==0, cols)
fresh()
admin, admin2, gate = mkstaff('Admin One','admin'), mkstaff('Admin Two','admin'), mkstaff('Gate One','gate')
sql("update settings set upi_id='org@upi', payee_name='Org', whatsapp_number='919999999999' where id=1")
a0 = sql("select pg_get_functiondef('public.admin_payment_alert()'::regprocedure)")[0][0]
sql(a0.replace("'whatsapp_number')", "'whatsapp_number', 'x')", 1))
rc4, out4 = psql_file(R217)
t.check("2.3 changed admin_payment_alert: file STOPS with an error", rc4!=0 and 'r2_17 STOPPED' in out4, out4[-400:])
t.check("2.4 ...and nothing was changed", sql("select count(*) from information_schema.columns where table_name='settings' and column_name ~ '^contact'")[0][0]==0)

# 3. clean database again, apply, then behaviour
fresh()
admin, admin2, gate = mkstaff('Admin One','admin'), mkstaff('Admin Two','admin'), mkstaff('Gate One','gate')
sql("update settings set upi_id='org@upi', payee_name='Org', whatsapp_number='919999999999' where id=1")
rc, out = psql_file(R217); t.check("3.0 applied on a clean database", rc==0, out[-400:])
stranger = uuid.uuid4(); sql("insert into auth.users (id,email) values (%s,%s)", (str(stranger),'s@test'))

# 3a. who may call admin_set_contacts
for who, role, uid, nm in [('anon','anon',None,'a visitor'),('authenticated','authenticated',gate,'gate staff'),('authenticated','authenticated',stranger,'a logged-in stranger')]:
    r = setc(uid, 'Ann','919111111111', role=role)
    t.check(f"3.1 {nm} cannot call admin_set_contacts", r[0]=='err', r)
t.check("3.2 ...and nothing was saved by the refused calls", srow()[3] is None and srow()[2]=='919999999999', srow())
t.check("3.3 visitors (anon) cannot execute it at the privilege level", sql("select has_function_privilege('anon','public.admin_set_contacts(text,text,text,text,text,text)','execute')")[0][0] is False)

# 3b. rules
r = setc(admin, '', '', 'Bo','919222222222'); t.check("3.4 contact 1 required: empty name+number refused", err(r,'FIRST_CONTACT_REQUIRED'), r)
r = setc(admin, 'Ann', '', None, None); t.check("3.5 contact 1 name without number refused", err(r,'FIRST_CONTACT_REQUIRED'), r)
r = setc(admin, '', '919111111111'); t.check("3.6 contact 1 number without name refused", err(r,'FIRST_CONTACT_REQUIRED'), r)
r = setc(admin, 'Ann', '12345'); t.check("3.7 short number refused (INVALID_WHATSAPP)", err(r,'INVALID_WHATSAPP'), r)
r = setc(admin, 'A'*41, '919111111111'); t.check("3.8 name over 40 characters refused", err(r,'INVALID_CONTACT_NAME'), r)
r = setc(admin, 'Ann', '919111111111', 'Bo', ''); t.check("3.9 contact 2 name without number refused (CONTACT_INCOMPLETE)", err(r,'CONTACT_INCOMPLETE'), r)
r = setc(admin, 'Ann', '919111111111', '', '919222222222'); t.check("3.10 contact 2 number without name refused", err(r,'CONTACT_INCOMPLETE'), r)
r = setc(admin, 'Ann', '919111111111', 'Bo', '919222222222', 'Cy', '77'); t.check("3.11 bad contact 3 number refused", err(r,'INVALID_WHATSAPP'), r)
t.check("3.12 refused saves changed nothing", srow()[3] is None and srow()[2]=='919999999999' and srow()[5] is None, srow())
c = db().cursor()
try:
    c.execute("begin"); c.execute("set local role authenticated"); c.execute("select set_config('request.jwt.claim.sub',%s,true)",(str(admin),)); c.execute("select admin_set_contacts('Ann','919111111111','Bo','919222222222','Cy','77')")
except Exception as e:
    d = getattr(e,'diag',None); t.check("3.13 the error DETAIL says 'contact 3'", d is not None and d.message_detail=='contact 3', d.message_detail if d else e)
    c.execute("rollback")

# 3c. good saves
LOG0 = sql("select coalesce(max(id),0) from settings_log")[0][0]
r = setc(admin, ' Ann  Mathew ', '+91 91111 11111', 'Bo', '919222222222', 'Cy', '919333333333')
t.check("3.14 admin saves three contacts", r[0]=='ok', r)
s = srow(); t.check("3.15 stored tidy (name spaces squeezed, number digits only; contact 1 number in whatsapp_number)", (s[2],s[3],s[4],s[5],s[6],s[7])==('919111111111','Ann Mathew','Bo','919222222222','Cy','919333333333'), s)
t.check("3.16 UPI and payee untouched by saving contacts", s[0]=='org@upi' and s[1]=='Org', s)
i = info(); t.check("3.17 old keys still in get_payment_info (upi_id, payee_name, whatsapp)", i['upi_id']=='org@upi' and i['payee_name']=='Org' and i['whatsapp']=='919111111111', i)
t.check("3.18 get_payment_info lists the 3 contacts in order", [c['name'] for c in i['contacts']]==['Ann Mathew','Bo','Cy'] and i['contacts'][0]['number']=='919111111111', i)
t.check("3.19 visitor (anon) can still read get_payment_info", call('anon',"select get_payment_info()")[0]=='ok')
r = setc(admin, 'Ann Mathew','919111111111')
t.check("3.20 saving with only contact 1 clears contacts 2 and 3", r[0]=='ok' and srow()[4:]==(None,None,None,None), (r, srow()))
i = info(); t.check("3.21 one contact: list has exactly one", len(i['contacts'])==1 and i['contacts'][0]['name']=='Ann Mathew', i)

# 3d. log + banner
setc(admin, 'Ann Mathew','919111111111','Bo','919222222222')
lg = sql("select who, field, old_value, new_value from settings_log where id > %s and (field ~ '^contact' or field='whatsapp_number') order by id", (LOG0,))
fields = {l[1] for l in lg}
t.check("3.22 the settings log records contact changes", {'contact2_name','contact2_number'} <= fields and 'contact1_name' in fields, lg)
t.check("3.23 the log names who did it", all(l[0]=='Admin One' for l in lg), lg)
a = call('authenticated',"select admin_payment_alert()", uid=admin2)
t.check("3.24 the other admin's banner reports the latest contact change", a[0]=='ok' and a[1][0][0] and a[1][0][0]['by_me'] is False and any(f.startswith('contact') for f in a[1][0][0]['fields']), a)
a = call('authenticated',"select admin_payment_alert()", uid=admin)
t.check("3.25 the changer sees by_me = true", a[0]=='ok' and a[1][0][0]['by_me'] is True, a)
t.check("3.26 gate cannot read the banner (still admin only)", call('authenticated',"select admin_payment_alert()", uid=gate)[0]=='err')
sql("update settings set upi_id='new@upi' where id=1")
a = call('authenticated',"select admin_payment_alert()", uid=admin2)
t.check("3.27 UPI changes still reported by the banner as before", a[0]=='ok' and 'upi_id' in a[1][0][0]['fields'], a)

# 3e. payment-details save and the transfers rule are unchanged
LOG1 = sql("select coalesce(max(id),0) from settings_log")[0][0]
r = call('authenticated',"select admin_set_payment_info(%s,%s,%s)",('org@upi','Org','919111111111'), uid=admin)
t.check("3.28 admin_set_payment_info (UPI/payee) still works as before", r[0]=='ok', r)
t.check("3.28b ...and writing the SAME contact 1 number back adds no whatsapp_number line to the log", sql("select count(*) from settings_log where id > %s and field='whatsapp_number'", (LOG1,))[0][0]==0)
r = call('authenticated',"select admin_set_payment_info(%s,%s,%s)",('org@upi','Org','919111111111'), uid=gate)
t.check("3.29 ...and still refuses gate accounts", r[0]=='err', r)
def tr(uid, o): return call('authenticated',"select admin_set_transfer_settings(p_open => %s)",(o,), uid=uid)
r = tr(admin, True); t.check("3.30 transfers ON accepted while UPI, payee and contact 1 number are set", r[0]=='ok', r)
tr(admin, False)
for col in ('upi_id','payee_name','whatsapp_number'):
    sql("update settings set upi_id='aa@upi', payee_name='P', whatsapp_number='919111111111'"); sql(f"update settings set {col}=null")
    r = tr(admin, True); t.check(f"3.31 transfers ON refused while {col} is missing (PAYMENT_INFO_MISSING)", err(r,'PAYMENT_INFO_MISSING'), r)
sql("update settings set upi_id='aa@upi', payee_name='P', whatsapp_number='919111111111'")

# 3f. table rules hold even for direct SQL (start with contacts 2 and 3 empty)
sql("update settings set contact2_name=null, contact2_number=null, contact3_name=null, contact3_number=null")
for q,nm in [("update settings set contact2_name='X'","contact 2 name alone"),("update settings set contact3_number='919333333333'","contact 3 number alone"),("update settings set contact2_name='X', contact2_number='123'","bad contact 2 number"),("update settings set contact1_name=''","empty contact 1 name")]:
    r = call('postgres', q); t.check(f"3.32 database refuses direct edit: {nm}", r[0]=='err', r)
t.report("r2_17 contacts")
