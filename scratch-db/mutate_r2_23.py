# Deliberate-mistake check for sql/r2_23_photos_service_read.sql: each broken copy MUST make test_r2_23 fail.
import os, subprocess, re
s = open('/home/claude/ca-meetup-register/sql/r2_23_photos_service_read.sql').read()
G = "grant select on public.photos to service_role;"
M = {
 'grant forgotten': (G, ""),
 'given to visitors instead': (G, "grant select on public.photos to anon;"),
 'function gets write rights too': (G, "grant select, insert, update, delete on public.photos to service_role;"),
 'visitors also get read': (G, G + "\ngrant select on public.photos to anon;"),
 'logged-in users get write rights': (G, G + "\ngrant insert, update, delete on public.photos to authenticated;"),
 'wrong table': (G, "grant select on public.staff to service_role;"),
}
bad = 0
for name, (a, b) in M.items():
    if a not in s: print("SKIP (pattern missing):", name); bad += 1; continue
    open('/tmp/r2_23_mut.sql', 'w').write(s.replace(a, b, 1))
    r = subprocess.run(['python3', '-s', 'test_r2_23.py'], capture_output=True, text=True, env={**os.environ, 'R23': '/tmp/r2_23_mut.sql', 'PYTHONPATH': '.'})
    m = re.search(r'=> (\d+) passed, (\d+) failed', r.stdout)
    caught = (m and int(m.group(2)) > 0) or 'FAILED' in r.stdout or r.returncode != 0
    print(('CAUGHT   ' if caught else 'MISSED!! ') + name); bad += 0 if caught else 1
print('all mistakes caught' if bad == 0 else f'{bad} PROBLEM(S)')
