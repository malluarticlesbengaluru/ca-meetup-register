import json, os, sys
from playwright.sync_api import sync_playwright
# Browser suite for the attendee page (gallery/) with the shared attendee space (r2_32): labels, the Share tab, one amount for photos and videos.
# Run:  cd scratch-db/browser && python3 run_gallery_shared.py | tail -1
ROOT = '/home/claude/ca-meetup-register'
HTML = open(ROOT + '/gallery/index.html', encoding='utf-8').read(); UP = open(ROOT + '/assets/photo-upload.js', encoding='utf-8').read()
MOCK = open('mock_supabase.js').read()
MB = 1048576; results = []
def check(name, cond, detail=''):
    results.append(bool(cond)); print(('  PASS  ' if cond else '  FAIL  ') + name + ('' if cond else '  ' + str(detail)[:200]))
def rpcs(shared):
    st = lambda lim, used: dict(ok=True, limit_bytes=lim*MB, used_bytes=used*MB, left_bytes=(lim-used)*MB, pool_left_bytes=1000*MB, max_bytes=100*MB, present=3, shared=shared)
    return {
        'photo_public_list': dict(ok=True, items=[], page=24, visibility='own'),
        'photo_public_status': st(200, 120) if shared else st(90, 10),
        'video_public_status': (lambda d: d)(st(200, 120) if shared else st(100, 0)),
        'video_public_list': dict(ok=True, items=[], page=24, can_download=False),
        'space_overview': dict(ok=True, sharing_on=True, shared=shared, items=[
            dict(id='g1', kind='photo', mb=40, dir='in', other='Carl', status='active', at='2026-11-22T10:00:00Z', can_return=False)],
            photo=dict(on=True, give_bytes=80*MB, net_bytes=40*MB), video=dict(on=True, give_bytes=80*MB if shared else 100*MB, net_bytes=40*MB if shared else 0)),
    }
def page(p, shared):
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 390, 'height': 800}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.route('**/*', lambda r: (r.fulfill(body=HTML, content_type='text/html') if r.request.url.endswith('/gallery/test.html')
        else r.fulfill(body=UP, content_type='text/javascript') if r.request.url.endswith('photo-upload.js')
        else r.fulfill(body='/*stub*/', content_type='text/javascript') if r.request.url.endswith('.js') or '/npm/' in r.request.url
        else r.fulfill(status=204, body='')))
    pg.add_init_script('window.__DB=' + json.dumps(dict(tables={}, rpc=rpcs(shared))) + ';'); pg.add_init_script(MOCK)
    pg.goto('https://example.test/gallery/test.html'); pg.wait_for_selector('#bid')
    pg.fill('#bid', 'ABCD2345'); pg.fill('#ph', '9000000001'); pg.click('#go'); pg.wait_for_timeout(500)
    return b, pg, errs
def tab(pg, k): pg.click(f'button[data-tab="{k}"]'); pg.wait_for_timeout(500)
with sync_playwright() as p:
    for shared in (False, True):
        tag = 'shared ' if shared else 'separate '
        b, pg, errs = page(p, shared)
        t = pg.inner_text('#st') if pg.query_selector('#st') else pg.inner_text('body')
        check(f'G1 {tag}: photo status label', ('Your space (photos and videos together)' in t) == shared and ('Your photo space' in t) != shared, t[:160])
        check(f'G2 {tag}: photo bar numbers', ('80 MB left' in t and 'of 200 MB' in t) if shared else ('80 MB left' in t and 'of 90 MB' in t), t[:200])
        tab(pg, 'videos'); t = pg.inner_text('body')
        check(f'G3 {tag}: video page wording', ('Your space for photos and videos together: 120 MB used of 200 MB' in t) if shared else ('Space for videos: 0' in t and 'together' not in t), t[:300])
        tab(pg, 'share'); t = pg.inner_text('body')
        has_seg = pg.query_selector('.seg2') is not None
        check(f'G4 {tag}: Photo space / Video space switch is {"hidden" if shared else "shown"}', has_seg != shared)
        check(f'G5 {tag}: Share tab wording', (('Photos and videos:' in t and 'one amount for photos and videos together' in t and 'MB photo space' not in t and '40 MB space from Carl' in t) if shared
                                                 else ('Photos:' in t and 'Videos:' in t and '40 MB photo space from Carl' in t)), t[:500])
        if shared:
            pg.fill('#sbid', 'WXYZ2345'); pg.fill('#smb', '20'); pg.evaluate("window.__DB.rpc.space_booking_peek={ok:true,name:'Carl',people:[{id:'p1',name:'Carl'}]};window.__DB.rpc.space_give_booking={ok:true,id:'g2'}")
            msgs = []; pg.on('dialog', lambda d: (msgs.append(d.message), d.accept()))
            pg.click('button[data-a="sgive"]'); pg.wait_for_timeout(600)
            c = [x for x in pg.evaluate('window.__CALLS') if x['name'] == 'space_give_booking']
            check('G6 shared: giving asks "Give 20 MB of space to Carl?" and sends a valid kind', msgs and msgs[0] == 'Give 20 MB of space to Carl?' and c and c[-1]['args']['p_kind'] in ('photo', 'video') and c[-1]['args']['p_mb'] == 20, (msgs, c))
        check(f'G7 {tag}: no page errors', not errs, errs); b.close()
print(f"{sum(results)} passed, {len(results)-sum(results)} failed")
