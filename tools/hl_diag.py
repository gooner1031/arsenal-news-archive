"""一時的な調査用（マージ前に削除）"""
import json, re, urllib.parse, xml.etree.ElementTree as ET
def run(get, walk):
    ns = {'a': 'http://www.w3.org/2005/Atom', 'y': 'http://www.youtube.com/xml/schemas/2015'}
    for name, cid in (('WOWOW', 'UCJQj2lbG_3w8UrncJd7JZXw'), ('DAZN', 'UCyeDNNizMGbVsn_8Ttc3FIw')):
        print('=====', name)
        for pre in ('UU', 'UULF'):
            pl = pre + cid[2:]
            try:
                html = get('https://www.youtube.com/playlist?list=' + pl); m = re.search(r'ytInitialData\s*=\s*(\{.*?\});</script>', html, re.S); out = []
                if m: walk(json.loads(m.group(1)), out)
                print(pre, 'page', len(out), '| continuation', html.count('continuationCommand'), '| alerts', re.findall(r'"alertRenderer".{0,200}', html)[:1])
                for v, t in out[:6]: print('   ', v, t[:90])
                for v, t in out:
                    if 'アーセナル' in t: print('   ARS', v, t[:110])
            except Exception as e: print('ERR page', pre, repr(e))
            try:
                r = ET.fromstring(get('https://www.youtube.com/feeds/videos.xml?playlist_id=' + pl)); es = r.findall('a:entry', ns)
                print(pre, 'rss', len(es), [(e.findtext('a:published', '', ns)[:10], e.findtext('a:title', '', ns)[:50]) for e in es[:3]])
            except Exception as e: print('ERR rss', pre, repr(e))
        try:
            html = get('https://www.youtube.com/channel/' + cid + '/playlists')
            seen = set()
            for pid, t in re.findall(r'"playlistId":"(PL[\w-]+)".{0,900}?"(?:content|simpleText|text)":"([^"]{3,80})"', html):
                if pid not in seen: seen.add(pid); print('  pl', pid, t)
            print('playlists', len(seen), '| html', len(html))
        except Exception as e: print('ERR pls', repr(e))
