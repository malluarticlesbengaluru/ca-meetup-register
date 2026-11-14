# Deliberate-mistake check for sql/r2_21_transfer_buyer_details.sql: each broken copy MUST make test_r2_21 fail.
import os, subprocess, re
s = open('/home/claude/ca-meetup-register/sql/r2_21_transfer_buyer_details.sql').read()
M = {
 'occupation not required': ("if v_occ not in ('Article Assistant', 'Industrial Trainee', 'Employee', 'Student', 'Others') then return jsonb_build_object('ok', false, 'error', 'INVALID_OCCUPATION'); end if;", ""),
 'detail not required': ("if length(v_occd) not between 1 and 100 then return jsonb_build_object('ok', false, 'error', 'INVALID_OCCUPATION_DETAIL'); end if;", ""),
 'detail not trimmed': ("v_occd := trim(coalesce(p_buyer->>'occ_detail', ''));", "v_occd := coalesce(p_buyer->>'occ_detail', '');"),
 'answers not saved on the application': ("now(), v_occ, v_occd);", "now(), null, null);"),
 'approve forgets to copy them': ("'guest', t.id, bu.occupation, bu.occupation_detail)", "'guest', t.id, null, null)"),
 'detail limit raised': ("length(v_occd) not between 1 and 100", "length(v_occd) not between 1 and 1000"),
 'visitors lose the right to apply': ("grant execute on function public.transfer_submit(text, uuid, jsonb) to anon, authenticated;", "grant execute on function public.transfer_submit(text, uuid, jsonb) to authenticated;"),
 'anyone may approve': ("grant execute on function public.admin_transfer_approve(uuid) to authenticated;", "grant execute on function public.admin_transfer_approve(uuid) to anon, authenticated;"),
}
bad = 0
for name, (a, b) in M.items():
    if a not in s: print("SKIP (pattern missing):", name); bad += 1; continue
    open('/tmp/r2_21_mut.sql', 'w').write(s.replace(a, b, 1))
    r = subprocess.run(['python3', '-s', 'test_r2_21.py'], capture_output=True, text=True, env={**os.environ, 'R21': '/tmp/r2_21_mut.sql', 'PYTHONPATH': '.'})
    m = re.search(r'=> (\d+) passed, (\d+) failed', r.stdout)
    caught = (m and int(m.group(2)) > 0) or 'FAILED' in r.stdout or r.returncode != 0
    print(('CAUGHT   ' if caught else 'MISSED!! ') + name); bad += 0 if caught else 1
print('all mistakes caught' if bad == 0 else f'{bad} PROBLEM(S)')
