#!/usr/bin/env python3
"""アーセナル公式YouTubeチャンネルのRSSからハイライト動画を取得して highlights.json に追記する（APIキー不要・無料）。"""
import json, sys, urllib.request, xml.etree.ElementTree as ET
CH = 'UCpryVRk_VDudG8SHXgWcG0w'   # Arsenal 公式
URL = 'https://www.youtube.com/feeds/videos.xml?channel_id=' + CH
ns = {'a': 'http://www.w3.org/2005/Atom', 'y': 'http://www.youtube.com/xml/schemas/2015'}
req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0 arsenal-archive'})
try:
    data = urllib.request.urlopen(req, timeout=30).read()
except Exception as e:
    sys.exit('RSS取得に失敗: %s' % e)
root = ET.fromstring(data)
print('チャンネル:', root.findtext('a:title', '', ns), '/ 動画数:', len(root.findall('a:entry', ns)))
try: cur = json.load(open('highlights.json', encoding='utf-8'))
except Exception: cur = []
have = {x['id'] for x in cur}; new = 0
for e in root.findall('a:entry', ns):
    vid = e.findtext('y:videoId', '', ns); t = e.findtext('a:title', '', ns); p = e.findtext('a:published', '', ns)[:10]
    low = t.lower()
    import re
    # 試合のハイライト（'Highlights' 表記、または 'A 2-1 B' のようなスコア入りタイトル）
    if not ('highlight' in low or re.search(r'\b\d{1,2}\s?[-–]\s?\d{1,2}\b', t)) or 'women' in low or 'u21' in low or 'u18' in low or 'u19' in low or 'u23' in low: continue
    if vid in have: continue
    cur.append({'id': vid, 't': t, 'p': p, 'u': 'https://www.youtube.com/watch?v=' + vid}); new += 1
cur.sort(key=lambda x: x['p'], reverse=True)
print('新規ハイライト:', new, '件 / 合計', len(cur))
json.dump(cur, open('highlights.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
