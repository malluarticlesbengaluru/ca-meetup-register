# Deliberate-mistake check for sql/r2_29_space_qr.sql: each broken copy MUST make test_r2_29 fail.
import os, subprocess, re
s = open('/home/claude/ca-meetup-register/sql/r2_29_space_qr.sql').read()
M = {
 'code never expires': ("select ticket_id into tid from space_codes where token = tk and expires_at > now();", "select ticket_id into tid from space_codes where token = tk;"),
 'unpaid booking accepted': (" and exists (select 1 from bookings b where b.id = t.booking_id and b.status = 'paid')", ""),
 'own code allowed': ("if me = other or w.all_ids && oall then", "if false then"),
 'too much allowed': ("if p_mb::bigint * 1048576 > left_b then", "if false then"),
 'sharing switch ignored in give': ("if not s.space_sharing_on then return jsonb_build_object('ok', false, 'error', 'SHARING_OFF'); end if;\n  if (p_kind", "if (p_kind"),
 'sharing switch ignored in make': ("if not s.space_sharing_on then return jsonb_build_object('ok', false, 'error', 'SHARING_OFF'); end if;\n  select * into w from _photo_public_who(p_code, p_phone);\n  if w.all_ids is null", "select * into w from _photo_public_who(p_code, p_phone);\n  if w.all_ids is null"),
 'giver login not checked': ("  select * into w from _photo_public_who(p_code, p_phone);\n  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;\n  oall", "  select * into w from _photo_public_who(p_code, p_phone);\n  oall"),
 'amount not checked': ("if p_mb is null or p_mb < 1 or p_mb > 100000 then return jsonb_build_object('ok', false, 'error', 'BAD_AMOUNT'); end if;", ""),
 'kind not checked': ("if p_kind not in ('photo', 'video') then return jsonb_build_object('ok', false, 'error', 'BAD_KIND'); end if;", ""),
 'feature off ignored': ("if (p_kind = 'photo' and not s.photos_on) or (p_kind = 'video' and not s.videos_on) then return jsonb_build_object('ok', false, 'error', 'FEATURE_OFF'); end if;", ""),
 'give not logged as QR': ("' (QR)'", "''"),
 'code shows phone': ("jsonb_build_object('ok', true, 'name', (select name from tickets where id = a[1]))", "jsonb_build_object('ok', true, 'name', (select name from tickets where id = a[1]), 'phone', (select phone from tickets where id = a[1]))"),
 'codes not reused': ("and expires_at > now() + interval '10 minutes' order by", "and false order by"),
 'code lives 30 days': ("exp := now() + interval '30 minutes'", "exp := now() + interval '30 days'"),
 'table open to anon': ("revoke all on public.space_codes from public, anon, authenticated;", "grant select on public.space_codes to anon;"),
 'token helper callable': ("revoke all on function public._space_token() from public, anon, authenticated, service_role;", "grant execute on function public._space_token() to anon;"),
 'code helper callable': ("revoke all on function public._space_code_all(text) from public, anon, authenticated, service_role;", "grant execute on function public._space_code_all(text) to anon;"),
 'website cannot give': ("grant execute on function public.space_give_token(text, text, text, text, integer) to anon, authenticated;", ""),
 'bad token shape allowed': ("check (token ~ '^[A-Z2-9]{10}$')", "check (true)"),
 'old codes kept': ("delete from space_codes where expires_at < now() - interval '1 day';", ""),
 'token not cleaned': ("upper(regexp_replace(coalesce(p_token, ''), '[^A-Za-z0-9]', '', 'g'))", "coalesce(p_token, '')"),
}
bad = 0
for name, (a, b) in M.items():
    if s.count(a) != 1: print("SKIP (pattern count %d):" % s.count(a), name); bad += 1; continue
    open('/tmp/r2_29_mut.sql', 'w').write(s.replace(a, b))
    r = subprocess.run(['python3', '-s', 'test_r2_29.py'], capture_output=True, text=True, env={**os.environ, 'R29': '/tmp/r2_29_mut.sql', 'PYTHONPATH': '.'})
    m = re.search(r'=> (\d+) passed, (\d+) failed', r.stdout)
    caught = (m is None) or int(m.group(2)) > 0
    print(('caught ' if caught else 'MISSED ') + name)
    if not caught: bad += 1
print('ALL CAUGHT' if bad == 0 else '%d PROBLEM(S)' % bad)
