# Deliberate-mistake check for sql/r2_30_space_by_booking.sql: each broken copy MUST make test_r2_30 fail.
import os, subprocess, re
s = open('/home/claude/ca-meetup-register/sql/r2_30_space_by_booking.sql').read()
M = {
 'unpaid booking accepted (peek and give)': (" and status = 'paid';\n  if bid is null", ";\n  if bid is null"),
 'short ids accepted': ("if length(bc) < 4 then return null; end if;", ""),
 'giver login not checked': ("  select * into w from _photo_public_who(p_code, p_phone);\n  if w.err is not null then return jsonb_build_object('ok', false, 'error', w.err); end if;\n  oall", "  select * into w from _photo_public_who(p_code, p_phone);\n  oall"),
 'own booking allowed': ("if me = other or w.all_ids && oall then", "if false then"),
 'too much allowed': ("if p_mb::bigint * 1048576 > left_b then", "if false then"),
 'sharing switch ignored': ("if not s.space_sharing_on then return jsonb_build_object('ok', false, 'error', 'SHARING_OFF'); end if;\n  if (p_kind", "if (p_kind"),
 'amount not checked': ("if p_mb is null or p_mb < 1 or p_mb > 100000 then return jsonb_build_object('ok', false, 'error', 'BAD_AMOUNT'); end if;", ""),
 'kind not checked': ("if p_kind not in ('photo', 'video') then return jsonb_build_object('ok', false, 'error', 'BAD_KIND'); end if;", ""),
 'feature off ignored': ("if (p_kind = 'photo' and not s.photos_on) or (p_kind = 'video' and not s.videos_on) then return jsonb_build_object('ok', false, 'error', 'FEATURE_OFF'); end if;", ""),
 'peek shows phone': ("jsonb_build_object('ok', true, 'name', (select name from tickets where id = a[1]))", "jsonb_build_object('ok', true, 'name', (select name from tickets where id = a[1]), 'phone', (select phone from tickets where id = a[1]))"),
 'moved-out tickets counted': ("from tickets where booking_id = bid and transferred_out_at is null order by reg_seq limit 1", "from tickets where booking_id = bid order by reg_seq limit 1"),
 'newest ticket instead of oldest': ("from tickets where booking_id = bid and transferred_out_at is null order by reg_seq limit 1", "from tickets where booking_id = bid and transferred_out_at is null order by reg_seq desc limit 1"),
 'helper callable': ("revoke all on function public._space_booking_all(text) from public, anon, authenticated, service_role;", "grant execute on function public._space_booking_all(text) to anon;"),
 'website cannot give': ("grant execute on function public.space_give_booking(text, text, text, text, integer) to anon, authenticated;", ""),
 'website cannot peek': ("grant execute on function public.space_booking_peek(text) to anon, authenticated;", ""),
 'id not cleaned': ("upper(regexp_replace(coalesce(p_booking, ''), '[^A-Za-z0-9]', '', 'g'))", "coalesce(p_booking, '')"),
 'no log line': ("insert into settings_log (changed_by, who, area, field, old_value, new_value)\n  values (null, 'attendee', 'settings', 'space given (' || p_kind || 's)', left(coalesce(n1, '?') || ' > ' || coalesce(n2, '?'), 300), p_mb || ' MB');", ""),
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
