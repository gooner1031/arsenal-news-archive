import json,re,collections
P=[json.loads(l.rstrip(',\n')) for l in open('site/posts.json') if l.startswith('{')]
M=json.load(open('site/meta.json'))
out=[]
for p in P:
    if p.get('k'): continue
    t=p['t']; plain=re.sub(r'https?://\S+','',t).strip(); L=len(plain)
    q=re.search(r'https?://(?:x|twitter)\.com/(\w+)/status/\d+',t)
    ext=re.search(r'https?://(?!(?:x|twitter)\.com)\S+',t)
    g='news' if (p.get('so') or ext) else 'q1' if q and L<60 else 'q2' if q else 'other'
    out.append({'id':p['id'],'d':p['d'][:10],'t':t,'g':g,'qa':q.group(1) if q else '','p':[M['people'][i]['n'] for i in p.get('p',[])][:3],'so':[M['sources'][i] for i in p.get('so',[])][:2],'f':p['f']})
order={'news':0,'q2':1,'other':2,'q1':3}
out.sort(key=lambda o:(order[o['g']],-o['f']))
print(len(out),collections.Counter(o['g'] for o in out))
open('review2/items.json','w').write('[\n'+',\n'.join(json.dumps(o,ensure_ascii=False,separators=(',',':')) for o in out)+'\n]\n')
json.dump([c for c in M['cats'] if c!='SNS・選手の発信'],open('review2/cats.json','w'),ensure_ascii=False)
