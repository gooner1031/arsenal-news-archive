#!/usr/bin/env python3
"""ローン移籍中・過去の所属選手・OB/レジェンドの「現在の所属」を nowclub.json に書き出す。

出典は英語版 Wikipedia の選手ページ冒頭の情報欄（Infobox football biography）。キー不要。
  current_club … 今のクラブ（「X (on loan from Y)」ならローン中）
  clubsN / yearsN … 所属歴（最後の行が「2026–」のように終わっていなければ、今は無所属か引退）
  manager_clubsN / manager_yearsN … 監督・コーチ歴（最後の行が続いていれば今の役職）
対象は meta.json の people のうち g が TARGET の人。

間違いを防ぐための確認：
  - 所属歴・ユース歴・監督歴のどこにも Arsenal が無いページは「同名の別人」とみなして載せない
    （ページ名が違う選手は tools/now_club.json の title に書く）。
  - 取れなかった選手は、前回の値をそのまま残す（消さない）。
手で直したいときは tools/now_club.json の fix に選手ごとに書く（Wikipedia の値より優先）。
  例：{"Tommy Setford": {"until": "2026/27シーズン終了まで", "untilEn": "Until end of 2026/27"}}
      {"Thierry Henry": {"role": "解説者", "roleEn": "Pundit"}}
クラブの日本語名は tools/now_club.json の ja（英語名 → 日本語名）。無いクラブは英語のまま出て、実行時に一覧が出る。

  python3 tools/now_club.py            # 全員を確認して nowclub.json を更新
  python3 tools/now_club.py --only "Ethan Nwaneri,Thierry Henry"   # 一部だけ（書き込みあり）
  python3 tools/now_club.py --dry      # 書き込まずに結果だけ表示
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'nowclub.json')
CONF = os.path.join(ROOT, 'tools', 'now_club.json')
UA = {'User-Agent': 'football-stats-reader/1.0 (occasional script; python-urllib)'}
RAW = 'https://en.wikipedia.org/w/index.php?'
JST = timezone(timedelta(hours=9))
TARGET = ('ローン移籍中', '過去の所属選手', 'OB・レジェンド')
MON = {m: i + 1 for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                                       'September', 'October', 'November', 'December'])}


def fetch(title, hop=0):
    """ページ冒頭の原文。転送ページ（#REDIRECT）は転送先を読む。無いページは None。"""
    txt = fetch1(title)
    m = re.match(r'\s*#REDIRECT\s*\[\[([^\]|#]+)', txt or '', re.I)
    if m and hop < 2:
        time.sleep(1.5)
        return fetch(m.group(1).strip(), hop + 1)
    return txt


def fetch1(title):
    u = RAW + urllib.parse.urlencode({'title': title.replace(' ', '_'), 'action': 'raw', 'section': '0'})
    err = None
    for k in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = e
        except Exception as e:  # 混雑時は少し待ってやり直す
            err = e
        time.sleep(5 + 6 * k)
    raise err


def plain(s):
    """情報欄の値から、参照・コメント・テンプレート・リンクの記号を外して表示名だけにする。"""
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    s = re.sub(r'<ref[^>]*/>', '', s)
    s = re.sub(r'<ref.*?</ref>', '', s, flags=re.S)
    s = re.sub(r'<br\s*/?>', ' ', s)
    for _ in range(5):
        s = re.sub(r'\{\{(?:nowrap|small|nobr)\|([^{}]*)\}\}', r'\1', s)
        s = re.sub(r'\{\{[^{}]*\}\}', '', s)
    s = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', s)
    s = re.sub(r"<[^>]+>|'''?", '', s)
    return re.sub(r'\s+', ' ', s).strip()


def infobox(txt):
    """{項目名: 値}。項目名は current_club / currentclub のどちらの書き方でも同じ名前にそろえる。"""
    m = re.search(r'\{\{\s*Infobox football biography', txt, re.I)
    if not m:
        return None
    # 入れ子（[[ ]] {{ }}）の外にある | で区切る。1行に複数の項目が並ぶ書き方のページもあるため
    f, depth, cur, parts, body, i = {}, 0, [], [], txt[m.end():], 0
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    while i < len(body):
        two = body[i:i + 2]
        if two in ('{{', '[['):
            depth += 1; cur.append(two); i += 2; continue
        if two in ('}}', ']]'):
            if depth == 0:
                break
            depth -= 1; cur.append(two); i += 2; continue
        if body[i] == '|' and depth == 0:
            parts.append(''.join(cur)); cur = []
        else:
            cur.append(body[i])
        i += 1
    parts.append(''.join(cur))
    for part in parts:
        k, eq, v = part.partition('=')
        k = k.strip().lower().replace('_', '')
        if eq and re.fullmatch(r'[a-z]+\d*', k) and k not in f:
            f[k] = v.strip()
    return f


def rows(f, ck, yk):
    out = []
    for k in sorted((int(x[len(ck):]) for x in f if re.fullmatch(ck + r'\d+', x)), key=int):
        c, y = plain(f.get(ck + str(k), '')), plain(f.get(yk + str(k), ''))
        if c:
            out.append((c, y.replace('-', '–')))
    return out


def is_open(y):
    return bool(re.search(r'\d{4}\s*–\s*$', y))


def first_year(y):
    m = re.search(r'\d{4}', y)
    return m.group(0) if m else ''


def club_name(c):
    return re.sub(r'^→\s*', '', re.sub(r'\s*\((?:loan|on loan)\)\s*$', '', c)).strip()


def parse(txt):
    """ページ冒頭 → 1人ぶんの記録。別人のページ・情報欄なしは None。"""
    f = infobox(txt)
    if not f:
        return None
    cl, yo, mg = rows(f, 'clubs', 'years'), rows(f, 'youthclubs', 'youthyears'), rows(f, 'managerclubs', 'manageryears')
    if not any(re.search(r'\bArsenal\b', c) for c, _ in cl + yo + mg):
        return None
    r = {}
    cur = plain(f.get('currentclub', ''))
    m = re.match(r'(.+?)\s*\(\s*on loan from\s+(.+?)\s*\)\s*$', cur, re.I)
    opens = [(c, y) for c, y in cl if is_open(y)]
    if m:
        r.update(st='loan', c=m.group(1).strip(), parent=m.group(2).strip())
    elif cur and not re.search(r'free agent|unattached|retired', cur, re.I):
        # 監督・コーチをしている人は current_club に「X (manager)」と入る
        role = re.match(r'(.+?)\s*\(([^)]*(?:manager|coach|director)[^)]*)\)\s*$', cur, re.I)
        if role:
            r.update(st='staff', c=role.group(1).strip(), role=role.group(2).strip())
        else:
            r.update(st='club', c=cur)
    elif opens:
        c, y = opens[-1]
        if c.startswith('→'):
            par = [x for x in opens if not x[0].startswith('→')]
            r.update(st='loan', c=club_name(c), parent=par[-1][0] if par else '')
        else:
            r.update(st='club', c=c)
    else:
        lead = plain(txt[txt.find("'''"):][:1500]) if "'''" in txt else ''
        r['st'] = 'ret' if (re.search(r'\b(former|retired)\b', lead, re.I) or not cl) else 'free'
    if r['st'] in ('club', 'loan'):
        mine = [y for c, y in cl if club_name(c) == r['c'] and is_open(y)] or [y for c, y in cl if club_name(c) == r['c']]
        if mine:
            r['y'] = first_year(mine[-1])
    if r['st'] in ('ret', 'free'):
        real = [(c, y) for c, y in cl if not c.startswith('→')] or cl
        if real:
            r['last'] = [club_name(real[-1][0]), real[-1][1]]
        mo = [(c, y) for c, y in mg if is_open(y)]
        if mo and r['st'] == 'ret':
            r['mgr'] = [mo[-1][0], first_year(mo[-1][1])]
    if r['st'] == 'staff':
        mo = [y for c, y in mg if c == r['c']]
        if mo:
            r['y'] = first_year(mo[-1])
    # アーセナル在籍（トップチーム。ローンでの在籍も含む）
    ars = [y for c, y in cl if re.fullmatch(r'Arsenal', club_name(c)) and y]
    if ars:
        r['ars'] = ', '.join(ars)
    else:  # 選手としては在籍せず、監督として在籍（ベンゲル）。最後の所属も監督歴から
        am = [y for c, y in mg if c == 'Arsenal' and y]
        if am:
            r['ars'], r['arsM'] = ', '.join(am), 1
            if r['st'] == 'ret' and mg and 'mgr' not in r:
                r['last'] = [mg[-1][0], mg[-1][1]]
    # 過去のローン先（今ローン中の選手だけ：今の所属元から出たローン）
    if r['st'] == 'loan':
        prev = [[club_name(c), y] for c, y in cl if c.startswith('→') and not is_open(y)]
        if prev:
            r['prev'] = prev[-3:]
    m = re.search(r'(\d{1,2}) ([A-Z][a-z]+) (\d{4})', plain(f.get('clubupdate', '')))
    if m and m.group(2) in MON:
        r['upd'] = '%s-%02d-%02d' % (m.group(3), MON[m.group(2)], int(m.group(1)))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    conf = json.load(open(CONF, encoding='utf-8'))
    title, ja, fix, skip = conf.get('title', {}), conf.get('ja', {}), conf.get('fix', {}), set(conf.get('skip', []))
    people = [p for p in json.load(open(os.path.join(ROOT, 'meta.json'), encoding='utf-8'))['people'] if p.get('g') in TARGET]
    only = [x.strip() for x in a.only.split(',') if x.strip()]
    old, prev_asof = {}, ''
    if os.path.exists(OUT):
        j = json.load(open(OUT, encoding='utf-8'))
        old, prev_asof = j.get('players', {}), j.get('asof', '')
    out, bad = {}, []
    for p in people:
        e = p['e']
        if e in skip:
            continue
        if only and e not in only:
            if e in old:
                out[e] = old[e]
            continue
        t = title.get(e, e)
        try:
            txt = fetch(t)
            r = parse(txt) if txt else None
        except Exception as ex:
            txt, r = None, None
            print('取得失敗 %s: %s' % (e, ex), file=sys.stderr)
        if not r:
            bad.append(e)
            if e in old:
                out[e] = old[e]  # 取れなかったら前回の値を残す
            continue
        r['u'] = 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(t.replace(' ', '_'))
        out[e] = r
        time.sleep(1.5)
    # 手での上書きと日本語名
    miss = set()
    for e, r in out.items():
        for k in [k for k in r if k.endswith('J')]:
            del r[k]
        r.update(fix.get(e, {}))
        for k, v in (('c', r.get('c')), ('parent', r.get('parent')), ('last', (r.get('last') or [None])[0]), ('mgr', (r.get('mgr') or [None])[0])):
            if v and k + 'J' not in r:
                if v in ja:
                    r[k + 'J'] = ja[v]
                else:
                    miss.add(v)
        if r.get('prev'):
            r['prev'] = [[c, y, ja[c]] if c in ja else [c, y] for c, y, *_ in r['prev']]
            miss.update(c for c, *_ in r['prev'] if c not in ja)
    for e in sorted(out):
        r = out[e]
        print('%-28s %-5s %s' % (e, r['st'], ' / '.join(str(r.get(k)) for k in ('c', 'y', 'parent', 'last', 'mgr', 'role') if r.get(k))))
    if bad:
        print('\n取れなかった選手（ページ名を tools/now_club.json の title に足す）: ' + ', '.join(bad))
    if miss:
        print('\n日本語名が無いクラブ（tools/now_club.json の ja に足す）: ' + ', '.join(sorted(miss)))
    if a.dry:
        return
    # 中身が同じなら書かない。ただし画面の「確認」の日付が古くなりすぎないよう、7日たったら日付だけ更新する
    today = datetime.now(JST).date()
    try:
        age = (today - datetime.strptime(prev_asof, '%Y-%m-%d').date()).days
    except ValueError:
        age = 99
    if old == out and (age < 7 or bad):
        print('nowclub.json: 変更なし')
        return
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump({'note': 'tools/now_club.py が自動で作るファイル。手で直すときは tools/now_club.json の fix に書く',
                   'src': 'Wikipedia (en) infobox, CC BY-SA 4.0', 'asof': today.strftime('%Y-%m-%d'),
                   'players': dict(sorted(out.items()))}, fp, ensure_ascii=False, indent=0)
        fp.write('\n')
    print('nowclub.json: 更新（%d人）' % len(out))


if __name__ == '__main__':
    main()
