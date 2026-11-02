"""The Colour theme card in admin Settings (needs sql/r2_15; hidden before). Fake database. Run: python3 run_adm_theme.py | tail -1"""
from admin_test import *
import re, os
ROOT = '/home/claude/ca-meetup-register/'
NAMES = ['navy', 'emerald', 'charcoal', 'mango', 'sky', 'terracotta']
def with_theme(th, extra=None):
    d = db(); d['tables']['settings'] = dict(d['tables']['settings'], theme=th); d['rpc']['admin_set_theme'] = None
    if extra: d['rpc'].update(extra)
    return d
def calls(pg, n): return [x for x in pg.evaluate('window.__CALLS') if x['name'] == n]
def lt(pg): return pg.evaluate("(()=>{const t=[...document.querySelectorAll('.toast')];return t.length?t[t.length-1].textContent:''})()")
with sync_playwright() as p:
    b, pg, errs = open_page(p, db(), 'settings')
    check('1.1 before r2_15 the Colour theme card is hidden (no Save button, no radios), while the other Settings cards still show', pg.query_selector('#themesave') is None and pg.query_selector('input[name="theme"]') is None and 'Colour theme' not in pg.inner_text('#v') and pg.query_selector('#tsave') is not None, errs); check('1.2 no page errors', not errs, errs); b.close()
    b, pg, errs = open_page(p, with_theme('emerald'), 'settings')
    check('2.1 the card shows six choices, in order, with their names', [x.inner_text().split('\n')[0] for x in pg.query_selector_all('.th')] == ['Midnight Navy (the original)', 'Emerald Night', 'Charcoal & Mint', 'Mango Fiesta', 'Sky Day', 'Terracotta Earth'], [x.inner_text() for x in pg.query_selector_all('.th')])
    check('2.2 the radio values are exactly the six database names', [x.get_attribute('value') for x in pg.query_selector_all('input[name="theme"]')] == NAMES)
    check('2.3 the current theme (emerald) is the ticked one, and highlighted', pg.eval_on_selector('input[name="theme"]:checked', 'e=>e.value') == 'emerald' and 'on' in pg.get_attribute('.th:nth-child(2)', 'class').split())
    sw = pg.evaluate("[...document.querySelectorAll('.th')].map(l=>[...l.querySelectorAll('.sw3 i')].map(i=>getComputedStyle(i).backgroundColor))")
    check('2.4 each choice shows three colour swatches (page, card, accent)', all(len(x) == 3 for x in sw) and sw[1] == ['rgb(6, 35, 27)', 'rgb(12, 49, 38)', 'rgb(227, 179, 65)'] and sw[3][2] == 'rgb(221, 51, 40)', sw)
    check('2.5 the group is labelled for screen readers', pg.get_attribute('.themes', 'role') == 'radiogroup' and pg.get_attribute('.themes', 'aria-label') == 'Colour theme')
    pg.click('.th:nth-child(5)'); pg.click('#themesave'); pg.wait_for_timeout(250)
    c = calls(pg, 'admin_set_theme')
    check('2.6 choosing Sky Day and saving sends exactly {p_theme:"sky"}, once', len(c) == 1 and c[0]['args'] == {'p_theme': 'sky'}, c)
    check('2.7 the toast says it is saved', 'Theme saved' in lt(pg), lt(pg))
    check('2.8 no page errors', not errs, errs); b.close()
    b, pg, errs = open_page(p, with_theme('navy'), 'settings'); pg.click('#themesave'); pg.wait_for_timeout(250); c = calls(pg, 'admin_set_theme')
    check('3.1 saving without changing sends the current theme (navy)', len(c) == 1 and c[0]['args'] == {'p_theme': 'navy'}, c); b.close()
    b, pg, errs = open_page(p, with_theme('navy', {'admin_set_theme': 'INVALID_THEME'}), 'settings'); pg.click('.th:nth-child(4)'); pg.click('#themesave'); pg.wait_for_timeout(250)
    check('3.2 a refused theme is explained in words, not as a raw code', 'not one the database knows' in lt(pg) and 'INVALID_THEME' not in lt(pg), lt(pg)); b.close()
    b, pg, errs = open_page(p, with_theme('navy', {'admin_set_theme': 'NOT_ALLOWED'}), 'settings'); pg.click('.th:nth-child(4)'); pg.click('#themesave'); pg.wait_for_timeout(250)
    check('3.3 a non-admin gets "Only admins can do this."', 'Only admins' in lt(pg), lt(pg)); b.close()
    b, pg, errs = open_page(p, with_theme('purple'), 'settings')
    check('3.4 an unknown value in the database ticks nothing and does not crash', pg.query_selector('input[name="theme"]:checked') is None and not errs, errs)
    pg.click('#themesave'); pg.wait_for_timeout(200)
    check('3.5 saving with nothing picked asks to pick, and sends nothing', 'Pick a theme' in lt(pg) and not calls(pg, 'admin_set_theme'), lt(pg)); b.close()
    b, pg, errs = open_page(p, with_theme('mango'), 'settings'); pg.focus('input[name="theme"]:checked'); pg.keyboard.press('ArrowDown'); pg.wait_for_timeout(100)
    check('3.6 the keyboard works (arrow keys move the choice)', pg.eval_on_selector('input[name="theme"]:checked', 'e=>e.value') == 'sky'); b.close()
    b = p.chromium.launch(); b.close()
    import admin_test as AT
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 360, 'height': 800}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.route('**/*', lambda r: (r.fulfill(body=AT.HTML, content_type='text/html') if r.request.url.endswith('/admin/test.html') else r.fulfill(body='/*stub*/', content_type='text/javascript') if r.request.url.endswith('.js') or '/npm/' in r.request.url else r.fulfill(status=204, body='')))
    pg.add_init_script('window.__DB=' + json.dumps(with_theme('sky')) + ';'); pg.add_init_script(AT.MOCK); pg.add_init_script(AT.CH); pg.goto('https://example.test/admin/test.html'); pg.wait_for_selector('.tabs'); pg.click('button[data-tab="settings"]'); pg.wait_for_timeout(200)
    check('4.1 at 360 px the card does not push the page sideways', pg.evaluate('document.documentElement.scrollWidth') <= 360 and not errs, (pg.evaluate('document.documentElement.scrollWidth'), errs))
    r = pg.evaluate("(()=>{const c=document.querySelector('.themes').getBoundingClientRect();return [...document.querySelectorAll('.th')].every(l=>l.getBoundingClientRect().right<=c.right+1)})()")
    check('4.2 every choice fits inside the card', r); b.close()
    # the three lists must agree: the database's check, the admin choices, the public page
    sql = open(ROOT + 'sql/r2_15_color_theme.sql').read(); pub = open(ROOT + 'index.html', encoding='utf-8').read(); adm = open(ROOT + 'admin/index.html', encoding='utf-8').read()
    dbn = re.search(r"check \(theme = any \(array\[([^\]]+)\]\)\)", sql).group(1).replace("'", '').split(',')
    fn = re.search(r"p_theme <> all \(array\[([^\]]+)\]\)", sql).group(1).replace("'", '').split(',')
    pubn = re.findall(r'^  (navy|emerald|charcoal|mango|sky|terracotta):\{meta', pub, re.M)
    css = re.findall(r'^html\[data-theme="(\w+)"\]', pub, re.M)
    admn = re.findall(r'\["(\w+)","[^"]+","[^"]+","#', adm)
    head = re.search(r'EH_LOGO=\{([^}]+)\}', pub).group(1)
    check('5.1 the database table check, the database function, the public page and the admin page all list the same six names', dbn == fn == NAMES == pubn == admn, (dbn, fn, pubn, admn))
    check('5.2 the public page has a colour block for each of the five non-navy themes', css == NAMES[1:], css)
    check('5.3 the head script accepts exactly the five names it has colours for', set(re.search(r'\^\(([^)]+)\)\$', pub).group(1).split('|')) == set(NAMES[1:]), re.search(r'\^\(([^)]+)\)\$', pub).group(1))
    check('5.4 every light theme has its logo file in the repo', all(os.path.exists(ROOT + f'assets/logo-mark-{n}.png') for n in re.findall(r'(\w+):"assets/logo-mark-', head)) and len(re.findall(r'(\w+):"assets/logo-mark-', head)) == 3)
print(f"{sum(results)} passed, {len(results)-sum(results)} failed")
