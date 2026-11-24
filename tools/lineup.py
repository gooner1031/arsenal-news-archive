#!/usr/bin/env python3
"""試合前のスタメン・ベンチ発表を取り込んで lineup.json に書き、発表を通知する。

  python3 tools/lineup.py                  # 次の試合がキックオフ80分前以内なら、発表まで2分ごとに確認
  python3 tools/lineup.py --event 401879232 --league eng.1 --dry   # 過去の試合で取り込みを試す（書き込み・通知なし）

- 取得元は ESPN の公開データ（試合ごとの summary の rosters。キー不要・非公式）。
- 次の試合は next.json（season.json から自動で作られる）のキックオフ時刻で判定する。
- 選手名は meta.json の people / academy.json の players の英語表記（e）に合わせる。合わない名前は ESPN の表記のまま。
- 通知：環境変数 NTFY_TOPIC があれば ntfy.sh に送る（無料・登録不要。スマホの ntfy アプリでそのトピックを購読すると届く）。
- .github/workflows/lineup.yml が15分ごとに実行する。lineup.json は手で編集しない。
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://gooner1031.github.io/arsenal-news-archive/'
JST = timezone(timedelta(hours=9))
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/soccer/%s/%s'
LEAGUE = {'プレミアリーグ': 'eng.1', 'チャンピオンズリーグ': 'uefa.champions', 'FA杯': 'eng.fa',
          'カラバオ杯': 'eng.league_cup', 'コミュニティ・シールド': 'eng.charity'}
WINDOW = 80      # キックオフの何分前から確認を始めるか
GIVEUP = 20      # キックオフ後この分数まで出なければあきらめる
EVERY = 120      # 確認の間隔（秒）


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (arsenal-archive lineup)', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def load(name, default=None):
    try:
        return json.load(open(os.path.join(ROOT, name), encoding='utf-8'))
    except Exception:
        return default


# ---- 選手名を サイトの英語表記（e）に合わせる ----
def norm(s):
    s = (s or '').replace('ø', 'o').replace('Ø', 'O').replace('æ', 'ae').replace('ß', 'ss').replace('ı', 'i')
    s = unicodedata.normalize('NFKD', s)
    return re.sub(r'[^a-z ]', '', ''.join(c for c in s if not unicodedata.combining(c)).lower().replace('-', ' ')).strip()


def name_index():
    meta, acad = load('meta.json', {}), load('academy.json', {})
    ars = [p['e'] for p in meta.get('people', []) if p.get('g') in ('アーセナル選手', 'ローン移籍中')]
    others = [p['e'] for p in meta.get('people', []) if p.get('e')] + [p['e'] for p in (acad or {}).get('players', []) if p.get('e')]
    return ars, others


def match_name(espn, ars, others):
    n = norm(espn)
    for e in ars + others:                       # 完全一致（アクセント違いは同じとみなす）
        if norm(e) == n: return e
    toks = n.split()
    if not toks: return espn
    hit = [e for e in ars if toks[-1] in norm(e).split()]  # 姓（またはワンネーム）で、アーセナルの選手に1人だけ当たる
    if len(hit) == 1: return hit[0]
    hit = [e for e in ars if set(toks) <= set(norm(e).split())]  # 「Gabriel」→「Gabriel Magalhães」のような省略形
    if len(hit) == 1: return hit[0]
    return espn


# ---- 配置：ESPN の position（略号）から列と左右を決める ----
ROW = [('G',), ('RB', 'LB', 'CD', 'CD-R', 'CD-L', 'RWB', 'LWB', 'SW'), ('DM', 'DM-R', 'DM-L'),
       ('CM', 'CM-R', 'CM-L', 'RM', 'LM'), ('AM', 'AM-R', 'AM-L', 'RW', 'LW'), ('F', 'CF', 'CF-R', 'CF-L', 'ST', 'SS')]


def row_of(ab, n_cb):
    ab = (ab or '').upper()
    if ab in ('RWB', 'LWB') and n_cb == 3: return 3   # 3バックのウイングバックは中盤の列
    for i, r in enumerate(ROW):
        if ab in r: return i
    return 3


def side(ab):  # 右サイド=0・右寄り=1・中央=2・左寄り=3・左サイド=4（サイトの図は右から左へ並べる）
    ab = (ab or '').upper()
    if ab.endswith('-R'): return 1
    if ab.endswith('-L'): return 3
    if ab.startswith('R'): return 0
    if ab.startswith('L'): return 4
    return 2


def arrange(starters):
    """starters: [(e, position略号, formationPlace)] → (GK→FW・各列は右→左の順に並べた11人, '4-2-3-1')"""
    n_cb = sum(1 for _, ab, _ in starters if (ab or '').upper().startswith('CD'))
    rows = {}
    for e, ab, fp in starters:
        rows.setdefault(row_of(ab, n_cb), []).append((side(ab), fp, e))
    pos = {e: (ab or '').upper() for e, ab, _ in starters}
    # 4-3-3 の形に寄せる：アンカー1人＋インサイドハーフ2人は中盤1列、ウイングだけの列はFWの列とまとめる
    if len(rows.get(2, [])) == 1 and rows.get(3) and all(pos[e] in ('CM-R', 'CM-L') for _, _, e in rows[3]):
        rows[3] = rows.pop(2) + rows[3]
    if rows.get(4) and rows.get(5) and all(pos[e] in ('RW', 'LW') for _, _, e in rows[4]):
        rows[5] = rows.pop(4) + rows[5]
    out, fm = [], []
    for r in sorted(rows):
        L = sorted(rows[r])
        out += [e for _, _, e in L]
        if r: fm.append(str(len(L)))
    return out, '-'.join(fm)


# ---- ESPN ----
def find_event(league, dates):
    for d in dates:
        try:
            sb = get(ESPN % (league, 'scoreboard?dates=' + d.replace('-', '')))
        except Exception as ex:
            print('scoreboard error', d, ex); continue
        for e in sb.get('events', []):
            if 'Arsenal' in e.get('name', ''):
                return e['id']
    return None


def read_lineup(league, eid):
    s = get(ESPN % (league, 'summary?event=' + str(eid)))
    ars, others = name_index()
    for r in s.get('rosters', []):
        if (r.get('team') or {}).get('displayName', '') != 'Arsenal': continue
        R = r.get('roster') or []
        st = [p for p in R if p.get('starter')]
        if len(st) != 11: return None
        xi, fm = arrange([(match_name(p['athlete'].get('displayName'), ars, others), (p.get('position') or {}).get('abbreviation'), int(p.get('formationPlace') or 0)) for p in st])
        bench = [match_name(p['athlete'].get('displayName'), ars, others) for p in R if not p.get('starter')]
        return {'xi': xi, 'bench': bench, 'fm': r.get('formation') or fm}
    return None


# ---- 通知 ----
def short(e, people):
    n = people.get(e, e)
    return n.split('・')[-1] if '・' in n else n


def notify(L):
    topic = os.environ.get('NTFY_TOPIC', '').strip()
    if not topic:
        print('NTFY_TOPIC なし：通知は送らない'); return
    people = {p['e']: p['n'] for p in load('meta.json', {}).get('people', [])}
    for p in (load('academy.json', {}) or {}).get('players', []):
        if p.get('e') and p.get('j'): people.setdefault(p['e'], p['j'])
    ko = datetime.fromisoformat(L['ko']).astimezone(JST)
    msg = '%s｜%s キックオフ\nスタメン：%s\nベンチ：%s' % (L.get('fm', ''), ko.strftime('%H:%M'),
        '・'.join(short(e, people) for e in L['xi']), '・'.join(short(e, people) for e in L['bench']))
    body = json.dumps({'topic': topic, 'title': 'スタメン発表 vs %s（%s）' % (L['o'], L['c']), 'message': msg,
                       'click': SITE + '#matchinfo', 'tags': ['soccer']}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request('https://ntfy.sh/', data=body, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r: print('通知を送信', r.status)
    except Exception as ex:
        print('通知の送信に失敗', ex)


def next_match(now):
    for m in (load('next.json', {}) or {}).get('matches', []):
        if not m.get('ko'): continue
        ko = datetime.fromisoformat(m['ko'])
        if ko + timedelta(minutes=GIVEUP) > now:
            return m, ko
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--event'); ap.add_argument('--league', default='eng.1'); ap.add_argument('--dry', action='store_true')
    ap.add_argument('--raw', help='league:eventId  ESPN のアーセナル側の生データ（名前・先発・ポジション・配置番号）を表示する調査用')
    a = ap.parse_args()
    if a.raw:
        lg, eid = a.raw.split(':')
        for r in get(ESPN % (lg, 'summary?event=' + eid)).get('rosters', []):
            print('TEAM', (r.get('team') or {}).get('displayName'), 'homeAway', r.get('homeAway'), 'formation', r.get('formation'), 'keys', sorted(k for k in r if k != 'roster'))
            for p in r.get('roster', []):
                if p.get('starter'):
                    print('  %-22s fp=%-3s pos=%-6s %-24s jersey=%s' % (p['athlete'].get('displayName'), p.get('formationPlace'), (p.get('position') or {}).get('abbreviation'), (p.get('position') or {}).get('displayName'), p.get('jersey')))
        return 0
    if a.event:
        L = read_lineup(a.league, a.event)
        print(json.dumps(L, ensure_ascii=False, indent=1)); return 0 if L else 1

    now = datetime.now(timezone.utc)
    m, ko = next_match(now)
    if not m:
        print('次の試合なし'); return 0
    if ko - now > timedelta(minutes=WINDOW):
        print('キックオフまで %d 分：まだ確認しない' % ((ko - now).total_seconds() // 60)); return 0
    cur = load('lineup.json', {}) or {}
    if cur.get('d') == m['d'] and cur.get('o') == m['o'] and len(cur.get('xi', [])) == 11:
        print('この試合のスタメンは取り込み済み'); return 0
    league = LEAGUE.get(m.get('c'))
    if not league:
        print('ESPN の大会が不明：', m.get('c')); return 0
    kou = ko.astimezone(timezone.utc)
    eid = find_event(league, [m['d'], kou.strftime('%Y-%m-%d'), (kou - timedelta(days=1)).strftime('%Y-%m-%d')])
    if not eid:
        print('ESPN に試合が見つからない'); return 0
    print('ESPN event', eid, league)
    while True:
        try:
            got = read_lineup(league, eid)
        except Exception as ex:
            print('summary error', ex); got = None
        now = datetime.now(timezone.utc)
        if got:
            L = {'d': m['d'], 'o': m['o'], 'o_en': m.get('o_en', ''), 'c': m.get('c', ''), 'ha': m.get('ha', ''), 'ko': m['ko'],
                 'fm': got['fm'], 'xi': got['xi'], 'bench': got['bench'], 'src': 'ESPN',
                 'u': 'https://www.espn.com/soccer/lineups/_/gameId/%s' % eid, 'at': now.astimezone(JST).strftime('%Y-%m-%dT%H:%M')}
            print(now.strftime('%H:%M:%S'), 'スタメンを取得', json.dumps(L, ensure_ascii=False))
            with open(os.path.join(ROOT, 'lineup.json'), 'w', encoding='utf-8') as f:
                json.dump(L, f, ensure_ascii=False, indent=1); f.write('\n')
            if os.environ.get('GITHUB_OUTPUT'):
                with open(os.environ['GITHUB_OUTPUT'], 'a') as f: f.write('found=1\n')
            return 0
        if now > ko + timedelta(minutes=GIVEUP):
            print('キックオフ後 %d 分を過ぎても出ないため終了' % GIVEUP); return 0
        print(now.strftime('%H:%M:%S'), 'まだ発表なし'); sys.stdout.flush()
        time.sleep(EVERY)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--notify':
        notify(load('lineup.json')); sys.exit(0)
    sys.exit(main())
