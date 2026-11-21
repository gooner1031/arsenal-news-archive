import sys, re, json, collections, html
sys.path.insert(0, '/home/claude/work')
from load import load, keep, ME, is_cut, load_threads
from cats import categorize, refine, ORDER as CAT_ORDER
from quote_ok import OK as QUOTE_OK
TR_STRONG = re.compile(r'獲得|関心|興味|オファー|交渉|合意|売却|放出|加入|退団|移籍金|ローン|レンタル|ターゲット|候補|狙|here we go', re.I)
LU_EXC = re.compile(r'登録|想定|Aリスト|予想|妄想|提案|移籍市場|仮定|パターン|HG|ホームグロウン|平均年齢|記録|試合目|ランキング|グループ|売却|獲得|退団|IN|起用し|調査|負傷|怪我|膝|筋肉|昇格|投票|補強|史上|通算|ローン|xG|%|％|🗣')
LU_HARD = re.compile(r'スタメン発表|STARTING|𝗦𝗧𝗔𝗥𝗧𝗜𝗡𝗚|先発メンバー|メンバー発表|戦スタメン|【先発')
def is_lineup(plain, npeople):
    t = plain.strip()
    if t == '#COYG': return True
    if LU_EXC.search(t): return False
    return bool(LU_HARD.search(t) or (npeople >= 10 and len(t) < 330))
import os as _os
PSWAP = json.load(open('/home/claude/work/person_swap.json')) if _os.path.exists('/home/claude/work/person_swap.json') else {}
SRCADD = json.load(open('/home/claude/work/src_add.json')) if _os.path.exists('/home/claude/work/src_add.json') else {}
QHANDLE = {'ジ・アスレチック': {'theathleticfc', 'theathleticuk'}, 'スカイスポーツ': {'skysportspl', 'skysportsnews', 'skysports'},
 'BBC': {'bbcsport', 'bbcfootball'}, 'GOAL': {'goal', 'goaljp_official'}, 'アーセナル公式': {'arsenal', 'arsenalacademy', 'arsenalwfc'},
 'サミ・モクベル': {'samimokbel_bbc'}, 'サシャ・タヴォリエリ': {'sachatavolieri'}, 'マルカ': {'marca'}, 'オプタ': {'optajoe', 'optaanalyst'},
 'フーズコアード': {'whoscored'}, 'テレグラフ': {'telegraphsport'}, 'ジョン・クロス': {'johncrossmirror'}}
from entities import CLUBS, CATS, BLOCK
from people import P, SRC, EN, GROUPS
from load import is_mond
BLOCK = [b for b in BLOCK if b != 'ACミラン']
CLUBS['ミラン'] = ['ACミラン', 'ミラン']
CLUBS['コヴェントリー'] = ['コヴェントリー','コベントリー']
CLUBS['ハル・シティ'] = ['ハル・シティ','ハルシティ']

# build alias table: (alias, kind, name)
al = []
for name, (g, aliases) in P.items():
    for a in aliases:
        al.append((a, 'p', name))
for name, aliases in CLUBS.items():
    for a in aliases:
        al.append((a, 'c', name))
for b in BLOCK:
    al.append((b, 'x', None))
# katakana aliases: substring; latin aliases: word boundary
al.sort(key=lambda x: -len(x[0]))
jp = [(a, k, n) for a, k, n in al if not re.fullmatch(r'[A-Za-zØøÖöé\- ]+', a)]
en = [(re.compile(r'(?<![A-Za-z])' + re.escape(a) + r'(?![A-Za-z])'), k, n) for a, k, n in al if re.fullmatch(r'[A-Za-zØøÖöé\- ]+', a)]

def find_entities(text):
    t = text
    found_p, found_c = collections.Counter(), collections.Counter()
    club_spans = []
    for a, k, n in jp:
        i = t.find(a)
        while i >= 0:
            if k == 'p': found_p[n] += 1
            elif k == 'c': found_c[n] += 1; club_spans.append((i, i + len(a), n))
            t = t[:i] + '\0' * len(a) + t[i + len(a):]
            i = t.find(a, i + len(a))
    for rx, k, n in en:
        if rx.search(t):
            if k == 'p': found_p[n] += 1
            elif k == 'c': found_c[n] += 1
    return found_p, found_c, club_spans

def season(dt):
    y = dt.year if dt.month >= 7 else dt.year - 1
    return f'{y % 100:02d}/{(y + 1) % 100:02d}'


def main():
    d = load_threads()
    allposts = {t['id_str']: t for t in d}
    FORCE={l.strip() for l in open('/home/claude/work/keep_ids.txt') if l.strip()}
    from manual_posts import MANUAL
    FORCE|={m['id'] for m in MANUAL}
    DROP={l.strip() for l in open('/home/claude/work/drop_ids.txt') if l.strip()}
    SNSRX=re.compile(r'(Instagram|instagram|インスタ)\s*(を更新|に投稿|の投稿|のストーリー|📸|📷)|【Instagram|SNSを更新|自身のSNS|Xを更新|ヘッダーが.{0,6}更新')
    for t in d:
        if t['dt'].year>=2022 and SNSRX.search(t['full_text']) and not (t.get('in_reply_to_user_id') and t['in_reply_to_user_id']!=ME) and find_entities(re.sub(r'https?://\S+','',t['full_text']))[0]:
            FORCE.add(t['id_str'])
    k = [t for t in d if t['id_str'] not in DROP and (t['id_str'] in FORCE or ((keep(t) or (t['_parts']>1 and any(keep(x) for x in t['_parts_list']))) and not any(is_mond(x) for x in t['_parts_list']) and not re.search('smarterscout|スマータースカウト|スマーター', t['full_text'] + ' '.join(u.get('expanded_url','') for u in t.get('entities',{}).get('urls',[])), re.I)))]
    dropped_photo = 0
    dropped_quote = 0
    import os
    CATRM = json.load(open('/home/claude/work/cat_remove.json')) if os.path.exists('/home/claude/work/cat_remove.json') else {}
    CATOVR = json.load(open('/home/claude/work/cat_override.json')) if os.path.exists('/home/claude/work/cat_override.json') else {}
    k.sort(key=lambda t: t['dt'])
    out = []
    for t in k:
        e = t.get('entities', {})
        text = t['full_text']
        media_urls = set()
        for m in (t.get('extended_entities') or e).get('media', []) or []:
            media_urls.add(m['url'])
        links = []
        for u in e.get('urls', []):
            text = text.replace(u['url'], u['expanded_url'])
            links.append(u['expanded_url'])
        for mu in media_urls:
            text = text.replace(mu, '')
        text = html.unescape(text).strip()
        plain = re.sub(r'https?://\S+', ' ', text)
        fp, fc, spans = find_entities(plain)
        if t['id_str'] in PSWAP:
            a, b = PSWAP[t['id_str']]; fp = [x for x in fp if x != a] + ([b] if b not in fp else [])
        low = (plain + ' ' + ' '.join(links)).lower()
        mentions = [m['screen_name'] for m in e.get('user_mentions', [])]
        ml = [m.lower() for m in mentions]
        brk = ' '.join(re.findall(r'【([^】]{1,40})】', text) + re.findall(r'[(（]([^)）]{1,40})[)）]', text)).lower()
        srcs = []
        for typ, jpn, enn, strong, weak in SRC:
            hit = False
            for a in strong:
                al = a.lower()
                if al in ml or al.lstrip('@') in ml: hit = True; break
                if re.search(r'[a-z]', al):
                    if re.search(r'(?<![a-z])' + re.escape(al) + r'(?![a-z])', low) or al in brk: hit = True; break
                elif al in plain: hit = True; break
            if not hit:
                for a in weak:
                    al = a.lower()
                    if al in ml: hit = True; break
                    if re.search(r'[a-z]', al):
                        if re.search(r'(?<![a-z])' + re.escape(al) + r'(?![a-z])', brk): hit = True; break
                    elif al in brk: hit = True; break
            if hit: srcs.append(jpn)
        for jn in SRCADD.get(t['id_str'], []):
            if jn not in srcs: srcs.append(jn)
        # quoted account -> source tag (e.g. quote of @FabrizioRomano -> ロマーノ)
        for u in links:
            m = re.search(r'//(?:x|twitter)\.com/(\w+)/status', u)
            if not m: continue
            h = m.group(1).lower()
            for typ, jpn, enn, strong, weak in SRC:
                if jpn in srcs: continue
                if h in QHANDLE.get(jpn, ()) or any(h == a.lower().replace(' ', '').lstrip('@') for a in strong if re.fullmatch(r'@?[A-Za-z0-9_ ]+', a)):
                    srcs.append(jpn)
        matchclubs = set(); headclubs = set()
        for i, j, n in spans:
            tail = plain[j:j + 1]
            if tail == '戦' or plain[max(0, i - 4):i].lower().strip().endswith('vs') or plain[j:j + 4].lower().strip().startswith('vs'):
                matchclubs.add(n)
                if i < 600: headclubs.add(n)
        if 'ノースロンドンダービー' in plain:
            matchclubs.add('トッテナム')
            if plain.find('ノースロンドンダービー') < 600: headclubs.add('トッテナム')
        extra = []
        if SNSRX.search(text): extra.append('SNS・選手の発信')
        if headclubs: extra.append('試合')
        cats = categorize(plain, extra, {'clubs': bool(fc), 'arsenal': 'アーセナル' in plain or 'Arsenal' in plain, 'people': bool(fp), 'src': bool(srcs), 'ext': bool([u for u in links if not re.search(r'//(x|twitter)\.com/', u)])})
        if '移籍・噂' in cats and 'インタビュー・コメント' in cats and not TR_STRONG.search(plain[:600]): cats = [c for c in cats if c != '移籍・噂']
        cats = refine(plain, cats)
        if t['id_str'] in CATRM: cats = [c for c in cats if c not in CATRM[t['id_str']]]
        if t['id_str'] in CATOVR: cats = [c for c in CAT_ORDER if c in set(cats) | set(CATOVR[t['id_str']])]
        thread = t.get('in_reply_to_status_id_str') if t.get('in_reply_to_user_id') == ME else None
        ext = [u for u in links if not re.search(r'//(x|twitter)\.com/', u)]
        quoted = [u for u in links if re.search(r'//(x|twitter)\.com/', u)]
        if t['id_str'] not in FORCE and media_urls and t['_parts']==1 and len(plain.strip())<140 and not ext and not quoted and not mentions and not t['_cut'] and not srcs \
           and not (set(cats) & {'戦術・分析', '記録・データ', '公式発表', '契約・クラブ運営', '移籍・噂', '負傷・コンディション'}):
            dropped_photo += 1
            continue
        if t['id_str'] not in FORCE and is_lineup(plain, len(fp)):
            if os.environ.get('LUDBG'): print('LU', t['id_str'], plain[:60].replace('\n',' '))
            dropped_quote += 1
            continue
        if t['id_str'] not in FORCE and quoted and not ext and not srcs and not cats and not t['_cut']:
            qh = {m.group(1).lower() for u in quoted for m in [re.search(r'\.com/(\w+)/status', u)] if m}
            if not (qh & QUOTE_OK):
                dropped_quote += 1
                continue
        out.append({
            'id': t['id_str'], 'ts': int(t['dt'].timestamp()),
            'd': t['dt'].astimezone(__import__('datetime').timezone(__import__('datetime').timedelta(hours=9))).strftime('%Y-%m-%d %H:%M'),
            's': season(t['dt']), 't': text, 'p': sorted(fp), 'c': sorted(fc), 'src': srcs, 'cat': cats,
            'mc': sorted(matchclubs), 'img': len(media_urls) > 0,
            'cut': t['_cut'], 'np': t['_parts'], 'f': int(t.get('favorite_count', 0)), 'r': int(t.get('retweet_count', 0)), 'th': thread,
        })
    # --- fixtures (Premier League) + inferred other matches
    import datetime as DT
    EN = {'Crystal Palace':'クリスタル・パレス','Leicester City':'レスター','AFC Bournemouth':'ボーンマス','Fulham':'フラム','Aston Villa':'アストン・ヴィラ',
      'Manchester United':'マンチェスター・ユナイテッド','Brentford':'ブレントフォード','Tottenham Hotspur':'トッテナム','Liverpool':'リヴァプール','Leeds United':'リーズ',
      'Southampton':'サウサンプトン','Nottingham Forest':'ノッティンガム・フォレスト','Chelsea':'チェルシー','Wolverhampton Wanderers':'ウルヴス','West Ham United':'ウェストハム',
      'Brighton & Hove Albion':'ブライトン','Newcastle United':'ニューカッスル','Everton':'エヴァートン','Manchester City':'マンチェスター・シティ','Sheffield United':'シェフィールド・ユナイテッド',
      'Burnley':'バーンリー','Napoli':'ナポリ','Lille':'リール','Bayern Munich':'バイエルン','Fleetwood Town':'フリートウッド','Slavia Prague':'スラヴィア・プラハ','Luton Town':'ルートン・タウン','Ipswich Town':'イプスウィッチ','Sunderland AFC':'サンダーランド','Coventry City':'コヴェントリー','Hull City AFC':'ハル・シティ'}
    def jp(n):
        n=n.strip(); n2=n[:-3] if n.endswith(' FC') else n
        return EN.get(n2, EN.get(n, n2))
    mlist=[]; byid={o['id']:o for o in out}
    for line in open('/home/claude/work/fixtures.txt'):
        p=[x.strip() for x in line.split('|')]
        if len(p)<3: continue
        d=p[0]; h,a=p[1],p[2]; sc=p[3] if len(p)>3 else ''; comp=p[4] if len(p)>4 and p[4] else 'プレミアリーグ'
        home = h.startswith('Arsenal')
        opp = jp(a if home else h)
        if sc and home: score=sc
        elif sc: x,y=sc.split('-'); score=f'{y}-{x}'
        else: score=''
        ko=DT.datetime.fromisoformat(d+'T15:00:00+00:00').timestamp()
        mid=('pl' if comp=='プレミアリーグ' else 'cx')+d.replace('-','')
        ids=[]
        for o in out:
            dtt=o['ts']-ko
            if -3*86400<=dtt<=2*86400 and opp in o['c'] and ('試合' in o['cat'] or '移籍・噂' not in o['cat']): ids.append(o['id'])
            elif -8*3600<=dtt<=30*3600 and not o['c'] and '試合' in o['cat']: ids.append(o['id'])
        for i in ids: byid[i].setdefault('m',[]).append(mid)
        mlist.append({'id':mid,'club':opp,'d':d,'ha':'H' if home else 'A','sc':score,'comp':comp,'n':len(ids),'ts':ko})
    # inferred others from "X戦"
    by = collections.defaultdict(list)
    for o in out:
        for c in o['mc']: by[c].append(o)
    k2=0
    for c, lst in by.items():
        lst.sort(key=lambda o: o['ts'])
        groups=[]; cur=[lst[0]]
        for o in lst[1:]:
            if o['ts']-cur[-1]['ts']<=4*86400: cur.append(o)
            else: groups.append(cur); cur=[o]
        groups.append(cur)
        for g in groups:
            if len(g)<2: continue
            if any(m['club']==c and abs(m['ts']-g[-1]['ts'])<=5*86400 for m in mlist if not m['comp'].startswith('その他')): continue
            k2+=1; mid=f'x{k2}'
            for o in g: o.setdefault('m',[]).append(mid)
            mlist.append({'id':mid,'club':c,'d':g[-1]['d'][:10],'ha':'','sc':'','comp':'その他の試合（推定）','n':len(g),'ts':g[-1]['ts']})
    mlist.sort(key=lambda m:m['ts'])
    for m in mlist: m.pop('ts')
    for o in out: o.pop('mc', None)
    print('dropped photo', dropped_photo, 'dropped quote', dropped_quote)
    groups = {n: g for n, (g, _) in P.items()}
    json.dump({'posts': out, 'matches': mlist, 'groups': groups, 'clubs': sorted(CLUBS)}, open('/home/claude/work/data.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    return out, mlist

if __name__ == '__main__':
    out, ml = main()
    pc = collections.Counter(p for o in out for p in o['p'])
    print('posts', len(out), 'matches', len(ml))
    print(pc.most_common(120))
    print(collections.Counter(c for o in out for c in o['cat']))
    print(collections.Counter(c for o in out for c in o['src']).most_common(40))
    print(collections.Counter(c for o in out for c in o['c']).most_common(30))
    print('no person', sum(not o['p'] for o in out), 'no cat', sum(not o['cat'] for o in out))
    import os; print(os.path.getsize('/home/claude/work/data.json'))
