#!/usr/bin/env python3
"""試合ハイライト動画のリンクを highlights.json に集める（APIキー不要）。
  src=unext  : U-NEXT公式YouTubeの日本語「ショートハイライト」（プレミアリーグ全試合）
  src=arsenal: Arsenal公式チャンネルのRSS（ハイライト／スコア入りタイトル）"""
import json, re, sys, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
      'Accept-Language': 'ja,en;q=0.8', 'Cookie': 'CONSENT=YES+1; SOCS=CAI'}
PL = 'PLoYMtUTlz8sYICoPp_j0CmyVtmv5038ai'          # U-NEXT「プレミアリーグ ショートハイライト」
ARS_PL = [('PLvuwbYTkUzHcWbmTUwc_TDprJHvpOZQCV', 2025), ('PLWblYkLdkM7Q', 2026)]   # Arsenal公式「MEN'S HIGHLIGHTS」25/26・26/27
UN_PL = ['PLKqgxiZjfJNY']                                                           # U-NEXT フットボール「プレミアリーグ 2026/27 ハイライト」
ARS = 'UCpryVRk_VDudG8SHXgWcG0w'                  # Arsenal 公式
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode('utf-8', 'replace')
def jload(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d
DEBUG_ALL = False
cur = jload('highlights.json', []); by = {x['id']: x for x in cur}
TITLE = re.compile(r'【\s*(.+?)\s+v\s+(.+?)\s*[｜|]\s*ショートハイライト\s*】\s*(\D*?)\s*(\d{2,4})/(\d{2,4})(?:\s*第(\d+)節)?')
def add_unext(vid, title, pub=''):
    m = TITLE.search(title)
    if not m or vid in by: return 0
    y = int(m.group(4)); y = y + 2000 if y < 100 else y
    by[vid] = {'id': vid, 't': title, 'p': pub, 'u': 'https://www.youtube.com/watch?v=' + vid, 'src': 'unext',
               'h': m.group(1).replace(' ', ''), 'a': m.group(2).replace(' ', ''), 'c': m.group(3).strip(), 's': y, 'r': int(m.group(6) or 0)}
    return 1
def walk(o, out):
    if isinstance(o, dict):
        if o.get('contentType') == 'LOCKUP_CONTENT_TYPE_VIDEO' and o.get('contentId'):
            t = (((o.get('metadata') or {}).get('lockupMetadataViewModel') or {}).get('title') or {}).get('content', '')
            if t: out.append((o['contentId'], t))
        if 'videoId' in o and isinstance(o.get('title'), dict):
            t = ''.join(r.get('text', '') for r in o['title'].get('runs', [])) or o['title'].get('simpleText', '')
            if t: out.append((o['videoId'], t))
        for v in o.values(): walk(v, out)
    elif isinstance(o, list):
        for v in o: walk(v, out)
def scrape(url):
    html = get(url); m = re.search(r'ytInitialData\s*=\s*(\{.*?\});</script>', html, re.S)
    out = []
    if m: walk(json.loads(m.group(1)), out)
    if 'results' in url and DEBUG_ALL: print('  titles:', [t for _, t in out][:6])
    print('  取得', url[:70], '| html', len(html), '| initialData', bool(m), '| 動画', len(out))
    return out
new_u = 0
# 1) U-NEXT 再生リスト（ページ先頭 + RSS）
try:
    for vid, t in scrape('https://www.youtube.com/playlist?list=' + PL): new_u += add_unext(vid, t)
    print('U-NEXT再生リスト取得 OK')
except Exception as e: print('U-NEXT再生リスト(ページ)失敗:', e)
try:
    ns = {'a': 'http://www.w3.org/2005/Atom', 'y': 'http://www.youtube.com/xml/schemas/2015'}
    r = ET.fromstring(get('https://www.youtube.com/feeds/videos.xml?playlist_id=' + PL))
    for e in r.findall('a:entry', ns): new_u += add_unext(e.findtext('y:videoId', '', ns), e.findtext('a:title', '', ns), e.findtext('a:published', '', ns)[:10])
    print('U-NEXT RSS OK')
except Exception as e: print('U-NEXT RSS失敗:', e)
# 1b) U-NEXT 追加の再生リスト（RSS＝最新15本。ページ読み取りも試す）
for pl in UN_PL:
    try:
        html = get('https://www.youtube.com/playlist?list=' + pl)
        print('  U-NEXT再生リスト', pl, '| playlistVideoRenderer', html.count('playlistVideoRenderer'), '| lockupViewModel', html.count('lockupViewModel'), '| videoId', html.count('"videoId"'))
        m = re.search(r'ytInitialData\s*=\s*(\{.*?\});</script>', html, re.S); out = []
        if m: walk(json.loads(m.group(1)), out)
        print('    ページから', len(out), '本')
        for vid, t in out: new_u += add_unext(vid, t)
    except Exception as e: print('  失敗', pl, e)
    try:
        ns = {'a': 'http://www.w3.org/2005/Atom', 'y': 'http://www.youtube.com/xml/schemas/2015'}
        r = ET.fromstring(get('https://www.youtube.com/feeds/videos.xml?playlist_id=' + pl))
        for e in r.findall('a:entry', ns): new_u += add_unext(e.findtext('y:videoId', '', ns), e.findtext('a:title', '', ns), e.findtext('a:published', '', ns)[:10])
    except Exception as e: print('  RSS失敗', pl, e)
# 1c) Arsenal公式の試合ハイライト再生リスト（25/26・26/27）
ARS_T = re.compile(r"([A-Z][A-Za-z.'’ -]+?) vs ([A-Z][A-Za-z.'’ -]+?)\s*\((\d+)\s*-\s*(\d+)")
new_a = 0
for pl, st in ARS_PL:
    try:
        items = scrape('https://www.youtube.com/playlist?list=' + pl)
        try:
            ns = {'a': 'http://www.w3.org/2005/Atom', 'y': 'http://www.youtube.com/xml/schemas/2015'}
            r = ET.fromstring(get('https://www.youtube.com/feeds/videos.xml?playlist_id=' + pl))
            items += [(e.findtext('y:videoId', '', ns), e.findtext('a:title', '', ns)) for e in r.findall('a:entry', ns)]
        except Exception as e: print('  RSS失敗', pl, e)
        for vid, t in items:
            if vid in by or 'highlight' not in t.lower(): continue
            m = ARS_T.search(t)
            if not m: continue
            hh, aa = m.group(1).strip(), m.group(2).strip()
            by[vid] = {'id': vid, 't': t, 'p': '', 'u': 'https://www.youtube.com/watch?v=' + vid, 'src': 'arsenal', 'h': hh, 'a': aa, 'sc': m.group(3) + '-' + m.group(4), 'ext': 'EXTENDED' in t.upper(), 's': st}; new_a += 1
    except Exception as e: print('  Arsenal再生リスト失敗', pl, e)
# 2) 試合ごとの検索で不足分を補う（アーセナルのPL試合・上限40件/回）
try:
    ms = jload('matchstats.json', {}); n = 0
    for d, S in sorted(ms.items(), reverse=True):
        if S.get('c') != 'プレミアリーグ': continue
        start = int(d[:4]) if int(d[5:7]) >= 8 else int(d[:4]) - 1
        key = S['o'][:4]
        if any(x.get('src') == 'unext' and x['s'] == start and 'アーセナル' in (x['h'], x['a']) and ((x['h'] == 'アーセナル') == (S['ha'] == 'H')) and (key in x['h'] or key in x['a']) for x in by.values()): continue
        if n >= 40: break
        n += 1
        if n > 3 and not DEBUG_ALL: pass
        short = {'ハル・シティ': 'ハル', 'マンチェスター・ユナイテッド': 'マンチェスター・U', 'マンチェスター・シティ': 'マンチェスター・C', 'トッテナム': 'トッテナム・ホットスパー', 'ウルヴァーハンプトン': 'ウォルヴァーハンプトン', 'ウルヴス': 'ウォルヴァーハンプトン'}.get(S['o'], S['o'])
        ss = '2026/27' if start >= 2026 else '%02d/%02d' % (start % 100, (start + 1) % 100)
        pair = ('アーセナル v ' + short) if S['ha'] == 'H' else (short + ' v アーセナル')
        q = '【%s｜ショートハイライト】プレミアリーグ%s' % (pair, ss)
        try:
            for vid, t in scrape('https://www.youtube.com/results?search_query=' + urllib.parse.quote(q)): new_u += add_unext(vid, t)
        except Exception as e: print('検索失敗', q, e)
        time.sleep(1.2)
except Exception as e: print('検索補完エラー:', e)
# 2b) matchstats の全試合（24/25〜・全大会）について、Arsenal公式の HIGHLIGHTS を検索で補う（上限30件/回）
EN = {'PSG': ['Paris Saint-Germain', 'PSG'], 'PSV': ['PSV'], 'アストン・ヴィラ': ['Aston Villa'], 'アスレティック・ビルバオ': ['Athletic Club', 'Athletic Bilbao'], 'アタランタ': ['Atalanta'],
      'イプスウィッチ': ['Ipswich'], 'インテル': ['Inter'], 'ウェストハム': ['West Ham'], 'ウルヴァーハンプトン': ['Wolverhampton', 'Wolves'], 'エヴァートン': ['Everton'],
      'クリスタル・パレス': ['Crystal Palace'], 'コヴェントリー': ['Coventry'], 'サウサンプトン': ['Southampton'], 'サンダーランド': ['Sunderland'], 'シャフタール': ['Shakhtar'],
      'ジローナ': ['Girona'], 'スポルティング': ['Sporting'], 'スラヴィア・プラハ': ['Slavia Prague'], 'チェルシー': ['Chelsea'], 'ディナモ・ザグレブ': ['Dinamo Zagreb'],
      'トッテナム': ['Tottenham', 'Spurs'], 'ナポリ': ['Napoli'], 'ニューカッスル': ['Newcastle'], 'ノッティンガム・フォレスト': ['Nottingham Forest', "Nott'm Forest"],
      'ハル・シティ': ['Hull'], 'バイエルン': ['Bayern'], 'フラム': ['Fulham'], 'フリートウッド': ['Fleetwood'], 'ブライトン': ['Brighton'], 'ブレントフォード': ['Brentford'],
      'プレストン': ['Preston'], 'ボルトン': ['Bolton'], 'ボーンマス': ['Bournemouth'], 'マンチェスター・シティ': ['Manchester City', 'Man City'],
      'マンチェスター・ユナイテッド': ['Manchester United', 'Man United', 'Man Utd'], 'モナコ': ['Monaco'], 'リヴァプール': ['Liverpool'], 'リーズ': ['Leeds'], 'リール': ['Lille'],
      'レアル・マドリード': ['Real Madrid'], 'レスター': ['Leicester']}
def walk_v(o, out):
    if isinstance(o, dict):
        if 'videoId' in o and isinstance(o.get('title'), dict):
            t = ''.join(r.get('text', '') for r in o['title'].get('runs', [])) or o['title'].get('simpleText', '')
            ow = ''.join(r.get('text', '') for r in ((o.get('ownerText') or o.get('longBylineText') or {}).get('runs', [])))
            if t: out.append((o['videoId'], t, ow))
        for v in o.values(): walk_v(v, out)
    elif isinstance(o, list):
        for v in o: walk_v(v, out)
try:
    ms = jload('matchstats.json', {}); n = 0; found = 0
    for d, S in sorted(ms.items(), reverse=True):
        start = int(d[:4]) if int(d[5:7]) >= 8 else int(d[:4]) - 1
        al = EN.get(S.get('o'))
        if start < 2024 or not al: continue
        def opp_of(x): return x['a'] if x['h'].strip().startswith('Arsenal') else x['h']
        if any(x.get('src') == 'arsenal' and x.get('h') and x.get('s') == start and any(z.lower() in opp_of(x).lower() for z in al) and (S['ha'] == 'N' or x['h'].strip().startswith('Arsenal') == (S['ha'] == 'H')) for x in by.values()): continue
        if n >= 30: break
        n += 1
        try: g, c = [int(v) for v in S['sc'].split('-')[:2]]
        except Exception: continue
        home, away, hs, as_ = ('Arsenal', al[0], g, c) if S['ha'] != 'A' else (al[0], 'Arsenal', c, g)
        html = get('https://www.youtube.com/results?search_query=' + urllib.parse.quote('%s vs %s (%d-%d) highlights Arsenal' % (home, away, hs, as_)))
        mm = re.search(r'ytInitialData\s*=\s*(\{.*?\});</script>', html, re.S); res = []
        if mm: walk_v(json.loads(mm.group(1)), res)
        hit = 0
        for vid, t, ow in res:
            if vid in by or 'highlight' not in t.lower(): continue
            m = ARS_T.search(t)
            if not m: continue
            a1, a2 = m.group(1).strip(), m.group(2).strip()
            if int(m.group(3)) != hs or int(m.group(4)) != as_: continue
            if not (a1.startswith('Arsenal') or a2.startswith('Arsenal')): continue
            if not any(z.lower() in (a2 if a1.startswith('Arsenal') else a1).lower() for z in al): continue
            if ow and 'arsenal' not in ow.lower(): continue
            if not ow and 'HIGHLIGHTS' not in t: continue
            by[vid] = {'id': vid, 't': t, 'p': '', 'u': 'https://www.youtube.com/watch?v=' + vid, 'src': 'arsenal', 'h': a1, 'a': a2, 'sc': '%d-%d' % (hs, as_), 'ext': 'EXTENDED' in t.upper(), 's': start}
            new_a += 1; hit += 1; found += 1
        print('  検索', d, home, 'vs', away, '| 候補', len(res), '| 追加', hit)
        time.sleep(1.2)
    print('Arsenal公式ハイライト検索: 追加', found, '件 / 検索', n, '件')
except Exception as e: print('Arsenal公式検索エラー:', e)
# 3) Arsenal 公式RSS
try:
    ns = {'a': 'http://www.w3.org/2005/Atom', 'y': 'http://www.youtube.com/xml/schemas/2015'}
    r = ET.fromstring(get('https://www.youtube.com/feeds/videos.xml?channel_id=' + ARS))
    for e in r.findall('a:entry', ns):
        vid = e.findtext('y:videoId', '', ns); t = e.findtext('a:title', '', ns); p = e.findtext('a:published', '', ns)[:10]; low = t.lower()
        if not ('highlight' in low or re.search(r'\b\d{1,2}\s?[-–]\s?\d{1,2}\b', t)) or any(k in low for k in ('women', 'u21', 'u18', 'u19', 'u23')) or vid in by: continue
        by[vid] = {'id': vid, 't': t, 'p': p, 'u': 'https://www.youtube.com/watch?v=' + vid, 'src': 'arsenal'}; new_a += 1
except Exception as e: print('Arsenal RSS失敗:', e)
out = sorted(by.values(), key=lambda x: (x.get('s', 0), x.get('r', 0), x.get('p', '')), reverse=True)
print('新規: U-NEXT %d 件 / Arsenal %d 件 / 合計 %d' % (new_u, new_a, len(out)))
json.dump(out, open('highlights.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
