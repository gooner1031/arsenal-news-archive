#!/usr/bin/env python3
"""日本の放映権元の公式ハイライト（YouTube）を highlights.json に足す（APIキー不要）。
  src=wowow: WOWOWサッカー公式（チャンピオンズリーグ）
  src=dazn : DAZN Japan公式（カラバオ杯・FA杯）
どちらも日本国内限定公開で、海外にある GitHub のサーバーからは YouTube の検索・チャンネル一覧に出てこない。
そのため (1) 公式チャンネルのRSS（新着15本）と (2) tools/hl_ids.txt に書いた URL（oEmbed で題名と投稿者を確認）から拾う。
アーセナルの試合だけを保存し、matchstats.json の試合と結び付いたら d（試合日）を付ける。"""
import json, os, re, sys, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hl_jp import parse_jp, fits, nk
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36', 'Accept-Language': 'ja,en;q=0.8', 'Cookie': 'CONSENT=YES+1; SOCS=CAI'}
CH = {'wowow': 'UCJQj2lbG_3w8UrncJd7JZXw', 'dazn': 'UCyeDNNizMGbVsn_8Ttc3FIw'}     # WOWOWサッカー official / DAZN Japan
def get(url): return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode('utf-8', 'replace')
def jload(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d
def entry(vid, t, src, pub=''):
    """アーセナルの試合の公式ハイライトなら highlights.json の1件にして返す。"""
    pj = parse_jp(t)
    if not pj or pj[0] != src or 'アーセナル' not in (nk(pj[1]), nk(pj[2])): return None
    return {'id': vid, 't': t, 'p': pub, 'u': 'https://www.youtube.com/watch?v=' + vid, 'src': src, 'h': pj[1], 'a': pj[2], 'c': pj[3], 's': pj[4]}
def link(by, ms):
    """d のない wowow / dazn の動画を matchstats の試合に結び付ける。候補が1試合に決まるときだけ。"""
    n = 0
    for x in by.values():
        if x.get('src') not in CH or x.get('d'): continue
        used = {y['d'] for y in by.values() if y.get('src') == x['src'] and y.get('d')}
        c = []
        for d, S in ms.items():
            start = int(d[:4]) if int(d[5:7]) >= 8 else int(d[:4]) - 1
            if d in used or not fits((x['src'], x['h'], x['a'], x['c'], x['s']), S, start): continue
            if x.get('p') and not -1 <= (date.fromisoformat(x['p']) - date.fromisoformat(d)).days <= 4: continue
            c.append(d)
        if len(c) == 1: x['d'] = c[0]; n += 1
    return n
def main():
    cur = jload('highlights.json', []); by = {x['id']: x for x in cur}; before = json.dumps(cur, ensure_ascii=False, sort_keys=True); new = 0
    ns = {'a': 'http://www.w3.org/2005/Atom', 'y': 'http://www.youtube.com/xml/schemas/2015'}
    for src, cid in CH.items():
        try:
            es = ET.fromstring(get('https://www.youtube.com/feeds/videos.xml?channel_id=' + cid)).findall('a:entry', ns)
            for e in es:
                vid = e.findtext('y:videoId', '', ns); x = entry(vid, e.findtext('a:title', '', ns), src, e.findtext('a:published', '', ns)[:10])
                if x and vid not in by: by[vid] = x; new += 1; print('  追加(RSS)', src, x['t'][:60])
            print(src, 'RSS', len(es), '本')
        except Exception as e: print(src, 'RSS失敗:', e)
    try: lines = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hl_ids.txt'), encoding='utf-8').read().split('\n')
    except Exception: lines = []
    for ln in lines:
        m = None if ln.strip().startswith('#') else re.search(r'(?:v=|youtu\.be/|shorts/|^)([\w-]{11})(?:[?&#\s]|$)', ln.strip())
        if not m or m.group(1) in by: continue
        vid = m.group(1)
        try:
            o = json.loads(get('https://www.youtube.com/oembed?format=json&url=' + urllib.parse.quote('https://www.youtube.com/watch?v=' + vid, safe='')))
            src = next((s for s in CH if s in o.get('author_name', '').lower()), '')
            x = entry(vid, o.get('title', ''), src) if src else None
            if x: by[vid] = x; new += 1; print('  追加(URL指定)', src, x['t'][:60])
            else: print('  対象外（公式チャンネルのアーセナル戦ハイライトではない）:', vid, o.get('author_name'), '|', o.get('title', '')[:50])
        except Exception as e: print('  oEmbed失敗', vid, e)
    linked = link(by, jload('matchstats.json', {}))
    out = sorted(by.values(), key=lambda x: (x.get('s', 0), x.get('r', 0), x.get('p', '')), reverse=True)
    print('WOWOW/DAZN: 新規 %d 件 / 試合と結び付け %d 件 / 合計 %d' % (new, linked, len(out)))
    if json.dumps(out, ensure_ascii=False, sort_keys=True) != before: json.dump(out, open('highlights.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
if __name__ == '__main__': main()
