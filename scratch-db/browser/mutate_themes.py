"""Deliberate-mistake check for run_themes.py (public page) and run_adm_theme.py (admin card). Breaks a temporary copy one way at a time.
CAUGHT = the suite failed (good). SURVIVED = blind spot. Run in the background: it takes a long time (about 40 minutes).  python3 mutate_themes.py > /tmp/mt.log &"""
import os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); R = '/home/claude/ca-meetup-register/'
PUB = open(R + 'index.html', encoding='utf-8').read(); ADM = open(R + 'admin/index.html', encoding='utf-8').read(); FX = open(R + 'assets/home-fx.js', encoding='utf-8').read()
def P(old, new, n=1):
    def f(s): assert s.count(old) == n, (old[:70], s.count(old)); return s.replace(old, new)
    return f
def block(name, old, new):
    def f(s):
        a = s.index(f'html[data-theme="{name}"]'); b = s.index('\n', a); t = s[a:b]; assert t.count(old) == 1, (name, old, t.count(old)); return s[:a] + t.replace(old, new) + s[b:]
    return f
# (name, which file, function, which suite)
M = [
 ("a theme name is ignored: always navy", 'pub', P('const n=Object.prototype.hasOwnProperty.call(THEMES,name)?name:"navy";', 'const n="navy";'), 'themes'),
 ("no guard against built-in words like 'constructor'", 'pub', P('const n=Object.prototype.hasOwnProperty.call(THEMES,name)?name:"navy";', 'const n=THEMES[name]?name:"navy";'), 'themes'),
 ("the theme is not remembered on the phone", 'pub', P('else localStorage.setItem("ehsaas_theme",n)', 'else 0'), 'themes'),
 ("navy does not forget the remembered theme", 'pub', P('if(n==="navy")localStorage.removeItem("ehsaas_theme");else', 'if(false)0;else'), 'themes'),
 ("the remembered theme is not applied before the page draws", 'pub', P('if(_t&&/^(emerald|charcoal|mango|sky|terracotta)$/.test(_t))document.documentElement.setAttribute("data-theme",_t)', ''), 'themes'),
 # (left out on purpose: 'any remembered junk is accepted' in the head script. The page script runs straight after it and puts any unknown name back to navy before the first paint, so the difference cannot be seen: an equivalent mutant.)
 ("the database flag is ignored", 'pub', P('if(S.flags&&S.flags.theme)applyTheme(S.flags.theme)', ''), 'themes'),
 ("navy leaves the old data-theme on the page", 'pub', P('if(n==="navy")de.removeAttribute("data-theme");else de.setAttribute("data-theme",n);', 'de.setAttribute("data-theme",n);'), 'themes'),
 ("the address-bar colour is not updated", 'pub', P('if(m)m.setAttribute("content",THEMES[n].meta);', ''), 'themes'),
 ("the header logo is not swapped", 'pub', P('document.querySelectorAll("#hdrlogo,#logo-fallback")', 'document.querySelectorAll("#logo-fallback")'), 'themes'),
 ("the Home logo file is not themed", 'pub', P('<img id="logo-fallback" src="${ehLogo()}"', '<img id="logo-fallback" src="assets/logo-mark.png"'), 'themes'),
 # (left out on purpose: 'the first paint of the header logo ignores the remembered theme'. The page script swaps the header logo before the first paint anyway, and the browser fetches the markup's logo file regardless, so the extra inline script cannot be seen from outside: an equivalent mutant.)
 ("the sky logo file name is wrong", 'pub', P('sky:"assets/logo-mark-sky.png"', 'sky:"assets/logo-mark-skyy.png"'), 'themes'),
 ("the animated logo keeps its white parts on light themes", 'pub', P('.logo-wrap #hr,.logo-wrap #bl{fill:var(--logo-w)}', ''), 'themes'),
 ("theme change is not announced to the motion script", 'pub', P('document.dispatchEvent(new Event("themechange"));', ''), 'themes'),
 ("particles ignore the theme (script keeps the old colours)", 'fx', P('let spr=cols().map(sprite)', 'let spr=COL0.map(sprite)'), 'themes'),
 ("particles are not repainted when the theme changes", 'fx', P('on(document,"themechange",()=>{spr=cols().map(sprite)});', ''), 'themes'),
 ("sky page colour is wrong", 'pub', block('sky', '--bg:#EAF4FF', '--bg:#EAF4FE'), 'themes'),
 ("emerald accent is wrong", 'pub', block('emerald', '--accent:#E3B341', '--accent:#E3B342'), 'themes'),
 ("charcoal card colour is wrong", 'pub', block('charcoal', '--card:#262B32', '--card:#262B33'), 'themes'),
 ("terracotta strip colour is wrong", 'pub', block('terracotta', '--teal:#6B8F71', '--teal:#6B8F72'), 'themes'),
 ("mango button text colour is wrong", 'pub', block('mango', '--dark:#FFFFFF', '--dark:#EEEEEE'), 'themes'),
 ("the original navy page colour changed", 'pub', P(':root{--logo-w:#FCFCFC;--bg:#081020;', ':root{--logo-w:#FCFCFC;--bg:#081021;'), 'themes'),
 ("headings are always white (unreadable on light themes)", 'pub', P('h1{font:800 clamp(2.1rem,8.5vw,2.9rem)/1.08 var(--sans);color:var(--head);', 'h1{font:800 clamp(2.1rem,8.5vw,2.9rem)/1.08 var(--sans);color:#fff;'), 'themes'),
 ("form labels are always white", 'pub', P('margin:16px 0 8px;color:var(--head)}', 'margin:16px 0 8px;color:#fff}'), 'themes'),
 ("Home date/time text is always white", 'pub', P('.when dd{margin:0;font:800 1.3rem/1.25 var(--sans);color:var(--head)}', '.when dd{margin:0;font:800 1.3rem/1.25 var(--sans);color:#fff}'), 'themes'),
 ("the top bar is always dark navy", 'pub', P('.top{background:var(--top-bg);color:var(--top-t);', '.top{background:rgba(8,16,32,.86);color:var(--top-t);'), 'themes'),
 ("the toast is always dark navy with light text colour taken from the theme", 'pub', P('background:var(--toast-bg);border:1px solid var(--line3);color:var(--toast-t);', 'background:#1B2656;border:1px solid var(--line3);color:var(--toast-t);'), 'themes'),
 ("the notice bar is always dark amber", 'pub', P('background:var(--gbar-bg);color:var(--gbar-t);', 'background:#2A2208;color:var(--gbar-t);'), 'themes'),
 ("the error box text is always pale pink", 'pub', P('color:var(--err-t)}', 'color:#FFC2BC}'), 'themes'),
 ("status pills keep their dark-page colours", 'pub', P('.p-ok{color:var(--ok);', '.p-ok{color:#5BE3A0;'), 'themes'),
 ("the payment notice keeps its dark-page text colour", 'pub', P('color:var(--verify-t);', 'color:#FFD98A;'), 'themes'),
 ("the switch OFF colour is the same as ON", 'pub', P('border-radius:999px;background:var(--sw-off);position:relative;', 'border-radius:999px;background:var(--accent);position:relative;'), 'themes'),
 ("input boxes keep a white tint (invisible on light pages)", 'pub', P('border-radius:10px;background:var(--field);color:var(--ink);', 'border-radius:10px;background:rgba(255,255,255,.03);color:var(--ink);'), 'themes'),
 ("option chips keep the old pink on every theme", 'pub', P('.opts label:nth-child(5n+1){--c:var(--k1);--ct:var(--kt1);--ci:var(--ki1)}', '.opts label:nth-child(5n+1){--c:#D82890;--ct:#FF7BC4;--ci:#fff}'), 'themes'),
 ("the five-colour strip keeps the old colours", 'pub', P('.kasavu{height:3px;background:linear-gradient(90deg,var(--pink),var(--violet),var(--teal),var(--blue),var(--orange))}', '.kasavu{height:3px;background:linear-gradient(90deg,#D82890,#7820E0,#20C8A0,#3050F0,#E86818)}'), 'themes'),
 ("light pages keep the dark colour scheme (scroll bars, file button)", 'pub', block('sky', 'color-scheme:light', 'color-scheme:dark'), 'themes'),
 ("the ticket header is always navy", 'pub', P('TK=THEMES[THEME].tk,', 'TK=THEMES.navy.tk,'), 'themes'),
 ("the ticket stripe colour is not themed", 'pub', P('AMB=TK.amb,', 'AMB="#FFA400",'), 'themes'),
 ("the ticket body is not themed (small labels keep brown)", 'pub', P('AI=TK.ai,', 'AI="#8A5200",'), 'themes'),
 ("the coordinator ticket loses its wine colour", 'pub', P('const P=coord?{acc:"#7d1c32"', 'const P=coord?{acc:"#0a2147"'), 'themes'),
 ("the sky ticket header is wrong", 'pub', P('sky:{meta:"#EAF4FF",tk:{head:"#0D2A52"', 'sky:{meta:"#EAF4FF",tk:{head:"#0D2A53"'), 'themes'),
 ("the mango ticket stripe colour is wrong", 'pub', P('mango:{meta:"#FFF6D6",tk:{head:"#3A2500",amb:"#FFB300"', 'mango:{meta:"#FFF6D6",tk:{head:"#3A2500",amb:"#FFB301"'), 'themes'),
 ("the admin card is shown before r2_15", 'adm', P('if(s.theme===undefined)return"";', ''), 'adm'),
 ("the admin card saves the wrong field", 'adm', P('{p_theme:c.value}', '{p_theme:"navy"}'), 'adm'),
 ("the admin card sends the old name key", 'adm', P('db.rpc("admin_set_theme",{p_theme:c.value})', 'db.rpc("admin_set_theme",{theme:c.value})'), 'adm'),
 ("the admin card does not tick the current theme", 'adm', P('${s.theme===t[0]?"checked":""}', ''), 'adm'),
 ("the admin card lists a seventh, unknown theme", 'adm', P('["terracotta","Terracotta Earth"', '["purple","Purple Haze","x","#000","#111","#222"],["terracotta","Terracotta Earth"'), 'adm'),
 ("the admin card swatch for mango is wrong", 'adm', P('"#FFFFFF","#DD3328"]', '"#FFFFFF","#E5362B"]'), 'adm'),
 ("a refused theme shows a raw error", 'adm', P('INVALID_THEME:"That theme name is not one the database knows. Reload this page and try again.",', ''), 'adm'),
 ("saving with nothing picked still calls the database", 'adm', P('if(!c)return toast("Pick a theme first");', ''), 'adm'),
 ("the card does not appear in Settings", 'adm', P("  ${themeCard(s)}\n  ${aboutCard(s)}", "  ${aboutCard(s)}"), 'adm'),
 ("the radio group has no accessible name", 'adm', P(' aria-label="Colour theme"', ''), 'adm'),
 ("the admin theme list does not fit a phone", 'adm', P('.th{display:flex;align-items:center;gap:12px;margin:0!important;padding:10px 12px;border:1px solid var(--line);border-radius:12px;cursor:pointer;min-width:0}', '.th{display:flex;align-items:center;gap:12px;margin:0!important;padding:10px 12px;border:1px solid var(--line);border-radius:12px;cursor:pointer;min-width:520px}'), 'adm'),
]
ONLY = [int(x) for x in os.environ.get('ONLY', '').split(',') if x]
tmp = tempfile.mkdtemp(prefix='mut_th_'); bad = 0; done = 0
for i, (name, kind, fn, suite) in enumerate(M, 1):
    if ONLY and i not in ONLY: continue
    src = {'pub': PUB, 'adm': ADM, 'fx': FX}[kind]; path = os.path.join(tmp, f'm{i:02d}.' + ('js' if kind == 'fx' else 'html')); open(path, 'w', encoding='utf-8').write(fn(src))
    env = dict(os.environ); script = 'run_themes.py' if suite == 'themes' else 'run_adm_theme.py'
    if kind == 'pub': env['PAGE'] = path
    elif kind == 'fx': env['HOMEFX'] = path
    else: env['ADMIN_HTML'] = path
    r = subprocess.run([sys.executable, os.path.join(HERE, script)], capture_output=True, text=True, env=env, cwd=HERE, timeout=1500)
    out = r.stdout + r.stderr; m = re.search(r'(\d+) passed, (\d+) failed', out)
    if not m and 'Traceback' in out: v, d = 'CAUGHT', 'the test script stopped with an error (counts as caught): ' + out.strip().splitlines()[-1][:80]
    elif not m: v, d = 'BROKEN', out.strip()[-250:]
    elif int(m.group(2)) > 0: v = 'CAUGHT'; d = next((l.strip() for l in out.splitlines() if 'FAIL' in l), '')[:110]
    else: v, d = 'SURVIVED', 'suite still passed: blind spot'
    if v != 'CAUGHT': bad += 1
    done += 1; print(f"{i:2d}. {v:8s} {name}\n      {d}", flush=True)
print(f"\n{done - bad} of {done} deliberate mistakes caught." + ("" if not bad else f"  {bad} NOT caught."))
sys.exit(1 if bad else 0)
