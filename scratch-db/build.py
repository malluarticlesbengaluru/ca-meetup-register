import re, collections
txt = open('/home/claude/sql/schema_snapshot.txt', encoding='utf-8').read().replace('\r', '')
secs = {}
cur = None
for line in txt.split('\n'):
    m = re.match(r'^=== ([A-Z ,()&-]+?)( \(.*)? ===$', line)
    if m: cur = m.group(1).strip(); secs[cur] = []; continue
    if cur: secs[cur].append(line)
out = []
out.append("""
drop schema if exists public cascade; create schema public;
drop schema if exists auth cascade; create schema auth;
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;
do $$ begin
  if not exists (select 1 from pg_roles where rolname='anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname='authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname='service_role') then create role service_role nologin; end if;
end $$;
create table auth.users (id uuid primary key default gen_random_uuid(), email text);
create or replace function auth.uid() returns uuid language sql stable as
 $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
grant usage on schema public, auth, extensions to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;
alter database postgres set search_path = public, extensions;
set search_path = public, extensions;
""")
# tables
cols = collections.OrderedDict()
for l in secs['COLUMNS']:
    if not l.strip(): continue
    p = l.split('|')
    t, pos, c, ty, nn, *d = p
    d = '|'.join(d)
    cols.setdefault(t, []).append((c, ty, nn == 't', d))
view_lines = [l for l in secs.get('VIEWS', []) if l.strip()]
view_name = view_lines[0].strip() if view_lines else None
view_def = '\n'.join(view_lines[1:]).strip().rstrip(';') if view_lines else None
for t, cl in cols.items():
    if t == view_name: continue
    defs = []
    for c, ty, nn, d in cl:
        s = f'"{c}" {ty}'
        if d: s += ' default ' + d
        if nn: s += ' not null'
        defs.append(s)
    out.append(f'create table public."{t}" (\n  ' + ',\n  '.join(defs) + '\n);')
# constraints: PK/UNIQUE first, then others
cons = [l for l in secs['CONSTRAINTS'] if ' | ' in l]
def key(l):
    d = l.split(' | ', 2)[2]
    return 0 if d.startswith(('PRIMARY', 'UNIQUE')) else (2 if d.startswith('FOREIGN') else 1)
for l in sorted(cons, key=key):
    t, n, d = l.split(' | ', 2)
    out.append(f'alter table public."{t}" add constraint "{n}" {d};')
for l in secs['INDEXES']:
    if ' | ' not in l: continue
    t, d = l.split(' | ', 1)
    d = d.replace('CREATE UNIQUE INDEX', 'CREATE UNIQUE INDEX IF NOT EXISTS').replace('CREATE INDEX', 'CREATE INDEX IF NOT EXISTS')
    out.append(d + ';')
# functions
f = secs['FUNCTIONS (with who is allowed to run them)'] if 'FUNCTIONS (with who is allowed to run them)' in secs else None
if f is None:
    k = [k for k in secs if k.startswith('FUNCTIONS')][0]; f = secs[k]
funcs = []; hdr = None; body = []
for l in f:
    if l.startswith('--- '):
        if hdr: funcs.append((hdr, '\n'.join(body)))
        hdr = l; body = []
    else: body.append(l)
if hdr: funcs.append((hdr, '\n'.join(body)))
fn_sql = []; grants = []
for hdr, body in funcs:
    m = re.match(r'^--- (\S+?)\((.*?)\) \| execute rights: (?:\{(.*)\}|default.*)$', hdr)
    name, args, rights = m.group(1), m.group(2), (m.group(3) or '')
    # identity args types only
    argtypes = []
    for a in [x.strip() for x in re.split(r',\s*(?![^()]*\))', args) if x.strip()]:
        argtypes.append(a)
    sig = f'public."{name}"({args})' if args else f'public."{name}"()'
    # signature for grants: strip names -> use full arg list w/o defaults is unnecessary; use regproc via pg_proc lookup
    fn_sql.append(body.strip() + ';')
    who = [r.split('=')[0] for r in rights.split(',') if r]
    grants.append((name, who))
if True:
    out.append('-- functions, pass 1 (errors tolerated)')
    out.extend(fn_sql)
    out.append('-- functions, pass 2')
    out.extend(fn_sql)
if view_name:
    out.append(f'create or replace view public."{view_name}" with (security_invoker=true) as {view_def};')
# grants: revoke from public on every function, then grant per list
out.append("""
do $$ declare r record; begin
  for r in select p.oid::regprocedure as sig, p.proname from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' loop
    execute 'revoke all on function ' || r.sig || ' from public, anon, authenticated, service_role';
  end loop; end $$;""")
for name, who in grants:
    for w in who:
        if w in ('anon', 'authenticated', 'service_role'):
            out.append(f"""do $$ declare r record; begin for r in select p.oid::regprocedure as sig from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname='{name}' loop execute 'grant execute on function ' || r.sig || ' to {w}'; end loop; end $$;""")
# triggers
for l in secs['TRIGGERS']:
    if ' | CREATE TRIGGER' in l:
        out.append(l.split(' | ', 1)[1] + ';')
# row level security, policies and table grants of the OLD tables, copied from the real snapshot
# (closes handover gap G8: before this, the scratch copy did not reproduce who can read what)
def raw_section(prefix):
    lines, on = [], False
    for l in txt.split('\n'):
        if l.startswith('=== '):
            on = l.startswith('=== ' + prefix); continue
        if on and l.strip(): lines.append(l)
    return lines
for l in raw_section('ROW LEVEL SECURITY'):
    m = re.match(r'^(\w+) : rls=(true|false)$', l)
    if m and m.group(2) == 'true':
        out.append(f"alter table public.{m.group(1)} enable row level security;")
for l in raw_section('POLICIES'):
    parts = [x.strip() for x in l.split(' | ')]
    if len(parts) != 6 or not parts[0].startswith('public.'): continue      # storage.objects is a stub in the scratch copy
    tbl, name, cmd, roles, using, chk = parts
    roles = roles.strip('{}')
    using = using.replace('using: ', '', 1); chk = chk.replace('check: ', '', 1)
    q = f'create policy "{name}" on {tbl} for {cmd.lower()} to {roles}'
    if using != '-': q += f' using ({using})'
    if chk != '-': q += f' with check ({chk})'
    out.append(q + ';')
PRIV = {'r': 'select', 'a': 'insert', 'w': 'update', 'd': 'delete'}
for l in raw_section('TABLE AND VIEW PERMISSIONS'):
    m = re.match(r'^(\w+) : \{(.*)\}$', l)
    if not m: continue
    tbl = m.group(1)
    for item in m.group(2).split(','):
        mm = re.match(r'^(\w+)=([a-zA-Z]*)/', item)
        if not mm or mm.group(1) not in ('anon', 'authenticated', 'service_role'): continue
        privs = [PRIV[c] for c in mm.group(2) if c in PRIV]
        if privs: out.append(f"grant {', '.join(privs)} on public.{tbl} to {mm.group(1)};")
# settings row
out.append("insert into public.settings (id) values (1) on conflict do nothing;")
open('build.sql', 'w').write('set check_function_bodies = off;\n' + '\n'.join(out))
print(len(cols), 'tables;', len(funcs), 'functions')
