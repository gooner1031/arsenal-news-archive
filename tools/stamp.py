#!/usr/bin/env python3
"""データごとの「出典」と「最終更新日時」を updated.json に書き出す。

画面に出る「最終更新」は手書きせず、ここで自動的に決める。
- 各データ（下の SECTIONS）の中身のハッシュを前回と比べ、変わっていたら
  そのファイルを main に入れたコミットの時刻（JST）を最終更新にする。
- GitHub Actions（.github/workflows/stamp.yml）が main への push のたびに実行し、
  updated.json が変わったときだけコミットする。

新しいデータ画面を足すときは、SECTIONS に 1 行足すだけでよい（画面側は
index.html の dsrc('<キー>') で出典と最終更新を表示する）。

  python3 tools/stamp.py            # 前回から変わったデータだけ時刻を更新
  python3 tools/stamp.py --rebuild  # git の履歴をさかのぼって全部作り直す
"""
import hashlib, json, os, re, subprocess, sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'updated.json')
JST = timezone(timedelta(hours=9))


def pick(*keys):
    return lambda d: {k: d.get(k) for k in keys}


def next_info(d):
    n = dict(d.get('next') or {})
    for k in ('ref', 'refHist', 'refFor'):
        n.pop(k, None)
    return n


def referee(d):
    n = d.get('next') or {}
    return {k: n.get(k) for k in ('ref', 'refHist', 'refFor')}


def bday(text):
    m = re.search(r'const BDAY=\{.*?\};', text, re.S)
    return m.group(0) if m else None


# キー, ファイル, 取り出し方, 表示名（日・英）, 出典（日・英）
# 取り出し方: None = ファイル全体（JSON）/ 関数（JSON を受け取る）/ ('text', 関数) = テキストのまま
SECTIONS = [
    ('table', 'season.json', pick('table', 'tableAsof', 'posHist'),
     'プレミアリーグ順位表', 'Premier League table',
     'Sky Sports・BBC・Wikipediaなど（2つ以上の情報源で照合）', 'Sky Sports, BBC, Wikipedia etc. (checked in 2+ sources)'),
    ('cl', 'season.json', pick('cl'),
     'チャンピオンズリーグ順位表', 'Champions League table',
     'NBC Sports・Wikipediaなど（2つ以上の情報源で照合）', 'NBC Sports, Wikipedia etc. (checked in 2+ sources)'),
    ('fixtures', 'season.json', pick('results', 'upcoming'),
     '日程・結果', 'Fixtures & results',
     'Sky Sports・BBC・Wikipediaなど（2つ以上の情報源で照合）', 'Sky Sports, BBC, Wikipedia etc. (checked in 2+ sources)'),
    ('nextmatch', 'season.json', next_info,
     '次の試合（会場・相手の直近成績・過去の対戦）', 'Next match (venue, opponent form, head-to-head)',
     'BBC・ESPN・11v11.comなど（2つ以上の情報源で照合）', 'BBC, ESPN, 11v11.com etc. (checked in 2+ sources)'),
    ('referee', 'season.json', referee,
     '主審と直近のアーセナル戦', 'Referee & recent Arsenal matches',
     'プレミアリーグ公式（担当発表）・transfermarkt・worldfootball.netなど', 'Premier League (appointments), transfermarkt, worldfootball.net etc.'),
    ('matchstats', 'matchstats.json', None,
     '試合スタッツ・今季の選手スタッツ', 'Match stats & season player stats',
     'fotmob・BBC・Sky Sports・ESPNなど（試合ごとに表示）', 'fotmob, BBC, Sky Sports, ESPN etc. (listed per match)'),
    ('injuries', 'profiles.json', pick('inj', 'injAsof'),
     '負傷者', 'Injuries',
     'アーセナル公式・premierinjuries.com・BBC・Sky Sportsなど', 'arsenal.com, premierinjuries.com, BBC, Sky Sports etc.'),
    ('players', 'profiles.json', pick('players'),
     '選手プロフィール（背番号・契約・経歴）', 'Player profiles (number, contract, history)',
     'アーセナル公式・footballtransfers.com（契約）・最新報道', 'arsenal.com, footballtransfers.com (contracts), latest reports'),
    ('birthdays', 'index.html', ('text', bday),
     '生年月日（年齢は毎日自動で計算）', 'Dates of birth (ages are calculated daily)',
     'アーセナル公式・Wikipediaなど', 'arsenal.com, Wikipedia etc.'),
    ('people', 'meta.json', pick('people'),
     '人物の区分（選手・スタッフ・過去の所属など）', 'People categories (squad, staff, former, etc.)',
     'アーセナル公式・Wikipedia・BBC・Sky Sportsなど', 'arsenal.com, Wikipedia, BBC, Sky Sports etc.'),
    ('milestones', 'milestones.json', None,
     '記念試合（プレミアリーグ出場数）', 'Milestones (Premier League appearances)',
     'StatMuse（11v11.comで照合）・アーセナル公式', 'StatMuse (checked with 11v11.com), arsenal.com'),
    ('transfers', 'transfers.json', None,
     '移籍の完了・移籍金', 'Completed transfers & fees',
     '各報道（移籍金は報道ベースの概算）', 'Media reports (fees are reported estimates)'),
    ('academy', 'academy.json', None,
     'アカデミー（U21登録リスト）', 'Academy (U21 squad list)',
     'アーセナル公式 2026/27 U21登録リスト', 'arsenal.com 2026/27 U21 squad list'),
    ('academystats', 'academystats.json', None,
     'アカデミーの今季成績', 'Academy season stats',
     'アーセナル公式の試合レポート', 'arsenal.com match reports'),
    ('careerstats', 'careerstats.json', None,
     '選手の過去シーズン・通算成績', 'Past seasons & career totals',
     '英語版Wikipediaの通算成績表（CC BY-SA 4.0）', 'English Wikipedia career statistics tables (CC BY-SA 4.0)'),
    ('nowclub', 'nowclub.json', pick('players'),
     '現在の所属（ローン中・過去の所属選手・OB）', 'Current clubs (loanees, former players, alumni)',
     '英語版Wikipediaの選手情報欄（CC BY-SA 4.0）', 'English Wikipedia player infoboxes (CC BY-SA 4.0)'),
]


def git(*a):
    return subprocess.run(['git', '-C', ROOT] + list(a), capture_output=True, text=True).stdout


def digest(v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:12]


def extract(text):
    """ファイルの中身から {キー: ハッシュ} を作る（試合スタッツは試合ごとにも）。"""
    out = {}
    for path in {s[1] for s in SECTIONS}:
        if path not in text or text[path] is None:
            continue
        raw = text[path]
        try:
            data = None if path.endswith('.html') else json.loads(raw)
        except ValueError:
            continue
        for key, p, how, *_ in SECTIONS:
            if p != path:
                continue
            if isinstance(how, tuple):
                v = how[1](raw)
            elif how is None:
                v = data
            else:
                v = how(data)
            if v is not None:
                out[key] = digest(v)
        if path == 'matchstats.json' and isinstance(data, dict):
            for d, v in data.items():
                out['ms:' + d] = digest(v)
    return out


def iso(t):
    return datetime.fromisoformat(t).astimezone(JST).isoformat(timespec='minutes')


def file_time(path):
    """そのファイルを main に入れた（first-parent の）コミット時刻。未コミットの変更があれば今。"""
    if subprocess.run(['git', '-C', ROOT, 'diff', '--quiet', 'HEAD', '--', path]).returncode != 0:
        return datetime.now(JST).isoformat(timespec='minutes')
    t = git('log', '-1', '--first-parent', '--format=%cI', '--', path).strip()
    return iso(t) if t else datetime.now(JST).isoformat(timespec='minutes')


def labels(sec):
    out = {}
    for key, path, how, ja, en, sja, sen in SECTIONS:
        if key in sec:
            out[key] = dict(sec[key], f=path, ja=ja, en=en, src=sja, srcEn=sen)
    for k in sorted(k for k in sec if k.startswith('ms:')):
        out[k] = {'t': sec[k]['t'], 'h': sec[k]['h']}
    return out


def rebuild():
    sec = {}
    paths = sorted({s[1] for s in SECTIONS})
    for path in paths:
        log = git('log', '--first-parent', '--reverse', '--format=%H %cI', '--', path).split('\n')
        for line in filter(None, log):
            h, t = line.split(' ', 1)
            raw = subprocess.run(['git', '-C', ROOT, 'show', h + ':' + path], capture_output=True, text=True)
            if raw.returncode != 0:
                continue
            for k, d in extract({path: raw.stdout}).items():
                if k not in sec or sec[k]['h'] != d:
                    sec[k] = {'t': iso(t), 'h': d}
    update(sec)  # 未コミットの変更も反映
    return sec


def update(sec):
    texts = {}
    for path in {s[1] for s in SECTIONS}:
        fp = os.path.join(ROOT, path)
        if os.path.exists(fp):
            with open(fp, encoding='utf-8') as f:
                texts[path] = f.read()
    cur = extract(texts)
    times = {}
    for k, d in cur.items():
        if k in sec and sec[k].get('h') == d:
            continue
        path = 'matchstats.json' if k.startswith('ms:') else next(s[1] for s in SECTIONS if s[0] == k)
        if path not in times:
            times[path] = file_time(path)
        sec[k] = {'t': times[path], 'h': d}
    for k in list(sec):
        if k not in cur:
            del sec[k]
    return sec


def main():
    old = {}
    if os.path.exists(OUT):
        with open(OUT, encoding='utf-8') as f:
            old = json.load(f).get('sections', {})
    sec = rebuild() if '--rebuild' in sys.argv else update({k: {'t': v['t'], 'h': v['h']} for k, v in old.items()})
    new = labels(sec)
    if new == old:
        print('updated.json: 変更なし')
        return
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'note': 'tools/stamp.py が自動で作るファイル。手で編集しない', 'sections': new}, f, ensure_ascii=False, indent=0)
        f.write('\n')
    changed = [k for k in new if old.get(k, {}).get('t') != new[k]['t']]
    print('updated.json: 更新 ' + ', '.join(changed[:20]) + (' …' if len(changed) > 20 else ''))


if __name__ == '__main__':
    main()
