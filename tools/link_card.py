#!/usr/bin/env python3
"""ポストのリンク先（元記事）のプレビュー画像（リンクカードの画像）を調べて、incoming.json の各ポストに `og` として入れる。
  og = {"u": 記事のURL, "img": 画像のURL}
画像そのものはサイトに保存しない（URL だけ持ち、表示のときに配信元から読み込む）。
取り方は2通り:
  1. X API が返すリンクカードの画像（entities.urls[].images。X に URL 付きでポストしたときに出る画像と同じ）… fetch_x.py が from_entities() を使う
  2. 記事のページの og:image / twitter:image … このスクリプトを実行したとき（毎時の fetch-x の後）
画像が無い・サイトに断られた（4xx）ポストには `ogx: 1` を付けて、次回から調べ直さない（調べ直すときは ogx を消す）。
通信の失敗は次回また調べる。
使い方: python3 tools/link_card.py [件数の上限=40]"""
import json, re, sys, html, urllib.request, urllib.parse, urllib.error

# 他のサービスのクローラー名（Facebook・X など）は名乗らない。断られたサイトの画像は出さない（ogx: 1）
UA = {'User-Agent': 'link-preview/1.0 (python-urllib)',
      'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'en-GB,en;q=0.8'}
SKIP = re.compile(r'^https?://(www\.|mobile\.)?(x\.com|twitter\.com|t\.co|gooner1031\.github\.io)/', re.I)
META = re.compile(r'<meta\b[^>]*>', re.I)
ATTR = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
KEYS = ('og:image:secure_url', 'og:image', 'og:image:url', 'twitter:image', 'twitter:image:src')

def ok_url(u):
    """https の普通の URL だけ通す（サイトの img にそのまま入るため）。"""
    return isinstance(u, str) and len(u) < 900 and re.match(r'^https://[^\s"\'<>]+$', u) is not None

def article_urls(urls):
    return [u for u in (urls or []) if isinstance(u, str) and u.startswith('http') and not SKIP.match(u)]

def parse(page, base):
    """HTML から og:image などを探して、絶対URLで返す。無ければ None。"""
    found = {}
    for tag in META.findall(page or ''):
        a = {k.lower(): (v1 or v2) for k, v1, v2 in ATTR.findall(tag)}
        k = (a.get('property') or a.get('name') or '').lower()
        if k in KEYS and a.get('content') and k not in found: found[k] = html.unescape(a['content']).strip()
    for k in KEYS:
        if k in found:
            u = urllib.parse.urljoin(base, found[k])
            if u.startswith('http://'): u = 'https://' + u[7:]
            if ok_url(u): return u
    return None

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if 'html' not in (r.headers.get('Content-Type') or 'html'): return None
        return parse(r.read(600000).decode('utf-8', 'replace'), r.geturl())

def from_entities(ents):
    """X API の entities.urls から、リンクカードの画像が付いている最初のリンクを og の形で返す。"""
    for e in (ents or {}).get('urls', []) or []:
        u = e.get('unwound_url') or e.get('expanded_url') or ''
        if not article_urls([u]): continue
        ims = [i for i in e.get('images') or [] if ok_url(i.get('url'))]
        if not ims: continue
        # 大きすぎない中で一番大きいもの（幅2400まで）
        ims.sort(key=lambda i: (i.get('width') or 0) <= 2400 and (i.get('width') or 0) or -1, reverse=True)
        return {'u': u, 'img': ims[0]['url']}
    return None

def lookup(urls):
    """(og または None, 確定か) を返す。通信の失敗（タイムアウトなど）は確定にせず、次回また調べる。"""
    final = True
    for u in article_urls(urls)[:2]:
        try:
            im = fetch(u)
            if im: return {'u': u, 'img': im}, True
        except urllib.error.HTTPError as e:
            print('  取れず:', u[:70], '/ HTTP', e.code)
            if not 400 <= e.code < 500 or e.code == 429: final = False
        except Exception as e:
            print('  取れず:', u[:70], '/', str(e)[:60]); final = False
    return None, final

def main(limit=40):
    inc = json.load(open('incoming.json', encoding='utf-8')); n = hit = ch = 0
    for x in sorted(inc, key=lambda x: x['id'], reverse=True):
        if 'og' in x or x.get('ogx') or not article_urls(x.get('u')): continue
        if n >= limit: break
        n += 1; og, final = lookup(x['u'])
        if og: x['og'] = og; hit += 1; ch += 1
        elif final: x['ogx'] = 1; ch += 1
    print('リンクカードの画像: %d 件を調べて %d 件取得' % (n, hit))
    if ch: json.dump(inc, open('incoming.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
