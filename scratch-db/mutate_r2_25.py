# Deliberate-mistake check for sql/r2_25_download_allowlist.sql: each broken copy MUST make test_r2_25 fail.
import os, subprocess, re
s = open('/home/claude/ca-meetup-register/sql/r2_25_download_allowlist.sql').read()
M = {
 'switch defaults to on': ("photo_download boolean not null default false", "photo_download boolean not null default true"),
 'switch ignored (any admin)': ("role = 'admin' and photo_download)", "role = 'admin')"),
 'role ignored (anyone with switch)': ("role = 'admin' and photo_download)", "photo_download)"),
 'switch alone not enough check removed in original_key': ("if not photo_may_download(p_user) then return null; end if;", ""),
 'removed photos downloadable': ("where id = p_id and status = 'stored';", "where id = p_id;"),
 'list always says can_download true': ("'can_download', photo_may_download(auth.uid()))", "'can_download', true)"),
 'list says can_download for any admin': ("'can_download', photo_may_download(auth.uid()))", "'can_download', adm)"),
 'may_download open to the website': ("grant execute on function public.photo_may_download(uuid) to service_role;", "grant execute on function public.photo_may_download(uuid) to service_role, authenticated;"),
 'original_key open to the website': ("grant execute on function public.photo_original_key(uuid, uuid) to service_role;", "grant execute on function public.photo_original_key(uuid, uuid) to service_role, anon;"),
 'list no longer protects own mode': ("or (p.kind = 'camera' and p.uploader = auth.uid()))", "or true)"),
}
bad = 0
for name, (a, b) in M.items():
    if a not in s: print("SKIP (pattern missing):", name); bad += 1; continue
    open('/tmp/r2_25_mut.sql', 'w').write(s.replace(a, b, 1))
    r = subprocess.run(['python3', '-s', 'test_r2_25.py'], capture_output=True, text=True, env={**os.environ, 'R25': '/tmp/r2_25_mut.sql', 'PYTHONPATH': '.'})
    m = re.search(r'=> (\d+) passed, (\d+) failed', r.stdout)
    caught = (m and int(m.group(2)) > 0) or 'FAIL' in r.stdout or r.returncode != 0
    print(('CAUGHT   ' if caught else 'MISSED!! ') + name); bad += 0 if caught else 1
print('all mistakes caught' if bad == 0 else f'{bad} PROBLEM(S)')
