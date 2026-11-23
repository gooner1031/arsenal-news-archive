#!/usr/bin/env python3
"""次の試合ウィジェット用のデータを作る。

  python3 tools/widget_data.py

season.json の今後の日程（upcoming）から次の3つを作る（手で編集しない）。
- next.json        … widget.html・iPhone の Scriptable ウィジェット（widget-scriptable.js）が読む。今後の試合の一覧（日英の名前・キックオフ時刻）
- fixtures.ics     … カレンダー購読用（日本語）。登録するとスマホのカレンダー／カレンダーウィジェットに試合が出る
- fixtures-en.ics  … 同じ内容の英語版
スコアは入れない（ネタバレ防止）。英語のクラブ名・大会名は index.html の英語表記の辞書（CL / CO）から取る。
season.json・index.html・このファイルが main に入ると .github/workflows/widget.yml が自動で作り直す。
"""
import datetime as dt, hashlib, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://gooner1031.github.io/arsenal-news-archive/'
JST = dt.timezone(dt.timedelta(hours=9))
SHORT = {'プレミアリーグ': 'PL', 'チャンピオンズリーグ': 'CL', 'カラバオ杯': 'カラバオ杯', 'FA杯': 'FA杯',
         'コミュニティ・シールド': 'CS', 'ヨーロッパリーグ': 'EL'}
SHORT_EN = {'カラバオ杯': 'Carabao Cup', 'FA杯': 'FA Cup'}


def en_dicts():
    """index.html の英語表記ブロックから、クラブ名（CL）と大会名（CO）の辞書を取る。"""
    src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    blk = src[src.index('English display / 英語表記'):]
    out = []
    for name in ('CL', 'CO'):
        m = re.search(r"const %s=\{(.*?)\};" % name, blk, re.S)
        out.append(dict(re.findall(r"'([^']+)':'([^']*)'", m.group(1))) if m else {})
    return out


def build():
    sea = json.load(open(os.path.join(ROOT, 'season.json'), encoding='utf-8'))
    clubs, comps = en_dicts()
    ms = []
    for u in sea.get('upcoming', []):
        c = u.get('c') or 'プレミアリーグ'
        base = c.split(' ')[0]
        ms.append({
            'd': u['d'],                                            # 試合日（現地の日付）
            'ko': (u['jst'] + ':00+09:00') if u.get('jst') else None,  # キックオフ（日本時間・ISO）。未定は null
            'c': c, 'c_en': comps.get(base, base), 'cs': SHORT.get(base, c), 'cs_en': SHORT_EN.get(base, SHORT.get(base, c)),
            'ha': u.get('ha', 'H'), 'o': u['o'], 'o_en': clubs.get(u['o'], u['o']),
        })
    return sea.get('asof', ''), ms


def ics_text(s):
    return s.replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')


def fold(line):
    """iCalendar の1行75オクテット制限（UTF-8 の文字の途中では切らない）。"""
    b = line.encode('utf-8')
    if len(b) <= 75:
        return line
    parts, cur, lim = [], b'', 75
    for ch in line:
        e = ch.encode('utf-8')
        if len(cur) + len(e) > lim:
            parts.append(cur.decode('utf-8'))
            cur, lim = b'', 74
        cur += e
    parts.append(cur.decode('utf-8'))
    return '\r\n '.join(parts)


def ics(asof, ms, en):
    stamp = (asof or '2026-01-01').replace('-', '') + 'T000000Z'  # 中身が変わらない限り同じファイルになるよう固定
    name = 'Arsenal fixtures (Arsenal News Archive)' if en else 'アーセナル 試合日程（Arsenal News Archive）'
    L = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Arsenal News Archive//Fixtures//' + ('EN' if en else 'JA'),
         'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:' + ics_text(name), 'X-WR-TIMEZONE:Asia/Tokyo',
         'X-WR-CALDESC:' + ics_text('Upcoming Arsenal matches. Kick-off times update automatically. No scores.' if en else
                                    'アーセナルの今後の試合。キックオフ時刻の変更も自動で反映されます（スコアは載せません）'),
         'REFRESH-INTERVAL;VALUE=DURATION:PT6H', 'X-PUBLISHED-TTL:PT6H']
    for m in ms:
        ars, opp = ('Arsenal', m['o_en']) if en else ('アーセナル', m['o'])
        home, away = (ars, opp) if m['ha'] == 'H' else (opp, ars)
        cs = m['cs_en'] if en else m['cs']
        summ = '⚽ %s vs %s (%s)' % (home, away, cs) if en else '⚽ %s vs %s［%s］' % (home, away, cs)
        uid = 'ars-%s-%s@gooner1031.github.io' % (m['d'], hashlib.md5(m['o'].encode()).hexdigest()[:8])
        L += ['BEGIN:VEVENT', 'UID:' + uid, 'DTSTAMP:' + stamp]
        if m['ko']:
            k = dt.datetime.fromisoformat(m['ko']).astimezone(dt.timezone.utc)
            L += ['DTSTART:' + k.strftime('%Y%m%dT%H%M%SZ'), 'DTEND:' + (k + dt.timedelta(hours=2)).strftime('%Y%m%dT%H%M%SZ')]
            when = (k.astimezone(JST).strftime('%Y-%m-%d %H:%M') + (' JST' if en else '（日本時間）'))
        else:
            d0 = dt.date.fromisoformat(m['d'])
            L += ['DTSTART;VALUE=DATE:' + d0.strftime('%Y%m%d'), 'DTEND;VALUE=DATE:' + (d0 + dt.timedelta(days=1)).strftime('%Y%m%d'),
                  'TRANSP:TRANSPARENT']
            summ += ' (kick-off TBC)' if en else '（時間未定）'
            when = 'Kick-off time TBC' if en else 'キックオフ時間は未定'
        ha = ('Home' if m['ha'] == 'H' else 'Away') if en else ('ホーム' if m['ha'] == 'H' else 'アウェイ')
        desc = '%s / %s\n%s\n%s' % (m['c_en'] if en else m['c'], ha, when, SITE + 'widget.html')
        L += ['SUMMARY:' + ics_text(summ), 'DESCRIPTION:' + ics_text(desc), 'URL:' + SITE + 'widget.html']
        if m['ha'] == 'H':
            L.append('LOCATION:' + ics_text('Emirates Stadium, London' if en else 'エミレーツ・スタジアム（ロンドン）'))
        L.append('END:VEVENT')
    L.append('END:VCALENDAR')
    return '\r\n'.join(fold(x) for x in L) + '\r\n'


def write(path, text):
    p = os.path.join(ROOT, path)
    old = open(p, encoding='utf-8', newline='').read() if os.path.exists(p) else None
    if old != text:
        with open(p, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        print('updated', path)


def main():
    asof, ms = build()
    write('next.json', json.dumps({'asof': asof, 'tz': 'Asia/Tokyo', 'site': SITE, 'matches': ms},
                                  ensure_ascii=False, separators=(',', ':')) + '\n')
    write('fixtures.ics', ics(asof, ms, False))
    write('fixtures-en.ics', ics(asof, ms, True))


if __name__ == '__main__':
    main()
