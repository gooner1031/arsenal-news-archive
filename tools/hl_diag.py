"""一時的な調査用（マージ前に削除）"""
import json, re, urllib.parse, xml.etree.ElementTree as ET
def run(get, walk):
    ns = {'a': 'http://www.w3.org/2005/Atom', 'y': 'http://www.youtube.com/xml/schemas/2015'}
    def titles(url):
        html = get(url); m = re.search(r'ytInitialData\s*=\s*(\{.*?\});</script>', html, re.S); out = []
        if m: walk(json.loads(m.group(1)), out)
        return html, out
    for name, vid, kw in (('WOWOW', 'z2IkYjteBCI', 'アーセナル チャンピオンズリーグ ハイライト'), ('DAZN', '6vdHRVJFI1A', 'アーセナル カラバオカップ ハイライト')):
        print('=====', name)
        try:
            o = json.loads(get('https://www.youtube.com/oembed?format=json&url=' + urllib.parse.quote('https://www.youtube.com/watch?v=' + vid, safe='')))
            print('oembed', o.get('title'), '|', o.get('author_name'), '|', o.get('author_url'))
            au = o['author_url']
            html = get(au); cid = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', html) or re.search(r'channel/(UC[\w-]{22})', html)
            cid = cid.group(1) if cid else ''; print('channel id', cid)
            if cid:
                r = ET.fromstring(get('https://www.youtube.com/feeds/videos.xml?channel_id=' + cid))
                for e in r.findall('a:entry', ns): print('  rss', e.findtext('y:videoId', '', ns), e.findtext('a:published', '', ns)[:10], e.findtext('a:title', '', ns)[:90])
            _, out = titles(au + '/search?query=' + urllib.parse.quote(kw)); print('channel search', len(out))
            for v, t in out[:25]: print('  cs', v, t[:100])
            html, _ = titles(au + '/playlists')
            for pid, t in re.findall(r'"playlistId":"(PL[\w-]+)".{0,600}?"(?:content|simpleText|text)":"([^"]{3,80})"', html)[:60]:
                if re.search('チャンピオンズ|CL|カラバオ|FA|ハイライト', t): print('  pl', pid, t)
            _, out = titles(au + '/videos'); print('videos tab', len(out))
            for v, t in out[:12]: print('  vt', v, t[:100])
        except Exception as e: print('ERR', name, repr(e))
        try:
            _, out = titles('https://www.youtube.com/results?gl=JP&hl=ja&search_query=' + urllib.parse.quote(name + ' ' + kw)); print('global search gl=JP', len(out))
            for v, t in out[:10]: print('  gs', v, t[:100])
        except Exception as e: print('ERR gs', repr(e))
    for vid in ('z2IkYjteBCI', '6vdHRVJFI1A'):
        try:
            html = get('https://www.youtube.com/watch?v=' + vid)
            print('watch', vid, re.findall(r'"playabilityStatus":\{"status":"(\w+)"', html)[:1], re.findall(r'"(?:reason|simpleText)":"([^"]{5,80}(?:country|国|利用)[^"]{0,60})"', html)[:2], re.findall(r'"availableCountries":\[([^\]]{0,60})', html)[:1])
        except Exception as e: print('ERR watch', repr(e))
