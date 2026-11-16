from lib import *
import json, uuid, os
# Database suite for sql/r2_24_originals_admin_only.sql (layered on r2_20 and r2_22). Set R24 to a different copy (mutate_r2_24.py does this).
R20 = '/home/claude/ca-meetup-register/sql/r2_20_photos.sql'
R22 = '/home/claude/ca-meetup-register/sql/r2_22_photo_gallery.sql'
R24 = os.environ.get('R24', '/home/claude/ca-meetup-register/sql/r2_24_originals_admin_only.sql')
t = T(); fresh([R20, R22, R24]); S = seed(); admin = S['admin']
MB = 1048576
def mkuser(email, role=None, name=None):
    u = uuid.uuid4(); sql("insert into auth.users (id,email) values (%s,%s)", (str(u), email))
    if role: sql("insert into staff (user_id,name,role) values (%s,%s,%s)", (str(u), name or email, role))
    return u
cam1 = mkuser('c1@t', 'camera', 'Cam One'); cam2 = mkuser('c2@t', 'camera', 'Cam Two'); gate = mkuser('g@t', 'gate', 'Gate'); visitor = mkuser('v@t')
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
# 1. originals: admin only, whatever the visibility setting says
for mode in ('own', 'photographers', 'all'):
    setp(photo_visibility=mode)
    t.check(f"1.{mode}.a admin gets a photographer's original ({mode})", OK(admin, c1a) == key(c1a))
    t.check(f"1.{mode}.b admin gets an attendee's original ({mode})", OK(admin, pa1) == key(pa1))
    t.check(f"1.{mode}.c photographer gets NOTHING, not even their own ({mode})", OK(cam1, c1a) is None)
    t.check(f"1.{mode}.d photographer gets nothing of another photographer's or an attendee's ({mode})", OK(cam1, c2a) is None and OK(cam1, pa1) is None)
t.check("1.4 gate login gets nothing", OK(gate, c1a) is None)
t.check("1.5 a login with no staff role gets nothing", OK(visitor, c1a) is None)
t.check("1.6 an unknown user id gets nothing", OK(uuid.uuid4(), c1a) is None)
t.check("1.7 a removed photo gives nothing even to the admin", (lambda: (sql("update photos set status='removed' where id=%s", (c2a,)), OK(admin, c2a) is None)[1])())
t.check("1.8 nobody but the service can call it", all(call(r, "select photo_original_key(%s,%s)", (pa1, str(admin)))[0] == 'err' for r in ('anon', 'authenticated')))
# 2. the list tells the page whether the Download button may show
setp(photo_visibility='all')
t.check("2.1 admin list: can_download true", adm("select photo_camera_list()")[1][0][0]['can_download'] is True)
t.check("2.2 photographer list: can_download false (even when they may see everything)", as_(cam1, "select photo_camera_list()")[1][0][0]['can_download'] is False)
t.check("2.3 attendee list: can_download false", anon("select photo_public_list(%s,%s)", (CODE['Asha'], PH['Asha']))[1][0][0]['can_download'] is False)
# 3. the rest of the list still works the same
setp(photo_visibility='own')
t.check("3.1 photographer still sees their own photos in own mode", {i['id'] for i in as_(cam1, "select photo_camera_list()")[1][0][0]['items']} == {c1a, c1b})
t.check("3.2 admin still sees every stored photo", len(adm("select photo_camera_list()")[1][0][0]['items']) == 5)
t.check("3.3 a visitor login is still refused the list", err(as_(visitor, "select photo_camera_list()"), 'NOT_ALLOWED'))
t.check("3.4 photographers can still delete their own photo (function unchanged)", svc("select photo_remove_camera(%s,%s)", (c1b, str(cam1)))[0] == 'ok' and rv(svc("select photo_remove_camera(%s,%s)", (c1a, str(cam2)))) is None)
t.report("r2_24 originals admin only")
