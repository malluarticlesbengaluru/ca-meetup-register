from lib import *
import json, uuid, os
# Database suite for sql/r2_25_download_allowlist.sql (layered on r2_20, r2_22, r2_24). Set R25 to a different copy (mutate_r2_25.py does this).
R20 = '/home/claude/ca-meetup-register/sql/r2_20_photos.sql'
R22 = '/home/claude/ca-meetup-register/sql/r2_22_photo_gallery.sql'
R24 = '/home/claude/ca-meetup-register/sql/r2_24_originals_admin_only.sql'
R25 = os.environ.get('R25', '/home/claude/ca-meetup-register/sql/r2_25_download_allowlist.sql')
t = T(); fresh([R20, R22, R24, R25]); S = seed(); admin = S['admin']
MB = 1048576
import subprocess
def subprocess_run(p): return subprocess.run(['psql','-h','/tmp','-p','5544','-q','-d','postgres','-U','postgres','-v','ON_ERROR_STOP=1','-f',p],capture_output=True,text=True)
def mkuser(email, role=None, name=None):
    u = uuid.uuid4(); sql("insert into auth.users (id,email) values (%s,%s)", (str(u), email))
    if role: sql("insert into staff (user_id,name,role) values (%s,%s,%s)", (str(u), name or email, role))
    return u
admin2 = mkuser('a2@t', 'admin', 'Admin Two'); cam1 = mkuser('c1@t', 'camera', 'Cam One'); cam2 = mkuser('c2@t', 'camera', 'Cam Two'); gate = mkuser('g@t', 'gate', 'Gate'); visitor = mkuser('v@t')
tk = {r[1]: r[0] for r in sql("select id, name from tickets order by name")}; A, B, C = tk['Asha'], tk['Ben'], tk['Carl']
CODE = {'Asha': S['A'], 'Ben': S['A'], 'Carl': S['B']}; PH = {'Asha': '9000000001', 'Ben': '9000000002', 'Carl': '9000000003'}
def svc(q, p=()): return call('service_role', q, p)
def adm(q, p=(), uid=None): return call('authenticated', q, p, uid=uid or admin)
def as_(u, q, p=()): return call('authenticated', q, p, uid=u)
def anon(q, p=()): return call('anon', q, p)
def err(r, c): return r[0] == 'err' and c in r[1]
def rv(r): return r[1][0][0] if r[0] == 'ok' else {'ok': False, 'error': r[1]}
def setp(**k):
    sets = ", ".join(f"{a}=%s" for a in k); sql(f"update settings set {sets} where id=1", tuple(k.values()))
def present(*ids): sql("update tickets set checked_in_at=now() where id = any(%s::uuid[])", ([str(i) for i in ids],))
def store_pub(who, mb=2, thumb='data:image/jpeg;base64,AAAA'):
    r = rv(svc("select photo_reserve('public',null,%s,%s,%s,'jpg')", (CODE[who], PH[who], int(mb*MB))))
    assert r['ok'], r
    assert rv(svc("select photo_confirm(%s,%s,%s)", (r['id'], int(mb*MB), thumb)))['ok']
    return r['id']
def store_cam(u, mb=3, thumb='data:image/jpeg;base64,BBBB'):
    r = rv(svc("select photo_reserve('camera',%s,null,null,%s,'jpg')", (str(u), int(mb*MB))))
    assert r['ok'], r
    assert rv(svc("select photo_confirm(%s,%s,%s)", (r['id'], int(mb*MB), thumb)))['ok']
    return r['id']

setp(photos_on=True, photo_public_mode='present'); present(A, B, C)
pa1 = store_pub('Asha'); pa2 = store_pub('Asha'); pc1 = store_pub('Carl'); c1a = store_cam(cam1); c1b = store_cam(cam1); c2a = store_cam(cam2)
ids = lambda r: {i['id'] for i in r[1][0][0]['items']}

key = lambda pid: sql("select object_key from photos where id=%s", (pid,))[0][0]
OK = lambda who, pid: rv(svc("select photo_original_key(%s,%s)", (pid, str(who))))
MAY = lambda who: rv(svc("select photo_may_download(%s)", (str(who),)))
LST = lambda u: as_(u, "select photo_camera_list()")[1][0][0]['can_download']
setf = lambda u, v: sql("update staff set photo_download=%s where user_id=%s", (v, str(u)))
# 1. everyone starts OFF
t.check("1.1 the switch exists and defaults to off for every admin", sql("select count(*) from staff where role='admin' and photo_download")[0][0] == 0)
t.check("1.2 an admin with the switch off gets no original", OK(admin, c1a) is None and OK(admin2, pa1) is None)
t.check("1.3 photo_may_download is false for admins with the switch off", MAY(admin) is False and MAY(admin2) is False)
t.check("1.4 list says can_download false for them", LST(admin) is False and LST(admin2) is False)
# 2. choose one admin
setf(admin, True)
t.check("2.1 the chosen admin gets any original", OK(admin, c1a) == key(c1a) and OK(admin, pa1) == key(pa1))
t.check("2.2 the other admin still gets nothing", OK(admin2, c1a) is None and OK(admin2, pa1) is None)
t.check("2.3 list: can_download true for the chosen admin, false for the other", LST(admin) is True and LST(admin2) is False)
t.check("2.4 may_download true only for the chosen admin", MAY(admin) is True and MAY(admin2) is False)
for mode in ('own', 'photographers', 'all'):
    setp(photo_visibility=mode)
    t.check(f"2.5.{mode} chosen admin gets originals, photographer gets none ({mode})", OK(admin, pa1) == key(pa1) and OK(cam1, c1a) is None and OK(cam1, pa1) is None)
setp(photo_visibility='own')
# 3. choose both, then switch one off again
setf(admin2, True)
t.check("3.1 two chosen admins both get originals", OK(admin, c1a) == key(c1a) and OK(admin2, c1a) == key(c1a))
setf(admin, False)
t.check("3.2 switching one off takes it away at once", OK(admin, c1a) is None and OK(admin2, c1a) == key(c1a) and LST(admin) is False)
setf(admin, True)
# 4. the switch is worth nothing without the admin role
setf(cam1, True)
t.check("4.1 a photographer with the switch on still gets nothing", OK(cam1, c1a) is None and MAY(cam1) is False and LST(cam1) is False)
setf(gate, True)
t.check("4.2 a gate login with the switch on still gets nothing", OK(gate, c1a) is None and MAY(gate) is False)
t.check("4.3 an unknown user gets nothing", OK(uuid.uuid4(), c1a) is None and MAY(uuid.uuid4()) is False)
t.check("4.4 a removed photo gives nothing even to a chosen admin", (lambda: (sql("update photos set status='removed' where id=%s", (c2a,)), OK(admin, c2a) is None)[1])())
# 5. nobody can switch themselves on from the website
t.check("5.1 a logged-in admin cannot change the switch (no direct table access)", (lambda: (setf(admin2, False), as_(admin2, "update staff set photo_download=true where user_id=%s", (str(admin2),)), sql("select photo_download from staff where user_id=%s", (str(admin2),))[0][0] is False)[2])())
t.check("5.2 nobody but the service can call photo_may_download or photo_original_key", all(call(r, q, a)[0] == 'err' for r in ('anon', 'authenticated') for q, a in (("select photo_may_download(%s)", (str(admin),)), ("select photo_original_key(%s,%s)", (pa1, str(admin))))))
# 6. attendee list and the rest are unchanged
t.check("6.1 attendee list: can_download false", anon("select photo_public_list(%s,%s)", (CODE['Asha'], PH['Asha']))[1][0][0]['can_download'] is False)
t.check("6.2 photographer still sees their own photos", {i['id'] for i in as_(cam1, "select photo_camera_list()")[1][0][0]['items']} == {c1a, c1b})
t.check("6.3 the list still refuses a visitor", err(as_(visitor, "select photo_camera_list()"), 'NOT_ALLOWED'))
t.check("6.4 running r2_25 a second time keeps the chosen switches", (lambda: (subprocess_run(R25), sql("select photo_download from staff where user_id=%s", (str(admin),))[0][0] is True)[1])())
t.report("r2_25 download allow-list")
