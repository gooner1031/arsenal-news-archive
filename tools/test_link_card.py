#!/usr/bin/env python3
"""tools/link_card.py の読み取りの回帰テスト（通信なし）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import link_card as L
ok = True
def t(name, got, want):
    global ok
    if got != want: ok = False
    print('OK ' if got == want else 'NG ', name, '' if got == want else '→ %r（期待 %r）' % (got, want))
B = 'https://example.com/news/a'
t('og:image', L.parse('<meta property="og:image" content="https://img.example.com/a.jpg" data-x=""/>', B), 'https://img.example.com/a.jpg')
t('content が先', L.parse("<meta content='https://img.example.com/b.jpg?w=1&amp;h=2' property='og:image'>", B), 'https://img.example.com/b.jpg?w=1&h=2')
t('twitter:image', L.parse('<meta name="twitter:image" content="/img/c.png">', B), 'https://example.com/img/c.png')
t('og を優先', L.parse('<meta name="twitter:image" content="https://e.com/t.png"><meta property="og:image" content="https://e.com/o.png">', B), 'https://e.com/o.png')
t('http は https に', L.parse('<meta property="og:image" content="http://e.com/o.png">', B), 'https://e.com/o.png')
t('og:image:alt は画像ではない', L.parse('<meta property="og:image:alt" content="Every word">', B), None)
t('引用符入りは通さない', L.parse('<meta property="og:image" content="https://e.com/a.png&quot; onerror=&quot;x">', B), None)
t('data: は通さない', L.parse('<meta property="og:image" content="data:image/png;base64,AAAA">', B), None)
t('無いとき', L.parse('<html></html>', B), None)
t('X・自サイトのリンクは対象外', L.article_urls(['https://twitter.com/a/status/1', 'https://x.com/a/status/1', 'https://gooner1031.github.io/arsenal-news-archive/', 'https://www.bbc.co.uk/sport/1']), ['https://www.bbc.co.uk/sport/1'])
E1 = {'urls': [{'expanded_url': 'https://x.com/a/status/1/photo/1'},
               {'expanded_url': 'https://www.bbc.co.uk/sport/1', 'unwound_url': 'https://www.bbc.co.uk/sport/football/1',
                'images': [{'url': 'https://pbs.twimg.com/news_img/1/a?format=jpg&name=orig', 'width': 4800, 'height': 2520},
                           {'url': 'https://pbs.twimg.com/news_img/1/a?format=jpg&name=150x150', 'width': 150, 'height': 150}]}]}
t('X API のカード画像（大きすぎない方）', L.from_entities(E1), {'u': 'https://www.bbc.co.uk/sport/football/1', 'img': 'https://pbs.twimg.com/news_img/1/a?format=jpg&name=150x150'})
E2 = {'urls': [{'expanded_url': 'https://www.bbc.co.uk/sport/1', 'images': [{'url': 'https://pbs.twimg.com/news_img/1/b?format=jpg&name=orig', 'width': 1200, 'height': 630}]}]}
t('X API のカード画像', L.from_entities(E2), {'u': 'https://www.bbc.co.uk/sport/1', 'img': 'https://pbs.twimg.com/news_img/1/b?format=jpg&name=orig'})
t('画像の無いリンク', L.from_entities({'urls': [{'expanded_url': 'https://www.bbc.co.uk/sport/1'}]}), None)
t('entities なし', L.from_entities(None), None)
sys.exit(0 if ok else 1)
