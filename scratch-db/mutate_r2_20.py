# Deliberate-mistake check for sql/r2_20_photos.sql: each broken copy MUST make test_r2_20 fail.
import os, subprocess, re
SRC = '/home/claude/ca-meetup-register/sql/r2_20_photos.sql'; s = open(SRC).read()
M = {
 'is_staff left wide open (camera can read bookings)': ("role in ('admin', 'gate')) $function$;\nrevoke all on function public.is_staff()", ") $function$;\nrevoke all on function public.is_staff()"),
 'no per-person limit': ("if mine + p_bytes > lim then", "if false then"),
 'no pool limit (camera)': ("if used + p_bytes > pool then return jsonb_build_object('ok', false, 'error', 'POOL_FULL'); end if;\n    k :=", "k :="),
 'no lock on settings (race)': ("select * into s from settings where id = 1 for update;            -- one claim", "select * into s from settings where id = 1;            -- one claim"),
 'cap ignored (division only)': ("least(p_cap_mb::numeric * 1048576, floor(", "least(1e18, floor("),
 'oversize upload accepted': ("p_actual > r.bytes_claimed then", "false then"),
 'any visitor skips Present check': ("if s.photo_public_mode = 'present' then", "if false then"),
 'pools may exceed total': ("if cam + pub > tot then raise exception 'POOLS_TOO_BIG'; end if;", ""),
 'unfinished claims never expire': ("created_at > now() - interval '20 minutes'))", "true))"),
}
bad = 0
for name, (a, b) in M.items():
    if a not in s: print("SKIP (pattern missing):", name); bad += 1; continue
    open('/tmp/r2_20_mut.sql', 'w').write(s.replace(a, b, 1))
    r = subprocess.run(['python3', '-s', 'test_r2_20.py'], capture_output=True, text=True, env={**os.environ, 'R20': '/tmp/r2_20_mut.sql', 'PYTHONPATH': '.'})
    m = re.search(r'=> (\d+) passed, (\d+) failed', r.stdout)
    caught = (m and int(m.group(2)) > 0) or 'FAILED' in r.stdout
    print(('CAUGHT   ' if caught else 'MISSED!! ') + name); bad += 0 if caught else 1
print('all mistakes caught' if bad == 0 else f'{bad} PROBLEM(S)')
