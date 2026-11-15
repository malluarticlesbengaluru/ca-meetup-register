from lib import *
import os, subprocess
# Database suite for sql/r2_23_photos_service_read.sql. Set R23 to a different copy (mutate_r2_23.py does this).
R20 = '/home/claude/ca-meetup-register/sql/r2_20_photos.sql'
R23 = os.environ.get('R23', '/home/claude/ca-meetup-register/sql/r2_23_photos_service_read.sql')
t = T(); fresh([R20])
def runfile(p): return subprocess.run(["psql","-h","/tmp","-p","5544","-q","-d","postgres","-U","postgres","-v","ON_ERROR_STOP=1","-f",p],capture_output=True,text=True)
def can(role, priv='select'): return sql("select has_table_privilege(%s,'public.photos',%s)", (role, priv))[0][0]
# put the scratch database in the same state as the real project: the Edge Function's role cannot read the table yet
sql("alter role service_role bypassrls")   # real Supabase's service_role skips row rules; the scratch one does not
sql("revoke all on public.photos from service_role")
t.check("0.1 before: the function's role cannot read the photos table (the real-project situation)", can('service_role') is False)
r = runfile(R23); t.check("1.1 the file runs", r.returncode == 0, r.stderr[-300:])
t.check("1.2 after: the function's role can read the photos table", can('service_role') is True)
r = runfile(R23); t.check("1.3 can be run a second time safely", r.returncode == 0, r.stderr[-300:])
t.check("2.1 visitors (anon) still have no access to the table", all(can('anon', p) is False for p in ('select','insert','update','delete')))
t.check("2.2 logged-in users can still only read (no insert/update/delete)", can('authenticated') is True and all(can('authenticated', p) is False for p in ('insert','update','delete')))
t.check("2.3 the function's role got read only, not write", all(can('service_role', p) is False for p in ('insert','update','delete')))
# the lookup the Edge Function does, as service_role
S = seed()
sql("insert into photos (id, kind, uploader, object_key, bytes_claimed) values ('11111111-1111-1111-1111-111111111111','camera',%s,'camera/x.jpg',1000)", (str(S['admin']),))
r = call('service_role', "select object_key, status from photos where id='11111111-1111-1111-1111-111111111111'")
t.check("3.1 service_role can look a photo up by id (what confirm/remove/view do)", r[0]=='ok' and r[1] and r[1][0][0]=='camera/x.jpg', str(r))
r = call('anon', "select count(*) from photos")
t.check("3.2 anon still cannot read photos", r[0] != 'ok', str(r))
t.report("r2_23 photos readable by the function")
