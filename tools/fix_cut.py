#!/usr/bin/env python3
"""アーカイブ由来で本文が途切れている長文ポスト（x フラグ付き）を、X API の note_tweet から全文に置き換える。
手動実行用（GitHub Actions: fix-cut）。必要: X_BEARER_TOKEN。

posts.json の t はスレッド（自己リプライ）を "\n\n" でつないだもの。id は先頭ポストなので、
先頭ポストの「…」で切れた部分を全文に差し替え、まだ「…」が残るときは自分のタイムラインから同じスレッドの続きを取って差し替える。
直せなかったものは x を残す（サイトに「続きはXで読む」が出る）。"""
import json, os, re, sys, urllib.request, urllib.parse, urllib.error

FILES = ['posts.json', 'posts-old.json']
ME = '1082527986430013440'
CUT = re.compile(r'…(?=\n|$)')  # 段落末・本文末の「…」


def clean(t):
    """API のポスト（dict）から全文を作る。t.co を展開し、写真リンクと末尾の t.co を消す。"""
    nt = t.get('note_tweet') or {}
    txt = nt.get('text') or t['text']
    ent = nt.get('entities') or t.get('entities') or {}
    for u in ent.get('urls', []):
        ex = u.get('expanded_url') or u.get('url')
        if 'x.com/' in ex and '/photo/' in ex: txt = txt.replace(u['url'], ''); continue
        txt = txt.replace(u['url'], ex)
    return re.sub(r'\s*https://t\.co/\w+\s*$', '', txt).strip()


def norm(s):
    return re.sub(r'https?://\S+|\s+', '', s)


def repair(t, full):
    """t の先頭ポストが full の途中で切れていれば差し替えた t を返す。直せなければ None。"""
    nf = norm(full)
    for m in CUT.finditer(t):
        head = t[:m.start()].rstrip()
        nh = norm(head)
        if not nh: continue
        if len(nh) > len(nf): break  # 先頭ポストより後ろの「…」
        if len(nf) <= len(nh) or not nf.startswith(nh): continue
        rest = nf[len(nh):].lstrip('…')
        if not rest or norm(t[m.end():]).startswith(rest[:20]): continue  # 本人の「…」で、続きが既にある
        return full + t[m.end():]
    return None


def repair_part(t, full):
    """スレッド内のどこかにある、full が途中で切れた段落を差し替える。直せなければ None。"""
    nf = norm(full)
    key = full.strip()[:15]
    i = t.find(key) if key else -1
    if i < 0: return None
    for m in CUT.finditer(t, i):
        nh = norm(t[i:m.start()])
        if len(nh) > len(nf): return None
        if len(nf) <= len(nh) or not nf.startswith(nh): continue
        rest = nf[len(nh):].lstrip('…')
        if not rest or norm(t[m.end():]).startswith(rest[:20]): continue  # 本人の「…」
        return t[:i] + full + t[m.end():]
    return None


def snow_time(i):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(((int(i) >> 22) + 1288834974657) / 1000, timezone.utc)


def still_cut(t):
    return bool(CUT.search(t))


def main():
    token = re.sub(r'\s+', '', re.sub(r'^(Bearer|bearer)\s+', '', os.environ.get('X_BEARER_TOKEN', '').strip()))
    if not token: sys.exit('X_BEARER_TOKEN が未設定です')
    data = {f: json.load(open(f, encoding='utf-8')) for f in FILES if os.path.exists(f)}
    targets = [p for l in data.values() for p in l if p.get('x')]
    print('対象', len(targets), '件')

    def get(path, params):
        req = urllib.request.Request('https://api.x.com/2/' + path + '?' + urllib.parse.urlencode(params), headers={'Authorization': 'Bearer ' + token, 'User-Agent': 'arsenal-archive'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            sys.exit('X API エラー %s: %s' % (e.code, e.read().decode('utf-8', 'replace')[:500]))

    def api(ids): return get('tweets', {'ids': ','.join(ids), 'tweet.fields': 'note_tweet,entities,conversation_id'})

    def parts(root, conv):
        """root から24時間以内の自分のポストのうち、同じスレッドのもの（古い順）。直近3200件より前は取れない。"""
        from datetime import timedelta
        st = snow_time(root); fmt = '%Y-%m-%dT%H:%M:%SZ'
        r = get('users/%s/tweets' % ME, {'start_time': st.strftime(fmt), 'end_time': (st + timedelta(hours=24)).strftime(fmt),
                                          'max_results': 100, 'tweet.fields': 'note_tweet,entities,conversation_id'})
        return sorted((t for t in r.get('data', []) if t.get('conversation_id') == conv and t['id'] != root), key=lambda t: int(t['id']))

    full, conv, errs = {}, {}, {}
    for i in range(0, len(targets), 100):
        r = api([p['id'] for p in targets[i:i + 100]])
        for t in r.get('data', []): full[t['id']] = clean(t); conv[t['id']] = t.get('conversation_id') or t['id']
        for e in r.get('errors', []): errs[e.get('resource_id') or e.get('value')] = e.get('title') or e.get('detail')
    fixed = 0
    for p in targets:
        f = full.get(p['id'])
        if f is None:
            print('  取得不可', p['id'], errs.get(p['id'], '')); continue
        new = repair(p['t'], f) or repair_part(p['t'], f)
        if new is None: print('  先頭は途切れなし/一致せず', p['id'], 'API', len(f), '字', repr(f[:30]))
        whole = False  # スレッドの全ポストを API で確認できたか
        if still_cut(new or p['t']):
            ps = parts(p['id'], conv[p['id']])
            print('  スレッドの続き', len(ps), '件を取得', p['id'])
            for t in ps:
                r2 = repair_part(new or p['t'], clean(t))
                if r2: new = r2; print('    続きを復元', t['id'])
            cur = norm(new or p['t'])
            whole = len(ps) + 1 >= p.get('n', 1) and all(norm(x) in cur for x in [f] + [clean(t) for t in ps])
        if new is None and not whole: continue
        if new is not None: p['t'] = new
        fixed += 1
        if whole or not still_cut(p['t']): p.pop('x', None); print('  復元' if new else '  途切れなしを確認（本人の「…」）', p['id'])
        else: print('  一部を復元（まだ「…」が残る）', p['id'])
    print('置換', fixed, '件 / 未修復', len(targets) - fixed, '件')
    for f, l in data.items():
        open(f, 'w', encoding='utf-8').write('[\n' + ',\n'.join(json.dumps(p, ensure_ascii=False, separators=(',', ':')) for p in l) + '\n]\n')


if __name__ == '__main__':
    main()
