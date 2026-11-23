#!/usr/bin/env python3
"""サイト（アプリ）自体の宣伝・告知ポストの判定。
@gooner1031 の告知ポスト（アプリ紹介・ホーム画面への追加方法・CONTACT/フォローのお願い）は
アーセナルのニュースではないので、アーカイブに取り込まない。
fetch_x.py（毎時の自動取得）と daily_review.md（毎日の正式タグ付け）の両方がこの判定に従う。

ルール（どれか1つに当たれば宣伝・告知ポスト）:
  1. tools/promo_ids.txt に載っている ID
  2. MARKERS のどれかが本文または URL に含まれる
  3. promo_ids.txt の告知ポストを引用・リンクしている（告知への補足・注意書き）
  4. アプリ・アカウント自体を指す言葉（SELF）と、注意書き・お礼・お願いの言葉（META）の両方を含む
     例: 「こちらでのポストは全て私のポスト…カウントし、アプリに反映…ご容赦ください」
  5. 寄せられた反響・要望・指摘へのお礼（FEEDBACK と THANKS の両方）
     例: 「皆様から沢山の反響をいただけてありがたいです…改善点の要望も…頂いています。善処します」
目印はサイト固有の言い回しだけにしてあり、#アーセナル #COYG やフォローの話だけでは除外しない
（過去 7,000 件超のポストで誤検知ゼロを tools/test_promo.py で確認）。"""
import os, re
_IDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'promo_ids.txt')

MARKERS = [
    'gooner1031.github.io/arsenal-news-archive',  # サイトの URL
    'Arsenal News Archive',                         # サイト名
    'ホーム画面に追加', 'ホーム画面への追加',        # インストール方法
    'サイト内のCONTACT',                            # 問い合わせ窓口の案内
    '「指摘」ボタン',
    'このアカウントで毎日発信',                      # フォローのお願い
    'アプリに反映', 'サイトに反映', 'こちらでのポスト', # アプリの仕組みの説明・注意書き
]
# 4. の判定用。SELF だけ・META だけでは除外しない（「このアカウントはシェシュコの似た選手として…」等は残す）
SELF = re.compile(r'アプリ|このサイト|当サイト|このアカウント|当アカウント|こちらのアカウント|私のポスト|僕のポスト')
META = re.compile(r'ご容赦|ご了承|(?<!ア)カウント|反映|注意|主観|抜けも|間違いも|フォローありがとう|フォローお願い|フォローして(?:ください|下さい|ね)|使い方|登録不要')
# 5. の判定用。「反響を呼んだ」「改善点は常にある」等の記事中の言い回しでは除外しない（〜を頂く/いただく の形だけ）
FEEDBACK = re.compile(r'(?:反響|要望|ご意見|ご指摘|フィードバック|改善点|リクエスト)[^。\n]{0,15}?(?:頂|いただ)')
THANKS = re.compile(r'ありがた|ありがとう|感謝|善処|引き続き')
STATUS = re.compile(r'/status(?:es)?/(\d+)')

def promo_ids():
    """目印のない告知ポストを手で除外するための ID リスト（1行1件、# 以降はメモ）。"""
    try: return {l.split('#')[0].strip() for l in open(_IDS, encoding='utf-8')} - {''}
    except FileNotFoundError: return set()

def is_promo(text, urls=(), pid=None):
    if pid is not None and str(pid) in promo_ids(): return True
    s = (text or '').replace('\u200b', '') + '\n' + '\n'.join(urls or [])
    if any(m in s for m in MARKERS): return True
    if set(STATUS.findall(s)) & promo_ids(): return True            # 告知ポストの引用・リンク
    if FEEDBACK.search(s) and THANKS.search(s): return True         # 反響・要望へのお礼
    return bool(SELF.search(s) and META.search(s))

if __name__ == '__main__':
    import json, sys
    for f in sys.argv[1:] or ['incoming.json', 'posts.json', 'posts-old.json']:
        for x in json.load(open(f, encoding='utf-8')):
            if is_promo(x.get('t'), x.get('u'), x['id']): print(f, x['id'], x['d'], x['t'][:40].replace('\n', ' '))
