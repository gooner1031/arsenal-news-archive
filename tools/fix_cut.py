#!/usr/bin/env python3
"""アーカイブ由来で本文が途切れている長文ポスト（x フラグ付き）を、X API の note_tweet から全文に置き換える。
手動実行用（GitHub Actions: fix-cut）。必要: X_BEARER_TOKEN。

posts.json の t はスレッド（自己リプライ）を "\n\n" でつないだもの。API で取れるのは先頭ポスト（id）だけなので、
先頭ポストの「…」で切れた部分だけを全文に差し替える。2本目以降が切れている場合は x を残し、ログに出す。"""
import json, os, re, sys, urllib.request, urllib.parse, urllib.error

FILES = ['posts.json', 'posts-old.json']
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
        if rest and norm(t[m.end():]).startswith(rest[:20]): continue  # 本人の「…」で、続きが既にある
        return full + t[m.end():]
    return None


def still_cut(t):
    return bool(CUT.search(t))


def main():
    token = re.sub(r'\s+', '', re.sub(r'^(Bearer|bearer)\s+', '', os.environ.get('X_BEARER_TOKEN', '').strip()))
    if not token: sys.exit('X_BEARER_TOKEN が未設定です')
    data = {f: json.load(open(f, encoding='utf-8')) for f in FILES if os.path.exists(f)}
    targets = [p for l in data.values() for p in l if p.get('x')]
    print('対象', len(targets), '件')

    def api(ids):
        q = urllib.parse.urlencode({'ids': ','.join(ids), 'tweet.fields': 'note_tweet,entities'})
        req = urllib.request.Request('https://api.x.com/2/tweets?' + q, headers={'Authorization': 'Bearer ' + token, 'User-Agent': 'arsenal-archive'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            sys.exit('X API エラー %s: %s' % (e.code, e.read().decode('utf-8', 'replace')[:500]))

    full, errs = {}, {}
    for i in range(0, len(targets), 100):
        r = api([p['id'] for p in targets[i:i + 100]])
        for t in r.get('data', []): full[t['id']] = clean(t)
        for e in r.get('errors', []): errs[e.get('resource_id') or e.get('value')] = e.get('title') or e.get('detail')
    fixed = 0
    for p in targets:
        f = full.get(p['id'])
        if f is None:
            print('  取得不可', p['id'], errs.get(p['id'], '')); continue
        new = repair(p['t'], f)
        if new is None:
            print('  先頭は途切れなし/一致せず', p['id'], 'API', len(f), '字'); continue
        p['t'] = new; fixed += 1
        if still_cut(new): print('  先頭を復元（2本目以降に「…」が残る）', p['id'])
        else: p.pop('x', None); print('  復元', p['id'])
    print('置換', fixed, '件 / 未修復', len(targets) - fixed, '件')
    for f, l in data.items():
        open(f, 'w', encoding='utf-8').write('[\n' + ',\n'.join(json.dumps(p, ensure_ascii=False, separators=(',', ':')) for p in l) + '\n]\n')


if __name__ == '__main__':
    main()
