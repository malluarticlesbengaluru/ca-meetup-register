from lib import *
import json, uuid, subprocess, os
# Database suite for sql/r2_21_transfer_buyer_details.sql. Set R21 to a different copy (mutate_r2_21.py does this).
R21 = os.environ.get('R21', '/home/claude/ca-meetup-register/sql/r2_21_transfer_buyer_details.sql')
t = T(); fresh([R21]); S = seed(); admin = S['admin']
sql("update settings set ask_email=false")   # the transfer page does not ask for an email
def runfile(p): return subprocess.run(["psql","-h","/tmp","-p","5544","-q","-d","postgres","-U","postgres","-v","ON_ERROR_STOP=1","-f",p],capture_output=True,text=True)
def adm(q, p=()): return call('authenticated', q, p, uid=admin)
def lab(name): return sql("select _ticket_label(kind,ticket_no,coord_no) from tickets where name=%s",(name,))[0][0]
def code_for(booking, name, phone):
    r = call('anon', "select private_sell(%s,%s,%s)", (booking, lab(name), phone)); assert r[0]=='ok' and r[1][0][0].get('code'), r
    return r[1][0][0]['code']
def buyer(**k):
    d = dict(name='Newbie', phone='9111111111', email='', loc='In Bengaluru', att='Surely', food='Veg', occ='Employee', occ_detail='ABC & Co.', consent='true'); d.update(k); return d
def submit(code, b): r = call('anon', "select transfer_submit(%s,%s,%s::jsonb)", (code, str(uuid.uuid4()), json.dumps(b))); return r[1][0][0] if r[0]=='ok' else {'ok': False, 'error': r[1]}

t.check("0.1 two columns exist on transfer_buyers", sql("select count(*) from information_schema.columns where table_name='transfer_buyers' and column_name in ('occupation','occupation_detail')")[0][0]==2)
r = runfile(R21); t.check("0.2 can be run a second time safely", r.returncode==0, r.stderr[-300:])
t.check("0.3 transfer_submit still open to visitors, approve admin-only",
        sql("select has_function_privilege('anon','transfer_submit(text,uuid,jsonb)','execute'), has_function_privilege('anon','admin_transfer_approve(uuid)','execute'), has_function_privilege('authenticated','admin_transfer_approve(uuid)','execute')")[0]==(True,False,True))

# validation (each gets its own seller code; a rejected application must not use up the code)
c1 = code_for(S['A'], 'Asha', '9000000001')
for name, kw, err in [("1.1 missing occupation", dict(occ=''), 'INVALID_OCCUPATION'), ("1.2 unknown occupation", dict(occ='Pilot'), 'INVALID_OCCUPATION'),
                      ("1.3 missing firm/detail", dict(occ_detail=''), 'INVALID_OCCUPATION_DETAIL'), ("1.4 blank-spaces detail", dict(occ_detail='   '), 'INVALID_OCCUPATION_DETAIL'),
                      ("1.5 detail over 100 characters", dict(occ_detail='x'*101), 'INVALID_OCCUPATION_DETAIL')]:
    r = submit(c1, buyer(**kw)); t.check(name+" is refused with "+err, r.get('error')==err, str(r))
t.check("1.6 refused applications left the code usable and made no rows", sql("select count(*) from transfer_buyers")[0][0]==0 and sql("select count(*) from transfers where code=%s and status='code_active'",(c1,))[0][0]==1)
b2 = buyer(occ=None); b2.pop('occ'); b2.pop('occ_detail')
t.check("1.7 an old-style application with neither field is refused", submit(c1, b2).get('error')=='INVALID_OCCUPATION')
r = submit(c1, buyer(occ='Article Assistant', occ_detail='  CA article at ABC & Co.  ', name='First'))
t.check("1.8 a valid application is accepted", r.get('ok') is True, str(r))
row = sql("select occupation, occupation_detail from transfer_buyers where name='First'")[0]
t.check("1.9 saved with the detail trimmed", row==('Article Assistant','CA article at ABC & Co.'), str(row))
c2 = code_for(S['A'], 'Ben', '9000000002'); ok = submit(c2, buyer(name='Second', occ='Others', occ_detail='x'*100))
t.check("1.10 'Others' with a 100-character detail is accepted", ok.get('ok') is True, str(ok))
c3 = code_for(S['B'], 'Carl', '9000000003')
good = [submit(c3, buyer(name='Third', occ='Student', occ_detail='Approaching CA Finals')).get('ok')]
t.check("1.11 Student accepted", good==[True])

# approve copies onto the new ticket
tr = sql("select id from transfers where status='pending_admin' order by created_at")
t.check("2.1 three applications are waiting", len(tr)==3)
first = sql("select t.id from transfers t join transfer_buyers b on b.transfer_id=t.id where b.name='First'")[0][0]
adm("select admin_transfer_confirm_call(%s,true)", (str(first),))
r = adm("select admin_transfer_approve(%s)", (str(first),)); t.check("2.2 approve works", r[0]=='ok', str(r))
nt = sql("select occupation, occupation_detail, name, kind from tickets where name='First'")[0]
t.check("2.3 the new ticket carries the occupation and detail", nt==('Article Assistant','CA article at ABC & Co.','First','guest'), str(nt))
t.check("2.4 the new ticket passes the table's own role rules (both set)", sql("select count(*) from tickets where name='First' and occupation is not null and occupation_detail is not null")[0][0]==1)

# an application made BEFORE this change (no answers) still gets approved, ticket has no role
sql("update transfer_buyers set occupation=null, occupation_detail=null where name='Second'")
sec = sql("select t.id from transfers t join transfer_buyers b on b.transfer_id=t.id where b.name='Second'")[0][0]
adm("select admin_transfer_confirm_call(%s,true)", (str(sec),))
r = adm("select admin_transfer_approve(%s)", (str(sec),)); t.check("3.1 an old application with no answers still approves", r[0]=='ok', str(r))
t.check("3.2 its ticket simply has no role", sql("select occupation, occupation_detail from tickets where name='Second'")[0]==(None,None))
# table rules
t.check("3.3 table refuses a role without detail", call('postgres',"update transfer_buyers set occupation='Student', occupation_detail=null where name='Third'")[0]=='err')
t.check("3.4 table refuses an unknown role", call('postgres',"update transfer_buyers set occupation='Pilot', occupation_detail='x' where name='Third'")[0]=='err')
t.check("3.5 the admin can read the new columns", adm("select occupation, occupation_detail from transfer_buyers where name='Third'")[1][0]==('Student','Approaching CA Finals'))
t.check("3.6 visitors cannot read transfer_buyers", call('anon',"select count(*) from transfer_buyers")[0]=='err')
t.report("r2_21 transfer buyer details")
