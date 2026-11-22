#!/usr/bin/env python3
"""カテゴリの再確認。
・posts.json / posts-old.json：コメント（「…」の発言引用）・プレビュー／レビュー（会見の時点）だけを“追加”する（削除はしない）
・incoming.json：新着ポストに、コメント等の追加カテゴリ(kx)を付ける（サイト側の簡易分類に足される）
使い方: python tools/recat.py  （リポジトリのルートで）"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import cats
meta = json.load(open('meta.json', encoding='utf-8')); CN = meta['cats']; IDX = {n: i for i, n in enumerate(CN)}
ADDABLE = {'インタビュー・コメント', 'プレビュー', 'レビュー'}
def body(t):
    import re
    return re.sub(r'^【[^】]*】(\s*[（(][^）)]*[）)])?\s*', '', (t or '').replace('​', '')).strip()
def dump(p, rows, pretty=False):
    if pretty: json.dump(rows, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    else: open(p, 'w', encoding='utf-8').write('[\n' + ',\n'.join(json.dumps(x, ensure_ascii=False, separators=(',', ':')) for x in rows) + '\n]\n')
tot = 0
for f in ('posts.json', 'posts-old.json'):
    rows = json.load(open(f, encoding='utf-8')); n = 0
    for x in rows:
        cur = [CN[i] for i in x.get('k', []) if i < len(CN)]
        new = [c for c in cats.refine(body(x['t']), cur) if c in ADDABLE and c not in cur]
        if new:
            x['k'] = list(x.get('k', [])) + [IDX[c] for c in new if c in IDX]; n += 1
    dump(f, rows); print(f, 'コメント/プレビュー/レビューを追加:', n); tot += n
inc = json.load(open('incoming.json', encoding='utf-8')); m = 0
for x in inc:
    x.pop('k', None)
    names = [c for c in cats.refine(body(x['t']), []) if c in ADDABLE]
    if names: x['kx'] = [IDX[c] for c in names if c in IDX]; m += 1
    else: x.pop('kx', None)
dump('incoming.json', inc, pretty=True)
print('incoming を分類:', m)
