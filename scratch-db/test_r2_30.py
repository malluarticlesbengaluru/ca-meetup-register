from lib import *
import json, uuid, os, subprocess, re
# Database suite for sql/r2_29_space_qr.sql (layered on r2_20 ... r2_28, 29). R29 = a different copy of the file (mutate_r2_29.py).
D = '/home/claude/ca-meetup-register/sql/'
R30 = os.environ.get('R30', D + 'r2_30_space_by_booking.sql')
t = T(); fresh([D+'r2_20_photos.sql', D+'r2_22_photo_gallery.sql', D+'r2_24_originals_admin_only.sql', D+'r2_25_download_allowlist.sql', D+'r2_26_photo_previews.sql', D+'r2_27_videos.sql', D+'r2_28_space_sharing.sql', D+'r2_29_space_qr.sql', R30]); S = seed(); admin = S['admin']
MB = 1048576
tk = {r[1]: r[0] for r in sql("select id, name from tickets order by name")}; A, B, C = tk['Asha'], tk['Ben'], tk['Carl']
CODE = {'Asha': S['A'], 'Ben': S['A'], 'Carl': S['B']}; PH = {'Asha': '9000000001', 'Ben': '9000000002', 'Carl': '9000000003'}
def anon(q, p=()): return call('anon', q, p)
def as_(u, q, p=()): return call('authenticated', q, p, uid=u)
def rv(r): return r[1][0][0] if r[0] == 'ok' else {'ok': False, 'error': r[1]}
def setp(**k):
    sets = ", ".join(f"{a}=%s" for a in k); sql(f"update settings set {sets} where id=1", tuple(k.values()))
def present(*ids): sql("update tickets set checked_in_at=now() where id = any(%s::uuid[])", ([str(i) for i in ids],))
def peek(c): return rv(anon("select space_booking_peek(%s)", (c,)))
def gb(a, to, kind, mb): return rv(anon("select space_give_booking(%s,%s,%s,%s,%s)", (CODE[a], PH[a], to, kind, mb)))
def pst(a): return rv(anon("select photo_public_status(%s,%s)", (CODE[a], PH[a])))
def vst(a): return rv(anon("select video_public_status(%s,%s)", (CODE[a], PH[a])))
setp(photos_on=True, videos_on=True, photo_public_mode='present', photo_max_pub_mb=100, video_cap_mb=100, photo_pool_pub_mb=12288, photo_cap_pub_mb=90)
present(A, B, C)


# 1. peek
t.check("1.1 peek shows the name of the person on the oldest ticket of the booking", peek(CODE['Carl']) == {'ok': True, 'name': 'Carl'} and peek(CODE['Asha'])['name'] in ('Asha', 'Ben'), peek(CODE['Asha']))
first_a = peek(CODE['Asha'])['name']
t.check("1.2 only name is shown (no phone, no ids)", set(peek(CODE['Carl'])) == {'ok', 'name'})
t.check("1.3 lower case, spaces and dashes are fine", peek(CODE['Carl'][:4].lower() + ' - ' + CODE['Carl'][4:].lower())['ok'] is True)
t.check("1.4 unknown, empty, null, too short", all(peek(x).get('error') == 'TO_NOT_FOUND' for x in ('ZZZZZZZZ', '', None, 'AB', '%%%')))
sql("update bookings set status='pending' where booking_code=%s", (CODE['Carl'],))
t.check("1.5 unpaid booking is not found", peek(CODE['Carl'])['error'] == 'TO_NOT_FOUND')
sql("update bookings set status='paid' where booking_code=%s", (CODE['Carl'],))

# 2. give by booking id only (no phone)
r = gb('Asha', CODE['Carl'], 'photo', 40)
t.check("2.1 give with Booking ID only: Asha 50, Carl 130", r['ok'] and pst('Asha')['limit_bytes'] == 50*MB and pst('Carl')['limit_bytes'] == 130*MB, r)
t.check("2.2 shows in the admin list", rv(call('authenticated', "select admin_space_transfers()", uid=admin))['items'][0]['to'] == 'Carl')
t.check("2.3 log line has both names", sql("select old_value from settings_log where field='space given (photos)' order by id desc limit 1")[0][0] == 'Asha > Carl')
t.check("2.4 video gift, separate amount", gb('Asha', CODE['Carl'], 'video', 25)['ok'] and vst('Asha')['limit_bytes'] == 75*MB and vst('Carl')['limit_bytes'] == 125*MB and pst('Asha')['limit_bytes'] == 50*MB)
t.check("2.5 too much: refused with the amount that can be given", (lambda x: x['error'] == 'TOO_MUCH' and x['give_bytes'] == 50*MB)(gb('Asha', CODE['Carl'], 'photo', 51)))
t.check("2.6 bad amount and bad kind", all(gb('Asha', CODE['Carl'], 'photo', x)['error'] == 'BAD_AMOUNT' for x in (0, -1, 100001, None)) and gb('Asha', CODE['Carl'], 'gif', 5)['error'] == 'BAD_KIND')
t.check("2.7 own booking (same person) refused", gb('Carl', CODE['Carl'], 'photo', 5)['error'] == 'SAME_PERSON')
other = 'Ben' if first_a == 'Asha' else 'Asha'
t.check("2.8 a different person on the same booking can give to the booking's first person", gb(other, CODE['Asha'], 'photo', 5)['ok'] is True)
t.check("2.9 the first person of that booking cannot give to their own booking", gb(first_a, CODE['Asha'], 'photo', 5)['error'] == 'SAME_PERSON')
t.check("2.10 unknown Booking ID", gb('Asha', 'ZZZZZZZZ', 'photo', 5)['error'] == 'TO_NOT_FOUND')
t.check("2.11 giver wrong login", rv(anon("select space_give_booking(%s,%s,%s,'photo',5)", (CODE['Asha'], '9999999999', CODE['Carl'])))['error'] == 'MISMATCH')
t.check("2.12 giver not Present", (sql("update tickets set checked_in_at=null where id=%s", (str(B),)), gb('Ben', CODE['Carl'], 'photo', 5)['error'] == 'NOT_PRESENT', present(B))[1])
sql("update bookings set status='pending' where booking_code=%s", (CODE['Carl'],))
t.check("2.13 friend's booking unpaid: refused", gb('Asha', CODE['Carl'], 'photo', 5)['error'] == 'TO_NOT_FOUND')
sql("update bookings set status='paid' where booking_code=%s", (CODE['Carl'],))
setp(space_sharing_on=False)
t.check("2.14 sharing off: refused", gb('Asha', CODE['Carl'], 'photo', 5)['error'] == 'SHARING_OFF')
setp(space_sharing_on=True, videos_on=False)
t.check("2.15 video off: refused for video, fine for photo", gb('Asha', CODE['Carl'], 'video', 5)['error'] == 'FEATURE_OFF' and gb('Asha', CODE['Carl'], 'photo', 5)['ok'])
setp(videos_on=True)
t.check("2.16 take-back works for a gift by Booking ID", (lambda g: rv(anon("select space_return(%s,%s,%s)", (CODE['Asha'], PH['Asha'], g['id'])))['ok'])(gb('Asha', CODE['Carl'], 'photo', 3)))
r17 = gb('Carl', CODE['Asha'], 'photo', 100)
t.check("2.17 received space can be passed on (Carl gives 100 MB, of which 90 were received)", r17['ok'] is True, r17)

# 3. permissions
for f in ("space_booking_peek(text)", "space_give_booking(text,text,text,text,integer)"):
    t.check(f"3.1 {f}: website can call", sql(f"select has_function_privilege('anon','public.{f}','execute')")[0][0] is True)
t.check("3.2 _space_booking_all: nobody can call", all(sql(f"select has_function_privilege('{x}','public._space_booking_all(text)','execute')")[0][0] is False for x in ('anon', 'authenticated', 'service_role')))
p = subprocess.run(['psql','-h','/tmp','-p','5544','-q','-d','postgres','-U','postgres','-v','ON_ERROR_STOP=1','-f',R30],capture_output=True,text=True)
t.check("4.1 running r2_30 again succeeds", p.returncode == 0, p.stderr[:200])
t.report("r2_30 space by booking id")
