from lib import *
import json, uuid, os, subprocess
# Database suite for sql/r2_32_shared_attendee_pool.sql (layered on r2_20 ... r2_31, 32). R32 = a different copy of the file (for deliberate-mistake checks).
D = '/home/claude/ca-meetup-register/sql/'
R32 = os.environ.get('R32', D + 'r2_32_shared_attendee_pool.sql')
t = T(); fresh([D+'r2_20_photos.sql', D+'r2_22_photo_gallery.sql', D+'r2_24_originals_admin_only.sql', D+'r2_25_download_allowlist.sql', D+'r2_26_photo_previews.sql', D+'r2_27_videos.sql', D+'r2_28_space_sharing.sql', D+'r2_29_space_qr.sql', D+'r2_30_space_by_booking.sql', R32]); S = seed(); admin = S['admin']
MB = 1048576
tk = {r[1]: r[0] for r in sql("select id, name from tickets order by name")}; A, B, C = tk['Asha'], tk['Ben'], tk['Carl']
CODE = {'Asha': S['A'], 'Ben': S['A'], 'Carl': S['B']}; PH = {'Asha': '9000000001', 'Ben': '9000000002', 'Carl': '9000000003'}
def anon(q, p=()): return call('anon', q, p)
def as_(u, q, p=()): return call('authenticated', q, p, uid=u)
def rv(r): return r[1][0][0] if r[0] == 'ok' else {'ok': False, 'error': r[1]}
def setp(**k):
    sets = ", ".join(f"{a}=%s" for a in k); sql(f"update settings set {sets} where id=1", tuple(k.values()))
def present(*ids): sql("update tickets set checked_in_at=now() where id = any(%s::uuid[])", ([str(i) for i in ids],))
def pst(a): return rv(anon("select photo_public_status(%s,%s)", (CODE[a], PH[a])))
def vst(a): return rv(anon("select video_public_status(%s,%s)", (CODE[a], PH[a])))
def pres(a, mb, acc=None, ext='jpg'): return rv(call('service_role', "select photo_reserve('public',null,%s,%s,%s,%s,%s::int[])", (CODE[a], PH[a], int(mb*MB), ext, acc)))
def vres(a, mb, acc=None): return rv(call('service_role', "select video_reserve(%s,%s,%s,'mp4',%s::int[])", (CODE[a], PH[a], int(mb*MB), acc)))
def give(a, to, kind, mb): return rv(anon("select space_give_booking(%s,%s,%s,%s,%s,null)", (CODE[a], PH[a], to, kind, mb)))
def adm(q, p=()): return as_(admin, q, p)
setp(photos_on=True, videos_on=True, photo_public_mode='present', photo_max_pub_mb=100, video_max_mb=150, video_cap_mb=100, photo_pool_pub_mb=12288, photo_cap_pub_mb=90, video_pool_mb=20480)
present(A, B, C)

# 1. the switch is OFF by default and nothing changes
t.check("1.1 columns exist with defaults: off, 75 GB, 500 MB", sql("select attendee_shared, attendee_pool_mb, attendee_cap_mb from settings")[0] == (False, 76800, 500))
t.check("1.2 off: photo limit is the old photo cap (90 MB), video limit the old video cap (100 MB), flag false", pst('Asha')['limit_bytes'] == 90*MB and vst('Asha')['limit_bytes'] == 100*MB and pst('Asha')['shared'] is False and vst('Asha')['shared'] is False)
r1, r2 = pres('Asha', 10), vres('Asha', 10)
t.check("1.3 off: keys are still public/ and video/ (even if the accounts list says 1,2,3)", r1['ok'] and r1['key'].startswith('public/') and r2['ok'] and r2['key'].startswith('video/') and pres('Asha', 1, [3])['key'].startswith('public/'), (r1, r2))
t.check("1.4 off: photo and video amounts stay separate (10 MB video does not touch the photo limit)", pst('Asha')['used_bytes'] == 11*MB and vst('Asha')['used_bytes'] == 10*MB)
t.check("1.5 old six-argument photo_reserve and four-argument video_reserve are gone (one version each)",
        sql("select to_regprocedure('public.photo_reserve(text,uuid,text,text,bigint,text)') is null, to_regprocedure('public.video_reserve(text,text,bigint,text)') is null")[0] == (True, True))
t.check("1.6 old-style call without the account list still works", rv(call('service_role', "select photo_reserve('public',null,%s,%s,%s,'jpg')", (CODE['Carl'], PH['Carl'], 1*MB)))['ok'] is True)
sql("delete from photos"); sql("delete from videos")

# 2. switch on: one pool, one limit, photos and videos together
setp(attendee_shared=True, attendee_pool_mb=600, attendee_cap_mb=500)       # 3 people Present: 600/3 = 200 MB each
p, v = pst('Asha'), vst('Asha')
t.check("2.1 on: photos and videos show the same limit (200 MB), nothing used, flag true", p['limit_bytes'] == v['limit_bytes'] == 200*MB and p['used_bytes'] == v['used_bytes'] == 0 and p['shared'] and v['shared'], (p, v))
t.check("2.2 the cap applies when it is lower than pool / people (cap 150 -> 150 MB)", (setp(attendee_cap_mb=150), pst('Asha')['limit_bytes'] == 150*MB, setp(attendee_cap_mb=500))[1])
r = pres('Asha', 100)
t.check("2.3 a 100 MB photo is accepted and the key is att/1/ (all accounts equal, lowest number wins)", r['ok'] and r['key'].startswith('att/1/'), r)
t.check("2.4 the photo counts for videos too: video status shows 100 MB used, 100 MB left", vst('Asha')['used_bytes'] == 100*MB and vst('Asha')['left_bytes'] == 100*MB)
r = vres('Asha', 80, [1, 2, 3])
t.check("2.5 an 80 MB video is accepted and goes to account 2 (account 1 holds 100 MB)", r['ok'] and r['key'].startswith('att/2/'), r)
t.check("2.6 now 20 MB are left for photos and for videos", pst('Asha')['left_bytes'] == 20*MB and vst('Asha')['left_bytes'] == 20*MB)
t.check("2.7 a 21 MB video and a 21 MB photo are refused: PERSON_FULL", vres('Asha', 21)['error'] == 'PERSON_FULL' and pres('Asha', 21)['error'] == 'PERSON_FULL')
t.check("2.8 exactly 20 MB still fits (photo)", pres('Asha', 20)['ok'] is True)
t.check("2.9 now nothing is left: photo and video both refused", pres('Asha', 1)['error'] == 'PERSON_FULL' and vres('Asha', 1)['error'] == 'PERSON_FULL')
t.check("2.10 the per-file limits still apply (a 101 MB photo is TOO_BIG, a 151 MB video TOO_BIG) even for someone with space", pres('Carl', 101)['error'] == 'TOO_BIG' and vres('Carl', 151)['error'] == 'TOO_BIG')
r = pres('Carl', 50, [1, 2, 3])
t.check("2.11 a third account is used when it holds the least: Carl's photo goes to att/3/", r['ok'] and r['key'].startswith('att/3/'), r)
t.check("2.12 only account 1 offered: att/1/; only account 3: att/3/; nonsense list: att/1/", pres('Ben', 5, [1])['key'].startswith('att/1/') and pres('Ben', 5, [3])['key'].startswith('att/3/') and pres('Ben', 5, [9])['key'].startswith('att/1/') and pres('Ben', 5, [])['key'].startswith('att/'))
acc = rv(adm("select admin_attendee_summary()"))
t.check("2.13 the admin summary adds the three accounts up to the pool use", sum(acc['accounts']) == acc['used_bytes'] and acc['used_bytes'] == sql("select (select coalesce(sum(coalesce(bytes_actual,bytes_claimed)),0) from photos where kind='public' and status in ('reserved','stored'))+(select coalesce(sum(coalesce(bytes_actual,bytes_claimed)),0) from videos where status in ('reserved','stored'))")[0][0], acc)

# 3. pool full
sql("delete from photos"); sql("delete from videos")
setp(attendee_pool_mb=300, attendee_cap_mb=500)       # 100 MB each, pool 300
t.check("3.1 pool 300 MB, 3 present: 100 MB each", pst('Carl')['limit_bytes'] == 100*MB)
pres('Asha', 100); pres('Carl', 100)
sql("update settings set attendee_pool_mb=150 where id=1")   # the admin lowered the pool below what is used; nothing is deleted
t.check("3.2 pool lowered below use: nobody can add, nothing is deleted, left is 0", pres('Ben', 5).get('error') == 'POOL_FULL' and pst('Ben')['left_bytes'] == 0 and sql("select count(*) from photos")[0][0] == 2)
sql("delete from photos"); setp(attendee_pool_mb=600)

# 4. gifts count for both kinds while the pool is shared
r = give('Asha', CODE['Carl'], 'photo', 40)
t.check("4.1 a gift made as 'photo' space: Carl's video limit grows too (240 MB), Asha's both shrink (160 MB)", r['ok'] and vst('Carl')['limit_bytes'] == 240*MB and pst('Carl')['limit_bytes'] == 240*MB and vst('Asha')['limit_bytes'] == 160*MB, r)
t.check("4.2 the Share screen says shared and gives the same amount for both kinds (Asha 160 MB)", (lambda o: o['shared'] is True and o['photo']['give_bytes'] == o['video']['give_bytes'] == 160*MB)(rv(anon("select space_overview(%s,%s)", (CODE['Asha'], PH['Asha'])))))
t.check("4.2b the Share screen's 'received/given' line is also combined (Carl: 40 MB received for photos and for videos)", (lambda o: o['photo']['net_bytes'] == o['video']['net_bytes'] == 40*MB)(rv(anon("select space_overview(%s,%s)", (CODE['Carl'], PH['Carl'])))))
t.check("4.3 give more than is left (Asha has 160, gives 161): refused with the combined amount", (lambda x: x['error'] == 'TOO_MUCH' and x['give_bytes'] == 160*MB)(give('Asha', CODE['Carl'], 'video', 161)))
gid = sql("select id from space_transfers order by created_at desc limit 1")[0][0]
t.check("4.4 take-back works while Carl has not used it", rv(anon("select space_return(%s,%s,%s)", (CODE['Asha'], PH['Asha'], str(gid))))['ok'] and pst('Carl')['limit_bytes'] == 200*MB)
give('Asha', CODE['Carl'], 'photo', 40)
setp(attendee_shared=False)
t.check("4.5 switch off again: the photo gift no longer adds to videos (video limit back to 100 MB, photo 90+40=130 MB)", vst('Carl')['limit_bytes'] == 100*MB and pst('Carl')['limit_bytes'] == 130*MB and vst('Carl')['shared'] is False)
sql("delete from space_transfers")

# 5. files saved under the old keys count in the account usage; photographers are unaffected
sql("delete from photos"); sql("delete from videos")
pres('Asha', 10); vres('Asha', 10)                          # switch is off: public/ and video/ keys
t.check("5.1 old keys: public/ counts for account 1, video/ for account 2", rv(adm("select admin_attendee_summary()"))['accounts'] == [10*MB, 10*MB, 0])
setp(attendee_shared=True)
r = vres('Ben', 5, [1, 2, 3])
t.check("5.2 a new file goes to the emptiest account (3), counting the old keys", r['ok'] and r['key'].startswith('att/3/'), r)
cam = uuid.uuid4(); sql("insert into auth.users (id,email) values (%s,'cam@test')", (str(cam),)); sql("insert into staff (user_id,name,role) values (%s,'Cam','camera')", (str(cam),))
r = rv(call('service_role', "select photo_reserve('camera',%s,null,null,%s,'jpg',null)", (str(cam), 3*MB)))
t.check("5.3 photographers are not affected: camera/ key, camera pool", r['ok'] and r['key'].startswith('camera/'), r)
sql("update photos set status='stored', bytes_actual=bytes_claimed where kind='camera'")
t.check("5.4 photographer photos are not counted in the attendee pool", rv(adm("select admin_attendee_summary()"))['photo_bytes'] == 10*MB)

# 6. admin function and permissions
t.check("6.1 admin sets pool 1000, cap 400 and the switch off; values saved, three log lines", (lambda: (adm("select admin_set_attendee_space(false, 1000, 400)"), sql("select attendee_shared, attendee_pool_mb, attendee_cap_mb from settings")[0] == (False, 1000, 400))[1])())
t.check("6.2 the log names the settings with before and after", sql("select field, old_value, new_value from settings_log where field like 'attendee%%' or field like 'shared attendee%%' order by id desc limit 3") and
        {x[0]: (x[1], x[2]) for x in sql("select field, old_value, new_value from settings_log where field like 'attendee%%' or field like 'shared attendee%%'")}.get('attendee shared space (MB)') == ('600', '1000'))
t.check("6.3 changing nothing writes no new log line", (lambda n: (adm("select admin_set_attendee_space(false, 1000, 400)"), sql("select count(*) from settings_log")[0][0] == n)[1])(sql("select count(*) from settings_log")[0][0]))
t.check("6.4 invalid values refused (pool -1, pool 10000001, cap 0, cap 100001)", all(adm("select admin_set_attendee_space(null, %s, %s)", x)[0] == 'err' for x in ((-1, None), (10000001, None), (None, 0), (None, 100001))))
t.check("6.5 a non-admin, a camera login and the website cannot change or read it", all(x[0] == 'err' for x in (as_(cam, "select admin_set_attendee_space(true, null, null)"), as_(cam, "select admin_attendee_summary()"), anon("select admin_set_attendee_space(true, null, null)"), anon("select admin_attendee_summary()"))))
t.check("6.6 the switch alone (null pool, null cap) changes only the switch", (lambda: (adm("select admin_set_attendee_space(true, null, null)"), sql("select attendee_shared, attendee_pool_mb, attendee_cap_mb from settings")[0] == (True, 1000, 400))[1])())
for f in ("admin_set_attendee_space(boolean,integer,integer)", "admin_attendee_summary()"):
    t.check(f"6.7 {f}: signed-in can call, website cannot", sql(f"select has_function_privilege('authenticated','public.{f}','execute'), has_function_privilege('anon','public.{f}','execute')")[0] == (True, False))
t.check("6.8 photo_reserve and video_reserve: only the Edge Function (service_role)", all(sql(f"select has_function_privilege('{x}','public.photo_reserve(text,uuid,text,text,bigint,text,integer[])','execute'), has_function_privilege('{x}','public.video_reserve(text,text,bigint,text,integer[])','execute')")[0] == (x == 'service_role',)*2 for x in ('anon', 'authenticated', 'service_role')))
t.check("6.9 helpers cannot be called by anyone", all(sql(f"select has_function_privilege('{x}','public.{f}','execute')")[0][0] is False for x in ('anon', 'authenticated', 'service_role') for f in ('_att_mine(uuid[])', '_att_used_all()', '_att_limit(integer,uuid)', '_att_acct_used(integer)', '_att_pick(integer[])')))
t.check("6.10 status functions are still callable by the website", all(sql(f"select has_function_privilege('anon','public.{f}','execute')")[0][0] is True for f in ('photo_public_status(text,text)', 'video_public_status(text,text)', 'space_overview(text,text)')))

# 7. a person not Present / wrong login still refused in shared mode
setp(attendee_shared=True, attendee_pool_mb=600)
sql("update tickets set checked_in_at=null where id=%s", (str(C),))
t.check("7.1 not Present: refused in shared mode too", pres('Carl', 1)['error'] == 'NOT_PRESENT' and vres('Carl', 1)['error'] == 'NOT_PRESENT')
t.check("7.2 wrong phone: MISMATCH", rv(call('service_role', "select photo_reserve('public',null,%s,'9999999999',%s,'jpg',null)", (CODE['Asha'], MB)))['error'] == 'MISMATCH')
present(C)
t.check("7.3 photos off or videos off still stops that kind", (setp(photos_on=False), pres('Asha', 1)['error'] == 'PHOTOS_OFF' and vres('Asha', 1)['ok'], setp(photos_on=True, videos_on=False), vres('Asha', 1)['error'] == 'VIDEOS_OFF', setp(videos_on=True))[1:4] == (True, None, True))

# 8. running the file again
p = subprocess.run(['psql','-h','/tmp','-p','5544','-q','-d','postgres','-U','postgres','-v','ON_ERROR_STOP=1','-f',R32],capture_output=True,text=True)
t.check("8.1 running r2_32 again succeeds, settings kept", p.returncode == 0 and sql("select attendee_pool_mb from settings")[0][0] == 600, p.stderr[:200])
t.report("r2_32 shared attendee pool")
