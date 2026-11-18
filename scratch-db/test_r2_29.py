from lib import *
import json, uuid, os, subprocess, re
# Database suite for sql/r2_29_space_qr.sql (layered on r2_20 ... r2_28, 29). R29 = a different copy of the file (mutate_r2_29.py).
D = '/home/claude/ca-meetup-register/sql/'
R29 = os.environ.get('R29', D + 'r2_29_space_qr.sql')
t = T(); fresh([D+'r2_20_photos.sql', D+'r2_22_photo_gallery.sql', D+'r2_24_originals_admin_only.sql', D+'r2_25_download_allowlist.sql', D+'r2_26_photo_previews.sql', D+'r2_27_videos.sql', D+'r2_28_space_sharing.sql', R29]); S = seed(); admin = S['admin']
MB = 1048576
tk = {r[1]: r[0] for r in sql("select id, name from tickets order by name")}; A, B, C = tk['Asha'], tk['Ben'], tk['Carl']
CODE = {'Asha': S['A'], 'Ben': S['A'], 'Carl': S['B']}; PH = {'Asha': '9000000001', 'Ben': '9000000002', 'Carl': '9000000003'}
def anon(q, p=()): return call('anon', q, p)
def as_(u, q, p=()): return call('authenticated', q, p, uid=u)
def rv(r): return r[1][0][0] if r[0] == 'ok' else {'ok': False, 'error': r[1]}
def setp(**k):
    sets = ", ".join(f"{a}=%s" for a in k); sql(f"update settings set {sets} where id=1", tuple(k.values()))
def present(*ids): sql("update tickets set checked_in_at=now() where id = any(%s::uuid[])", ([str(i) for i in ids],))
def mk(a): return rv(anon("select space_make_code(%s,%s)", (CODE[a], PH[a])))
def peek(tok): return rv(anon("select space_code_peek(%s)", (tok,)))
def gt(a, tok, kind, mb): return rv(anon("select space_give_token(%s,%s,%s,%s,%s)", (CODE[a], PH[a], tok, kind, mb)))
def pst(a): return rv(anon("select photo_public_status(%s,%s)", (CODE[a], PH[a])))
def vst(a): return rv(anon("select video_public_status(%s,%s)", (CODE[a], PH[a])))
setp(photos_on=True, videos_on=True, photo_public_mode='present', photo_max_pub_mb=100, video_cap_mb=100, photo_pool_pub_mb=12288, photo_cap_pub_mb=90)
present(A, B, C)

# 1. make a code
r = mk('Carl'); tok = r['token']
t.check("1.1 code made: 10 characters from the safe alphabet", r['ok'] and re.fullmatch(r'[A-HJ-NP-Z2-9]{10}', tok) is not None, r)
t.check("1.2 expires in about 30 minutes", sql("select expires_at - now() between interval '29 minutes' and interval '31 minutes' from space_codes where token=%s", (tok,))[0][0])
t.check("1.3 asking again reuses the same code", mk('Carl')['token'] == tok and sql("select count(*) from space_codes")[0][0] == 1)
t.check("1.4 a code that is about to expire is replaced", (sql("update space_codes set expires_at = now() + interval '5 minutes'"), mk('Carl')['token'] != tok)[1])
tok = mk('Carl')['token']
t.check("1.5 wrong login gets no code", rv(anon("select space_make_code(%s,%s)", (CODE['Carl'], '9999999999')))['error'] == 'MISMATCH' and rv(anon("select space_make_code('x','y')"))['error'] == 'MISMATCH')
t.check("1.6 the code does not contain the Booking ID or phone", CODE['Carl'] not in tok and PH['Carl'] not in tok)
sql("update bookings set status='pending' where booking_code=%s", (CODE['Carl'],))
t.check("1.7 unpaid booking gets no code", rv(anon("select space_make_code(%s,%s)", (CODE['Carl'], PH['Carl'])))['error'] == 'NOT_PAID')
sql("update bookings set status='paid' where booking_code=%s", (CODE['Carl'],))
sql("update tickets set checked_in_at=null where id=%s", (str(C),))
t.check("1.8 not Present yet still gets a code (space waits for them)", mk('Carl')['ok'] is True)
present(C)
setp(space_sharing_on=False)
t.check("1.9 sharing off: no code", mk('Carl')['error'] == 'SHARING_OFF')
setp(space_sharing_on=True)
t.check("1.10 old codes are cleaned up", (sql("insert into space_codes(token,ticket_id,expires_at) values ('AAAAAAAAAA',%s,now()-interval '2 days')", (str(B),)), mk('Carl'), sql("select count(*) from space_codes where token='AAAAAAAAAA'")[0][0])[2] == 0)
t.check("1.11 the table is closed to the website", anon("select * from space_codes")[0] == 'err' and as_(admin, "select * from space_codes")[0] == 'err')
t.check("1.12 two people never share a code", len({mk(x)['token'] for x in ('Asha', 'Ben', 'Carl')}) == 3)

# 2. peek
t.check("2.1 peek shows the name on the ticket", peek(tok) == {'ok': True, 'name': 'Carl'}, peek(tok))
t.check("2.2 typed lower-case with spaces and dashes still works", peek(tok[:5].lower() + ' - ' + tok[5:].lower())['ok'] is True)
t.check("2.3 unknown code", peek('ZZZZZZZZZZ')['error'] == 'CODE_INVALID' and peek('')['error'] == 'CODE_INVALID' and peek(None)['error'] == 'CODE_INVALID')
sql("update space_codes set expires_at = now() - interval '1 second' where token=%s", (tok,))
t.check("2.4 expired code is refused", peek(tok)['error'] == 'CODE_INVALID')
tok = mk('Carl')['token']
sql("update bookings set status='pending' where booking_code=%s", (CODE['Carl'],))
t.check("2.5 code of a booking that became unpaid is refused", peek(tok)['error'] == 'CODE_INVALID')
sql("update bookings set status='paid' where booking_code=%s", (CODE['Carl'],))
t.check("2.6 peek works for anyone with the code (that is the point) but never shows phone or booking", set(peek(tok)) == {'ok', 'name'})

# 3. give by code
r = gt('Asha', tok, 'photo', 40)
t.check("3.1 give by code ok; Asha 50, Carl 130", r['ok'] and pst('Asha')['limit_bytes'] == 50*MB and pst('Carl')['limit_bytes'] == 130*MB, r)
t.check("3.2 same row as a typed gift (shows in the admin list)", rv(call('authenticated', "select admin_space_transfers()", uid=admin))['items'][0]['to'] == 'Carl')
t.check("3.3 log line says QR", sql("select old_value from settings_log where field='space given (photos)' order by id desc limit 1")[0][0] == 'Asha > Carl (QR)')
t.check("3.4 the same code can be used by other friends (a group)", gt('Ben', tok, 'photo', 30)['ok'] and pst('Carl')['limit_bytes'] == 160*MB)
t.check("3.5 video gift by code", gt('Asha', tok, 'video', 25)['ok'] and vst('Asha')['limit_bytes'] == 75*MB and vst('Carl')['limit_bytes'] == 125*MB and pst('Asha')['limit_bytes'] == 50*MB)
t.check("3.6 too much: refused with the amount that can be given", (lambda x: x['error'] == 'TOO_MUCH' and x['give_bytes'] == 50*MB)(gt('Asha', tok, 'photo', 51)))
t.check("3.7 bad amount, bad kind", all(gt('Asha', tok, 'photo', x)['error'] == 'BAD_AMOUNT' for x in (0, -1, 100001, None)) and gt('Asha', tok, 'gif', 5)['error'] == 'BAD_KIND')
t.check("3.8 your own code is refused", gt('Carl', tok, 'photo', 5)['error'] == 'SAME_PERSON')
t.check("3.9 a code of the same login (Ben/Asha share booking but not phone) is a different person", gt('Asha', mk('Ben')['token'], 'photo', 5)['ok'] is True)
t.check("3.10 unknown or expired code", gt('Asha', 'ZZZZZZZZZZ', 'photo', 5)['error'] == 'CODE_INVALID')
t.check("3.11 giver wrong login", rv(anon("select space_give_token(%s,%s,%s,'photo',5)", (CODE['Asha'], '9999999999', tok)))['error'] == 'MISMATCH')
t.check("3.12 giver not Present", (sql("update tickets set checked_in_at=null where id=%s", (str(B),)), gt('Ben', tok, 'photo', 5)['error'] == 'NOT_PRESENT', present(B))[1])
setp(space_sharing_on=False)
t.check("3.13 sharing off: refused", gt('Asha', tok, 'photo', 5)['error'] == 'SHARING_OFF')
setp(space_sharing_on=True, videos_on=False)
t.check("3.14 video off: refused for video, fine for photo", gt('Asha', tok, 'video', 5)['error'] == 'FEATURE_OFF' and gt('Asha', tok, 'photo', 5)['ok'])
setp(videos_on=True)
t.check("3.15 take-back works for a QR gift", (lambda g: rv(anon("select space_return(%s,%s,%s)", (CODE['Asha'], PH['Asha'], g['id'])))['ok'])(gt('Asha', tok, 'photo', 3)))

# 4. permissions
for f in ("space_make_code(text,text)", "space_code_peek(text)", "space_give_token(text,text,text,text,integer)"):
    t.check(f"4.1 {f}: website can call", sql(f"select has_function_privilege('anon','public.{f}','execute')")[0][0] is True)
for f in ("_space_token()", "_space_code_all(text)"):
    t.check(f"4.2 {f}: nobody can call", all(sql(f"select has_function_privilege('{x}','public.{f}','execute')")[0][0] is False for x in ('anon', 'authenticated', 'service_role')))
t.check("4.3 table refuses a bad token shape", call('postgres', f"insert into space_codes(token,ticket_id,expires_at) values ('abc', '{A}', now())")[0] == 'err')
p = subprocess.run(['psql','-h','/tmp','-p','5544','-q','-d','postgres','-U','postgres','-v','ON_ERROR_STOP=1','-f',R29],capture_output=True,text=True)
t.check("5.1 running r2_29 again succeeds, codes kept", p.returncode == 0 and sql("select count(*) from space_codes")[0][0] >= 1, p.stderr[:200])
t.report("r2_29 space qr")
