import sys,json,collections,os
sys.path.insert(0,'/home/claude/work')
from people import P as EP, EN, GROUPS, SRC
D=json.load(open('data.json'))
P=D['posts']
pc=collections.Counter(x for o in P for x in o['p'])
people=[n for n,_ in pc.most_common()]
clubs=[n for n,_ in collections.Counter(x for o in P for x in o['c']).most_common()]
srcs=[n for n,_ in collections.Counter(x for o in P for x in o['src']).most_common()]
from cats import ORDER as cats
pi={n:i for i,n in enumerate(people)};ci={n:i for i,n in enumerate(clubs)};si={n:i for i,n in enumerate(srcs)};ki={n:i for i,n in enumerate(cats)}
G=GROUPS
SI={jp:(typ,en) for typ,jp,en,_,__ in SRC}
lines=[]
for o in sorted(P,key=lambda o:-o['ts']):
    r={'id':o['id'],'d':o['d'],'s':o['s'],'t':o['t'],'f':o['f'],'r':o['r']}
    if o['p']: r['p']=[pi[x] for x in o['p']]
    if o['c']: r['c']=[ci[x] for x in o['c']]
    if o['src']: r['so']=[si[x] for x in o['src']]
    if o['cat']: r['k']=[ki[x] for x in o['cat']]
    if o.get('m'): r['m']=o['m']
    if o['img']: r['i']=1
    if o.get('np',1)>1: r['n']=o['np']
    if o.get('cut'): r['x']=1
    lines.append(json.dumps(r,ensure_ascii=False,separators=(',',':')))
open('site/posts.json','w').write('[\n'+',\n'.join(lines)+'\n]\n')
from positions import POS
meta={'people':[dict({'n':n,'e':EN[n],'g':G[EP[n][0]]},**({'pos':POS[EN[n]]} if EN[n] in POS else {})) for n in people],'clubs':clubs,'sources':srcs,'stype':[SI[x][0] for x in srcs],'sen':[SI[x][1] for x in srcs],'tier':[__import__('tiers').TIER.get(x,0 if SI[x][0]=='データ' else 1) for x in srcs],'cats':cats,
 'groups':list(G.values()),'matches':[m for m in D['matches'] if m['n']>0],'total':len(P),'updated':'2026-11-19'}
json.dump(meta,open('site/meta.json','w'),ensure_ascii=False,separators=(',',':'))
print(os.path.getsize('site/posts.json'),os.path.getsize('site/meta.json'),len(people),len(meta['matches']))
