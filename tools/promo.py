#!/usr/bin/env python3
"""サイト（アプリ）自体の宣伝・告知ポストの判定。
@gooner1031 の告知ポスト（アプリ紹介・ホーム画面への追加方法・CONTACT/フォローのお願い）は
アーセナルのニュースではないので、アーカイブに取り込まない。
fetch_x.py（毎時の自動取得）と daily_review.md（毎日の正式タグ付け）の両方がこの判定に従う。

ルール: tools/promo_ids.txt に載っている ID、または次の目印のどれか1つでも本文または URL に含まれたら宣伝ポスト。
目印はサイト固有の言い回しだけにしてあり、#アーセナル #COYG やフォローの話だけでは除外しない
（過去 7,000 件超のポストで誤検知ゼロを tools/test_promo.py で確認）。"""
import os
_IDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'promo_ids.txt')

MARKERS = [
    'gooner1031.github.io/arsenal-news-archive',  # サイトの URL
    'Arsenal News Archive',                         # サイト名
    'ホーム画面に追加', 'ホーム画面への追加',        # インストール方法
    'サイト内のCONTACT',                            # 問い合わせ窓口の案内
    '「指摘」ボタン',
    'このアカウントで毎日発信',                      # フォローのお願い
]

def promo_ids():
    """目印のない告知ポストを手で除外するための ID リスト（1行1件、# 以降はメモ）。"""
    try: return {l.split('#')[0].strip() for l in open(_IDS, encoding='utf-8')} - {''}
    except FileNotFoundError: return set()

def is_promo(text, urls=(), pid=None):
    if pid is not None and str(pid) in promo_ids(): return True
    s = (text or '').replace('​', '') + '\n' + '\n'.join(urls or [])
    return any(m in s for m in MARKERS)

if __name__ == '__main__':
    import json, sys
    for f in sys.argv[1:] or ['incoming.json', 'posts.json', 'posts-old.json']:
        for x in json.load(open(f, encoding='utf-8')):
            if is_promo(x.get('t'), x.get('u'), x['id']): print(f, x['id'], x['d'], x['t'][:40].replace('\n', ' '))
