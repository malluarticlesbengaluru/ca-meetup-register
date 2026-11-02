"""Deliberate-mistake check for test_r2_15.py.

A green test run alone proves little. This script breaks sql/r2_15_color_theme.sql in one way at a time (a "mutant"),
runs test_r2_15.py against each broken copy, and expects the suite to FAIL every time.
  - CAUGHT   = the suite failed (good: the test notices that mistake)
  - SURVIVED = the suite still passed (bad: the test has a blind spot)
  - BROKEN   = the broken SQL would not even load (the mutant is not a useful test; fix the mutant)
It never touches the real file: broken copies go in a temporary folder. Run:  python3 mutate_r2_15.py
"""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = '/home/claude/ca-meetup-register/sql/r2_15_color_theme.sql'
orig = open(SRC).read()

def patch(old, new, expect=1, nth=None):
    """Return a function that edits the SQL text. It asserts the old text exists exactly `expect` times,
    so a mutant can never silently do nothing."""
    def f(s):
        assert s.count(old) == expect, f"expected {expect} x {old!r}, found {s.count(old)}"
        if nth is None: return s.replace(old, new)
        parts = s.split(old); return old.join(parts[:nth]) + new + old.join(parts[nth:])
    return f

MUTANTS = [
    ("default theme is not navy", patch("add column if not exists theme text not null default 'navy'", "add column if not exists theme text not null default 'sky'")),
    ("table accepts any word (check removed)", patch("alter table public.settings add constraint settings_theme_check check (theme = any (array['navy','emerald','charcoal','mango','sky','terracotta']));", "")),
    ("table check misses terracotta", patch("check (theme = any (array['navy','emerald','charcoal','mango','sky','terracotta']))", "check (theme = any (array['navy','emerald','charcoal','mango','sky']))")),
    ("table check allows an extra name", patch("check (theme = any (array['navy','emerald','charcoal','mango','sky','terracotta']))", "check (theme = any (array['navy','emerald','charcoal','mango','sky','terracotta','purple']))")),
    ("flags do not return the theme", patch(", 'theme', s.theme) from settings", ") from settings")),
    ("flags return the wrong column", patch("'theme', s.theme", "'theme', 'navy'")),
    ("set_theme: no admin check", patch("if not is_admin() then raise exception 'NOT_ALLOWED'; end if;\n  if p_theme is null", "if false then raise exception 'NOT_ALLOWED'; end if;\n  if p_theme is null")),
    ("set_theme: wrong words allowed (function check removed)", patch("if p_theme is null or p_theme <> all (array['navy','emerald','charcoal','mango','sky','terracotta']) then raise exception 'INVALID_THEME'; end if;", "if p_theme is null then raise exception 'INVALID_THEME'; end if;")),
    ("set_theme: null allowed through the function check", patch("if p_theme is null or p_theme <> all", "if p_theme <> all")),
    ("set_theme: not security definer", patch("create or replace function public.admin_set_theme(p_theme text) returns void\n language plpgsql security definer", "create or replace function public.admin_set_theme(p_theme text) returns void\n language plpgsql")),
    ("set_theme: search path not fixed", patch("language plpgsql security definer set search_path to 'public' as $function$\nbegin\n  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;\n  if p_theme", "language plpgsql security definer as $function$\nbegin\n  if not is_admin() then raise exception 'NOT_ALLOWED'; end if;\n  if p_theme")),
    ("visitors may execute set_theme", lambda s: s + "\ngrant execute on function public.admin_set_theme(text) to anon;\n"),
    ("everyone (PUBLIC) may execute set_theme", lambda s: s + "\ngrant execute on function public.admin_set_theme(text) to public;\n"),
    ("service_role may execute set_theme", lambda s: s + "\ngrant execute on function public.admin_set_theme(text) to service_role;\n"),
    ("signed-in users can write the table directly", lambda s: s + "\ngrant update on public.settings to authenticated;\ncreate policy w on public.settings for update to authenticated using (true) with check (true);\n"),
    ("flags function runs as the caller (not security definer)", patch("language sql stable security definer set search_path to 'public' as $function$\n  select jsonb_build_object('show_about'", "language sql stable set search_path to 'public' as $function$\n  select jsonb_build_object('show_about'")),
    ("flags drop the about flag", patch("'show_about', s.show_about, ", "")),
    ("flags drop the feedback flag", patch(", 'ask_feedback', s.ask_feedback", "")),
    ("flags drop the email flag", patch("'ask_email', s.ask_email, ", "")),
    ("flags no longer callable by visitors", patch("grant execute on function public.get_site_flags() to anon, authenticated;", "grant execute on function public.get_site_flags() to authenticated;")),
    # (left out on purpose: 'update every row' cannot be seen, the settings table is held to a single row by its own rule id = 1: an equivalent mutant)
    ("set_theme silently picks navy for a wrong word", patch("p_theme <> all (array['navy','emerald','charcoal','mango','sky','terracotta']) then raise exception 'INVALID_THEME'; end if;", "p_theme <> all (array['navy','emerald','charcoal','mango','sky','terracotta']) then p_theme := 'navy'; end if;")),
]
tmp = tempfile.mkdtemp(prefix='mut_r2_15_')
rows, bad = [], 0
for i, (name, fn) in enumerate(MUTANTS, 1):
    path = os.path.join(tmp, f'mutant_{i:02d}.sql')
    open(path, 'w').write(fn(orig))
    assert open(path).read() != orig, "mutant is identical to the original"
    r = subprocess.run([sys.executable, os.path.join(HERE, 'test_r2_15.py')], capture_output=True, text=True,
                       env=dict(os.environ, R15=path), cwd=HERE, timeout=600)
    out = r.stdout + r.stderr
    m = re.search(r'=> (\d+) passed, (\d+) failed', out)
    if 'SQL FILE FAILED' in out or not m: verdict, detail = 'BROKEN', out.strip()[-300:]
    elif int(m.group(2)) > 0:
        verdict = 'CAUGHT'; first = next((l.strip() for l in out.splitlines() if 'FAIL' in l), '')
        detail = f"{m.group(2)} check(s) failed, first: {first[:90]}"
    else: verdict, detail = 'SURVIVED', 'suite still passed: blind spot'
    if verdict != 'CAUGHT': bad += 1
    print(f"{i:2d}. {verdict:8s} {name}\n      {detail}", flush=True)

print(f"\n{len(MUTANTS) - bad} of {len(MUTANTS)} deliberate mistakes caught." + ("" if not bad else f"  {bad} NOT caught: see above."))
sys.exit(1 if bad else 0)
