from admin_test import *
import json
# Browser suite for the admin Messages tab (game activity): the tab, the Settings switch, dealing out, giving, taking away,
# one-person select. Uses a small STATEFUL stand-in for the five database functions (the real ones are tested in test_r2_13.py).
STATEFUL = r"""
(function(){
  const orig = window.supabase.createClient;
  window.supabase.createClient = function(){
    const c = orig.apply(this, arguments), D = window.__DB, T = D.tables;
    const real = T.game_messages !== undefined && T.game_messages !== null;
    const M = window.__M = {n: 100};
    if (real) { M.msgs = T.game_messages; M.tm = {}; (T.ticket_messages||[]).forEach(r => M.tm[r.ticket_id] = r.message_id); }
    const realP = T.ticket_prizes !== undefined && T.ticket_prizes !== null; M.pz = {}; M.pzh = {}; if (realP) (T.ticket_prizes||[]).forEach(r => { M.pz[r.ticket_id] = r.body; M.pzh[r.ticket_id] = r.heading; });
    const ofrom = c.from.bind(c), orpc = c.rpc.bind(c);
    c.from = function(t){
      if (real && (t === 'game_messages' || t === 'ticket_messages')) {
        const rows = t === 'game_messages' ? M.msgs.slice() : Object.keys(M.tm).map(k => ({ticket_id:k, message_id:M.tm[k]}));
        const b = {select(){return b}, order(){return b}, limit(){return b}, then(res,rej){return Promise.resolve({data:rows,error:null}).then(res,rej)}};
        return b;
      }
      if (realP && t === 'ticket_prizes') { const rows = Object.keys(M.pz).map(k => ({ticket_id:k, body:M.pz[k], heading:M.pzh[k]})); const b = {select(c){b.cols = String(c||'').split(',').map(x=>x.trim()); return b}, then(res,rej){const cs = b.cols || []; return Promise.resolve({data:rows.map(r=>Object.fromEntries(Object.entries(r).filter(([k])=>cs.includes(k)))),error:null}).then(res,rej)}}; return b; }
      return ofrom(t);
    };
    c.rpc = async function(name, a){
      if (realP && name === 'admin_set_prizes') { (window.__CALLS = window.__CALLS || []).push({name, args:a}); if (window.__FAIL && window.__FAIL[name]) return {data:null,error:{message:window.__FAIL[name]}};
        const b = (a.p_body||'').trim(); if (!b) return {data:null,error:{message:'INVALID_MESSAGE'}}; const h = ((a.p_heading||'').trim()) || 'You are a winner!'; if (h.length > 60) return {data:null,error:{message:'INVALID_NAME'}}; const ts = a.p_tickets || [];
        if (new Set(ts).size !== ts.length) return {data:null,error:{message:'DUPLICATE_TICKET'}};
        for (const id of ts) { const tk = T.tickets.find(x => x.id === id); if (!tk || tk.transferred_out_at) return {data:null,error:{message:'TICKET_NOT_FOUND'}}; }
        ts.forEach(id => { M.pz[id] = b; M.pzh[id] = h; }); return {data:ts.length,error:null}; }
      if (realP && name === 'admin_clear_prizes') { (window.__CALLS = window.__CALLS || []).push({name, args:a}); let n = 0; Object.keys(M.pz).forEach(k => { if (!a.p_tickets || a.p_tickets.includes(k)) { delete M.pz[k]; delete M.pzh[k]; n++; } }); return {data:n,error:null}; }
      if (!real || !/^admin_(set_show_messages|save_message|delete_message|assign_messages|clear_messages)$/.test(name)) return orpc(name, a);
      (window.__CALLS = window.__CALLS || []).push({name, args:a});
      const err = m => ({data:null, error:{message:m}});
      if (window.__FAIL && window.__FAIL[name]) return err(window.__FAIL[name]);
      if (name === 'admin_set_show_messages') { T.settings.show_messages = a.p_show; return {data:null,error:null}; }
      if (name === 'admin_save_message') {
        const n = (a.p_name||'').trim(), b = (a.p_body||'').trim();
        if (!n) return err('INVALID_NAME'); if (!b) return err('INVALID_MESSAGE');
        if (M.msgs.some(x => x.name.toLowerCase() === n.toLowerCase() && x.id !== a.p_id)) return err('NAME_TAKEN');
        if (a.p_id) { const x = M.msgs.find(y => y.id === a.p_id); if (!x) return err('NOT_FOUND'); x.name = n; x.body = b; return {data:a.p_id,error:null}; }
        const id = 'm' + (++M.n); M.msgs.push({id, name:n, body:b, created_at:new Date().toISOString()}); return {data:id,error:null};
      }
      if (name === 'admin_delete_message') { const i = M.msgs.findIndex(x => x.id === a.p_id); if (i < 0) return err('NOT_FOUND'); let n = 0;
        Object.keys(M.tm).forEach(k => { if (M.tm[k] === a.p_id) { delete M.tm[k]; n++; } }); M.msgs.splice(i,1); return {data:n,error:null}; }
      if (name === 'admin_assign_messages') {
        const ps = a.p_pairs; if (!Array.isArray(ps)) return err('INVALID_PAIRS');
        const seen = new Set(); for (const p of ps) { if (seen.has(p.t)) return err('DUPLICATE_TICKET'); seen.add(p.t);
          const t = T.tickets.find(x => x.id === p.t); if (!t || t.transferred_out_at) return err('TICKET_NOT_FOUND'); if (!M.msgs.some(x => x.id === p.m)) return err('MESSAGE_NOT_FOUND'); }
        ps.forEach(p => M.tm[p.t] = p.m); return {data:ps.length,error:null};
      }
      if (name === 'admin_clear_messages') { let n = 0;
        Object.keys(M.tm).forEach(k => { if ((!a.p_message || M.tm[k] === a.p_message) && (!a.p_tickets || a.p_tickets.includes(k))) { delete M.tm[k]; n++; } }); return {data:n,error:null}; }
    };
    return c;
  };
})();
"""
def people_set(n_books=10, per=3, present=(), extra=None):
    T, B = [], []
    for i in range(n_books):
        B.append(bk(i+1, n=per, amt=250*per))
        for j in range(per):
            n = i*per + j + 1
            T.append(mk(n, ticket_no=n, name=f'Person{n:02d}', booking_id=f'b{i+1}', checked_in_at=('2026-11-22T09:00:00Z' if n in present else None)))
    return T, B
def mdb(T, B, msgs=('Tiger','Elephant','Lion'), assigned=None, show=False, prizes=None, heads=None):
    ms = [dict(id=f'm{i+1}', name=n, body=f'Team {n.upper()}', created_at=f'2026-10-30T10:0{i}:00Z') for i, n in enumerate(msgs)]
    d = db(tables=dict(tickets=T, bookings=B, transfers=None, transfer_buyers=None, ticket_emails=None, game_messages=ms,
                       ticket_messages=[dict(ticket_id=t, message_id=m) for t, m in (assigned or {}).items()],
                       settings=dict(SETTINGS, show_messages=show)))
    if prizes is not None: d['tables']['ticket_prizes'] = [dict(ticket_id=k, body=v, heading=(heads or {}).get(k, 'You are a winner!')) for k, v in prizes.items()]
    return d
def opn(p, d, tab=None, w=1300, h=900):
    b = p.chromium.launch(); pg = b.new_page(viewport={'width':w,'height':h}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'relation' not in m.text else None)
    pg.route('**/*', lambda r: (r.fulfill(body=HTML, content_type='text/html') if r.request.url.endswith('/admin/test.html')
        else r.fulfill(body='/*stub*/', content_type='text/javascript') if r.request.url.endswith('.js') or '/npm/' in r.request.url else r.fulfill(status=204, body='')))
    pg.add_init_script('window.__DB=' + json.dumps(d) + ';'); pg.add_init_script(MOCK); pg.add_init_script(CH); pg.add_init_script(STATEFUL); pg.add_init_script(DLG_BOT)
    pg.goto('https://example.test/admin/test.html'); pg.wait_for_selector('#v')
    if tab: go_tab(pg, tab)
    return b, pg, errs
def calls(pg, name=None): return [x for x in pg.evaluate('window.__CALLS||[]') if name is None or x['name'] == name]
def tm(pg): return pg.evaluate('window.__M.tm')
def pz(pg): return pg.evaluate('window.__M.pz')
def lt(pg): return pg.evaluate("(()=>{const t=document.querySelectorAll('.toast');return t.length?t[t.length-1].textContent:''})()")
def accept(pg): auto(pg)
def counts(pm): 
    c = {}; [c.__setitem__(v, c.get(v, 0) + 1) for v in pm.values()]; return c

with sync_playwright() as p:
    T, B = people_set(); 
    # ---- 1. before the database file is run: nothing shows, nothing breaks
    b, pg, errs = open_page(p, db()); 
    check('1.1 before r2_13: no Messages tab', pg.query_selector('button[data-tab="messages"]') is None)
    go_tab(pg, 'settings'); check('1.2 before r2_13: no Game messages card, no crash', pg.query_selector('#msgshow') is None and not errs, errs); b.close()
    # ---- 2. tab, banner and the Settings switch
    b, pg, errs = opn(p, mdb(T, B), 'messages'); t = pg.inner_text('#v')
    check('2.1 Messages tab appears, with the three messages and 0 people each', pg.query_selector('button[data-tab="messages"]') and 'Tiger' in t and 'Elephant' in t and 'Lion' in t and t.count('0 people') >= 3, t[:300])
    check('2.2 banner says messages are HIDDEN while the switch is off', 'HIDDEN' in t and 'Show messages on tickets' in t)
    auto(pg, False); pg.click('#mtoggle'); pg.wait_for_timeout(350)
    check('2.3 Show: asks first; Cancel changes nothing', not calls(pg, 'admin_set_show_messages'))
    accept(pg); pg.click('#mtoggle'); pg.wait_for_timeout(250)
    check('2.4 Show: after OK the database function gets p_show = true', calls(pg, 'admin_set_show_messages')[-1]['args'] == {'p_show': True}, calls(pg))
    check('2.5 the banner now says SHOWN', 'SHOWN' in pg.inner_text('#v') and 'Hide messages' in pg.inner_text('#v'))
    pg.click('#mtoggle'); pg.wait_for_timeout(250)
    check('2.6 Hide: no question asked, sends false', calls(pg, 'admin_set_show_messages')[-1]['args'] == {'p_show': False} and 'HIDDEN' in pg.inner_text('#v'))
    go_tab(pg, 'settings'); check('2.7 Settings no longer repeats the Show/Hide switch (it lives only in the Messages tab)', pg.query_selector('#msgshow') is None and 'Game messages' not in pg.inner_text('#v'))
    check('2.8 the jump bar has no Messages entry', not any('Messages' == x.inner_text().strip() for x in pg.query_selector_all('#snav .chip')))
    check('2.9 the Messages tab itself still shows the state after the toggles', 'HIDDEN' in (go_tab(pg, 'messages') or pg.inner_text('#v')) or 'HIDDEN' in pg.inner_text('#v'))
    check('2.10 no page errors', not errs, errs); b.close()
    # ---- 3. writing messages
    b, pg, errs = opn(p, mdb(T, B), 'messages')
    pg.click('#msave'); pg.wait_for_timeout(100); check('3.1 saving an empty form asks for a name and calls nothing', 'Type a name' in lt(pg) and not calls(pg, 'admin_save_message'))
    pg.fill('#mname', 'Zebra'); pg.click('#msave'); pg.wait_for_timeout(300); check('3.2 name without text asks for the text', 'Type the text' in lt(pg) and not calls(pg, 'admin_save_message'))
    pg.fill('#mbody', 'Team ZEBRA 🦓'); pg.click('#msave'); pg.wait_for_timeout(300)
    check('3.3 a new message is sent with a null id and listed', calls(pg, 'admin_save_message')[-1]['args'] == {'p_id': None, 'p_name': 'Zebra', 'p_body': 'Team ZEBRA 🦓'} and 'Zebra' in pg.inner_text('#v') and 'ZEBRA 🦓' in pg.inner_text('#v'))
    check('3.4 the form is empty again', pg.input_value('#mname') == '' and pg.input_value('#mbody') == '')
    pg.fill('#mname', 'tiger'); pg.fill('#mbody', 'x'); pg.click('#msave'); pg.wait_for_timeout(300)
    check('3.5 a repeated name shows a plain sentence, never the code', 'already a message' in lt(pg) and 'NAME_TAKEN' not in pg.inner_text('body'), lt(pg))
    pg.fill('#mname', '<b>Hi</b>'); pg.fill('#mbody', '<img src=x onerror=alert(1)>'); pg.click('#msave'); pg.wait_for_timeout(300)
    check('3.6 markup typed into a message is shown as plain text, not run', pg.query_selector('#v img') is None and '<img src=x' in pg.inner_text('#v') and not errs, errs)
    pg.click('[data-medit="m1"]'); check('3.7 Edit fills the form with that message', pg.input_value('#mname') == 'Tiger' and pg.input_value('#mbody') == 'Team TIGER' and 'Save changes' in pg.inner_text('#msave'))
    pg.fill('#mbody', 'Team TIGER 🐯'); pg.click('#msave'); pg.wait_for_timeout(300)
    check('3.8 saving an edit sends the same id', calls(pg, 'admin_save_message')[-1]['args'] == {'p_id': 'm1', 'p_name': 'Tiger', 'p_body': 'Team TIGER 🐯'})
    pg.click('[data-medit="m2"]'); pg.click('#mcancel'); check('3.9 Cancel edit empties the form', pg.input_value('#mname') == '' and 'Add message' in pg.inner_text('#msave'))
    pg.fill('#mname', 'Draft'); pg.select_option('#mscope', 'present'); check('3.10 typed text survives a change elsewhere on the tab', pg.input_value('#mname') == 'Draft')
    b.close()
    # ---- 4. deal out at random
    b, pg, errs = opn(p, mdb(T, B), 'messages')
    check('4.1 the group size says 30 people', '30' in pg.inner_text('.msgrid .card:nth-child(2) p.mute b') or '30 people' in pg.inner_text('#v'))
    pg.click('#mshuf'); pg.wait_for_timeout(150); pv = pg.inner_text('.plan')
    check('4.2 the preview says nothing is saved yet and shows 10 / 10 / 10', 'nothing is saved' in pv and pv.count('10') >= 3 and not calls(pg, 'admin_assign_messages'), pv[:200])
    pg.click('#mplanagain'); pg.wait_for_timeout(100); check('4.3 Shuffle again re-deals (still nothing saved)', not calls(pg, 'admin_assign_messages') and pg.query_selector('.plan') is not None)
    accept(pg); pg.click('#mplansave'); pg.wait_for_timeout(350)
    a = calls(pg, 'admin_assign_messages')[-1]['args']['p_pairs']; ts = [x['t'] for x in a]
    check('4.4 Save sends 30 pairs, one per person, no one twice', len(a) == 30 and len(set(ts)) == 30 and set(ts) == {t['id'] for t in T}, len(a))
    check('4.5 each of the three messages went to exactly 10', sorted(counts({x['t']: x['m'] for x in a}).values()) == [10, 10, 10], counts({x['t']: x['m'] for x in a}))
    check('4.6 after saving, the page shows 10 people per message and the preview is gone', pg.query_selector('.plan') is None and pg.inner_text('#v').count('10 people') >= 3)
    pg.click('.ros summary >> nth=0'); check('4.7 Who has what lists names', 'Person' in pg.inner_text('.ros >> nth=0'))
    check('4.8 People tab shows each person\'s message tag', (pg.click('button[data-tab="people"]'), 'Tiger' in pg.inner_text('#tbl') or 'Elephant' in pg.inner_text('#tbl'))[1])
    check('4.9 no page errors', not errs, errs); b.close()
    # ---- 5. uneven numbers, kept together, only present, only people with none
    T31, B31 = people_set(n_books=31, per=1)
    b, pg, errs = opn(p, mdb(T31, B31), 'messages'); pg.click('#mshuf'); accept(pg); pg.click('#mplansave'); pg.wait_for_timeout(350)
    check('5.1 31 people into 3 messages: 11 / 10 / 10', sorted(counts(tm(pg)).values()) == [10, 10, 11], counts(tm(pg))); b.close()
    b, pg, errs = opn(p, mdb(T, B), 'messages'); pg.check('#mtog'); pg.click('#mshuf'); accept(pg); pg.click('#mplansave'); pg.wait_for_timeout(350)
    byb = {}; [byb.setdefault(t['booking_id'], set()).add(tm(pg)[t['id']]) for t in T]
    check('5.2 "keep bookings together": everyone in a booking got the same message, 4 / 3 / 3 bookings = 12 / 9 / 9 people', all(len(v) == 1 for v in byb.values()) and sorted(counts(tm(pg)).values()) == [9, 9, 12], (byb, counts(tm(pg))))
    check('5.2b ... and it is still balanced to within one booking (3 people)', max(counts(tm(pg)).values()) - min(counts(tm(pg)).values()) <= 3, counts(tm(pg))); b.close()
    PRES = set(range(1, 9))
    Tp, Bp = people_set(present=PRES)
    b, pg, errs = opn(p, mdb(Tp, Bp), 'messages'); pg.select_option('#mscope', 'present'); pg.wait_for_timeout(100)
    check('5.3 "only present": the group size becomes 8', '8 people are in this group' in pg.inner_text('#v'), pg.inner_text('#v')[:400])
    pg.click('#mshuf'); accept(pg); pg.click('#mplansave'); pg.wait_for_timeout(350)
    check('5.4 only the 8 present people got a message, split 3 / 3 / 2', set(tm(pg)) == {f't{n}' for n in PRES} and sorted(counts(tm(pg)).values()) == [2, 3, 3], (len(tm(pg)), counts(tm(pg)))); b.close()
    first10 = {f't{n}': 'm1' for n in range(1, 11)}
    b, pg, errs = opn(p, mdb(T, B, assigned=first10), 'messages'); pg.check('#mnomsg'); pg.wait_for_timeout(100)
    check('5.5 "only people with no message": group size 20', '20 people are in this group' in pg.inner_text('#v'))
    pg.click('#mshuf'); pg.wait_for_timeout(100); check('5.6 the preview does not touch the 10 who already have one', pg.query_selector('.plan') is not None and 'already have a different' not in pg.inner_text('.plan'))
    accept(pg); pg.click('#mplansave'); pg.wait_for_timeout(350); c = counts(tm(pg))
    check('5.7 the 20 new people balance against the existing 10: Tiger 10, Elephant 10, Lion 10', c == {'m1': 10, 'm2': 10, 'm3': 10}, c)
    check('5.8 the first ten still have Tiger', all(tm(pg)[k] == 'm1' for k in first10)); b.close()
    # replacing existing messages must warn
    b, pg, errs = opn(p, mdb(T, B, assigned=first10), 'messages'); pg.click('#mshuf'); pg.wait_for_timeout(100)
    check('5.9 a full reshuffle over people who already have messages warns that some will be replaced', 'will be replaced' in pg.inner_text('.plan') or 'already have a different' in pg.inner_text('.plan'), pg.inner_text('.plan')[:200])
    auto(pg, False); pg.click('#mplansave'); pg.wait_for_timeout(350); msg = dlg_msgs(pg)
    check('5.10 the Save question also says so, and Cancel saves nothing', msg and 'replaced' in msg[0] and not calls(pg, 'admin_assign_messages'), msg)
    pg.click('#mplancancel'); check('5.11 Cancel closes the preview', pg.query_selector('.plan') is None); b.close()
    # use only some of the messages
    b, pg, errs = opn(p, mdb(T, B), 'messages'); pg.uncheck('[data-muse="m3"]'); pg.click('#mshuf'); accept(pg); pg.click('#mplansave'); pg.wait_for_timeout(350)
    check('5.12 unticking a message leaves it out: 15 / 15 / 0', counts(tm(pg)) == {'m1': 15, 'm2': 15}, counts(tm(pg)))
    pg.uncheck('[data-muse="m1"]'); pg.uncheck('[data-muse="m2"]'); check('5.13 with none ticked the button warns and does nothing', (pg.click('#mshuf'), 'at least one' in lt(pg))[1]); b.close()
    # ---- 6. same message to the whole group, taking away
    b, pg, errs = opn(p, mdb(T, B), 'messages')
    pg.click('#mgivego'); pg.wait_for_timeout(100); check('6.1 "Give" without choosing a message asks you to choose', 'Choose a message' in lt(pg) and not calls(pg, 'admin_assign_messages'))
    pg.select_option('#mgive', 'm2'); accept(pg); pg.click('#mgivego'); pg.wait_for_timeout(350)
    check('6.2 everyone in the group got Elephant', counts(tm(pg)) == {'m2': 30}, counts(tm(pg)))
    accept(pg); pg.click('[data-mclear="m2"]'); pg.wait_for_timeout(350); check('6.3 "Take away" on one message empties it', tm(pg) == {} and calls(pg, 'admin_clear_messages')[-1]['args'] == {'p_message': 'm2', 'p_tickets': None})
    pg.select_option('#mgive', 'm1'); accept(pg); pg.click('#mgivego'); pg.wait_for_timeout(300)
    pg.select_option('#mscope', 'present'); pg.wait_for_timeout(100); check('6.4 a group with nobody present: Give is disabled', pg.is_disabled('#mgivego'))
    pg.select_option('#mscope', 'paid'); accept(pg); pg.click('#mclrall'); pg.wait_for_timeout(350)
    check('6.5 "From everyone" clears all and sends no filters', tm(pg) == {} and calls(pg, 'admin_clear_messages')[-1]['args'] == {'p_message': None, 'p_tickets': None})
    check('6.6 ... and the messages themselves are still there', 'Tiger' in pg.inner_text('#v') and 'Lion' in pg.inner_text('#v'))
    dlg_msgs(pg); auto(pg); pg.click('[data-mdel="m3"]'); pg.wait_for_timeout(500); dl = dlg_msgs(pg)
    check('6.7 Delete asks first, then removes the message', dl and 'Lion' in dl[0] and 'Lion' not in pg.inner_text('#v').split('Who has what')[0] and calls(pg, 'admin_delete_message')[-1]['args'] == {'p_id': 'm3'}, dl)
    pg.select_option('#mgive', 'm1'); pg.select_option('#mscope', 'present'); b.close()
    b, pg, errs = opn(p, mdb(Tp, Bp, assigned={f't{n}': 'm1' for n in range(1, 31)}), 'messages'); pg.select_option('#mscope', 'present'); accept(pg); pg.click('#mclrgrp'); pg.wait_for_timeout(350)
    check('6.8 "From the people in this group" clears only those 8', set(tm(pg)) == {f't{n}' for n in range(9, 31)} and sorted(calls(pg, 'admin_clear_messages')[-1]['args']['p_tickets']) == sorted(f't{n}' for n in PRES), len(tm(pg))); b.close()
    # ---- 7. who is left out of every group
    Tx, Bx = people_set(n_books=4, per=3)
    Bx[1]['status'] = 'pending'; Bx[2]['status'] = 'rejected'; Tx[0]['transferred_out_at'] = '2026-10-22T10:00:00Z'; Tx[10]['kind'] = 'coordinator'; Tx[10]['coord_no'] = 1; Tx[10]['ticket_no'] = None
    b, pg, errs = opn(p, mdb(Tx, Bx), 'messages'); pg.click('#mshuf'); accept(pg); pg.click('#mplansave'); pg.wait_for_timeout(350)
    got = set(tm(pg)); want = {t['id'] for t in Tx if not t['transferred_out_at'] and t['booking_id'] in ('b1', 'b4')}
    check('7.1 only paid, not-transferred-away people are dealt to (pending, rejected and the transferred ticket are left out)', got == want, (sorted(got), sorted(want)))
    check('7.2 a coordinator is dealt to like anyone else', 't11' in got, sorted(got))
    b.close()
    Ty = [dict(t) for t in Tx]; Ty[6]['checked_in_at'] = '2026-11-22T09:00:00Z'; Ty[9]['checked_in_at'] = '2026-11-22T09:00:00Z'; Ty[3]['checked_in_at'] = '2026-11-22T09:00:00Z'   # b3 rejected, b4 paid, b2 pending
    b, pg, errs = opn(p, mdb(Ty, Bx), 'messages'); pg.select_option('#mscope', 'present'); pg.click('#mshuf'); accept(pg); pg.click('#mplansave'); pg.wait_for_timeout(350)
    check('7.3 "present" never includes a rejected booking (a rejected person who was checked in is left out); the paid present person and the pending one are dealt to', set(tm(pg)) == {Ty[9]['id'], Ty[3]['id']}, sorted(tm(pg)))
    b.close()
    # ---- 8. one person, from their sheet
    b, pg, errs = opn(p, mdb(T, B), 'people'); pg.click('#tbl .lk >> nth=0') if pg.query_selector('#tbl .lk') else pg.click('#tbl .pc b >> nth=0'); pg.wait_for_timeout(100)
    if not pg.query_selector('#sheetbg'): pg.evaluate("openSheet('person','t1')"); pg.wait_for_timeout(100)
    check('8.1 the person sheet has a Message select with "None" and the three names', pg.query_selector('#sheetbg select[data-pmsg]') is not None and pg.inner_text('#sheetbg select[data-pmsg]').split() == ['None', 'Tiger', 'Elephant', 'Lion'], pg.inner_text('#sheetbg')[:200])
    pg.select_option('#sheetbg select[data-pmsg]', 'm2'); pg.wait_for_timeout(350)
    check('8.2 choosing a message sends one pair', calls(pg, 'admin_assign_messages')[-1]['args'] == {'p_pairs': [{'t': 't1', 'm': 'm2'}]}, calls(pg))
    check('8.3 the sheet still shows it chosen after the page refreshed', pg.eval_on_selector('#sheetbg select[data-pmsg]', 'e=>e.value') == 'm2')
    pg.select_option('#sheetbg select[data-pmsg]', ''); pg.wait_for_timeout(350)
    check('8.4 choosing None clears just that person', calls(pg, 'admin_clear_messages')[-1]['args'] == {'p_message': None, 'p_tickets': ['t1']} and tm(pg) == {})
    check('8.5 no page errors', not errs, errs); b.close()
    # ---- 9. errors from the database are explained, and the page recovers
    b, pg, errs = opn(p, mdb(T, B), 'messages'); pg.evaluate("window.__FAIL={admin_assign_messages:'TICKET_NOT_FOUND'}"); pg.select_option('#mgive', 'm1'); accept(pg); pg.click('#mgivego'); pg.wait_for_timeout(350)
    check('9.1 a refused save shows a plain sentence, not the code', 'no longer exists' in lt(pg) and 'TICKET_NOT_FOUND' not in pg.inner_text('body'), lt(pg))
    check('9.2 nothing was changed on screen', tm(pg) == {}); b.close()
    # ---- 10. phone width
    b, pg, errs = opn(p, mdb(T, B), 'messages', w=360, h=740); sw = pg.evaluate('document.documentElement.scrollWidth'); check('10.1 no sideways scroll at 360 px', sw <= 360, sw)
    pg.click('#mshuf'); pg.wait_for_timeout(150); check('10.2 preview fits at 360 px', pg.evaluate('document.documentElement.scrollWidth') <= 360); b.close()
    # ---- 12. the shuffle itself: balanced, random, no one twice
    b, pg, errs = opn(p, mdb(T, B), 'messages')
    r = pg.evaluate("""()=>{const P=Array.from({length:150},(_,i)=>({id:'p'+i,booking_id:'b'+Math.floor(i/3)})),ids=['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o'];
      const worst=[],seen={},first={};let sameAsLast=0,last=null;
      for(let r=0;r<300;r++){const pairs=planShuffle(P,ids,{},false),c={};pairs.forEach(([t,m])=>c[m]=(c[m]||0)+1);
        worst.push(Math.max(...Object.values(c))-Math.min(...Object.values(c)));if(new Set(pairs.map(x=>x[0])).size!==150)return {dupe:true};
        const s=pairs.slice().sort().join();if(s===last)sameAsLast++;last=s;seen[s]=1;pairs.forEach(([t,m])=>{if(t==='p0')first[m]=(first[m]||0)+1})}
      const odd=planShuffle(Array.from({length:148},(_,i)=>({id:'q'+i,booking_id:'x'+i})),ids,{},false),oc={};odd.forEach(([t,m])=>oc[m]=(oc[m]||0)+1);
      return {maxdiff:Math.max(...worst),distinct:Object.keys(seen).length,sameAsLast,firstSpread:Object.keys(first).length,firstMax:Math.max(...Object.values(first)),n148:Object.values(oc).sort().join()}}""")
    check('12.1 150 people / 15 messages x 300 runs: always exactly even, nobody twice', r.get('maxdiff') == 0 and not r.get('dupe'), r)
    check('12.2 every run is different, and person #1 lands on all 15 messages over 300 runs, none hugely favoured', r['distinct'] == 300 and r['sameAsLast'] == 0 and r['firstSpread'] == 15 and r['firstMax'] < 60, r)
    r2 = pg.evaluate("""()=>{const P=Array.from({length:31},(_,i)=>({id:'p'+i,booking_id:'b'+i})),big={};for(let r=0;r<200;r++){const c={};planShuffle(P,['a','b','c'],{},false).forEach(([t,m])=>c[m]=(c[m]||0)+1);const k=Object.keys(c).find(x=>c[x]===11);big[k]=(big[k]||0)+1}return big}""")
    check('12.4 31 people / 3 messages: the message that gets the extra person is chosen at random (all three get it sometimes)', len(r2) == 3 and min(r2.values()) > 30, r2)
    check('12.3 148 people / 15 messages: thirteen of 10 and two of 9... sizes differ by at most 1', sorted(map(int, r['n148'].split(','))) == [9, 9] + [10] * 13, r['n148'])
    b.close()

    # ---- 13. the lottery (needs r2_14; hidden before)
    b, pg, errs = opn(p, mdb(T, B), 'messages')
    check('13.1 before r2_14 is run: no lottery card, no crash, the rest still works', pg.query_selector('#ldraw') is None and 'Pick random people' not in pg.inner_text('#v') and '3. Who has what' in pg.inner_text('#v') and not errs, errs); b.close()
    b, pg, errs = opn(p, mdb(T, B, prizes={}), 'messages')
    check('13.2 with r2_14: the card is there, numbered 3, and "Who has what" becomes 4', '3. Pick random people' in pg.inner_text('#v') and '4. Who has what' in pg.inner_text('#v'))
    check('13.3 it says 30 eligible by default', '30 people are eligible' in pg.inner_text('#v'))
    pg.click('#ldraw'); pg.wait_for_timeout(100); check('13.4 Draw without a prize line asks for it and draws nothing', 'message line' in lt(pg) and pg.query_selector('.plan') is None)
    pg.fill('#lbody', 'You won extra food! 🍛'); pg.fill('#ln', '0'); pg.click('#ldraw'); pg.wait_for_timeout(100); check('13.5 0 winners is refused', 'how many' in lt(pg) and pg.query_selector('.plan') is None)
    pg.fill('#ln', '31'); pg.dispatch_event('#ln', 'change'); pg.wait_for_timeout(100); pg.click('#ldraw'); pg.wait_for_timeout(100); check('13.6 more winners than eligible people is refused with the number', 'Only 30' in lt(pg))
    pg.fill('#ln', '1'); pg.dispatch_event('#ln', 'change'); pg.wait_for_timeout(100)
    check('13.7 typed prize line survives re-drawing the card', pg.input_value('#lbody') == 'You won extra food! 🍛')
    pg.click('#ldraw'); pg.wait_for_timeout(100); pv = pg.inner_text('.plan')
    check('13.8 Draw shows ONE winner and says nothing is saved', 'nothing is saved' in pv and 'The person picked is' in pv and not calls(pg, 'admin_set_prizes'), pv[:200])
    w1 = pg.evaluate('S.mf.lot.plan'); pg.click('#ldrawagain'); pg.wait_for_timeout(50)
    accept(pg); pg.click('#lsave'); pg.wait_for_timeout(350); c = calls(pg, 'admin_set_prizes')[-1]['args']
    check('13.9 Save sends exactly the previewed winner with the prize text', c['p_body'] == 'You won extra food! 🍛' and len(c['p_tickets']) == 1 and c['p_tickets'][0] in {t['id'] for t in T}, c)
    check('13.10 the winner now appears under "Winners so far (1)" with the text, and the preview is gone', 'Picked so far (1)' in pg.inner_text('#v') and 'extra food' in pg.inner_text('#v') and pg.query_selector('.plan') is None)
    check('13.11 the draw excludes people who already won (default): the only winner is not eligible any more', '29 people are eligible' in pg.inner_text('#v'))
    pg.uncheck('#lex'); pg.wait_for_timeout(100); check('13.12 unticking "leave out people who already have a prize" makes everyone eligible again', '30 people are eligible' in pg.inner_text('#v')); pg.check('#lex'); pg.wait_for_timeout(100)
    pg.fill('#ln', '5'); pg.dispatch_event('#ln', 'change'); pg.wait_for_timeout(100); pg.click('#ldraw'); pg.wait_for_timeout(100); pl = pg.evaluate('S.mf.lot.plan')
    check('13.13 five winners: five different people, none of them the earlier winner', len(pl) == 5 and len(set(pl)) == 5 and not (set(pl) & set(pz(pg))), pl)
    check('13.14 the preview says "The people picked are"', 'The people picked are' in pg.inner_text('.plan'))
    pg.click('#lcancel'); check('13.15 Cancel closes the preview and saves nothing new', pg.query_selector('.plan') is None and len(pz(pg)) == 1)
    check('13.16 People tab shows a prize tag on exactly one person', (pg.click('button[data-tab="people"]'), pg.inner_text('#tbl').count('🎲 picked'))[1] == 1)
    wid = list(pz(pg))[0]; pg.evaluate(f"openSheet('person','{wid}')"); pg.wait_for_timeout(100)
    check('13.17 the winner\'s sheet shows the prize line', 'Message line' in pg.inner_text('#sheetbg') and 'extra food' in pg.inner_text('#sheetbg'))
    pg.keyboard.press('Escape'); pg.click('button[data-tab="messages"]'); accept(pg); pg.click('[data-pzdel]'); pg.wait_for_timeout(350)
    check('13.18 "Take away" removes just that prize', pz(pg) == {} and calls(pg, 'admin_clear_prizes')[-1]['args'] == {'p_tickets': [wid]})
    check('13.19 no page errors in the lottery', not errs, errs); b.close()
    b, pg, errs = opn(p, mdb(T, B, prizes={}), 'messages'); pg.fill('#lbody', 'Five winners'); pg.fill('#ln', '5'); pg.dispatch_event('#ln', 'change'); pg.wait_for_timeout(100)
    pg.click('#ldraw'); pg.click('#ldrawagain'); pg.wait_for_timeout(100); plan5 = pg.evaluate('S.mf.lot.plan'); accept(pg); pg.click('#lsave'); pg.wait_for_timeout(350); c5 = calls(pg, 'admin_set_prizes')[-1]['args']
    check('13.19b Save sends exactly the five previewed winners, in the previewed order (not a fresh draw)', c5['p_tickets'] == plan5 and len(plan5) == 5 and sorted(pz(pg)) == sorted(plan5), (c5['p_tickets'], plan5)); b.close()
    # present scope, rejected, transferred away, pending are never eligible
    Tz, Bz = people_set(n_books=4, per=3, present={2, 4, 5, 6, 8, 9, 10, 11, 12})
    Bz[1]['status'] = 'pending'; Bz[2]['status'] = 'rejected'; Tz[0]['transferred_out_at'] = '2026-10-22T10:00:00Z'
    b, pg, errs = opn(p, mdb(Tz, Bz, prizes={}), 'messages')
    check('13.20 "Draw from everyone with a paid ticket": only paid, not-transferred people count (b1 minus the transferred one, plus b4 = 5)', '5 people are eligible' in pg.inner_text('#v'), pg.inner_text('#v')[:600])
    pg.select_option('#lscope', 'present'); pg.wait_for_timeout(100)
    check('13.21 "Only people present": only those checked in; pending people who are present count, rejected and transferred never (b1:1 + b2:3 + b4:3 = 7)', '7 people are eligible' in pg.inner_text('#v'), pg.inner_text('#v')[:600])
    pg.fill('#lbody', 'P'); pg.fill('#ln', '7'); pg.dispatch_event('#ln', 'change'); pg.wait_for_timeout(100); pg.click('#ldraw'); pg.wait_for_timeout(100); pl = pg.evaluate('S.mf.lot.plan')
    ok_ids = {t['id'] for t in Tz if not t['transferred_out_at'] and t['booking_id'] in ('b1', 'b2', 'b4') and t['checked_in_at']}
    check('13.22 drawing all 7 eligible people returns exactly them, no one else', set(pl) == ok_ids and len(pl) == 7, (sorted(pl), sorted(ok_ids))); b.close()
    # the draw itself: uniform, no repeats
    b, pg, errs = opn(p, mdb(T, B, prizes={}), 'messages')
    r = pg.evaluate("""()=>{const pool=Array.from({length:10},(_,i)=>({id:'p'+i})),c={};let dupe=false,wrong=false;
      for(let k=0;k<6000;k++){const w=drawWinners(pool,1);if(w.length!==1)wrong=true;c[w[0].id]=(c[w[0].id]||0)+1}
      for(let k=0;k<2000;k++){const w=drawWinners(pool,3);if(new Set(w.map(x=>x.id)).size!==3||w.length!==3)dupe=true}
      const all=drawWinners(pool,50);const small=drawWinners([],3);
      return {c,dupe,wrong,all:all.length,small:small.length}}""")
    cnt = list(r['c'].values())
    check('13.23 6000 single draws among 10 people: all 10 win, each about 600 (500 to 700), none favoured', len(cnt) == 10 and min(cnt) > 500 and max(cnt) < 700 and not r['wrong'], r['c'])
    check('13.24 draws of 3: always 3 different people', not r['dupe'])
    check('13.25 asking for more than the pool gives the whole pool; an empty pool gives nobody', r['all'] == 10 and r['small'] == 0, r)
    # errors: database refuses
    b.close()
    b, pg, errs = opn(p, mdb(T, B, prizes={}), 'messages'); pg.evaluate("window.__FAIL={admin_set_prizes:'TICKET_NOT_FOUND'}"); pg.fill('#lbody', 'x'); pg.click('#ldraw'); accept(pg); pg.click('#lsave'); pg.wait_for_timeout(350)
    check('13.26 a refused save explains itself in words and keeps nothing', 'no longer exists' in lt(pg) and pz(pg) == {}, lt(pg)); b.close()
    # winner replaced warning; "take every prize away"
    b, pg, errs = opn(p, mdb(T, B, prizes={'t1': 'old prize', 't2': 'old prize'}), 'messages'); pg.uncheck('#lex'); pg.fill('#lbody', 'new'); pg.fill('#ln', '30'); pg.dispatch_event('#ln', 'change'); pg.wait_for_timeout(100); pg.click('#ldraw'); pg.wait_for_timeout(100)
    check('13.27 the preview warns when some winners already have a prize', 'already has a message line' in pg.inner_text('.plan'))
    auto(pg, False); pg.click('#lsave'); pg.wait_for_timeout(350); msg = dlg_msgs(pg)
    check('13.28 the Save question says the old prize will be replaced, and Cancel saves nothing', msg and 'replaced' in msg[0] and not calls(pg, 'admin_set_prizes'), msg)
    pg.click('#lcancel'); accept(pg); pg.click('#pzclr'); pg.wait_for_timeout(350)
    check('13.29 "Take every prize away" clears all and does not touch team messages', pz(pg) == {} and calls(pg, 'admin_clear_prizes')[-1]['args'] == {'p_tickets': None}); b.close()
    b, pg, errs = opn(p, mdb(T, B, assigned={'t1': 'm1'}, prizes={'t1': 'Free dessert'}), 'messages', w=360, h=740); pg.fill('#lbody', 'x'); pg.click('#ldraw'); pg.wait_for_timeout(100)
    check('13.30 no sideways scroll at 360 px with the lottery open', pg.evaluate('document.documentElement.scrollWidth') <= 360, pg.evaluate('document.documentElement.scrollWidth'))
    check('13.31 a team message and a prize on the same person are both kept', tm(pg) == {'t1': 'm1'} and pz(pg) == {'t1': 'Free dessert'}); b.close()
    # 13h. the editable heading
    b, pg, errs = opn(p, mdb(T, B, prizes={}), 'messages')
    check('13.40 the heading box exists, is empty, allows 60 characters, and says what happens when left empty', pg.input_value('#lhead') == '' and pg.get_attribute('#lhead', 'maxlength') == '60' and 'You are a winner!' in pg.inner_text('#v'))
    pg.fill('#lbody', 'Find the organiser'); pg.fill('#lhead', '  Secret mission  '); pg.click('#ldraw'); pg.wait_for_timeout(100); pg.click('#ldrawagain'); pg.wait_for_timeout(100)
    check('13.41 a typed heading survives re-drawing the card', pg.input_value('#lhead') == '  Secret mission  ')
    auto(pg); pg.click('#lsave'); pg.wait_for_timeout(500); msg = dlg_msgs(pg); c = calls(pg, 'admin_set_prizes')[-1]['args']
    check('13.42 Save sends the trimmed heading as p_heading, and the Save question names the heading', c['p_heading'] == 'Secret mission' and c['p_body'] == 'Find the organiser' and msg and 'Secret mission' in msg[0], (c, msg))
    check('13.43 the "Picked so far" list shows the heading above the line', 'Secret mission' in pg.inner_text('#v') and 'Find the organiser' in pg.inner_text('#v'))
    wid = list(pz(pg))[0]; pg.evaluate(f"openSheet('person','{wid}')"); pg.wait_for_timeout(100)
    check('13.44 the person sheet shows heading and line', 'Secret mission: Find the organiser' in pg.inner_text('#sheetbg'), pg.inner_text('#sheetbg')[-200:]); pg.keyboard.press('Escape')
    check('13.45 no page errors', not errs, errs); b.close()
    b, pg, errs = opn(p, mdb(T, B, prizes={}), 'messages'); pg.fill('#lbody', 'Plain'); pg.click('#ldraw'); pg.wait_for_timeout(100); accept(pg); pg.click('#lsave'); pg.wait_for_timeout(350); c = calls(pg, 'admin_set_prizes')[-1]['args']
    check('13.46 an empty heading is sent as null (the database then uses the default), and the list shows the default', c['p_heading'] is None and 'You are a winner!' in pg.inner_text('#v').split('Picked so far')[1], c); b.close()
    b, pg, errs = opn(p, mdb(T, B, prizes={}), 'messages'); pg.fill('#lbody', 'Line'); pg.click('#ldraw'); pg.wait_for_timeout(100); pg.fill('#lhead', 'Typed after the draw'); pg.fill('#ln', '2'); pg.dispatch_event('#ln', 'change'); pg.wait_for_timeout(100)
    check('13.48 a heading typed while a preview is open survives the card being redrawn (number of people changed)', pg.input_value('#lhead') == 'Typed after the draw', pg.input_value('#lhead')); b.close()
    b, pg, errs = opn(p, mdb(T, B, prizes={'t1': 'old'}, heads={'t1': None}), 'messages')
    check('13.49 an old row without a heading is listed with the default heading (and nothing crashes)', 'You are a winner!' in pg.inner_text('#v').split('Picked so far')[1] and not errs, errs); b.close()
    b, pg, errs = opn(p, mdb(T, B, prizes={'t1': 'old'}, heads={'t1': 'Old heading'}), 'messages')
    check('13.47 a heading already in the database is listed for its person', 'Old heading' in pg.inner_text('#v')); b.close()
print(f'{sum(results)} passed, {len(results)-sum(results)} failed')
