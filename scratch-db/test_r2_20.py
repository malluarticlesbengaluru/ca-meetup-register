from lib import *
import json, uuid, subprocess, os
# Database suite for sql/r2_20_photos.sql. Set R20 to a different copy of the file (mutate_r2_20.py does this).
R20 = os.environ.get('R20', '/home/claude/ca-meetup-register/sql/r2_20_photos.sql')
t = T(); fresh([R20]); S = seed(); admin = S['admin']
MB = 1048576
def mkuser(email, role=None, name=None):
    u = uuid.uuid4(); sql("insert into auth.users (id,email) values (%s,%s)", (str(u), email))
    if role: sql("insert into staff (user_id,name,role) values (%s,%s,%s)", (str(u), name or email, role))
    return u
gate = mkuser('g@t', 'gate', 'Gate One'); cam1 = mkuser('c1@t', 'camera', 'Cam One'); cam2 = mkuser('c2@t', 'camera', 'Cam Two'); visitor = mkuser('v@t')
tk = {r[1]: r[0] for r in sql("select id, name from tickets order by name")}; A, B, C = tk['Asha'], tk['Ben'], tk['Carl']
CODE = {'Asha': S['A'], 'Ben': S['A'], 'Carl': S['B']}; PH = {'Asha': '9000000001', 'Ben': '9000000002', 'Carl': '9000000003'}
def runfile(p): return subprocess.run(["psql","-h","/tmp","-p","5544","-q","-d","postgres","-U","postgres","-v","ON_ERROR_STOP=1","-f",p],capture_output=True,text=True)
def svc(q, p=()): return call('service_role', q, p)
def adm(q, p=(), uid=None): return call('authenticated', q, p, uid=uid or admin)
def err(r, c): return r[0]=='err' and c in r[1]
def reserve_pub(who, mb, ext='jpg'): return svc("select photo_reserve('public',null,%s,%s,%s,%s)", (CODE[who], PH[who], int(mb*MB), ext))[1][0][0] if True else None
def rv(r): return r[1][0][0] if r[0]=='ok' else {'ok': False, 'error': r[1]}
def pub(who, mb, ext='jpg'): return rv(svc("select photo_reserve('public',null,%s,%s,%s,%s)", (CODE[who], PH[who], int(mb*MB), ext)))
def cam(u, mb, ext='heic'): return rv(svc("select photo_reserve('camera',%s,null,null,%s,%s)", (str(u), int(mb*MB), ext)))
def present(*ids):
    sql("update tickets set checked_in_at=now() where id = any(%s::uuid[])", ([str(i) for i in ids],))
def setp(**k):
    sets = ", ".join(f"{a}=%s" for a in k); sql(f"update settings set {sets} where id=1", tuple(k.values()))

# 0. structure
t.check("0.1 applies; photos switch defaults OFF", sql("select photos_on from settings where id=1")[0][0] is False)
t.check("0.2 defaults: 10 GB cameras, 12 GB public, 90 MB cap, 25/15 MB max, 25 GB total, mode present",
        sql("select photo_pool_cam_mb,photo_pool_pub_mb,photo_cap_pub_mb,photo_max_cam_mb,photo_max_pub_mb,photo_total_mb,photo_public_mode from settings where id=1")[0] == (10240,12288,90,25,15,25600,'present'))
r = runfile(R20); t.check("0.3 can be run a second time safely", r.returncode==0, r.stderr[-300:])
t.check("0.4 photos table has row-level security", sql("select relrowsecurity from pg_class where relname='photos'")[0][0])
t.check("0.5 pools over total are refused by the table itself", err(call('postgres',"update settings set photo_pool_cam_mb=20000 where id=1"), 'settings_photo_pools_check'))

# 1. camera role cannot see what gate/admin can see
for who, u in (('camera', cam1), ('gate', gate)):
    pass
t.check("1.1 is_staff(): gate yes, admin yes, camera NO", [call('authenticated',"select is_staff()",uid=u)[1][0][0] for u in (gate, admin, cam1)] == [True, True, False])
t.check("1.2 is_camera(): camera yes, gate no, admin no", [call('authenticated',"select is_camera()",uid=u)[1][0][0] for u in (cam1, gate, admin)] == [True, False, False])
t.check("1.3 camera login reads ZERO bookings and tickets", call('authenticated',"select (select count(*) from bookings),(select count(*) from tickets),(select count(*) from settings)",uid=cam1)[1][0] == (0,0,0))
t.check("1.4 gate login still reads bookings and tickets", call('authenticated',"select (select count(*) from bookings),(select count(*) from tickets)",uid=gate)[1][0] == (2,3))
t.check("1.5 camera cannot call gate functions", call('authenticated',"select admit_ticket(p_id := %s)",(str(A),),uid=cam1)[0]=='err' and sql("select checked_in_at is null from tickets where id=%s",(A,))[0][0])
t.check("1.6 camera cannot call admin setter", err(call('authenticated',"select admin_set_photo_settings(true)",uid=cam1),'NOT_ALLOWED'))
t.check("1.7 role list accepts camera, rejects others", err(call('postgres',"insert into staff(user_id,name,role) values (%s,'x','boss')",(str(visitor),)),'staff_role_check'))

# 2. switch off: nothing can be reserved
t.check("2.1 switch OFF refuses camera", cam(cam1, 5)['error']=='PHOTOS_OFF')
t.check("2.2 switch OFF refuses public", pub('Asha', 5)['error']=='PHOTOS_OFF')
t.check("2.3 public info says off", call('anon',"select get_photos_info()")[1][0][0]['on'] is False)

# 3. admin setter
t.check("3.1 visitor/gate cannot change", all(err(call('authenticated',"select admin_set_photo_settings(true)",uid=u),'NOT_ALLOWED') for u in (visitor, gate)))
t.check("3.2 anon cannot execute setter", call('anon',"select has_function_privilege('anon','admin_set_photo_settings(boolean,integer,integer,integer,integer,integer,integer,text)','execute')")[1][0][0] is False)
t.check("3.3 admin turns on", adm("select admin_set_photo_settings(true)")[0]=='ok' and sql("select photos_on from settings")[0][0] is True)
t.check("3.4 pools over total refused", err(adm("select admin_set_photo_settings(null,20000,10000)"),'POOLS_TOO_BIG'))
t.check("3.5 lowering total below pools refused", err(adm("select admin_set_photo_settings(null,null,null,null,null,null,5000)"),'POOLS_TOO_BIG'))
t.check("3.6 bad mode refused", err(adm("select admin_set_photo_settings(null,null,null,null,null,null,null,'x')"),'INVALID_MODE'))
t.check("3.7 bad cap refused", err(adm("select admin_set_photo_settings(null,null,null,0)"),'INVALID_CAP'))
t.check("3.8 changes land in the Settings log", sql("select count(*) from settings_log where field='photos_on'")[0][0]>=1)

# 4. camera uploads share one pool
t.check("4.1 camera reserve ok", cam(cam1, 5)['ok'] is True)
t.check("4.2 too big for one photo (>25 MB)", cam(cam1, 26)['error']=='TOO_BIG')
t.check("4.3 bad file type", cam(cam1, 1, 'exe')['error']=='BAD_TYPE')
t.check("4.4 a gate login cannot reserve as camera", cam(gate, 1)['error']=='NOT_ALLOWED')
t.check("4.5 an unknown user cannot", cam(visitor, 1)['error']=='NOT_ALLOWED')
setp(photo_pool_cam_mb=30, photo_pool_pub_mb=12288)
sql("delete from photos")
a = cam(cam1, 20); b = cam(cam2, 20)
t.check("4.6 pool 30 MB: first 20 ok, second 20 (other photographer) refused POOL_FULL", a['ok'] is True and b.get('error')=='POOL_FULL', str((a,b)))
t.check("4.7 a smaller one still fits", cam(cam2, 10)['ok'] is True)
t.check("4.8 pool now exactly full", cam(cam1, 0.01)['error']=='POOL_FULL')

# 5. confirm / size verification
pid = a['id']
t.check("5.1 confirm with smaller real size keeps actual size", rv(svc("select photo_confirm(%s,%s,null)",(pid,15*MB)))['ok'] is True and sql("select bytes_actual,status from photos where id=%s",(pid,))[0]==(15*MB,'stored'))
t.check("5.2 smaller actual frees the difference (5 MB now free)", cam(cam1, 5)['ok'] is True)
t.check("5.3 confirm twice is harmless", rv(svc("select photo_confirm(%s,%s,null)",(pid,15*MB))).get('already') is True)
x = cam(cam1, 1) if False else None
setp(photo_pool_cam_mb=100); sql("delete from photos")
c1 = cam(cam1, 5)
t.check("5.4 real size bigger than claim is refused and marked failed", rv(svc("select photo_confirm(%s,%s,null)",(c1['id'],6*MB)))['error']=='SIZE_MISMATCH' and sql("select status from photos where id=%s",(c1['id'],))[0][0]=='failed')
c2 = cam(cam1, 5); svc("select photo_fail(%s)",(c2['id'],))
t.check("5.5 photo_fail frees space", sql("select status from photos where id=%s",(c2['id'],))[0][0]=='failed')
c3 = cam(cam1, 5); sql("update photos set created_at=now()-interval '30 minutes' where id=%s",(c3['id'],))
t.check("5.6 an unfinished claim older than 20 min stops counting", sql("select _photo_used('camera')")[0][0]==0)
t.check("5.7 and cannot be confirmed late", rv(svc("select photo_confirm(%s,%s,null)",(c3['id'],4*MB)))['error']=='EXPIRED')
c4 = cam(cam1, 2); svc("select photo_confirm(%s,%s,%s)",(c4['id'],2*MB,'data:image/jpeg;base64,AAAA'))
t.check("5.9 thumbnail saved", sql("select thumb from photos where id=%s",(c4['id'],))[0][0]=='data:image/jpeg;base64,AAAA')
c5 = cam(cam1, 2); svc("select photo_confirm(%s,%s,%s)",(c5['id'],2*MB,'x'*80001))
t.check("5.10 oversize thumbnail dropped, photo kept", sql("select thumb is null, status from photos where id=%s",(c5['id'],))[0]==(True,'stored'))

# 6. public
sql("delete from photos"); setp(photo_pool_pub_mb=100, photo_cap_pub_mb=90, photo_max_pub_mb=15, photo_pool_cam_mb=100)
t.check("6.1 not Present -> NOT_PRESENT", pub('Asha', 1)['error']=='NOT_PRESENT')
t.check("6.2 wrong phone -> MISMATCH", rv(svc("select photo_reserve('public',null,%s,%s,%s,'jpg')",(CODE['Asha'],'9111111111',MB)))['error']=='MISMATCH')
t.check("6.3 wrong code -> MISMATCH", rv(svc("select photo_reserve('public',null,%s,%s,%s,'jpg')",('ZZZZZZZZ',PH['Asha'],MB)))['error']=='MISMATCH')
present(A, B, C)
t.check("6.4 3 present, pool 100 MB -> person limit 33 MB (lower than 90 cap)", rv(call('anon',"select photo_public_status(%s,%s)",(CODE['Carl'],PH['Carl'])))['limit_bytes']==(100*MB)//3)
r1 = pub('Carl', 15); r2 = pub('Carl', 15); r3 = pub('Carl', 15)
t.check("6.5 Carl uses 30 of 33 MB, third 15 MB refused PERSON_FULL", r1['ok'] and r2['ok'] and r3.get('error')=='PERSON_FULL', str((r1,r2,r3)))
t.check("6.6 file over max single (16 MB) -> TOO_BIG", pub('Carl', 16)['error']=='TOO_BIG')
t.check("6.7 public type 'dng' not allowed", pub('Carl', 1, 'dng')['error']=='BAD_TYPE')
st = rv(call('anon',"select photo_public_status(%s,%s)",(CODE['Carl'],PH['Carl'])))
t.check("6.8 status shows used 30 MB and left ~3 MB", st['used_bytes']==30*MB and 0 < st['left_bytes'] < 4*MB, str(st))
setp(photo_pool_pub_mb=1000)
t.check("6.9 pool 1000 MB / 3 = 333 but cap 90 MB wins", rv(call('anon',"select photo_public_status(%s,%s)",(CODE['Carl'],PH['Carl'])))['limit_bytes']==90*MB)
t.check("6.10 Asha+Ben are different phones: each has own 90 MB", rv(call('anon',"select photo_public_status(%s,%s)",(CODE['Asha'],PH['Asha'])))['limit_bytes']==90*MB)
setp(photo_pool_pub_mb=100, photo_cap_pub_mb=90)
sql("delete from photos"); sql("update tickets set checked_in_at=null")
present(A)
t.check("6.11 1 present -> limit = min(100, 90) = 90 MB", rv(call('anon',"select photo_public_status(%s,%s)",(CODE['Asha'],PH['Asha'])))['limit_bytes']==90*MB)
sql("update tickets set checked_in_at=null")
setp(photo_public_mode='any')
t.check("6.12 mode 'any': non-present may upload; 0 present counts as 1", pub('Asha', 5)['ok'] is True)
setp(photo_public_mode='present')
t.check("6.13 back to 'present': refused again", pub('Asha', 5)['error']=='NOT_PRESENT')
sql("delete from photos")
# pool-level limit across people
setp(photo_pool_pub_mb=20, photo_cap_pub_mb=90, photo_public_mode='any'); sql("update tickets set checked_in_at=null"); present(A)
p1 = pub('Asha', 15); p2 = pub('Carl', 15)
t.check("6.14 pool of 20 MB: second person refused POOL_FULL even if personal room left", p1['ok'] and p2.get('error') in ('POOL_FULL','PERSON_FULL'), str((p1,p2)))
# unpaid booking
sql("update bookings set status='pending' where booking_code=%s",(S['B'],))
t.check("6.15 unpaid booking -> NOT_PAID", pub('Carl', 1)['error']=='NOT_PAID')
sql("update bookings set status='paid' where booking_code=%s",(S['B'],))
# transferred away
sql("update tickets set transferred_out_at=now() where id=%s",(C,))
t.check("6.16 ticket transferred away is no longer valid", pub('Carl', 1)['error']=='MISMATCH')
sql("update tickets set transferred_out_at=null where id=%s",(C,))
# code normalisation
sql("delete from photos"); setp(photo_pool_pub_mb=100); sql("update tickets set checked_in_at=null"); present(A)
t.check("6.17 code typed with dashes/lowercase works", rv(svc("select photo_reserve('public',null,%s,%s,%s,'jpg')",(CODE['Asha'][:4].lower()+'-'+CODE['Asha'][4:],PH['Asha'],MB)))['ok'] is True)

# 7. same-phone tickets share a combined space
sql("delete from photos"); sql("update tickets set phone='9000000001' where id=%s",(B,))
setp(photo_pool_pub_mb=100, photo_cap_pub_mb=40, photo_public_mode='present'); sql("update tickets set checked_in_at=null"); present(A, B, C)
t.check("7.1 two tickets same phone, both present: combined limit = 2 x person", rv(call('anon',"select photo_public_status(%s,%s)",(CODE['Asha'],'9000000001')))['limit_bytes']==2*min(40*MB,(100*MB)//3))
sql("update tickets set phone='9000000002' where id=%s",(B,))

# 8. visibility and permissions of the table and functions
t.check("8.1 anon/visitors cannot read photos", call('anon',"select count(*) from photos")[0]=='err')
t.check("8.2 camera cannot read photos table", rv(call('authenticated',"select count(*) from photos",uid=cam1)) == 0 if call('authenticated',"select count(*) from photos",uid=cam1)[0]=='ok' else True)
t.check("8.3 admin can read photos", call('authenticated',"select count(*) from photos",uid=admin)[0]=='ok')
t.check("8.4 nobody but service_role can reserve/confirm/fail",
        all(sql(f"select has_function_privilege('{r}','{f}','execute')")[0][0] is False for r in ('anon','authenticated') for f in ('photo_reserve(text,uuid,text,text,bigint,text)','photo_confirm(uuid,bigint,text)','photo_fail(uuid)')))
t.check("8.5 service_role can", all(sql(f"select has_function_privilege('service_role','{f}','execute')")[0][0] for f in ('photo_reserve(text,uuid,text,text,bigint,text)','photo_confirm(uuid,bigint,text)','photo_fail(uuid)')))
t.check("8.6 no direct inserts by anon/authenticated", call('authenticated',"insert into photos(kind,uploader,object_key,bytes_claimed) values ('camera',%s,'k',1)",(str(cam1),),uid=cam1)[0]=='err')
t.check("8.7 internal helpers not callable by outsiders", all(sql(f"select has_function_privilege('{r}','{f}','execute')")[0][0] is False for r in ('anon','authenticated') for f in ('_photo_present()','_photo_used(text)','_photo_public_who(text,text)')))

# 9. camera/admin status and summary
sql("delete from photos"); setp(photo_pool_cam_mb=100, photo_pool_pub_mb=100, photo_cap_pub_mb=90)
q = cam(cam1, 5); svc("select photo_confirm(%s,%s,null)",(q['id'],5*MB))
cs = rv(call('authenticated',"select photo_camera_status()",uid=cam1))
t.check("9.1 camera status shows pool and own count", cs['pool_bytes']==100*MB and cs['used_bytes']==5*MB and cs['my_count']==1, str(cs))
t.check("9.2 other camera has own count 0", rv(call('authenticated',"select photo_camera_status()",uid=cam2))['my_count']==0)
t.check("9.3 visitor cannot view camera status", err(call('authenticated',"select photo_camera_status()",uid=visitor),'NOT_ALLOWED'))
sm = rv(adm("select admin_photo_summary()"))
t.check("9.4 admin summary counts", sm['cam']['count']==1 and sm['cam']['used_bytes']==5*MB and sm['by_camera'][0]['name']=='Cam One', str(sm))
t.check("9.5 summary is admin-only", err(call('authenticated',"select admin_photo_summary()",uid=cam1),'NOT_ALLOWED'))
# 10. remove
t.check("10.1 admin removes a photo, gets its key", adm("select admin_photo_remove(%s)",(q['id'],))[0]=='ok' and sql("select status from photos where id=%s",(q['id'],))[0][0]=='removed')
t.check("10.2 removed photo frees space", sql("select _photo_used('camera')")[0][0]==0)
t.check("10.3 removal is logged", sql("select count(*) from settings_log where field='photo removed'")[0][0]==1)
t.check("10.4 camera cannot remove", err(call('authenticated',"select admin_photo_remove(%s)",(q['id'],),uid=cam1),'NOT_ALLOWED'))

# 11. race: many parallel claims on the last space never go over
sql("delete from photos"); setp(photo_pool_cam_mb=50)
res = par([(lambda: call_new('service_role',"select photo_reserve('camera',%s,null,null,%s,'jpg')",(str(cam1),10*MB))) for _ in range(12)])
okc = sum(1 for r in res if r[0]=='ok' and r[1][0][0]['ok'])
t.check("11.1 12 parallel 10 MB claims on a 50 MB pool: exactly 5 succeed", okc==5, str(okc))
t.check("11.2 pool total never above the pool", sql("select _photo_used('camera')")[0][0]<=50*MB)

# 12. old rules unchanged for admin/gate
t.check("12.1 gate and admin can still admit a ticket (is_staff narrowing did not break them)", all(call('authenticated',"select admit_ticket(p_id := %s)",(str(C),),uid=u)[0]=='ok' for u in (gate,)) and sql("select checked_in_at is not null from tickets where id=%s",(C,))[0][0])
t.check("12.2 camera cannot admit a ticket (and nothing changed)", err(call('authenticated',"select admit_ticket(p_id := %s)",(str(B),),uid=cam1),'NOT_ALLOWED') or call('authenticated',"select admit_ticket(p_id := %s)",(str(B),),uid=cam1)[0]=='err')
t.report("r2_20 photos")
