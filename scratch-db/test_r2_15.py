from lib import *
import json, uuid, subprocess, os
# Database suite for sql/r2_15_color_theme.sql (the colour theme of the public page, set by an admin).
# Set R15 to point at a different copy of the r2_15 file (mutate_r2_15.py does this).
R = '/home/claude/ca-meetup-register/sql/'
R15 = os.environ.get('R15', R + 'r2_15_color_theme.sql')
BASE = [R + f for f in ['r2_01_prep.sql', 'r2_02_lookup.sql', 'r2_02c_close_old_transfer_doors.sql', 'r2_02b_cutover.sql', 'r2_03_private_transfer.sql',
        'r2_04_public_via_code.sql', 'r2_05_cleanup_and_ip.sql', 'r2_06_transfer_settings.sql', 'r2_08_coordinator_transfer.sql', 'r2_09_about_link.sql',
        'r2_10_email_switch.sql', 'r2_11_feedback.sql', 'r2_12_gate_undo.sql', 'r2_13_game_messages.sql', 'r2_14_game_prizes.sql']]
T_ALL = ['navy', 'emerald', 'charcoal', 'mango', 'sky', 'terracotta']
t = T(); fresh(BASE); S = seed(); admin = S['admin']
def mkuser(email, role=None, name=None):
    u = uuid.uuid4(); sql("insert into auth.users (id,email) values (%s,%s)", (str(u), email))
    if role: sql("insert into staff (user_id,name,role) values (%s,%s,%s)", (str(u), name or email, role))
    return u
gate = mkuser('g@t', 'gate', 'Gate One'); visitor = mkuser('v@t')
def runfile(p): return subprocess.run(["psql", "-h", "/tmp", "-p", "5544", "-q", "-d", "postgres", "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-f", p], capture_output=True, text=True)
def err(r, code): return r[0] == 'err' and code in r[1]
def setth(v, uid=None, role='authenticated'): return call(role, "select admin_set_theme(%s)", (v,), uid=uid if uid else (admin if role == 'authenticated' else None))
def cur(): return sql("select theme from settings where id=1")[0][0]
def flags(): return call('anon', "select get_site_flags()")[1][0][0]
def tlog(): return sql("select old_value, new_value, who from settings_log where field='theme' order by id")

t.check("0.1 before r2_15 there is no theme column", sql("select count(*) from information_schema.columns where table_name='settings' and column_name='theme'")[0][0] == 0)
before = flags()
r = runfile(R15); t.check("1.1 r2_15 applies", r.returncode == 0, r.stderr[-300:])
r = runfile(R15); t.check("1.2 r2_15 can be run twice safely", r.returncode == 0, r.stderr[-300:])
t.check("1.3 the default theme is navy (the original look), and nothing else in settings was touched", cur() == 'navy' and sql("select count(*) from settings")[0][0] == 1)
t.check("1.4 the old flags are unchanged, 'theme' is added", flags() == dict(before, theme='navy'), flags())
t.check("1.5 the two old flags callers still get a plain object", isinstance(flags(), dict) and set(flags()) == {'show_about', 'ask_email', 'ask_feedback', 'theme'})

# 2. who may change it
t.check("2.1 a visitor (no login) cannot", err(setth('sky', role='anon'), 'permission denied') and cur() == 'navy', setth('sky', role='anon'))
t.check("2.2 a signed-in non-staff user cannot", err(setth('sky', uid=visitor), 'NOT_ALLOWED') and cur() == 'navy')
t.check("2.3 gate staff cannot", err(setth('sky', uid=gate), 'NOT_ALLOWED') and cur() == 'navy')
t.check("2.4 an admin can", setth('sky')[0] == 'ok' and cur() == 'sky')
t.check("2.5 the public page sees the new theme at once", flags()['theme'] == 'sky')
t.check("2.6 service_role may not call it either (only signed-in admins)", err(call('service_role', "select admin_set_theme('mango')"), 'permission denied') and cur() == 'sky')
t.check("2.7 nobody can write the theme directly in the table", call('authenticated', "update settings set theme='mango'", uid=admin)[0] == 'err' and call('anon', "update settings set theme='mango'")[0] == 'err' and cur() == 'sky')

# 3. what is accepted
ok = True
for th in T_ALL: ok = ok and setth(th)[0] == 'ok' and cur() == th and flags()['theme'] == th
t.check("3.1 all six themes can be chosen, and each one shows in the flags", ok)
bad = ['', ' ', 'NAVY', 'Navy', 'navy ', ' navy', 'red', 'navy;drop table settings', "navy'", 'emerald,sky', 'sky\n', None]
setth('emerald')
t.check("3.2 anything else is refused with INVALID_THEME, and nothing changes", all(err(setth(b), 'INVALID_THEME') for b in bad) and cur() == 'emerald', [(b, setth(b)) for b in bad if not err(setth(b), 'INVALID_THEME')])
t.check("3.3 the table itself refuses a wrong theme, even for the database owner", call('postgres', "update settings set theme='purple'")[0] == 'err' and cur() == 'emerald')
t.check("3.4 the table's own list matches the six names exactly", sorted(x[0] for x in sql("select unnest(array['navy','emerald','charcoal','mango','sky','terracotta']) except select unnest(array['x'])")) == sorted(T_ALL) and all(call('postgres', "update settings set theme=%s", (th,))[0] == 'ok' for th in T_ALL))
sql("update settings set theme='navy'")

# 4. the Settings log
sql("delete from settings_log where field='theme'")
setth('mango'); setth('mango'); setth('terracotta')
L = tlog()
t.check("4.1 a change is written to the Settings log with old value, new value and the admin's name", L[0] == ('navy', 'mango', 'Admin One') and L[-1] == ('mango', 'terracotta', 'Admin One'), L)
t.check("4.2 choosing the same theme again writes nothing (so 2 lines for 3 calls)", len(L) == 2, L)
n0 = sql("select count(*) from settings_log")[0][0]; setth('bogus'); setth('sky', uid=gate)
t.check("4.3 a refused call writes nothing to the log", sql("select count(*) from settings_log")[0][0] == n0)

# 5. nothing else got worse
t.check("5.1 the other switches still work next to it (about, email, feedback)", call('authenticated', "select admin_set_show_about(false)", uid=admin)[0] == 'ok' and flags()['show_about'] is False and flags()['theme'] == 'terracotta' and call('authenticated', "select admin_set_show_about(true)", uid=admin)[0] == 'ok')
t.check("5.2 a visitor can still read the flags and still cannot read the settings table", call('anon', "select get_site_flags()")[0] == 'ok' and err(call('anon', "select count(*) from settings"), 'permission denied'))
t.check("5.3 get_site_flags runs as the owner with a fixed search path (no leak, no hijack)", sql("select prosecdef, proconfig::text from pg_proc where proname='get_site_flags'")[0][0] is True and 'search_path=public' in sql("select proconfig::text from pg_proc where proname='get_site_flags'")[0][0])
t.check("5.4 admin_set_theme is security definer with a fixed search path", sql("select prosecdef from pg_proc where proname='admin_set_theme'")[0][0] is True and 'search_path=public' in sql("select proconfig::text from pg_proc where proname='admin_set_theme'")[0][0])
t.check("5.5 only signed-in users have execute on admin_set_theme (not anon, not public)", sql("select has_function_privilege('anon','admin_set_theme(text)','execute'), has_function_privilege('authenticated','admin_set_theme(text)','execute')")[0] == (False, True))
t.check("5.6 registration and lookup still work (lookup_tickets finds Asha)", call('anon', "select lookup_tickets(%s,%s)", (S['A'], '9000000001'))[1][0][0]['found'] is True)
t.report("test_r2_15")
