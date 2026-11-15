# Deliberate-mistake check for sql/r2_22_photo_gallery.sql: each broken copy MUST make test_r2_22 fail.
import os, subprocess, re
SRC = '/home/claude/ca-meetup-register/sql/r2_22_photo_gallery.sql'; s = open(SRC).read()
M = {
 'photographer sees everything even in "own" mode': ("(adm or s.photo_visibility in ('photographers', 'all') or (p.kind = 'camera' and p.uploader = auth.uid()))", "true"),
 'attendee sees everything even in "own" mode': ("(s.photo_visibility = 'all' or (p.kind = 'public' and p.ticket_id = any (w.all_ids)))", "true"),
 'attendee sees only own even when admin chose "all"': ("(s.photo_visibility = 'all' or (p.kind = 'public' and p.ticket_id = any (w.all_ids)))", "((p.kind = 'public' and p.ticket_id = any (w.all_ids)))"),
 'any photographer gets any original': ("if rl = 'admin' or s.photo_visibility in ('photographers', 'all') or (r.kind = 'camera' and r.uploader = p_user) then", "if true then"),
 'photographer can delete anyone\'s photo': ("or r.kind <> 'camera' or r.uploader is distinct from p_user then return null;", "or r.kind <> 'camera' then return null;"),
 'attendee can delete anyone\'s photo': ("or r.kind <> 'public' or not (r.ticket_id = any (w.all_ids)) then return null;", "or r.kind <> 'public' then return null;"),
 'attendee needs a right phone? no: wrong phone may delete': ("if w.all_ids is null then return null; end if;\n  select * into r from photos where id = p_id for update;\n  if not found or r.status <> 'stored' or r.kind <> 'public'", "select * into r from photos where id = p_id for update;\n  if not found or r.status <> 'stored' or r.kind <> 'public'"),
 'anyone may change who sees what': ("if not is_admin() then raise exception 'NOT_ALLOWED'; end if;\n  if p_value is null", "if p_value is null"),
 'bad visibility value accepted': ("if p_value is null or p_value not in ('own', 'photographers', 'all') then raise exception 'INVALID_VISIBILITY'; end if;", ""),
 'unfinished and removed photos are listed (camera list)': ("where p.status = 'stored'\n             and (p_before is null or p.created_at < p_before)\n             and (adm", "where true\n             and (p_before is null or p.created_at < p_before)\n             and (adm"),
 'attendee not yet Present cannot even view': ("if w.all_ids is null then return jsonb_build_object('ok', false, 'error', coalesce(w.err, 'MISMATCH'));", "if w.err is not null then return jsonb_build_object('ok', false, 'error', coalesce(w.err, 'MISMATCH'));"),
 'page size not capped': ("least(greatest(coalesce(p_limit, 24), 1), 48)", "coalesce(p_limit, 24)"),
 'paging ignores the cursor (camera list)': ("and (p_before is null or p.created_at < p_before)\n             and (adm", "and (adm"),
 'attendees can call the service-only delete': ("grant execute on function public.photo_remove_public(uuid, text, text) to service_role;", "grant execute on function public.photo_remove_public(uuid, text, text) to anon, authenticated, service_role;"),
 'anyone can read originals keys': ("grant execute on function public.photo_original_key(uuid, uuid) to service_role;", "grant execute on function public.photo_original_key(uuid, uuid) to anon, authenticated, service_role;"),
 'preview picture not checked': ("check (thumb is null or thumb ~ '^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$') not valid;", "check (true) not valid;"),
 'delete does not clear the preview': ("update photos set status = 'removed', thumb = null where id = p_id;\n  insert into settings_log (changed_by, who, area, field, old_value, new_value)\n  values (null, 'attendee'", "update photos set status = 'removed' where id = p_id;\n  insert into settings_log (changed_by, who, area, field, old_value, new_value)\n  values (null, 'attendee'"),
}
bad = 0
for name, (a, b) in M.items():
    if a not in s: print("SKIP (pattern missing):", name); bad += 1; continue
    open('/tmp/r2_22_mut.sql', 'w').write(s.replace(a, b, 1))
    r = subprocess.run(['python3', '-s', 'test_r2_22.py'], capture_output=True, text=True, env={**os.environ, 'R22': '/tmp/r2_22_mut.sql', 'PYTHONPATH': '.'})
    m = re.search(r'=> (\d+) passed, (\d+) failed', r.stdout)
    caught = (m and int(m.group(2)) > 0) or 'FAILED' in r.stdout or 'SQL FILE FAILED' in r.stdout
    print(('CAUGHT   ' if caught else 'MISSED!! ') + name); bad += 0 if caught else 1
print('all mistakes caught' if bad == 0 else f'{bad} PROBLEM(S)')
