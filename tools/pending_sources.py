"""新着ポストから、一覧にない出典（媒体・記者・引用元アカウント）を拾って pending_sources.json に記録する。
サイト側は同じ規則で自動的に Tier4 として表示する。管理人への確認待ちの一覧として使う。"""
import json, re
BLOCK = {'roundtable sports'}  # 管理人が不採用とした出典
meta = json.load(open('meta.json'))
html = open('index.html', encoding='utf-8').read()
known = {s.lower() for s in meta['sen']} | set(meta['sources'])
m = re.search(r'const SRCH=(\{.*?\});', html, re.S)
handles = {v.lower() for v in json.loads(m.group(1)).values()} if m else set()
try: pend = json.load(open('pending_sources.json'))
except Exception: pend = []
seen = {p['name'].lower() for p in pend}
inc = json.load(open('incoming.json'))
for x in inc:
    t = x['t']
    h = re.match(r'^【([^】]+)】\s*(?:\(@([A-Za-z0-9_]+)\s*\))?', t)
    cand = []
    if h:
        n = 'Arsenal (official)' if h[1] == 'Arsenal' else h[1]
        if n.lower() not in known and n not in meta['sources']: cand.append((n, h[2] or ''))
    else:
        for u in re.findall(r'x\.com/([A-Za-z0-9_]+)/status', t):
            if u.lower() not in handles: cand.append(('@' + u, u)); break
    for n, hd in cand:
        if n.lower() in BLOCK or n.lower() in seen: continue
        seen.add(n.lower())
        pend.append({'name': n, 'handle': hd, 'first': x['d'], 'sample': re.sub(r'\s+', ' ', t)[:80], 'tier': 4, 'asked': False})
json.dump(pend, open('pending_sources.json', 'w'), ensure_ascii=False, indent=1)
print('pending', len(pend))
