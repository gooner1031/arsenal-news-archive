import json
from datetime import datetime
ME='1082527986430013440'
def load():
    s=open('/mnt/user-data/uploads/tweets.js',encoding='utf-8').read()
    d=[t['tweet'] for t in json.loads(s[s.index('['):])]
    for t in d:
        t['dt']=datetime.strptime(t['created_at'],'%a %b %d %H:%M:%S %z %Y')
    return d
def keep(t):
    if t['dt'].year<2022: return False
    if t['full_text'].startswith('RT @'): return False
    r=t.get('in_reply_to_user_id')
    if r and r!=ME: return False
    e=t.get('entities',{})
    has_url=bool(e.get('urls')) or bool(e.get('media'))
    has_men=bool(e.get('user_mentions'))
    return has_url or has_men or is_cut(t)
def wlen(s): return sum(1 if ord(c)<0x1100 else 2 for c in s)
def body(t):
    a,b=map(int,t['display_text_range']); return t['full_text'][a:b]
def is_cut(t):
    b=body(t).rstrip()
    if not b.endswith('…'): return False
    return ('【' in b or '🚨' in b or '@' in b or wlen(b)>=240)

import re as _re
MOND=_re.compile(r'mond|質問箱|お題箱|odaibako|querie|匿名メッセージ|質問を募集|質問募集|peing|marshmallow|マシュマロ',_re.I)
def is_mond(t):
    e=t.get('entities',{})
    hay=t['full_text']+' '+' '.join(u.get('expanded_url','') for u in e.get('urls',[]))
    if MOND.search(hay): return True
    if any(m['screen_name'].lower()=='gooner1031_' for m in e.get('user_mentions',[])): return True
    return False

def load_threads():
    """Merge self-reply chains into one pseudo-tweet per thread (root first)."""
    d = load()
    by = {t['id_str']: t for t in d}
    parent = {}
    for t in d:
        if t.get('in_reply_to_user_id') == ME and t.get('in_reply_to_status_id_str') in by:
            parent[t['id_str']] = t['in_reply_to_status_id_str']
    def root(i):
        seen = 0
        while i in parent and seen < 500: i = parent[i]; seen += 1
        return i
    groups = {}
    for t in d:
        if t['full_text'].startswith('RT @'): continue
        groups.setdefault(root(t['id_str']), []).append(t)
    out = []
    for rid, parts in groups.items():
        parts.sort(key=lambda x: x['dt'])
        r = by[rid]
        if r['full_text'].startswith('RT @'): continue
        if len(parts) == 1:
            r['_parts'] = 1; r['_cut'] = is_cut(r); r['_parts_list'] = [r]; out.append(r); continue
        m = dict(r)
        m['full_text'] = '\n\n'.join(p['full_text'] for p in parts)
        ent = {'urls': [], 'user_mentions': [], 'media': [], 'hashtags': []}
        for p in parts:
            e = p.get('entities', {})
            for k in ent: ent[k] += e.get(k, []) or []
            ee = (p.get('extended_entities') or {}).get('media')
            if ee: ent['media'] += ee
        m['entities'] = ent; m['extended_entities'] = {'media': ent['media']}
        m['display_text_range'] = ['0', str(len(m['full_text']))]
        m['_parts'] = len(parts); m['_cut'] = any(is_cut(p) for p in parts); m['_parts_list'] = parts
        out.append(m)
    from manual_posts import MANUAL
    for mp in MANUAL:
        t={'id_str':mp['id'],'full_text':mp['full_text'],'dt':datetime.fromisoformat(mp['created_at']),
           'entities':{'urls':[],'user_mentions':[],'hashtags':[]},'display_text_range':['0',str(len(mp['full_text']))],
           'favorite_count':0,'retweet_count':0,'_parts':1,'_cut':False,'_manual':True}
        t['_parts_list']=[t]; out.append(t)
    return out
