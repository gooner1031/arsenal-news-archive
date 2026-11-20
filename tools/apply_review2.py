import json,sys
# usage: apply_review2.py decisions.json   ({id:{v:keep|drop,c:[...]}})
D=json.load(open(sys.argv[1]))
keep={l.strip() for l in open('keep_ids.txt') if l.strip()}
drop={l.strip() for l in open('drop_ids.txt') if l.strip()}
try: co=json.load(open('cat_override.json'))
except FileNotFoundError: co={}
for i,d in D.items():
    if d['v']=='keep':
        keep.add(i); drop.discard(i)
        if d.get('c'): co[i]=d['c']
    else:
        drop.add(i); keep.discard(i); co.pop(i,None)
open('keep_ids.txt','w').write('\n'.join(sorted(keep))+'\n')
open('drop_ids.txt','w').write('\n'.join(sorted(drop))+'\n')
json.dump(co,open('cat_override.json','w'),ensure_ascii=False,indent=0)
print(len(keep),len(drop),len(co))
