#!/usr/bin/env python3
"""選手のプロキャリア通算（クラブ・シーズン・大会別の出場とゴール）を careerstats.json に書く。

出典は英語版 Wikipedia の各選手ページ「Career statistics > Club」の表
（Appearances and goals by club, season and competition）。文章は取り込まず、数字だけを使う。

  python3 tools/career_stats.py                 # profiles.json の全選手を取得して careerstats.json を更新
  python3 tools/career_stats.py --cache DIR     # DIR にあるページ（<名前>.txt）を使い、無ければ取得して置く
  python3 tools/career_stats.py --check         # 書き込まず、検算の結果だけ出す

検算：各行の大会別の数字の合計が「Total」列と合うこと、過去のクラブの「Total」行と行の合計が合うことを選手ごとに確かめる。
合わない選手は careerstats.json に入れない（サイトでは過去シーズン・通算を出さない）。
いまのクラブの合計と「Career total」の行は、ページ側の更新遅れで食い違うことがあるので注意だけ出す。
欧州大会の内訳（CL・EL・ECLなど）は表の脚注から読む。読めなかった行は内訳なしの「欧州大会」として持つ。

終わったシーズンの数字は変わらないので、シーズン終了後か、新加入の選手を profiles.json に足したときに回す。
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {'User-Agent': 'football-stats-reader/1.0 (occasional script; python-urllib)'}
RAW = 'https://en.wikipedia.org/w/index.php?'
# profiles.json の名前とページ名が違う選手
TITLE = {'Ben White': 'Ben White (footballer)'}
JST = timezone(timedelta(hours=9))

NUMW = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
        'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'a': 1, 'an': 1, 'no': 0}
# 欧州大会の分類（脚注の文から）
EURO = [('cl', r'UEFA Champions League|Champions League|European Cup'), ('el', r'UEFA Europa League|Europa League|UEFA Cup'),
        ('ecl', r'UEFA (?:Europa )?Conference League|Conference League'), ('usc', r'UEFA Super Cup'),
        ('yl', r'UEFA Youth League'), ('lib', r'Copa Libertadores'), ('sud', r'Copa Sudamericana')]


def fetch(title):
    u = RAW + urllib.parse.urlencode({'title': title.replace(' ', '_'), 'action': 'raw'})
    for k in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode('utf-8')
        except Exception as e:  # 混雑時は少し待ってやり直す
            err = e
            time.sleep(4 + 4 * k)
    raise err


def strip_tpl(s):
    """入れ子のテンプレートを内側から外す。nowrap/small などは中身を残す。"""
    for _ in range(20):
        m = re.search(r'\{\{([^{}]*)\}\}', s)
        if not m:
            break
        body = m.group(1)
        name = body.split('|')[0].strip().lower()
        if name in ('nowrap', 'small', 'nobr', 'abbr', 'sort', 'sortname'):
            keep = body.split('|')[1] if '|' in body else ''
        elif name in ('dash', 'snd', 'spnd', 'ndash', 'en dash'):
            keep = ' – '
        elif name in ('0',):
            keep = ''
        else:
            keep = ''
        s = s[:m.start()] + keep + s[m.end():]
    return s


def clean(text):
    """表の部分から、参照・リンク・テンプレートを外す。脚注（efn）は «n» の印に置き換えて別に返す。"""
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    text = re.sub(r'<ref[^>]*/>', '', text)
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.S)
    notes, named = [], {}

    def efn(m):
        body = m.group(1)
        parts = [p.strip() for p in re.split(r'\|(?![^\[]*\]\])', body)]
        nm = None
        txt = None
        for p in parts[1:]:
            mm = re.match(r'name\s*=\s*"?([^"]+?)"?$', p)
            if mm:
                nm = mm.group(1).strip()
            elif re.match(r'(group|reference)\s*=', p):
                continue
            else:
                txt = p if txt is None else txt + '|' + p
        if txt is not None:
            txt = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', txt)
            if nm:
                named[nm] = txt
        elif nm is not None:
            txt = ('@', nm)
        notes.append(txt)
        return '«%d»' % (len(notes) - 1)

    # efn の中に別のテンプレートが入ることがあるので、内側のテンプレートを先に外してから拾う
    for _ in range(5):
        text2 = re.sub(r'\{\{\s*(?:efn|Efn|notetag|NoteTag|refn|Refn)\s*((?:\|(?:[^{}]|\{\{[^{}]*\}\})*)?)\}\}',
                       lambda m: efn(re.match(r'(.*)', 'efn' + strip_tpl(m.group(1)), re.S)), text, flags=re.S)
        if text2 == text:
            break
        text = text2
    notes = [named.get(n[1], '') if isinstance(n, tuple) else n for n in notes]
    text = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', text)
    text = strip_tpl(text)
    text = re.sub(r"'{2,}", '', text)
    text = re.sub(r'<br\s*/?>', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text, notes


def club_table(txt):
    i = txt.find('areer statistics')
    if i < 0:
        return None
    sec = txt[i:]
    j = sec.find('===Club')
    if j < 0:
        j = sec.find('=== Club')
    if j >= 0:
        sec = sec[j:]
    a = sec.find('{|')
    b = sec.find('\n|}', a)
    if a < 0 or b < 0:
        return None
    up = re.search(r'\{\{\s*[Uu]pdated\s*\|([^}]*)\}\}', sec[:a])
    return sec[a:b], (up.group(1).strip() if up else '')


def grid(tbl):
    """wikitable を、rowspan/colspan を展開した2次元の表にする。各セルは (文字, 見出しか)。"""
    rows = re.split(r'\n\|-[^\n]*', tbl)
    out, carry = [], {}
    for r in rows:
        cells = []
        for line in r.split('\n'):
            if not line or line.startswith('{|') or line.startswith('|+') or line.startswith('|}'):
                continue
            if line[0] not in '|!':
                if cells:
                    cells[-1] = (cells[-1][0] + ' ' + line, cells[-1][1], cells[-1][2])
                continue
            hd = line[0] == '!'
            for c in re.split(r'\|\||!!', line[1:]):
                attr = ''
                if '|' in c:
                    a, rest = c.split('|', 1)
                    if re.search(r'(rowspan|colspan|style|align|scope|class|width)\s*=', a):
                        attr, c = a, rest
                cells.append((c.strip(), hd, attr))
        if not cells:
            continue
        row, k = [], 0
        ci = 0
        while ci < len(cells) or k in carry:
            if k in carry:
                v, n = carry[k]
                row.append(v)
                if n <= 1:
                    del carry[k]
                else:
                    carry[k] = (v, n - 1)
                k += 1
                continue
            c, hd, attr = cells[ci]
            ci += 1
            rs = re.search(r'rowspan\s*=\s*"?(\d+)', attr)
            cs = re.search(r'colspan\s*=\s*"?(\d+)', attr)
            rs = int(rs.group(1)) if rs else 1
            cs = int(cs.group(1)) if cs else 1
            for _ in range(cs):
                while k in carry:  # 途中に上からの結合セルが挟まる場合
                    v, n = carry[k]
                    row.append(v)
                    if n <= 1:
                        del carry[k]
                    else:
                        carry[k] = (v, n - 1)
                    k += 1
                row.append((c, hd))
                if rs > 1:
                    carry[k] = ((c, hd), rs - 1)
                k += 1
        out.append(row)
    return out


def num(s):
    s = re.sub(r'«\d+»', '', s).strip()
    s = s.replace(',', '')
    if s in ('', '—', '–', '-', '−'):
        return 0
    m = re.match(r'^(\d+)', s)
    return int(m.group(1)) if m else None


def kind(h):
    h = h.lower()
    if 'league cup' in h or 'efl cup' in h or 'coupe de la ligue' in h or 'taça da liga' in h or 'taca da liga' in h:
        return 'lc'
    if h.startswith('league') or h in ('liga', 'division'):
        return 'lg'
    if 'europe' in h or 'continental' in h or 'uefa' in h or 'international' in h:
        return 'eu'
    if 'total' in h:
        return 'tot'
    if 'other' in h:
        return 'ot'
    if 'cup' in h or 'copa' in h or 'coupe' in h or 'pokal' in h or 'coppa' in h or 'taça' in h or 'beker' in h or 'cupen' in h or 'state league' in h:
        return 'nc' if 'state league' not in h else 'ot'
    return None


def euro_split(a, g, texts):
    """欧州大会のセル（出場 a・ゴール g）を脚注から大会別に分ける。分けられなければ None。"""
    texts = [t for t in texts if t]
    if not a and not g:
        return {}
    if not texts:
        return None
    t = ' '.join(texts)
    found = []
    for key, rx in EURO:
        if re.search(rx, t):
            found.append(key)
    # 「Conference League」は「Europa League」の一部と重なって数えないようにする
    if 'ecl' in found and 'el' in found and not re.search(r'UEFA Europa League(?! Conference)|Europa League(?! Conference)|UEFA Cup', re.sub(r'UEFA Europa Conference League', '', t)):
        found.remove('el')
    if len(found) == 1:
        return {found[0]: [a, g]}
    if not found:
        return None
    res = {}
    seg = re.findall(r'(\w+) appearances?(?:\s*(?:and|,)\s*(\w+) goals?)?\s+in (?:the )?((?:UEFA |European )[A-Za-z ]+?(?:League|Cup))', t, flags=re.I)
    for n, gg, comp in seg:
        key = next((k for k, rx in EURO if k != 'el' and re.fullmatch(rx, comp)), None) or next((k for k, rx in EURO if re.fullmatch(rx, comp)), None)
        n1 = NUMW.get(n.lower(), int(n) if n.isdigit() else None)
        g1 = 0 if not gg else NUMW.get(gg.lower(), int(gg) if gg.isdigit() else None)
        if key is None or n1 is None or g1 is None:
            return None
        res[key] = [res.get(key, [0, 0])[0] + n1, res.get(key, [0, 0])[1] + g1]
    if res and sum(v[0] for v in res.values()) == a and sum(v[1] for v in res.values()) == g:
        return res
    return None


def parse(txt):
    """→ (rows, asof, problems)。rows＝[{y, club, loan, div, lg, nc, lc, eu, ot, tot, eus}]（各値は [出場, ゴール]）"""
    ct = club_table(txt)
    if not ct:
        return None, '', ['Club の表が見つからない']
    raw, asof = ct
    text, notes = clean(raw.replace('|||', '||'))
    G = grid(text)
    note_of = lambda s: [notes[int(k)] for k in re.findall(r'«(\d+)»', s)]
    plain = lambda s: re.sub(r'«\d+»', '', s).strip()
    # 見出し2行
    h1, h2 = G[0], G[1]
    n = max(len(h1), len(h2))
    cols = []
    for k in range(n):
        a = plain(h1[k][0]) if k < len(h1) else ''
        b = plain(h2[k][0]) if k < len(h2) else ''
        cols.append((a, b))
    idx = {}
    for k, (a, b) in enumerate(cols):
        kd = kind(a)
        if kd is None:
            continue
        bl = b.lower()
        if kd == 'lg' and bl.startswith('div'):
            idx['div'] = k
        elif bl.startswith('app'):
            idx.setdefault((kd, 'a'), []).append(k)
        elif bl.startswith('goal'):
            idx.setdefault((kd, 'g'), []).append(k)
    prob = []
    if ('tot', 'a') not in idx or ('lg', 'a') not in idx:
        return None, asof, ['表の見出しが読めない: %r' % cols]
    unknown = [a for a, b in cols[2:] if kind(a) is None]
    if unknown:
        prob.append('分類できない列: %r' % sorted(set(unknown)))
    rows, raws, totals, career = [], [], {}, None
    for r in G[2:]:
        if len(r) < n:
            r = r + [('', False)] * (n - len(r))
        c0, c1 = plain(r[0][0]), plain(r[1][0])
        val = {}
        bad = False
        for kd in ('lg', 'nc', 'lc', 'eu', 'ot', 'tot'):
            a = g = 0
            for k in idx.get((kd, 'a'), []):
                v = num(r[k][0]); bad |= v is None; a += v or 0
            for k in idx.get((kd, 'g'), []):
                v = num(r[k][0]); bad |= v is None; g += v or 0
            val[kd] = [a, g]
        if re.match(r'career total', c0, re.I):
            career = val
            continue
        if re.search(r'\btotal\b', c1, re.I) or re.match(r'total', c0, re.I):
            totals[c0 if not re.match(r'total', c0, re.I) else '?'] = val
            continue
        m = re.match(r'^(\d{4})(?:[–\-/](\d{2,4}))?', c1)
        if not m:
            prob.append('シーズンが読めない行: %r %r' % (c0, c1))
            continue
        if bad:
            prob.append('数字が読めない行: %s %s' % (c0, c1))
        loan = bool(re.search(r'\(loan\)', c0, re.I))
        club = re.sub(r'\s*\(loan\)', '', c0, flags=re.I).strip()
        eu_notes = []
        for k in idx.get(('eu', 'a'), []) + idx.get(('eu', 'g'), []):
            eu_notes += note_of(r[k][0])
        eus = euro_split(val['eu'][0], val['eu'][1], eu_notes)
        if eus is None:
            prob.append('欧州大会の内訳が読めない: %s %s %r' % (club, c1, eu_notes))
        raws.append(c0)
        row = {'y': int(m.group(1)), 's': c1.split(' ')[0], 'club': club, 'div': plain(r[idx['div']][0]) if 'div' in idx else ''}
        if loan:
            row['loan'] = 1
        for kd in ('lg', 'nc', 'lc', 'eu', 'ot', 'tot'):
            row[kd] = val[kd]
        if eus:
            row['eus'] = eus
        rows.append(row)
    # 検算
    ok = True
    for r in rows:
        s = [sum(r[k][i] for k in ('lg', 'nc', 'lc', 'eu', 'ot')) for i in (0, 1)]
        if s != r['tot']:
            prob.append('行の合計が合わない: %s %s %r≠%r' % (r['club'], r['s'], s, r['tot'])); ok = False
    # クラブごとの「Total」の行と照らす。いまのクラブ（最後の行のクラブ）は今季分の更新途中で食い違うことがあり、
    # 今季分はサイトの試合データを使うので、注意だけ出す。過去のクラブで合わなければ取り込まない。
    cur = raws[-1] if raws else ''
    base = lambda c: re.sub(r'\s*\(loan\)', '', c, flags=re.I).strip()
    for club, tv in totals.items():
        # 合計行は、ローン期間を含めて書くページと、含めずに書くページがある。どちらかと合えばよい
        sets = [[r for r, c in zip(rows, raws) if c == club], [r for r, c in zip(rows, raws) if base(c) == base(club)]]
        if not sets[1]:
            continue
        diff = None
        for mine in sets:
            d = [(kd, [sum(r[kd][i] for r in mine) for i in (0, 1)], tv[kd]) for kd in ('lg', 'nc', 'lc', 'eu', 'ot', 'tot')]
            d = [x for x in d if x[1] != x[2]]
            if not d:
                diff = None
                break
            diff = diff or d
        for kd, s, t in diff or []:
            prob.append('%sクラブ合計が合わない(%s %s): 行の合計%r≠表%r' % ('（注意）' if base(club) == base(cur) else '', club, kd, s, t))
            if base(club) != base(cur):
                ok = False
    # 「Career total」の行は更新が遅れていることが多いので、注意だけ
    if career is not None:
        for kd in ('lg', 'nc', 'lc', 'eu', 'ot', 'tot'):
            s = [sum(r[kd][i] for r in rows) for i in (0, 1)]
            if s != career[kd]:
                prob.append('（注意）Career total の行と合わない(%s): 行の合計%r≠表%r' % (kd, s, career[kd]))
    return (rows if ok else None), asof, prob


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    P = json.load(open(os.path.join(ROOT, 'profiles.json'), encoding='utf-8'))['players']
    out, bad = {}, 0
    for e in P:
        title = TITLE.get(e, e)
        fn = a.cache and os.path.join(a.cache, ''.join(c if c.isalnum() else '_' for c in e) + '.txt')
        if fn and os.path.exists(fn):
            txt = open(fn, encoding='utf-8').read()
        else:
            txt = fetch(title)
            time.sleep(1)
            if fn:
                open(fn, 'w', encoding='utf-8').write(txt)
        rows, asof, prob = parse(txt)
        hard = rows is None
        print(('NG ' if hard else 'ok ') + e + ('  （%d行・%s）' % (len(rows), asof) if rows else ''))
        for p in prob:
            print('     - ' + p)
        if hard:
            bad += 1
            continue
        out[e] = {'asof': asof, 'u': 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_')), 'rows': rows}
    if a.check:
        return 1 if bad else 0
    J = {'src': 'Wikipedia (en) “Career statistics”, CC BY-SA 4.0', 't': datetime.now(JST).strftime('%Y-%m-%dT%H:%M+09:00'), 'players': out}
    with open(os.path.join(ROOT, 'careerstats.json'), 'w', encoding='utf-8') as f:
        json.dump(J, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    print('careerstats.json: %d人（読めなかった選手 %d人）' % (len(out), bad))
    return 0


if __name__ == '__main__':
    sys.exit(main())
