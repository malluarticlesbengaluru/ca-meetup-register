import psycopg2, psycopg2.extras, subprocess, json, uuid, sys
DSN = "host=/tmp port=5544 dbname=postgres user=postgres"
def ensure_server():
    """Start the private test Postgres if it is not running (it stops between chat steps)."""
    ok = subprocess.run(["psql","-h","/tmp","-p","5544","-U","postgres","-d","postgres","-At","-c","select 1"],capture_output=True,text=True).returncode == 0
    if not ok:
        subprocess.run("su postgres -c \"/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/pgdata -o '-p 5544 -k /tmp' -l /tmp/pg.log start\"", shell=True, capture_output=True)
        import time; time.sleep(2)
def fresh(extra_sql_files=()):
    ensure_server()
    r = subprocess.run(["psql","-h","/tmp","-p","5544","-q","-d","postgres","-U","postgres","-f","/home/claude/scratch/build.sql"],
                       capture_output=True, text=True)
    c = psycopg2.connect(DSN); c.autocommit = True; cur = c.cursor()
    cur.execute("create schema if not exists storage; create table if not exists storage.objects(bucket_id text, name text)")
    cur.execute("alter table public.settings_log alter column id add generated always as identity")
    cur.execute("alter table public.tickets alter column reg_seq add generated always as identity")
    cur.execute("grant usage on schema storage to anon, authenticated")
    cur.execute("grant select on storage.objects to anon, authenticated")
    c.close()
    for f in extra_sql_files:
        r = subprocess.run(["psql","-h","/tmp","-p","5544","-q","-d","postgres","-U","postgres","-v","ON_ERROR_STOP=1","-f",f],
                           capture_output=True, text=True)
        if r.returncode != 0: print("SQL FILE FAILED:", f, r.stderr[-1500:]); sys.exit(1)
    import os
    for f in filter(None, os.environ.get("ALSO_SQL", "").split(",")):   # optional: apply more files on top (used to check a new file against the older suites)
        r = subprocess.run(["psql","-h","/tmp","-p","5544","-q","-d","postgres","-U","postgres","-v","ON_ERROR_STOP=1","-f",f], capture_output=True, text=True)
        if r.returncode != 0: print("SQL FILE FAILED:", f, r.stderr[-1500:]); sys.exit(1)
conn = None
def db():
    global conn
    if conn is None or conn.closed:
        conn = psycopg2.connect(DSN); conn.autocommit = True
    return conn
def call(role, sql, params=(), uid=None, headers=None):
    """Run one statement as role (anon/authenticated/postgres). Returns ('ok', rows) or ('err', message)."""
    c = db(); cur = c.cursor()
    try:
        cur.execute("begin")
        if role != 'postgres': cur.execute(f"set local role {role}")
        if uid: cur.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(uid),))
        if headers is not None: cur.execute("select set_config('request.headers', %s, true)", (headers,))
        cur.execute(sql, params)
        rows = cur.fetchall() if cur.description else []
        cur.execute("commit")
        return ('ok', rows)
    except Exception as e:
        cur.execute("rollback")
        return ('err', str(e).strip().split('\n')[0])
def val(res):
    return res[1][0][0] if res[0]=='ok' and res[1] else None
def sql(q, params=()):  # superuser
    r = call('postgres', q, params)
    if r[0]=='err': raise Exception(q[:100] + ' -> ' + r[1])
    return r[1]
class T:
    def __init__(s):
        import atexit
        s.passed=0; s.failed=0; s.lines=[]; s.reported=False
        atexit.register(s._final)
    def check(s, name, cond, detail=''):
        if cond: s.passed+=1; s.lines.append(f"  PASS  {name}")
        else: s.failed+=1; s.lines.append(f"  FAIL  {name}  {detail}")
    def report(s, title):
        s.reported=True
        print(title); print('\n'.join(s.lines)); print(f"  => {s.passed} passed, {s.failed} failed")
    def _final(s):
        # a test script that stops early (an exception) must count as a FAILURE and still show what ran
        if not s.reported and (s.lines):
            print("TEST SCRIPT STOPPED EARLY (counts as a failure)"); print('\n'.join(s.lines))
            print(f"  => {s.passed} passed, {s.failed + 1} failed (script crashed)")
def seed():
    """One open event, one admin, booking A (Asha 9000000001, Ben 9000000002), booking B (Carl 9000000003), all paid."""
    admin = uuid.uuid4()
    sql("insert into auth.users (id,email) values (%s,'admin@test')", (str(admin),))
    sql("insert into staff (user_id,name,role) values (%s,'Admin One','admin')", (str(admin),))
    sql("update settings set is_open=true, deadline=now()+interval '30 days', cap=150, price_per_head=250, pause_enabled=false, transfers_open=true, max_resale_price=250, upi_id='test@upi', payee_name='Test', whatsapp_number='919999999999' where id=1")
    out = {'admin': admin}
    def book(name_phones, tag):
        sid = uuid.uuid4(); path = f'{sid}.jpg'
        sql("insert into storage.objects values ('payment-proofs', %s)", (path,))
        people = [dict(name=n, phone=p, email=f'{n.lower()}@example.com', loc='In Bengaluru', att='Surely', food='Veg', occ='Student', occ_detail='Student') for n,p in name_phones]
        r = call('anon', "select submit_booking(%s,%s::jsonb,%s)", (str(sid), json.dumps(people), path))
        assert r[0]=='ok', r
        j = r[1][0][0]
        code = j['booking_code'] if isinstance(j, dict) and 'booking_code' in j else None
        bid = sql("select id, booking_code from bookings order by created_at desc limit 1")[0]
        call('authenticated', "select set_booking_status(%s,'paid')", (str(bid[0]),), uid=admin)
        out[tag] = bid[1]
    book([('Asha','9000000001'),('Ben','9000000002')], 'A')
    book([('Carl','9000000003')], 'B')
    return out

def call_new(role, q, params=(), uid=None):
    """Same as call() but on its own connection (for parallel tests)."""
    c = psycopg2.connect(DSN); c.autocommit = True; cur = c.cursor()
    try:
        cur.execute("begin")
        if role != 'postgres': cur.execute(f"set local role {role}")
        if uid: cur.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(uid),))
        cur.execute(q, params)
        rows = cur.fetchall() if cur.description else []
        cur.execute("commit"); return ('ok', rows)
    except Exception as e:
        try: cur.execute("rollback")
        except Exception: pass
        return ('err', str(e).strip().split('\n')[0])
    finally:
        c.close()
def par(fns):
    """Run callables at the same time, return their results in order."""
    import threading
    out = [None]*len(fns)
    def run(i, f): out[i] = f()
    th = [threading.Thread(target=run, args=(i,f)) for i,f in enumerate(fns)]
    [x.start() for x in th]; [x.join() for x in th]
    return out
