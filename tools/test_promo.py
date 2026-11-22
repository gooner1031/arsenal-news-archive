#!/usr/bin/env python3
"""宣伝・告知ポスト判定（tools/promo.py）の回帰テスト。実行: python3 tools/test_promo.py
過去の告知ポストは除外され、本物のアーセナルのポストは1件も除外されないことを固定する。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import promo
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
fails = []
def chk(c, msg):
    print(('OK  ' if c else 'NG  ') + msg)
    if not c: fails.append(msg)
# 2026-11-22 21:42 の告知スレッド（自動取得で HOME に載ってしまった3件）
chk(promo.is_promo('🔴⚪️アーセナルファンのためのアプリを作りました\n\n「Arsenal News Archive」\n\n📰ニュースを選手別に検索\n\n無料・登録不要・ホーム画面に追加OK👇\nhttps://gooner1031.github.io/arsenal-news-archive',
                   ['https://gooner1031.github.io/arsenal-news-archive']), 'アプリ紹介ポストは除外(2124483743876563050)')
chk(promo.is_promo('📱 ホーム画面への追加方法（ストア不要）\n\niPhone：Safariで開く → 共有ボタン →「ホーム画面に追加」'), 'ホーム画面への追加方法は除外(2124483769638035694)')
chk(promo.is_promo('毎日更新しています。\n「こんな機能がほしい」「ここが間違っている」は、サイト内のCONTACTからいつでも送れます。各ポストの「指摘」ボタンからも送れます。\n\nアーセナルの最新情報はこのアカウントで毎日発信中。\nフォローしておくと見逃しません🔔\n\n#アーセナル #Arsenal #COYG'), 'CONTACT・フォローのお願いは除外(2124483772230094854)')
chk(promo.is_promo('本文に目印なし', ['https://gooner1031.github.io/arsenal-news-archive/#transfers']), 'URL 欄にサイトの URL があれば除外')
# 本物のアーセナルのポストは残す
chk(not promo.is_promo('【The Athletic】\nアーセナルはニューカッスルと2-2で引き分け、首位をキープ。\n\n#アーセナル #Arsenal #COYG'), 'ハッシュタグだけでは除外しない')
chk(not promo.is_promo('【TEAMtalk】\nジェズスの代理人は複数クラブとcontactを取っている。'), '記事中の contact（英語）では除外しない')
chk(not promo.is_promo('アーセナルの情報を追いたいのならジャガーさんはフォロー必須ですよ！！'), '他アカウントのフォロー推奨では除外しない')
# 実データ: 過去のポストで目印に当たるものがない（誤検知ゼロ）
P = []
for f in ('posts.json', 'posts-old.json', 'incoming.json'):
    try: P += json.load(open(f, encoding='utf-8'))
    except FileNotFoundError: pass
hit = [x['id'] for x in P if promo.is_promo(x.get('t'), x.get('u'), x['id'])]
chk(not hit, 'アーカイブ内に宣伝ポストが残っていない（%d 件中 %s）' % (len(P), hit or 0))
sys.exit(1 if fails else 0)
