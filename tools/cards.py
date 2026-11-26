#!/usr/bin/env python3
"""アーセナルの選手の警告・退場を matchstats.json の `cards` に入れ、得点のアシストを照合する。

  python3 tools/cards.py              # 今季の試合のうち cards がまだない試合に入れる
  python3 tools/cards.py --all        # 今季の全試合を取り直す（内容が変われば上書き）
  python3 tools/cards.py --dry        # 書き込まずに結果だけ表示

- 取得元は ESPN の公開データ（試合ごとの summary の keyEvents。キー不要・非公式。tools/lineup.py と同じ）。
- プレミアリーグの試合は FPL の公開データ（fantasy.premierleague.com/api/fixtures/）でも確認し、
  2つが合った試合だけ入れる。合わない試合は入れずに表示する（手で確認する）。
- カップ戦（CL・カラバオ杯・FA杯・コミュニティ・シールド）は ESPN だけ。keyEvents と rosters の
  選手別スタッツ（yellowCards / redCards）が合った試合だけ入れる。
- アシストは書き換えない。ESPN（リーグ戦は FPL も）と違うところを表示するだけ。直すかどうかは人が決める。
- `cards` の形：[{m: 分, p: 選手（people の e）, k: 'Y'（警告）/ 'R'（退場）}]。カードがなかった試合は []。
  2枚目の警告での退場は Y・Y・R の3件になる（ESPN の記録どおり）。
"""
import argparse, json, os, re, sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lineup import ESPN, LEAGUE, ROOT, get, load, match_name, name_index, norm  # noqa: E402

TEAM = '359'  # ESPN のアーセナル
FPL = 'https://fantasy.premierleague.com/api/'


def season_year(d):
    return int(d[:4]) if int(d[5:7]) >= 8 else int(d[:4]) - 1


def minute(clock):
    """「90'+5'」→ 90（サイトの得点・交代と同じく追加時間は丸める）"""
    m = re.match(r"\s*(\d+)", clock or '')
    return int(m.group(1)) if m else 0


def espn_events(league, year):
    """その大会のアーセナルの終了済みの試合 {UTCの日付: 試合番号}"""
    out = {}
    try:
        d = get(ESPN % (league, 'teams/%s/schedule?season=%d' % (TEAM, year)))
    except Exception as ex:
        print('schedule error', league, ex); return out
    for e in d.get('events', []):
        c = e['competitions'][0]
        if c['status']['type'].get('completed'):
            out[e['date'][:10]] = e['id']
    return out


def find(events, day):
    """matchstats のキー（試合日）に前後1日で合う試合"""
    t = datetime.strptime(day, '%Y-%m-%d')
    for off in (0, 1, -1):
        k = (t + timedelta(days=off)).strftime('%Y-%m-%d')
        if k in events: return events[k]
    return None


def read_espn(league, eid, ars, others):
    s = get(ESPN % (league, 'summary?event=' + eid))
    cards, goals = [], []
    for k in s.get('keyEvents', []):
        if (k.get('team') or {}).get('id') != TEAM: continue
        t = k['type']['text']
        ps = [match_name(p['athlete']['displayName'], ars, others) for p in k.get('participants', [])]
        m = minute((k.get('clock') or {}).get('displayValue'))
        if 'Card' in t and ps:
            cards.append({'m': m, 'p': ps[0], 'k': 'R' if 'Red' in t else 'Y'})
        elif ('Goal' in t or 'Penalty - Scored' in t) and 'Own' not in t and ps:
            goals.append({'m': m, 'p': ps[0], 'a': ps[1] if len(ps) > 1 else ''})
    box, ast = {}, {}   # 選手別スタッツでのカードの枚数（keyEvents との照合用）とアシスト数
    for r in s.get('rosters', []):
        if (r.get('team') or {}).get('id') != TEAM: continue
        for p in r.get('roster', []):
            st = {x['name']: x.get('value') or 0 for x in p.get('stats', [])}
            y, rd = int(st.get('yellowCards', 0)), int(st.get('redCards', 0))
            if y or rd: box[match_name(p['athlete']['displayName'], ars, others)] = (y, rd)
            if st.get('goalAssists'): ast[match_name(p['athlete']['displayName'], ars, others)] = int(st['goalAssists'])
    return cards, goals, box, ast


def count(cards):
    o = {}
    for c in cards:
        y, r = o.get(c['p'], (0, 0))
        o[c['p']] = (y + (c['k'] == 'Y'), r + (c['k'] == 'R'))
    return o


def fpl_data(ars, others):
    """FPL：{キックオフのUTC日付: {'cards': {選手: (Y, R)}, 'assists': {選手: 数}}}。取れなければ None"""
    try:
        b = get(FPL + 'bootstrap-static/'); fx = get(FPL + 'fixtures/')
    except Exception as ex:
        print('FPL error', ex); return None
    tid = next((t['id'] for t in b['teams'] if t['name'] == 'Arsenal'), None)
    nm = {}
    for e in b['elements']:
        if e['team'] != tid: continue
        full = e['first_name'] + ' ' + e['second_name']
        hit = match_name(full, ars, others)
        if hit == full:  # 「David Raya Martín」のような長い本名は、people の名前が全部含まれる人に合わせる
            c = [x for x in ars if set(norm(x).split()) <= set(norm(full).split())]
            if len(c) == 1: hit = c[0]
        nm[e['id']] = hit
    out = {}
    for f in fx:
        if tid not in (f['team_h'], f['team_a']) or not f.get('finished'): continue
        side = 'h' if f['team_h'] == tid else 'a'
        st = {s['identifier']: {nm.get(x['element'], str(x['element'])): x['value'] for x in s[side]} for s in f['stats']}
        cards = {}
        for p, v in st.get('yellow_cards', {}).items(): cards[p] = (v, 0)
        for p, v in st.get('red_cards', {}).items(): cards[p] = (cards.get(p, (0, 0))[0], v)
        out[f['kickoff_time'][:10]] = {'cards': cards, 'assists': st.get('assists', {})}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true'); ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    ms = load('matchstats.json', {})
    if not ms: sys.exit('matchstats.json が読めません')
    year = max(season_year(d) for d in ms)
    ars, others = name_index()
    days = [d for d in sorted(ms) if season_year(d) == year and (a.all or 'cards' not in ms[d])]
    if not days: print('入れる試合はありません'); return
    sched, fpl, changed = {}, None, 0
    for d in days:
        S = ms[d]; lg = LEAGUE.get(S.get('c'))
        if not lg: print(d, S.get('c'), '… 大会が対応外'); continue
        if lg not in sched: sched[lg] = espn_events(lg, year)
        eid = find(sched[lg], d)
        if not eid: print(d, S['o'], '… ESPN に試合が見つからない'); continue
        try:
            cards, goals, box, ast = read_espn(lg, eid, ars, others)
        except Exception as ex:
            print(d, S['o'], '… ESPN の取得に失敗', ex); continue
        ok = count(cards) == box
        why = '' if ok else 'ESPN の経過と選手別スタッツが合わない %s / %s' % (count(cards), box)
        F = None
        if lg == 'eng.1':
            if fpl is None: fpl = fpl_data(ars, others) or {}
            F = fpl.get(d) or next((fpl[k] for k in fpl if abs((datetime.strptime(k, '%Y-%m-%d') - datetime.strptime(d, '%Y-%m-%d')).days) <= 1), None)
            if F is None: ok, why = False, 'FPL で確認できない'
            elif F['cards'] != count(cards): ok, why = False, 'ESPN と FPL が合わない %s / %s' % (count(cards), F['cards'])
        tag = 'ESPN・FPL一致' if F else 'ESPNのみ'
        if ok:
            if S.get('cards') != cards:
                S['cards'] = cards; changed += 1
            print(d, S['o'], '… カード', len(cards), '件（%s）' % tag, ' '.join('%s%d\' %s' % ('🟥' if c['k'] == 'R' else '🟨', c['m'], c['p']) for c in cards))
        else:
            print(d, S['o'], '… カードは入れない：', why)
        # アシストの照合（表示だけ）。ESPN は選手別スタッツの数で比べ、違う試合だけ得点ごとの記録も出す
        site = [g for g in S.get('goals', []) if g.get('t') == 'A']
        mine = {}
        for g in site:
            if g.get('a'): mine[g['a']] = mine.get(g['a'], 0) + 1
        if mine != ast:
            print('   ⚠ アシストが ESPN と違う：サイト', mine, '／ESPN', ast)
            for g in site:
                e = next((x for x in goals if x['p'] == g['p'] and abs(x['m'] - g['m']) <= 2), None)
                if e and (e['a'] or '') != (g.get('a') or ''):
                    print('      %d\' %s　サイト「%s」／ESPN「%s」' % (g['m'], g['p'], g.get('a') or 'なし', e['a'] or 'なし'))
        if F and mine != F['assists']:
            print('   ⚠ アシストが FPL と違う：FPL', F['assists'], '（FPL はこぼれ球やPK獲得もアシストに数える）')
    if changed and not a.dry:
        with open(os.path.join(ROOT, 'matchstats.json'), 'w', encoding='utf-8') as f:
            json.dump(ms, f, ensure_ascii=False)
        print('matchstats.json を更新：', changed, '試合')
    elif changed: print('（--dry のため書き込みなし：%d 試合）' % changed)


if __name__ == '__main__':
    main()
