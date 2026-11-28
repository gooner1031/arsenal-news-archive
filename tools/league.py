#!/usr/bin/env python3
"""プレミアリーグ全クラブの試合（全節の結果・日程）と、選手・クラブのスタッツランキングを league.json に書く。

  python3 tools/league.py          # 取得して league.json を更新（中身が変わったときだけ書く）
  python3 tools/league.py --dry    # 書かずに要約だけ表示
  python3 tools/league.py --all    # ESPN の保存済みの日も含めて全部取り直す

- 取得元はプレミアリーグ公式ファンタジー（FPL）の公開データ（キー不要）。
  fixtures/ が全380試合のスコア・キックオフ・カード、bootstrap-static/ が全選手の得点・アシスト・xG・xA・守備（タックルなど）・無失点・セーブ・カード・出場時間。
- スコアは試合終了（finished / finished_provisional）のものだけ入れる。試合中のスコアは入れない。
- クラブ名は season.json の順位表と同じ日本語表記（下の CLUBS）。昇格・降格でクラブが替わったら CLUBS を直す。
- 選手の日本語表記は tools/league_names.json。未登録は英語表記のまま出る（このスクリプトが未登録の名前を表示する）。
- ポゼッション・シュート・枠内シュート・CK・ファウルは FPL に無いので、ESPN の公開データ（キー不要・非公式）の scoreboard から足す。
  ESPN は1日ずつしか取れないので、取得済みの日は tools/pl_days.json に保存して取り直さない（直近3日だけ毎回確認）。
  ESPN が取れないときは、この5項目だけ前回の値のままにする（他の項目は更新する）。
- .github/workflows/league.yml が毎日の更新（season.json / matchstats.json の push）のたびに実行する。league.json は手で編集しない。
"""
import json, os, sys, urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'league.json')
FPL = 'https://fantasy.premierleague.com/api/'
CACHE = os.path.join(ROOT, 'tools', 'pl_days.json')   # ESPN から取得済みの日ごとの試合スタッツ（サイトは読まない）
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates='
START = date(2026, 8, 14)      # ESPN を確認し始める日（開幕の少し前）。シーズンが替わったら直す
TSTAT = ['possessionPct', 'totalShots', 'shotsOnTarget', 'wonCorners', 'foulsCommitted']
# ESPN のクラブ名 → 上の CLUBS の日本語表記
ESPN_CLUBS = {'Arsenal': 'アーセナル', 'Aston Villa': 'アストン・ヴィラ', 'AFC Bournemouth': 'ボーンマス', 'Brentford': 'ブレントフォード',
              'Brighton & Hove Albion': 'ブライトン', 'Chelsea': 'チェルシー', 'Coventry City': 'コヴェントリー', 'Crystal Palace': 'クリスタル・パレス',
              'Everton': 'エヴァートン', 'Fulham': 'フラム', 'Hull City': 'ハル・シティ', 'Ipswich Town': 'イプスウィッチ', 'Leeds United': 'リーズ',
              'Liverpool': 'リヴァプール', 'Manchester City': 'マンチェスター・シティ', 'Manchester United': 'マンチェスター・ユナイテッド',
              'Newcastle United': 'ニューカッスル', 'Nottingham Forest': 'ノッティンガム・フォレスト', 'Tottenham Hotspur': 'トッテナム',
              'Sunderland': 'サンダーランド', 'West Ham United': 'ウェストハム', 'Wolverhampton Wanderers': 'ウルヴス', 'Burnley': 'バーンリー',
              'Leicester City': 'レスター', 'Southampton': 'サウサンプトン', 'Sheffield United': 'シェフィールド・ユナイテッド',
              'West Bromwich Albion': 'ウェスト・ブロム', 'Middlesbrough': 'ミドルズブラ', 'Norwich City': 'ノリッジ', 'Watford': 'ワトフォード',
              'Luton Town': 'ルートン'}
JST = timezone(timedelta(hours=9))
TOP = 20   # ランキングに入れる人数（画面は10人まで出し、「もっと見る」で全部）
CLUBS = {'ARS': 'アーセナル', 'AVL': 'アストン・ヴィラ', 'BOU': 'ボーンマス', 'BRE': 'ブレントフォード', 'BHA': 'ブライトン',
         'CHE': 'チェルシー', 'COV': 'コヴェントリー', 'CRY': 'クリスタル・パレス', 'EVE': 'エヴァートン', 'FUL': 'フラム',
         'HUL': 'ハル・シティ', 'IPS': 'イプスウィッチ', 'LEE': 'リーズ', 'LIV': 'リヴァプール', 'MCI': 'マンチェスター・シティ',
         'MUN': 'マンチェスター・ユナイテッド', 'NEW': 'ニューカッスル', 'NFO': 'ノッティンガム・フォレスト', 'TOT': 'トッテナム',
         'SUN': 'サンダーランド', 'WHU': 'ウェストハム', 'WOL': 'ウルヴス', 'BUR': 'バーンリー', 'LEI': 'レスター',
         'SOU': 'サウサンプトン', 'SHU': 'シェフィールド・ユナイテッド', 'WBA': 'ウェスト・ブロム', 'MID': 'ミドルズブラ',
         'NOR': 'ノリッジ', 'WAT': 'ワトフォード', 'LUT': 'ルートン'}


def get(path):
    req = urllib.request.Request(FPL + path, headers={'User-Agent': 'Mozilla/5.0 (arsenal-archive league)', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def espn_day(d):
    """その日の終わった試合を [[クラブ名(ESPN), ポゼッション, シュート, 枠内シュート, CK, ファウル], ...]（1試合につき2行）にする。"""
    req = urllib.request.Request(ESPN + d.strftime('%Y%m%d'), headers={'User-Agent': 'Mozilla/5.0 (arsenal-archive league)', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=40) as r:
        j = json.load(r)
    rows = []
    for e in j.get('events', []):
        if not e['status']['type'].get('completed'):
            continue
        for x in e['competitions'][0]['competitors']:
            st = {s['name']: s['displayValue'] for s in x.get('statistics', [])}
            if st.get('possessionPct') in (None, ''):     # スタッツがまだ付いていない試合は数えない
                continue
            rows.append([x['team']['displayName']] + [float(st.get(k) or 0) for k in TSTAT])
    return rows


def espn_collect(old, everything=False):
    """days＝{YYYYMMDD: 行のリスト}。過去の日は保存したものを使い、直近3日と未取得の日だけ取る。1日でも取れなければ None。"""
    days = {} if everything else dict(old)
    today = datetime.now(timezone.utc).date()
    d = START
    while d <= today:
        key = d.strftime('%Y%m%d')
        if key not in days or d >= today - timedelta(days=3):
            try:
                days[key] = espn_day(d)
            except Exception as ex:
                print('ESPN が取れなかった日:', key, ex)
                return None
        d += timedelta(days=1)
    return {k: days[k] for k in sorted(days)}


def espn_totals(days, clubs):
    """クラブごとの [ESPNで数えた試合, ポゼッション合計, シュート, 枠内シュート, CK, ファウル]。clubs は league.json の clubs。"""
    T = [[0] * 6 for _ in clubs]
    unknown = set()
    for rows in days.values():
        for name, *vals in rows:
            ja = ESPN_CLUBS.get(name)
            if ja not in clubs:
                unknown.add(name)
                continue
            t = T[clubs.index(ja)]
            t[0] += 1
            for i, v in enumerate(vals):
                t[1 + i] += v
    for t in T:
        t[1] = round(t[1], 1)
        t[2:] = [int(v) for v in t[2:]]
    return T, sorted(unknown)


def build(boot, fixtures, names):
    teams = {t['id']: t for t in boot['teams']}
    order = sorted(teams)                                  # クラブは league.json の clubs の番号で指す
    idx = {tid: i for i, tid in enumerate(order)}
    unknown = [teams[t]['short_name'] for t in order if teams[t]['short_name'] not in CLUBS]
    clubs = [CLUBS.get(teams[t]['short_name'], teams[t]['name']) for t in order]
    weeks = {}
    for x in fixtures:
        if not x.get('event') or not x.get('kickoff_time'):   # 節・日時が未定（延期）の試合は載せない
            continue
        ko = datetime.strptime(x['kickoff_time'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        row = [ko.astimezone(JST).strftime('%Y-%m-%dT%H:%M'), idx[x['team_h']], idx[x['team_a']]]
        done = x.get('finished') or x.get('finished_provisional')
        if done and x.get('team_h_score') is not None and x.get('team_a_score') is not None:
            row += [x['team_h_score'], x['team_a_score'], ko.strftime('%Y-%m-%d')]   # 最後は現地の試合日（ネタバレ防止の判定用）
        weeks.setdefault(str(x['event']), []).append(row)
    for w in weeks.values():
        w.sort(key=lambda r: (r[0], r[1]))
    cur = next((e['id'] for e in boot['events'] if e.get('is_current')), None) or next((e['id'] for e in boot['events'] if e.get('is_next')), 1)
    # 今の節が全部終わっていて次の節があれば、次の節を最初に見せる
    if str(cur) in weeks and all(len(r) > 3 for r in weeks[str(cur)]) and str(cur + 1) in weeks:
        cur += 1
    missing = []

    def player(e):
        short = teams[e['team']]['short_name']
        ja = names.get(e['web_name'] + '@' + short) or names.get(e['web_name'])
        if not ja:
            missing.append('%s (%s %s, %s)' % (e['web_name'], e['first_name'], e['second_name'], short))
        p = {'e': e['web_name'], 'c': idx[e['team']]}
        if ja:
            p['n'] = ja
        return p

    def top(val, pool=None, fmt=int):
        el = [e for e in (pool or boot['elements']) if val(e) > 0]
        el.sort(key=lambda e: (-val(e), e['minutes'], e['web_name']))
        if len(el) > TOP:                                   # 同数で並ぶ選手は切らずに入れる（最大30人）
            cut = val(el[TOP - 1])
            el = ([e for e in el if val(e) > cut] + [e for e in el if val(e) == cut])[:30]
        return [dict(player(e), v=fmt(val(e))) for e in el]   # 整数の項目は fmt=int で整数にする

    gks = [e for e in boot['elements'] if e['element_type'] == 1]
    xg = lambda e: float(e.get('expected_goals') or 0)
    xa = lambda e: float(e.get('expected_assists') or 0)
    num = lambda k: (lambda e: float(e.get(k) or 0))
    r2 = lambda v: round(v, 2)
    players = {'g': top(num('goals_scored')), 'a': top(num('assists')),
               'ga': top(lambda e: e['goals_scored'] + e['assists']), 'xg': top(xg, fmt=r2), 'xa': top(xa, fmt=r2),
               'xgi': top(num('expected_goal_involvements'), fmt=r2),
               'tk': top(num('tackles')), 'cbi': top(num('clearances_blocks_interceptions')), 'rec': top(num('recoveries')),
               'cs': top(num('clean_sheets'), gks), 'sv': top(num('saves'), gks), 'ps': top(num('penalties_saved'), gks),
               'yc': top(num('yellow_cards')), 'rc': top(num('red_cards')), 'min': top(num('minutes'))}
    # クラブ別：[試合, 得点, 失点, 無失点, イエロー, レッド, セーブ, xG, ホーム勝, ホーム分, ホーム敗, アウェー勝, アウェー分, アウェー敗]
    # （main がこの後ろに ESPN の [数えた試合, ポゼッション合計, シュート, 枠内シュート, CK, ファウル] を足す）
    # 終わった試合から数える（カード・セーブは試合ごとの記録なので移籍した選手の分もずれない）。xG だけは今そのクラブにいる選手の合計
    tstats = [[0] * 14 for _ in order]
    for x in fixtures:
        if not ((x.get('finished') or x.get('finished_provisional')) and x.get('team_h_score') is not None and x.get('team_a_score') is not None):
            continue
        st = {s['identifier']: s for s in x.get('stats') or []}
        tot = lambda k, side: sum(v['value'] for v in st.get(k, {}).get(side, []))
        for side, tid, gf, ga in (('h', x['team_h'], x['team_h_score'], x['team_a_score']), ('a', x['team_a'], x['team_a_score'], x['team_h_score'])):
            t = tstats[idx[tid]]
            t[0] += 1; t[1] += gf; t[2] += ga; t[3] += 1 if ga == 0 else 0
            t[4] += tot('yellow_cards', side); t[5] += tot('red_cards', side); t[6] += tot('saves', side)
            t[(8 if side == 'h' else 11) + (0 if gf > ga else 1 if gf == ga else 2)] += 1
    for e in boot['elements']:
        tstats[idx[e['team']]][7] += xg(e)
    for t in tstats:
        t[7] = round(t[7], 1)

    data = {'note': 'tools/league.py が自動で作るファイル。手で編集しない', 'season': '26/27', 'mw': cur, 'clubs': clubs,
            'weeks': weeks, 'players': players, 'teams': tstats}
    return data, sorted(set(missing)), unknown


def main():
    dry = '--dry' in sys.argv
    names = json.load(open(os.path.join(ROOT, 'tools', 'league_names.json'), encoding='utf-8'))
    data, missing, unknown = build(get('bootstrap-static/'), get('fixtures/'), names)
    n = sum(len(w) for w in data['weeks'].values())
    if len(data['clubs']) != 20 or n < 300:               # おかしなデータで上書きしない
        sys.exit('FPL のデータが想定と違う（クラブ %d・試合 %d）。league.json は変えない' % (len(data['clubs']), n))
    if unknown:
        print('CLUBS に無いクラブ（英語表記のまま出る）:', ', '.join(unknown))
    if missing:
        print('日本語表記が未登録の選手（tools/league_names.json に足す）:\n  ' + '\n  '.join(missing))
    try:
        old = json.load(open(OUT, encoding='utf-8'))
    except Exception:
        old = {}
    try:
        cache = json.load(open(CACHE, encoding='utf-8'))
    except Exception:
        cache = {}
    days = espn_collect(cache, '--all' in sys.argv)
    if days is not None:
        extra, eu = espn_totals(days, data['clubs'])
        if eu:
            print('ESPN_CLUBS に無いクラブ（ポゼッションなどに入らない）:', ', '.join(eu))
        for t, x in zip(data['teams'], extra):
            t += x
        if not dry and days != cache:
            with open(CACHE, 'w', encoding='utf-8') as f:
                json.dump(days, f, ensure_ascii=False, separators=(',', ':'))
                f.write('\n')
    elif old.get('clubs') == data['clubs'] and all(len(t) >= 20 for t in old.get('teams', [])):
        for t, o in zip(data['teams'], old['teams']):     # ESPN が取れないときは前回の値のまま
            t += o[14:20]
    same = {k: v for k, v in old.items() if k != 'asof'} == data
    print('第%d節・%d試合（うち終了 %d）・得点1位 %s %d' % (data['mw'], n, sum(1 for w in data['weeks'].values() for r in w if len(r) > 3),
                                               data['players']['g'][0]['e'], data['players']['g'][0]['v']), '・変更なし' if same else '')
    if dry or same:
        return
    data['asof'] = datetime.now(JST).strftime('%Y-%m-%dT%H:%M+09:00')
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')


if __name__ == '__main__':
    main()
