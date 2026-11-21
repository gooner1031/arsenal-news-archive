#!/usr/bin/env python3
"""アーカイブ由来で本文が途切れている長文ポスト（x フラグ付き）を、X API の note_tweet から全文に置き換える。
手動実行用（GitHub Actions: fix-cut）。必要: X_BEARER_TOKEN。"""
import json, os, re, sys, urllib.request, urllib.parse, urllib.error
TOKEN = re.sub(r'\s+', '', re.sub(r'^(Bearer|bearer)\s+', '', os.environ.get('X_BEARER_TOKEN', '').strip()))
if not TOKEN: sys.exit('X_BEARER_TOKEN が未設定です')
FILES = ['posts.json', 'posts-old.json']
data = {f: json.load(open(f, encoding='utf-8')) for f in FILES if os.path.exists(f)}
targets = [p for l in data.values() for p in l if p.get('x')]
print('対象', len(targets), '件')
def api(ids):
    q = urllib.parse.urlencode({'ids': ','.join(ids), 'tweet.fields': 'note_tweet,entities'})
    req = urllib.request.Request('https://api.x.com/2/tweets?' + q, headers={'Authorization': 'Bearer ' + TOKEN, 'User-Agent': 'arsenal-archive'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit('X API エラー %s: %s' % (e.code, e.read().decode('utf-8', 'replace')[:500]))
full = {}
for i in range(0, len(targets), 100):
    r = api([p['id'] for p in targets[i:i+100]])
    for t in r.get('data', []):
        nt = t.get('note_tweet') or {}
        txt = nt.get('text') or t['text']
        ent = nt.get('entities') or t.get('entities') or {}
        for u in ent.get('urls', []):
            ex = u.get('expanded_url') or u.get('url')
            if 'x.com/' in ex and '/photo/' in ex: txt = txt.replace(u['url'], ''); continue
            txt = txt.replace(u['url'], ex)
        full[t['id']] = (re.sub(r'\s*https://t\.co/\w+\s*$', '', txt).strip(), bool(nt.get('text')))
fixed = skipped = 0
for p in targets:
    r = full.get(p['id'])
    if not r: skipped += 1; continue
    txt, is_note = r
    old = p['t'].rstrip().rstrip('…').rstrip()
    if len(txt) > len(old) and txt[:12] == old[:12]:
        p['t'] = txt; p.pop('x', None); fixed += 1
    else: skipped += 1
print('置換', fixed, '件 / スキップ', skipped, '件')
for f, l in data.items():
    open(f, 'w', encoding='utf-8').write('[\n' + ',\n'.join(json.dumps(p, ensure_ascii=False, separators=(',', ':')) for p in l) + '\n]\n')
