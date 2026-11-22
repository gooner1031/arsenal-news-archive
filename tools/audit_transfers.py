#!/usr/bin/env python3
"""移籍トラッカーの取りこぼし監査。
 1) 直近の「移籍・噂」ポストに出てくるカタカナ人名のうち、META.people に未登録のものを頻度順に列挙（登録漏れ＝トラッカーに載らない原因）
 2) 登録済み選手でも p タグが付いていない移籍ポストを列挙
 使い方: python3 tools/audit_transfers.py [since=2026-05-01] [min=2]
 出力: pending_players.json（管理人が確認して people.py に追加する候補）"""
import json,re,sys,collections
since=(sys.argv[1] if len(sys.argv)>1 else '2026-05-01'); mn=int(sys.argv[2]) if len(sys.argv)>2 else 2
m=json.load(open('meta.json',encoding='utf8')); P=m['people']
posts=[]
for f in ('posts.json','incoming.json'):
    d=json.load(open(f,encoding='utf8')); posts+= d
def has_name(t,q):
    last=q['n'].split('・')[-1]; first=q['n'].split('・')[0]
    return q['n'] in t or (len(last)>=3 and last in t) or (len(first)>=4 and first in t)
# 選手名らしさ: 「名前（23）」「MF/FW/DF/GK/WG/CB/CF/ストライカー/ウインガー/DF 名前」「名前選手」の形だけ拾う（クラブ名・一般語を避ける）
NM=r'([ァ-ヴー]{2,}(?:[・＝=][ァ-ヴー]{1,})+|[ァ-ヴー]{3,})'
PAT=[re.compile(NM+r'\s*[（(]\s*\d{2}\s*[）)]'), re.compile(r'(?:MF|FW|DF|GK|WG|CB|CF|LB|RB|AMF|CMF|DMF|ストライカー|ウインガー|ウィンガー|センターバック|サイドバック|ミッドフィルダー|ゴールキーパー|FW陣|選手)\s*'+NM), re.compile(NM+r'(?:選手|を獲得|の獲得|獲得へ|に関心|への関心|をリストアップ|との契約)')]
STOP=set('シーズン タイトル プレミア フットボール スカッド ポジション アプローチ アカデミー ボーナス エミレーツ オーナー パフォーマンス チームメイト アシスト ライバル リストアップ アタッカー オプション スタッフ スタメン ガナーズ トロフィー キャプテン'.split())
CLUBS=set(m['clubs'])
cnt=collections.Counter(); ex={}
for x in posts:
    if x['d'][:10]<since: continue
    t=re.sub(r'^【[^】]*】','',x['t'])
    if not (0 in x.get('k',[]) or re.search(r'獲得|移籍|オファー|関心|ターゲット|リスト',t)): continue
    seen=set()
    for pt in PAT:
        for mm in pt.finditer(t):
            nm=mm.group(1)
            if '・' not in nm or nm in seen or nm in STOP or nm in CLUBS or any(c in nm for c in CLUBS if len(c)>=4): continue
            if any(nm==q['n'] or nm in q['n'].split('・') or q['n'] in nm or q['n'].split('・')[-1]==nm.split('・')[-1] for q in P): continue
            seen.add(nm); cnt[nm]+=1; ex.setdefault(nm,[]).append(x['id'])
out=[{'name':k,'count':v,'ids':ex[k][:5]} for k,v in cnt.most_common() if v>=mn]
json.dump(out,open('pending_players.json','w',encoding='utf8'),ensure_ascii=False,indent=1)
print('未登録の人名候補（%d件以上）:'%mn)
for o in out[:40]: print(' ',o['name'],o['count'],o['ids'][0])
miss=[x for x in posts if x['d'][:10]>=since and 0 in x.get('k',[]) and not x.get('p')]
print('移籍・噂なのに人物タグなし:',len(miss),'件')
