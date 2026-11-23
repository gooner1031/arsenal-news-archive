#!/usr/bin/env python3
"""公式Xに貼る投稿文の下書きを作る（自動投稿はしない。下書きを drafts.json に貯めるだけ）。

tools/share_cards.py から呼ばれる（シェアカードと同じデータ・同じタイミング）。
- 移籍：トラッカーの段階が「合意」「完了」になった選手（直近3日以内に報道があったもの）
- 試合：結果（スコア）が入った試合（試合日が直近3日以内）。スコア入りと、ネタバレなし（スコアなし）の2案
リンクはシェアカードの共有ページ（s/...html）なので、Xに貼るとカード画像が出る。
下書きは drafts.html（サイトからはリンクしていない管理用ページ）で見て、「Xで投稿」かコピーで使う。
一度作った下書きは key で覚えておき、同じ出来事で二度作らない。
"""
import datetime, json, os, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'drafts.json')
SITE = 'https://gooner1031.github.io/arsenal-news-archive/'
DAYS = 3        # この日数より前の出来事は下書きにしない（初回に過去分が大量に出ないように）
KEEP = 40       # 残す下書きの数
TAG = '#アーセナル'


def xlen(text, url=True):
    """Xの文字数（全角は2、URLは23）。"""
    n = sum(1 if unicodedata.east_asian_width(c) in 'NaH' else 2 for c in text)
    return n + (24 if url else 0)


def fit(lines, limit=280):
    """長すぎるときは、途中の行（説明）から削る。1行目とハッシュタグは残す。"""
    lines = [l for k, l in enumerate(lines) if l or (k and lines[k - 1])]  # 空行は1つまで残す
    while xlen('\n'.join(lines)) > limit and len(lines) > 2:
        lines.pop(-2)
        while len(lines) > 2 and not lines[-2]: lines.pop(-2)
    return '\n'.join(lines)


def tr_draft(r):
    nm, club, fee = r['name'], r['club'], r['fee']
    inn = r['dir'] == 'IN'
    if r['st'] == 'done':
        head = f'【加入決定】{nm}がアーセナルに加入🔴⚪' if inn else (f'【移籍決定】{nm}が{club}へ移籍' if club else f'【退団決定】{nm}が退団')
        label = '加入決定' if inn else '退団決定'
    else:
        head = (f'【合意】{nm}のアーセナル加入で合意との報道🔴⚪' if inn else
                (f'【合意】{nm}の{club}移籍で合意との報道' if club else f'【合意】{nm}の移籍で合意との報道'))
        label = '合意'
    sub = ''
    if club and inn:
        sub = f'{club}から' + (f'・{fee}' if fee else '')
    elif fee:
        sub = f'移籍金 {fee}'
    text = fit([head, sub, '', f'報道{r["n"]}件の時系列はこちら👇', TAG])
    return {'kind': 'transfer', 'label': label, 'title': f'{nm}（{r["win"]}）',
            'text': text, 'url': SITE + f's/tr-{r["i"]}-{r["w"]}.html?v={r["st"]}', 'slug': f'tr-{r["i"]}-{r["w"]}'}


def m_drafts(m):
    ttl = ('アーセナル vs ' if m['ha'] == 'H' else '' if m['ha'] == 'A' else 'vs ') + m['club'] + (' vs アーセナル' if m['ha'] == 'A' else '')
    d = m['d'][5:].replace('-', '/')
    res = {'W': '勝利🔴⚪', 'L': '敗戦', 'D': '引き分け'}.get(m['r'], '')
    a = {'kind': 'match', 'label': '試合結果', 'title': f'{d} {ttl}',
         'text': fit([f'{d} {ttl} {m["sc"]} {res}（{m["comp"]}）', '', 'スタッツ・ベンチ・関連ポストをまとめました👇', TAG]),
         'url': SITE + f's/match-{m["id"]}.html?v=r', 'slug': f'match-{m["id"]}'}
    b = {'kind': 'match', 'label': '試合結果（ネタバレなし）', 'title': f'{d} {ttl}',
         'text': fit([f'{d} {ttl}（{m["comp"]}）', '', '結果はリンク先で（ネタバレなし）。スタッツと関連ポストまとめ👇', TAG]),
         'url': SITE + f's/match-{m["id"]}-ns.html?v=r', 'slug': f'match-{m["id"]}-ns'}
    return [a, b]


def make(data, images, now=None):
    """data は share_cards.py の EXTRACT の結果。images は {slug: 画像ファイル名}。新しく作った下書きの数を返す。"""
    now = now or datetime.datetime.utcnow() + datetime.timedelta(hours=9)   # 日本時間
    since = (now - datetime.timedelta(days=DAYS)).strftime('%Y-%m-%d'); today = now.strftime('%Y-%m-%d')
    try:
        st = json.load(open(PATH, encoding='utf-8'))
    except Exception:
        st = {}
    seen, drafts = set(st.get('seen', [])), st.get('drafts', [])
    new = []
    for r in data['tr']:
        if r['dead'] or r['st'] not in ('agreed', 'done') or (r.get('last') or '')[:10] < since:
            continue
        key = f'tr-{r["i"]}-{r["w"]}:{r["st"]}'
        if key not in seen:
            seen.add(key); new.append(dict(tr_draft(r), key=key))
    for m in data['m']:
        if not m['sc'] or not since <= m['d'] <= today:
            continue
        key = f'match-{m["id"]}:r'
        if key not in seen:
            seen.add(key)
            for k, x in enumerate(m_drafts(m)):
                new.append(dict(x, key=key + ('' if k == 0 else ':ns')))
    t = now.strftime('%Y-%m-%d %H:%M')
    for x in new:
        x['t'] = t
        im = images.get(x['slug'])
        x['img'] = SITE + 's/img/' + im if im else SITE + 'og.png'
    drafts = (new + drafts)[:KEEP]
    with open(PATH, 'w', encoding='utf-8') as f:
        json.dump({'note': '公式X用の投稿文の下書き（自動生成・自動投稿はしない）。drafts.html で確認', 'drafts': drafts,
                   'seen': sorted(seen)}, f, ensure_ascii=False, indent=1)
    return len(new)
