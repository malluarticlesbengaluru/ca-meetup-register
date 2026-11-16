# Deliberate-mistake check for sql/r2_24_originals_admin_only.sql: each broken copy MUST make test_r2_24 fail.
import os, subprocess, re
s = open('/home/claude/ca-meetup-register/sql/r2_24_originals_admin_only.sql').read()
M = {
 'photographers allowed again': ("if rl is distinct from 'admin' then return null; end if;", "if rl is null or rl not in ('admin','camera') then return null; end if;"),
 'anyone with a staff role allowed': ("if rl is distinct from 'admin' then return null; end if;", "if rl is null then return null; end if;"),
 'no role check at all': ("if rl is distinct from 'admin' then return null; end if;", ""),
 'removed photos downloadable': ("where id = p_id and status = 'stored';", "where id = p_id;"),
 'list says photographers can download': ("'can_download', adm)", "'can_download', true)"),
 'list says nobody can download': ("'can_download', adm)", "'can_download', false)"),
 'list no longer protects own mode': ("or (p.kind = 'camera' and p.uploader = auth.uid()))", "or true)"),
 'original lookup open to the public': ("grant execute on function public.photo_original_key(uuid, uuid) to service_role;", "grant execute on function public.photo_original_key(uuid, uuid) to service_role, anon;"),
}
bad = 0
for name, (a, b) in M.items():
    if a not in s: print("SKIP (pattern missing):", name); bad += 1; continue
    open('/tmp/r2_24_mut.sql', 'w').write(s.replace(a, b, 1))
    r = subprocess.run(['python3', '-s', 'test_r2_24.py'], capture_output=True, text=True, env={**os.environ, 'R24': '/tmp/r2_24_mut.sql', 'PYTHONPATH': '.'})
    m = re.search(r'=> (\d+) passed, (\d+) failed', r.stdout)
    caught = (m and int(m.group(2)) > 0) or 'FAIL' in r.stdout or r.returncode != 0
    print(('CAUGHT   ' if caught else 'MISSED!! ') + name); bad += 0 if caught else 1
print('all mistakes caught' if bad == 0 else f'{bad} PROBLEM(S)')
