#!/usr/bin/env python3
"""宣伝・告知ポスト判定（tools/promo.py）と載せるポストの判定（tools/post_rule.py）の回帰テスト。実行: python3 tools/test_promo.py
過去の告知ポストは除外され、本物のアーセナルのポストは1件も除外されないことを固定する。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import promo, post_rule
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
# 2026-11-22 22:52 のアプリの注意書き（告知を引用。PR #7 のルールでは引用RPとして載ってしまった）
NOTE = '一応注意なのですが、こちらでのポストは全て私のポストです。ロマーノやオーンスタインの過去ポストを全て遡れるというわけではなく、私がそれらを引用RP等したものをカウントし、アプリに反映しています。なので私の主観ですし、抜けも間違いもあります。そこはご容赦ください。 https://twitter.com/gooner1031/status/2124483743876563050'
chk(promo.is_promo(NOTE, ['https://twitter.com/gooner1031/status/2124483743876563050']), 'アプリの注意書きは除外(2124501294056611863)')
chk(promo.is_promo('補足です', ['https://x.com/gooner1031/status/2124483772230094854']), '告知ポストを引用・リンクした補足は除外')
chk(promo.is_promo('いつも見てくださりありがとうございます。抜けもあるのでご容赦ください。このアカウントは私の主観です。'), 'アカウント自体の注意書き（目印の言い回しなし）は除外')
chk(not post_rule.keep(NOTE, ['https://twitter.com/gooner1031/status/2124483743876563050'], quoted=True), '注意書きは引用RPでも載せない')
# 本物のアーセナルのポストは残す
chk(not promo.is_promo('このアカウントはシェシュコの似た選手として、ワトキンスを挙げています🫢🔥🔥⬇ https://x.com/N5Scouting/status/1'), '他アカウントの紹介（このアカウント＋情報）は除外しない')
chk(not promo.is_promo('【Daily Mail】SNSの誹謗中傷で、アーセナルは問題のあるアカウントを報告。アプリ上の対策も進める。'), '記事中のアカウント・アプリでは除外しない（アカウントの「カウント」は数えない）')
chk(not promo.is_promo('【Arsenal】配信障害に伴い、公式アプリでのプレシーズン配信を全額返金。'), '公式アプリの話題は除外しない')
chk(not promo.is_promo('サカの過去のゴールはこちら https://x.com/gooner1031/status/2017644030553915540'), '告知以外の自分のポストの引用は除外しない')
chk(not promo.is_promo('【The Athletic】\nアーセナルはニューカッスルと2-2で引き分け、首位をキープ。\n\n#アーセナル #Arsenal #COYG'), 'ハッシュタグだけでは除外しない')
chk(not promo.is_promo('【TEAMtalk】\nジェズスの代理人は複数クラブとcontactを取っている。'), '記事中の contact（英語）では除外しない')
chk(not promo.is_promo('アーセナルの情報を追いたいのならジャガーさんはフォロー必須ですよ！！'), '他アカウントのフォロー推奨では除外しない')
chk(promo.is_promo('わずか10時間ほどですが、皆様から沢山の反響をいただけてありがたいです🙏間違いや改善点の要望もすでに20件近く頂いています。善処しますので引き続き宜しくお願いします😊'), '反響・要望へのお礼は除外(2124643961650446417)')
chk(promo.is_promo('たくさんのご意見をいただき感謝しています。順次対応します。'), '寄せられた意見へのお礼は除外')
chk(not promo.is_promo('ガブリエウからの感謝のメッセージ…それが大きな反響を呼んだことは素晴らしい（@DailyMail）'), '記事中の「反響を呼んだ」「感謝」では除外しない')
chk(not promo.is_promo('ギェケレシュ「改善点は常にある。常に今より良くなれる」'), '選手コメントの「改善点」では除外しない')
chk(not promo.is_promo('【Arsenal】クラブはファンからの要望を受けてチケット価格を見直した。'), '記事中の「要望」では除外しない')
# 載せるポストの判定（post_rule.keep。ME は自分のユーザーID）
ME = '1082527986430013440'; K = post_rule.keep
chk(K('【TEAMtalk】\nモスケラにインテルが関心', ['https://www.teamtalk.com/x']), 'URL 付きの記事ポストは載せる')
chk(K('これは大きい', quoted=True), '引用RPは載せる')
chk(K('サカの今季スタッツ', media=1), '画像付きのスタッツは載せる')
chk(K('イアン・ライトはSky Sportsでラヤの負傷に言及。「…」と語った。 （@DailyMail）'), '（@媒体）の出典表記つきは URL がなくても載せる(11/22 15:15)')
chk(K('続きです。アルテタは…', reply_to=ME, me=ME, parent_kept=True), '載せたポストに自分で続けたスレッドは載せる')
chk(not K('ありがとうございます！', ['https://x.com/a/status/1'], reply_to='999', me=ME), '他人へのリプライは URL があっても載せない')
chk(not K('今日は仕事が忙しかった…', me=ME), 'URL・画像・引用なしの私的な一言は載せない')
chk(not K('眠い', reply_to=ME, me=ME, parent_kept=False), '載っていないポストへの自分の返信で目印なしは載せない')
chk(not K('毎日更新しています。サイト内のCONTACTから送れます', quoted=True), '宣伝ポストは引用RPでも載せない')
# 実データ: 過去のポストで目印に当たるものがない（誤検知ゼロ）
P = []
for f in ('posts.json', 'posts-old.json', 'incoming.json'):
    try: P += json.load(open(f, encoding='utf-8'))
    except FileNotFoundError: pass
hit = [x['id'] for x in P if promo.is_promo(x.get('t'), x.get('u'), x['id'])]
chk(not hit, 'アーカイブ内に宣伝ポストが残っていない（%d 件中 %s）' % (len(P), hit or 0))
sys.exit(1 if fails else 0)
