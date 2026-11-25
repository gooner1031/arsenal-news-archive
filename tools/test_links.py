#!/usr/bin/env python3
"""日程・結果の行から試合ページへ飛べるかの回帰テスト。実行: python3 tools/test_links.py
index.html の mLink() と同じ規則で、season.json の結果・今後の日程すべてに行き先があるか確認する。
行き先がないのは「相手クラブが meta.json の clubs にない」ときだけ（新しい対戦相手が来たら追加する）。"""
import json, os, sys
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
meta = json.load(open('meta.json')); season = json.load(open('season.json'))
clubs = meta['clubs']; matches = meta.get('matches', [])
from datetime import date
def dd(s): y, m, d = map(int, s[:10].split('-')); return date(y, m, d)
def dest(club, d):  # mLink と同じ
    for m in matches:
        if m['club'] == club and abs((dd(m['d']) - dd(d)).days) <= 1.5: return '#match-' + m['id']
    return '#mx-%d-%s' % (clubs.index(club), d) if club in clubs else ''
fails = []
for r in season['results']:
    if not dest(r['o'], r['d']): fails.append('結果 %s %s の行き先がない（meta.json の clubs に「%s」を追加）' % (r['d'], r['o'], r['o']))
for u in season['upcoming']:
    d = u['jst'][:10] if u.get('jst') else u['d']
    if u['o'] not in clubs: fails.append('日程 %s %s の行き先がない（meta.json の clubs に「%s」を追加）' % (d, u['o'], u['o']))
n = len(season['results']) + len(season['upcoming'])
print('NG  ' + '\nNG  '.join(fails) if fails else 'OK  日程・結果 %d 件すべてに行き先がある' % n)
sys.exit(1 if fails else 0)
