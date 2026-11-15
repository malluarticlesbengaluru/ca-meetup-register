from lib import *
import json, uuid, os
# Database suite for sql/r2_22_photo_gallery.sql (layered on r2_20_photos.sql). Set R22 to a different copy (mutate_r2_22.py does this).
R20 = '/home/claude/ca-meetup-register/sql/r2_20_photos.sql'
R22 = os.environ.get('R22', '/home/claude/ca-meetup-register/sql/r2_22_photo_gallery.sql')
t = T(); fresh([R20, R22]); S = seed(); admin = S['admin']
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

# 1. the setting
t.check("1.1 visibility defaults to own", sql("select photo_visibility from settings where id=1")[0][0] == 'own')
t.check("1.2 admin can change it", adm("select admin_set_photo_visibility('all')")[0] == 'ok' and sql("select photo_visibility from settings where id=1")[0][0] == 'all')
adm("select admin_set_photo_visibility('own')")
t.check("1.3 a bad value is refused", err(adm("select admin_set_photo_visibility('everyone')"), 'INVALID_VISIBILITY'))
t.check("1.4 photographer cannot change it", err(as_(cam1, "select admin_set_photo_visibility('all')"), 'NOT_ALLOWED'))
t.check("1.5 gate cannot change it", err(as_(gate, "select admin_set_photo_visibility('all')"), 'NOT_ALLOWED'))
t.check("1.6 anonymous cannot change it", anon("select admin_set_photo_visibility('all')")[0] == 'err')
t.check("1.7 table refuses a value outside the three", sql("select 1")[0][0] == 1 and call('postgres', "update settings set photo_visibility='x' where id=1")[0] == 'err')
t.check("1.8 the change is written to the settings log", sql("select count(*) from settings_log where field ilike '%%visib%%'")[0][0] >= 1)

# 2. photographer list: own
setp(photo_visibility='own')
r = as_(cam1, "select photo_camera_list()")
t.check("2.1 own: photographer sees only their own two", r[0] == 'ok' and ids(r) == {c1a, c1b}, r)
t.check("2.2 own: no attendee photo and no other photographer's photo", pa1 not in ids(r) and c2a not in ids(r))
items = r[1][0][0]['items']
t.check("2.3 items carry id, kind, bytes, thumb, time, mine, by", all(set(i) == {'id','kind','bytes','thumb','at','mine','by'} for i in items))
t.check("2.4 mine is true and 'by' is the photographer's name", all(i['mine'] and i['by'] == 'Cam One' for i in items))
t.check("2.5 newest first", [i['at'] for i in items] == sorted([i['at'] for i in items], reverse=True))
r = adm("select photo_camera_list()")
t.check("2.6 admin sees all six", r[0] == 'ok' and ids(r) == {pa1, pa2, pc1, c1a, c1b, c2a})
t.check("2.7 admin: mine only for their own (none)", not any(i['mine'] for i in r[1][0][0]['items']))
t.check("2.8 gate cannot list", err(as_(gate, "select photo_camera_list()"), 'NOT_ALLOWED'))
t.check("2.9 a visitor login cannot list", err(as_(visitor, "select photo_camera_list()"), 'NOT_ALLOWED'))
t.check("2.10 anonymous cannot call the photographer list", anon("select photo_camera_list()")[0] == 'err')

# 3. photographers see all / everyone sees all
setp(photo_visibility='photographers')
r = as_(cam1, "select photo_camera_list()")
t.check("3.1 photographers mode: photographer sees all six", ids(r) == {pa1, pa2, pc1, c1a, c1b, c2a})
t.check("3.2 mine is only their own", {i['id'] for i in r[1][0][0]['items'] if i['mine']} == {c1a, c1b})
t.check("3.3 attendee photos carry no name (by is null)", all(i['by'] is None for i in r[1][0][0]['items'] if i['kind'] == 'public'))
r = anon("select photo_public_list(%s,%s)", (CODE['Asha'], PH['Asha']))
t.check("3.4 photographers mode: attendee still sees only their own", r[0] == 'ok' and ids(r) == {pa1, pa2})
setp(photo_visibility='all')
r = anon("select photo_public_list(%s,%s)", (CODE['Asha'], PH['Asha']))
t.check("3.5 all mode: attendee sees all six", ids(r) == {pa1, pa2, pc1, c1a, c1b, c2a})
t.check("3.6 mine is true only for their own", {i['id'] for i in r[1][0][0]['items'] if i['mine']} == {pa1, pa2})
t.check("3.7 photographers' names shown, attendees' not", all((i['by'] == ('Cam One' if i['id'] in (c1a, c1b) else 'Cam Two')) for i in r[1][0][0]['items'] if i['kind'] == 'camera') and all(i['by'] is None for i in r[1][0][0]['items'] if i['kind'] == 'public'))

# 4. attendee list: own, login rules
setp(photo_visibility='own')
r = anon("select photo_public_list(%s,%s)", (CODE['Asha'], PH['Asha']))
t.check("4.1 own: attendee Asha sees only her two", ids(r) == {pa1, pa2}, r)
r = anon("select photo_public_list(%s,%s)", (CODE['Carl'], PH['Carl']))
t.check("4.2 own: Carl sees only his one", ids(r) == {pc1})
r = anon("select photo_public_list(%s,%s)", (CODE['Ben'], PH['Ben']))
t.check("4.3 Ben (same booking as Asha, other phone) sees none of Asha's", r[0] == 'ok' and ids(r) == set())
t.check("4.4 wrong phone is refused", rv(anon("select photo_public_list(%s,%s)", (CODE['Asha'], '9999999999')))['error'] == 'MISMATCH')
t.check("4.5 wrong code is refused", rv(anon("select photo_public_list(%s,%s)", ('ZZZZZZZZ', PH['Asha'])))['error'] == 'MISMATCH')
t.check("4.6 junk input is refused", rv(anon("select photo_public_list(%s,%s)", ('x', 'y')))['error'] == 'MISMATCH')
t.check("4.7 the letter O counts as zero, like the Tickets page", rv(anon("select photo_public_list(%s,%s)", (CODE['Asha'].replace('0', 'o'), PH['Asha'])))['ok'] is True)
sql("update tickets set checked_in_at=null where id=%s", (str(A),))
r = anon("select photo_public_list(%s,%s)", (CODE['Asha'], PH['Asha']))
t.check("4.8 not Present yet: can still VIEW their photos", rv(r)['ok'] is True and ids(r) == {pa1, pa2})
t.check("4.9 not Present yet: cannot upload (unchanged rule)", rv(svc("select photo_reserve('public',null,%s,%s,%s,'jpg')", (CODE['Asha'], PH['Asha'], MB)))['error'] == 'NOT_PRESENT')
present(A)
setp(photos_on=False)
t.check("4.10 uploads switched off: viewing still works", rv(anon("select photo_public_list(%s,%s)", (CODE['Asha'], PH['Asha'])))['ok'] is True)
setp(photos_on=True)
sql("update bookings set status='pending' where booking_code=%s", (CODE['Carl'],))
t.check("4.11 unpaid booking cannot view", rv(anon("select photo_public_list(%s,%s)", (CODE['Carl'], PH['Carl'])))['error'] == 'NOT_PAID')
sql("update bookings set status='paid' where booking_code=%s", (CODE['Carl'],))
t.check("4.12 visitor with no ticket sees nothing and gets no photos", rv(anon("select photo_public_list(%s,%s)", (CODE['Carl'], PH['Asha'])))['error'] == 'MISMATCH')

# 5. paging and only stored photos
setp(photo_visibility='all')
r = adm("select photo_camera_list(null, 2)")
first = r[1][0][0]['items']
t.check("5.1 page size honoured", len(first) == 2 and r[1][0][0]['page'] == 2)
r2 = adm("select photo_camera_list(%s::timestamptz, 2)", (first[-1]['at'],))
t.check("5.2 next page continues after the last one", all(i['at'] < first[-1]['at'] for i in r2[1][0][0]['items']) and not ({i['id'] for i in first} & ids(r2)))
t.check("5.3 limit is capped at 48 and floored at 1", adm("select photo_camera_list(null, 9999)")[1][0][0]['page'] == 48 and adm("select photo_camera_list(null, 0)")[1][0][0]['page'] == 1)
rsv = rv(svc("select photo_reserve('camera',%s,null,null,%s,'jpg')", (str(cam1), MB)))
t.check("5.4 a photo that is only reserved (not stored) is not listed", rsv['id'] not in ids(adm("select photo_camera_list()")))
svc("select photo_fail(%s)", (rsv['id'],))
setp(photo_visibility='own')

# 6. originals
key = lambda pid: sql("select object_key from photos where id=%s", (pid,))[0][0]
t.check("6.1 admin may get any original", rv(svc("select photo_original_key(%s,%s)", (pa1, str(admin)))) == key(pa1))
t.check("6.2 photographer gets their own original", rv(svc("select photo_original_key(%s,%s)", (c1a, str(cam1)))) == key(c1a))
t.check("6.3 own mode: photographer cannot get another photographer's", rv(svc("select photo_original_key(%s,%s)", (c2a, str(cam1)))) is None)
t.check("6.4 own mode: photographer cannot get an attendee's", rv(svc("select photo_original_key(%s,%s)", (pa1, str(cam1)))) is None)
setp(photo_visibility='photographers')
t.check("6.5 photographers mode: photographer gets anyone's", rv(svc("select photo_original_key(%s,%s)", (pa1, str(cam1)))) == key(pa1))
setp(photo_visibility='own')
t.check("6.6 gate login gets nothing", rv(svc("select photo_original_key(%s,%s)", (c1a, str(gate)))) is None)
t.check("6.7 visitor login gets nothing", rv(svc("select photo_original_key(%s,%s)", (c1a, str(visitor)))) is None)
t.check("6.8 a removed photo gives nothing", (lambda: (sql("update photos set status='removed' where id=%s", (c2a,)), rv(svc("select photo_original_key(%s,%s)", (c2a, str(admin)))) is None)[1])())
sql("update photos set status='stored' where id=%s", (c2a,))
t.check("6.9 nobody but the service can call it", all(call(r, "select photo_original_key(%s,%s)", (pa1, str(admin)))[0] == 'err' for r in ('anon', 'authenticated')))

# 7. delete your own
t.check("7.1 photographer cannot delete another photographer's", rv(svc("select photo_remove_camera(%s,%s)", (c2a, str(cam1)))) is None and sql("select status from photos where id=%s", (c2a,))[0][0] == 'stored')
t.check("7.2 photographer cannot delete an attendee's", rv(svc("select photo_remove_camera(%s,%s)", (pa1, str(cam1)))) is None)
t.check("7.3 photographer deletes their own", rv(svc("select photo_remove_camera(%s,%s)", (c1b, str(cam1)))) == key(c1b) and sql("select status,thumb from photos where id=%s", (c1b,))[0] == ('removed', None))
t.check("7.4 deleting twice gives nothing the second time", rv(svc("select photo_remove_camera(%s,%s)", (c1b, str(cam1)))) is None)
t.check("7.5 gate login cannot delete", rv(svc("select photo_remove_camera(%s,%s)", (c1a, str(gate)))) is None)
t.check("7.6 attendee cannot delete a photographer's", rv(svc("select photo_remove_public(%s,%s,%s)", (c1a, CODE['Asha'], PH['Asha']))) is None)
t.check("7.7 attendee cannot delete someone else's", rv(svc("select photo_remove_public(%s,%s,%s)", (pc1, CODE['Asha'], PH['Asha']))) is None and sql("select status from photos where id=%s", (pc1,))[0][0] == 'stored')
t.check("7.8 wrong phone cannot delete", rv(svc("select photo_remove_public(%s,%s,%s)", (pa1, CODE['Asha'], '9999999999'))) is None)
t.check("7.9 attendee deletes their own", rv(svc("select photo_remove_public(%s,%s,%s)", (pa1, CODE['Asha'], PH['Asha']))) == key(pa1) and sql("select status from photos where id=%s", (pa1,))[0][0] == 'removed')
t.check("7.9b the deleted photo's preview picture is cleared too", sql("select thumb from photos where id=%s", (pa1,))[0][0] is None)
t.check("7.10 the freed space counts again", sql("select coalesce(sum(bytes_actual),0) from photos where kind='public' and status='stored'")[0][0] == 4 * MB)
t.check("7.11 deleted photos disappear from lists", pa1 not in ids(anon("select photo_public_list(%s,%s)", (CODE['Asha'], PH['Asha']))) and c1b not in ids(adm("select photo_camera_list()")))
t.check("7.12 own deletions are written to the settings log", sql("select count(*) from settings_log where field = 'photo removed (own)'")[0][0] == 2)
t.check("7.13 nobody but the service can call the delete functions", all(call(r, "select photo_remove_camera(%s,%s)", (c1a, str(cam1)))[0] == 'err' for r in ('anon', 'authenticated')) and all(call(r, "select photo_remove_public(%s,%s,%s)", (pa2, CODE['Asha'], PH['Asha']))[0] == 'err' for r in ('anon', 'authenticated')))

# 8. preview picture must be a plain image
bad = rv(svc("select photo_reserve('camera',%s,null,null,%s,'jpg')", (str(cam1), MB)))
t.check("8.1 a preview with markup is refused by the database", svc("select photo_confirm(%s,%s,%s)", (bad['id'], MB, 'data:image/jpeg;base64,AA" onerror="x'))[0] == 'err')
t.check("8.2 a plain jpeg preview is accepted", rv(svc("select photo_confirm(%s,%s,%s)", (bad['id'], MB, 'data:image/jpeg;base64,/9j/4AAQ+=')))['ok'] is True)
t.check("8.3 svg previews are refused", (lambda r: svc("update photos set thumb=%s where id=%s", ('data:image/svg+xml;base64,AAAA', r)))(bad['id'])[0] == 'err')

# 9. nothing else broke
t.check("9.1 the old status functions still work", rv(as_(cam1, "select photo_camera_status()"))['on'] is True and rv(anon("select photo_public_status(%s,%s)", (CODE['Asha'], PH['Asha'])))['ok'] is True)
t.check("9.2 admin summary still works", adm("select admin_photo_summary()")[0] == 'ok')
t.check("9.3 admin settings function still works", adm("select admin_set_photo_settings(p_mode := 'present')")[0] == 'ok')
t.check("9.4 applying the file twice is harmless", subprocess.run(["psql","-h","/tmp","-p","5544","-q","-d","postgres","-U","postgres","-v","ON_ERROR_STOP=1","-f",R22],capture_output=True,text=True).returncode == 0)
t.report("r2_22 photo gallery")
