#!/usr/bin/env python3
"""チャンピオンズリーグの全試合（結果・日程）と、選手・チームのスタッツランキングを cl.json に書く。

  python3 tools/cl_stats.py          # 取得して cl.json を更新（中身が変わったときだけ書く）
  python3 tools/cl_stats.py --dry    # 書かずに要約だけ表示
  python3 tools/cl_stats.py --all    # 保存済みの日も含めて全部取り直す

- 取得元は ESPN の公開データ（キー不要・非公式。スタメン取り込みの tools/lineup.py と同じ取得元）。
  scoreboard（日付ごと）が試合のスコア・ポゼッション・シュート・CK・ファウル・得点/カードの記録、
  statistics が得点・アシストの上位50人。
- scoreboard は1日ずつしか取れないので、終わった日は tools/cl_days.json に保存して取り直さない
  （直近3日と今後14日だけ毎回確認。それ以外の火・水・木は一度だけ取る）。
- スコアは試合終了のものだけ入れる。試合中のスコアは入れない。
- クラブ名は season.json の cl.table と同じ日本語表記（下の CLUBS）。選手の日本語表記は tools/cl_names.json
  （キーは ESPN の表示名）。未登録は英語表記のまま出る（このスクリプトが未登録の名前を表示する）。
- .github/workflows/league.yml が30分ごとに実行する。cl.json は手で編集しない。
"""
import json, os, sys, urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'cl.json')
CACHE = os.path.join(ROOT, 'tools', 'cl_days.json')   # 取得済みの日ごとの試合（サイトは読まない。取り直しを減らすための保存）
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/'
JST = timezone(timedelta(hours=9))
START = date(2026, 9, 8)       # リーグフェーズ初日。シーズンが替わったら直す
TOP = 30                       # ランキングに入れる人数
CLUBS = {'Real Madrid': 'レアル・マドリード', 'Paris Saint-Germain': 'パリ・サンジェルマン', 'Como': 'コモ', 'Barcelona': 'バルセロナ',
         'Liverpool': 'リヴァプール', 'Real Betis': 'レアル・ベティス', 'Arsenal': 'アーセナル', 'Manchester City': 'マンチェスター・シティ',
         'Sporting CP': 'スポルティングCP', 'Borussia Dortmund': 'ドルトムント', 'Aston Villa': 'アストン・ヴィラ', 'Internazionale': 'インテル',
         'Club Brugge': 'クラブ・ブルッヘ', 'Galatasaray': 'ガラタサライ', 'Bayern Munich': 'バイエルン', 'Fenerbahce': 'フェネルバフチェ',
         'VfB Stuttgart': 'シュトゥットガルト', 'Atlético Madrid': 'アトレティコ・マドリード', 'Manchester United': 'マンチェスター・ユナイテッド',
         'Bodo/Glimt': 'ボデ/グリムト', 'LASK Linz': 'LASKリンツ', 'FC Porto': 'ポルト', 'RB Leipzig': 'RBライプツィヒ', 'Villarreal': 'ビジャレアル',
         'AS Roma': 'ローマ', 'Shakhtar Donetsk': 'シャフタール・ドネツク', 'Viking FK': 'ヴァイキング', 'Napoli': 'ナポリ', 'Lille': 'リール',
         'PSV Eindhoven': 'PSV', 'AEK Athens': 'AEKアテネ', 'Feyenoord Rotterdam': 'フェイエノールト', 'Sabah FK': 'サバフ', 'Lens': 'ランス',
         'Slavia Prague': 'スラヴィア・プラハ', 'Slovan Bratislava': 'スロヴァン・ブラチスラヴァ'}
# season.json の日程（results / upcoming の o）で使っている別表記。アーセナル戦のリンクとネタバレ防止の判定に使う
ALIAS = {'レアル・ベティス': ['ベティス'], 'サバフ': ['サバFK'], 'パリ・サンジェルマン': ['PSG'], 'スポルティングCP': ['スポルティング'],
         'バイエルン': ['バイエルン・ミュンヘン'], 'ボデ/グリムト': ['ボデ／グリムト', 'ボデ・グリムト']}
ROUNDS = {'league-phase': None, 'knockout-round-playoffs': ['プレーオフ', 'Play-offs'], 'rd-of-16': ['ラウンド16', 'Round of 16'],
          'round-of-16': ['ラウンド16', 'Round of 16'], 'quarterfinals': ['準々決勝', 'Quarter-finals'],
          'semifinals': ['準決勝', 'Semi-finals'], 'final': ['決勝', 'Final']}
TSTAT = ['possessionPct', 'totalShots', 'shotsOnTarget', 'wonCorners', 'foulsCommitted']


def get(path):
    req = urllib.request.Request(ESPN + path, headers={'User-Agent': 'Mozilla/5.0 (arsenal-archive cl)', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def club(name):
    return CLUBS.get(name, name)


def day_rows(d):
    """その日の試合を小さな行にする。行＝{k:キックオフ(JST), d:現地日, r:ラウンド, h, a, fin, hs, as, st:{h:[..],a:[..]}, ev:[[種類, 選手, クラブ]]}"""
    rows = []
    for e in get('scoreboard?dates=' + d.strftime('%Y%m%d')).get('events', []):
        c = e['competitions'][0]
        slug = (e.get('season') or {}).get('slug') or ''
        if slug not in ROUNDS:                       # 予選などは載せない
            continue
        ko = datetime.strptime(e['date'], '%Y-%m-%dT%H:%MZ').replace(tzinfo=timezone.utc)
        side = {x['homeAway']: x for x in c['competitors']}
        if 'home' not in side or 'away' not in side:
            continue
        ids = {x['team']['id']: x['team']['displayName'] for x in c['competitors']}
        state = e['status']['type']
        row = {'k': ko.astimezone(JST).strftime('%Y-%m-%dT%H:%M'), 'd': ko.strftime('%Y-%m-%d'), 'r': slug,
               'h': side['home']['team']['displayName'], 'a': side['away']['team']['displayName'],
               'fin': bool(state.get('completed'))}
        if row['fin']:
            row['hs'], row['as'] = int(side['home']['score']), int(side['away']['score'])
            row['st'] = {}
            for ha in ('home', 'away'):
                st = {s['name']: s['displayValue'] for s in side[ha].get('statistics', [])}
                row['st'][ha[0]] = [float(st.get(k) or 0) for k in TSTAT]
            row['ev'] = []
            for t in c.get('details', []):
                kind = 'y' if t.get('yellowCard') else 'r' if t.get('redCard') else ''
                who = (t.get('athletesInvolved') or [{}])[0].get('displayName')
                if kind and who:
                    row['ev'].append([kind, who, ids.get((t.get('team') or {}).get('id'), '')])
        rows.append(row)
    return rows


def collect(old, everything):
    """days＝{YYYYMMDD: 行のリスト}。終わった日は保存したものを使い、直近と今後だけ取り直す。"""
    days = {} if everything else dict(old)
    today = datetime.now(timezone.utc).date()
    want, d = set(), START
    while d <= today + timedelta(days=75):             # 先の日程は一度だけ取り、試合の14日前から毎回確認する
        recent = today - timedelta(days=3) <= d <= today + timedelta(days=14)
        key = d.strftime('%Y%m%d')
        if recent or (key not in days and d.weekday() in (1, 2, 3)):   # 過去の分は火・水・木だけ（決勝など他の曜日は直近の確認で拾う）
            want.add(d)
        d += timedelta(days=1)
    for d in sorted(want):
        key = d.strftime('%Y%m%d')
        try:
            days[key] = day_rows(d)
        except Exception as ex:                      # 1日取れなくても、保存済みの分で続ける
            print('取得できなかった日:', key, ex)
            days.setdefault(key, [])
    # まだ終わっていない過去の試合が残っている日は、次回も取り直す
    for key in list(days):
        dd = datetime.strptime(key, '%Y%m%d').date()
        if dd < today - timedelta(days=3) and any(not r['fin'] for r in days[key]):
            try:
                days[key] = day_rows(dd)
            except Exception:
                pass
    return {k: days[k] for k in sorted(days)}


def build(days, stats, names):
    rows = [r for k in sorted(days) for r in days[k]]
    order = []                                         # クラブは cl.json の clubs の番号で指す
    for r in rows:
        for n in (r['h'], r['a']):
            if n not in order:
                order.append(n)
    idx = {n: i for i, n in enumerate(order)}
    unknown = sorted(n for n in order if n not in CLUBS)
    missing = []

    def nm(en):
        ja = names.get(en)
        if not ja:
            missing.append(en)
        return ja

    # 試合：リーグフェーズは週ごとに第N節、決勝トーナメントはラウンド名
    weeks, wk, md = {}, [], {}
    for r in sorted(rows, key=lambda r: r['k']):
        if ROUNDS.get(r['r']) is None:
            y, w, _ = datetime.strptime(r['d'], '%Y-%m-%d').isocalendar()
            if (y, w) not in md:
                md[(y, w)] = len(md) + 1
            key, lab = 'md%d' % md[(y, w)], ['第%d節' % md[(y, w)], 'MD %d' % md[(y, w)]]
        else:
            key, lab = r['r'], ROUNDS[r['r']]
        if key not in weeks:
            weeks[key] = []
            wk.append([key] + lab)
        row = [r['k'], idx[r['h']], idx[r['a']]]
        if r['fin']:
            row += [r['hs'], r['as'], r['d']]
        weeks[key].append(row)
    for w in weeks.values():
        w.sort(key=lambda r: (r[0], r[1]))
    cur = next((k for k, *_ in wk if any(len(r) < 4 for r in weeks[k])), wk[-1][0] if wk else '')

    # チーム別：[試合, 得点, 失点, 無失点, イエロー, レッド, ポゼッション合計, シュート, 枠内シュート, CK, ファウル]
    T = [[0] * 11 for _ in order]
    cards = {}
    for r in rows:
        if not r['fin']:
            continue
        for ha, me, gf, ga in (('h', r['h'], r['hs'], r['as']), ('a', r['a'], r['as'], r['hs'])):
            t = T[idx[me]]
            t[0] += 1; t[1] += gf; t[2] += ga; t[3] += 1 if ga == 0 else 0
            for i, v in enumerate(r['st'][ha]):
                t[6 + i] += v
        for kind, who, team in r['ev']:
            if team in idx:
                T[idx[team]][4 if kind == 'y' else 5] += 1
                c = cards.setdefault((who, team), [0, 0])
                c[0 if kind == 'y' else 1] += 1
    for t in T:
        t[6] = round(t[6], 1)
        t[7:] = [int(v) for v in t[7:]]

    def leaders(name):
        out = []
        for s in stats.get('stats', []):
            if s.get('name') != name:
                continue
            for l in s.get('leaders', []):
                a = l.get('athlete') or {}
                team = (a.get('team') or {}).get('displayName')
                if team in idx and l.get('value'):
                    out.append((a['displayName'], team, int(l['value'])))
        return out

    def top(items):
        items = sorted(items, key=lambda x: (-x[2], x[0]))
        if len(items) > TOP:                             # 同数で並ぶ選手は切らずに入れる（最大40人）
            cut = items[TOP - 1][2]
            items = ([x for x in items if x[2] > cut] + [x for x in items if x[2] == cut])[:40]
        out = []
        for en, team, v in items:
            p = {'e': en, 'c': idx[team], 'v': v}
            ja = nm(en)
            if ja:
                p['n'] = ja
            out.append(p)
        return out

    players = {'g': top(leaders('goalsLeaders')), 'a': top(leaders('assistsLeaders')),
               'yc': top([(w, t, c[0]) for (w, t), c in cards.items() if c[0]]),
               'rc': top([(w, t, c[1]) for (w, t), c in cards.items() if c[1]])}
    data = {'note': 'tools/cl_stats.py が自動で作るファイル。手で編集しない', 'season': '26/27', 'mw': cur, 'wk': wk,
            'clubs': [club(n) for n in order], 'alias': ALIAS, 'weeks': weeks, 'players': players, 'teams': T}
    return data, sorted(set(missing)), unknown


def main():
    dry, everything = '--dry' in sys.argv, '--all' in sys.argv
    names = json.load(open(os.path.join(ROOT, 'tools', 'cl_names.json'), encoding='utf-8'))
    try:
        old = json.load(open(OUT, encoding='utf-8'))
    except Exception:
        old = {}
    try:
        cache = json.load(open(CACHE, encoding='utf-8'))
    except Exception:
        cache = {}
    days = collect(cache, everything)
    data, missing, unknown = build(days, get('statistics'), names)
    n = sum(len(w) for w in data['weeks'].values())
    done = sum(1 for w in data['weeks'].values() for r in w if len(r) > 3)
    if len(data['clubs']) < 30 or n < 80 or not data['players']['g']:   # おかしなデータで上書きしない
        sys.exit('ESPN のデータが想定と違う（クラブ %d・試合 %d）。cl.json は変えない' % (len(data['clubs']), n))
    if unknown:
        print('CLUBS に無いクラブ（英語表記のまま出る）:', ', '.join(unknown))
    if missing:
        print('日本語表記が未登録の選手（tools/cl_names.json に足す）:\n  ' + '\n  '.join(missing))
    same = {k: v for k, v in old.items() if k != 'asof'} == data
    print('%d クラブ・%d試合（うち終了 %d）・得点1位 %s %d' % (len(data['clubs']), n, done, data['players']['g'][0]['e'], data['players']['g'][0]['v']),
          '・変更なし' if same else '')
    if dry:
        return
    if days != cache:
        with open(CACHE, 'w', encoding='utf-8') as f:
            json.dump(days, f, ensure_ascii=False, separators=(',', ':'))
            f.write('\n')
    if same:
        return
    data['asof'] = datetime.now(JST).strftime('%Y-%m-%dT%H:%M+09:00')
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')


if __name__ == '__main__':
    main()
