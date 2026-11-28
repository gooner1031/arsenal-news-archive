#!/usr/bin/env python3
"""X API から @gooner1031 の新着ポストを取得して incoming.json に追記する。
必要: 環境変数 X_BEARER_TOKEN（GitHub Secrets）。新着のみ取得（since_id）して課金を最小化。"""
import json, os, re, sys, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
ME = '1082527986430013440'
JST = timezone(timedelta(hours=9))
TOKEN = os.environ.get('X_BEARER_TOKEN', '').strip()
if not TOKEN: sys.exit('X_BEARER_TOKEN が未設定です')
TOKEN = re.sub(r'^(Bearer|bearer)\s+', '', TOKEN)
TOKEN = re.sub(r'\s+', '', TOKEN)   # 貼り付け時の改行・空白を除去
bad = [c for c in TOKEN if not (33 <= ord(c) < 127)]
if bad: sys.exit('X_BEARER_TOKEN に使えない文字が %d 個含まれています（全角文字など）。コピーし直してください。' % len(bad))
print('token length:', len(TOKEN), '/ 先頭10文字が全てA:', TOKEN[:10]=='A'*10, '/ %を含む:', '%' in TOKEN, '/ 文字種:', sorted({('英大' if c.isupper() else '英小' if c.islower() else '数' if c.isdigit() else c) for c in TOKEN}))

def load(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d
posts = load('posts.json', []) + load('posts-old.json', []); inc = load('incoming.json', [])
# スレッド（自分への返信の連なり）は先頭のポスト1件にまとめて入れる（アーカイブ本体と同じ形：t を空行でつなぎ、n=件数、ids=続きのID）。
# 続きのIDは known に入れて、since_id と取り込み済みの判定に使う
known = {str(x['id']) for x in posts} | {str(x['id']) for x in inc} | {str(i) for x in inc for i in x.get('ids', [])}
nums = [int(i) for i in known if i.isdigit()]
since = max(nums) if nums else None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import link_card

def api(path, params):
    url = 'https://api.x.com/2/' + path + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + TOKEN, 'User-Agent': 'arsenal-archive'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit('X API エラー %s: %s' % (e.code, e.read().decode('utf-8', 'replace')[:500]))

params = {'max_results': 100, 'exclude': 'retweets',
          'tweet.fields': 'created_at,entities,note_tweet,referenced_tweets,in_reply_to_user_id,attachments,public_metrics',
          'expansions': 'attachments.media_keys', 'media.fields': 'url,preview_image_url,type'}
if since: params['since_id'] = since
new, token = [], None
for _ in range(3):
    if token: params['pagination_token'] = token
    r = api('users/%s/tweets' % ME, params)
    media = {m['media_key']: m for m in r.get('includes', {}).get('media', [])}
    for t in r.get('data', []):
        if t.get('in_reply_to_user_id') not in (None, ME): continue   # 他人へのリプライは除外
        txt = (t.get('note_tweet') or {}).get('text') or t['text']
        ent = (t.get('note_tweet') or {}).get('entities') or t.get('entities') or {}
        urls = []
        for u in ent.get('urls', []):
            ex = u.get('expanded_url') or u.get('url')
            if 'x.com/' in ex and '/photo/' in ex: txt = txt.replace(u['url'], ''); continue
            txt = txt.replace(u['url'], ex); urls.append(ex)
        txt = re.sub(r'\s*https://t\.co/\w+\s*$', '', txt).strip()
        mk = (t.get('attachments') or {}).get('media_keys', [])
        imgs = [m.get('url') or m.get('preview_image_url') for k in mk for m in [media.get(k, {})] if m.get('type') == 'photo']
        d = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00')).astimezone(JST)
        pm = t.get('public_metrics') or {}
        refs = {x.get('type'): x.get('id') for x in t.get('referenced_tweets') or []}
        try: og = link_card.from_entities(ent) or link_card.from_entities(t.get('entities'))   # リンクカードの画像（X に出るものと同じ）
        except Exception: og = None
        new.append({'id': t['id'], 'd': d.strftime('%Y-%m-%d %H:%M'), 't': txt, 'u': urls, 'img': [i for i in imgs if i], 'f': pm.get('like_count', 0), 'r': pm.get('retweet_count', 0), **({'og': og} if og else {}),
                    '_rule': dict(media=len(mk), quoted='quoted' in refs, reply_to=t.get('in_reply_to_user_id'), parent=refs.get('replied_to'))})
    token = r.get('meta', {}).get('next_token')
    if not token: break
new = [n for n in new if n['id'] not in known]
# 載せるポストだけ残す（判定は tools/post_rule.py / promo.py。daily_review.md と共通）
# 引用RP・URL・画像/動画・出典表記つきとそのスレッドの続きは残し、他人へのリプライ・私的な一言・サイトの宣伝は除外
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import post_rule
merged = False
kept_ids, _keep = set(known), []
# 続きのID → 先頭ポスト（incoming.json にあるスレッドの続きをここで先頭にまとめる。アーカイブ本体 posts.json の先頭に続ける場合はまとめず、そのまま別のポストとして載る）
root_of = {}
for x in inc:
    root_of[str(x['id'])] = x
    for i in x.get('ids', []): root_of[str(i)] = x
for n in sorted(new, key=lambda x: int(x['id'])):
    ru = n.pop('_rule')
    if post_rule.keep(n['t'], n['u'], ru['media'], ru['quoted'], ru['reply_to'], ME, ru['parent'] in kept_ids, n['id']):
        kept_ids.add(n['id'])
        r = root_of.get(str(ru['parent'])) if ru['reply_to'] == ME and ru['parent'] else None
        if r is not None:
            r['t'] = r['t'].rstrip() + '\n\n' + n['t']
            r['img'] = (r.get('img') or []) + n['img']; r['u'] = (r.get('u') or []) + n['u']
            if n.get('og') and not r.get('og'): r['og'] = n['og']; r.pop('ogx', None)
            r['n'] = r.get('n', 1) + 1; r.setdefault('ids', []).append(n['id'])
            root_of[n['id']] = r; merged = True
            print('スレッドの続きを先頭にまとめた:', n['id'], '→', r['id'])
        else:
            _keep.append(n); root_of[n['id']] = n
    else: print('載せないポスト:', n['id'], n['t'][:30].replace('\n', ' '))
new = _keep
print('新着', len(new), '件 (since_id=%s)' % since)
# 新着には cats.py の発言（コメント）判定を kx として付ける（サイト側の簡易分類に足される）
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import cats
    _CN = load('meta.json', {}).get('cats', []); _IX = {n: i for i, n in enumerate(_CN)}
    _body = lambda t: re.sub(r'^【[^】]*】(\s*[（(][^）)]*[）)])?\s*', '', (t or '').replace('\u200b', '')).strip()
    for n in new:
        _nm = [c for c in cats.refine(_body(n['t']), []) if c in ('インタビュー・コメント', 'プレビュー', 'レビュー')]
        if _nm: n['kx'] = [_IX[c] for c in _nm if c in _IX]
except Exception as e: print('カテゴリ付与をスキップ:', e)
changed = bool(new) or merged
inc = sorted(inc + new, key=lambda x: x['id'])
# 告知・お礼ポスト（promo.py のルールや promo_ids.txt に後から追加したもの）は、取り込み済みでも incoming.json から外す
_n = len(inc)
inc = [x for x in inc if not post_rule.promo.is_promo(x.get('t'), x.get('u'), x['id'])]
if len(inc) != _n: changed = True; print('告知ポストを除外:', _n - len(inc), '件')
# いいね・RT数の更新：直近3日分を1日4回（手動実行時は必ず）。同日UTC内の重複は課金されない
if os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' or datetime.now(timezone.utc).hour % 6 == 1:
    cut = (datetime.now(JST) - timedelta(days=3)).strftime('%Y-%m-%d %H:%M')
    ids = [x['id'] for x in inc if x['d'] >= cut][:100]
    if ids:
        r = api('tweets', {'ids': ','.join(ids), 'tweet.fields': 'public_metrics'})
        pm = {t['id']: t.get('public_metrics') or {} for t in r.get('data', [])}
        for x in inc:
            m = pm.get(x['id'])
            if m and (x.get('f') != m.get('like_count', 0) or x.get('r') != m.get('retweet_count', 0)):
                x['f'], x['r'] = m.get('like_count', 0), m.get('retweet_count', 0); changed = True
        print('指標を更新:', len(ids), '件を確認')
if changed:
    json.dump(inc, open('incoming.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
