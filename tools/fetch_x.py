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
posts = load('posts.json', []); inc = load('incoming.json', [])
known = {str(x['id']) for x in posts} | {str(x['id']) for x in inc}
nums = [int(i) for i in known if i.isdigit()]
since = max(nums) if nums else None

def api(path, params):
    url = 'https://api.x.com/2/' + path + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + TOKEN, 'User-Agent': 'arsenal-archive'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit('X API エラー %s: %s' % (e.code, e.read().decode('utf-8', 'replace')[:500]))

params = {'max_results': 100, 'exclude': 'retweets',
          'tweet.fields': 'created_at,entities,note_tweet,referenced_tweets,in_reply_to_user_id,attachments',
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
        imgs = [m.get('url') or m.get('preview_image_url') for k in (t.get('attachments') or {}).get('media_keys', []) for m in [media.get(k, {})] if m.get('type') == 'photo']
        d = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00')).astimezone(JST)
        new.append({'id': t['id'], 'd': d.strftime('%Y-%m-%d %H:%M'), 't': txt, 'u': urls, 'img': [i for i in imgs if i]})
    token = r.get('meta', {}).get('next_token')
    if not token: break
new = [n for n in new if n['id'] not in known]
print('新着', len(new), '件 (since_id=%s)' % since)
if new:
    inc = sorted(inc + new, key=lambda x: x['id'])
    json.dump(inc, open('incoming.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
