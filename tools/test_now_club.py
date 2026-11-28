#!/usr/bin/env python3
"""tools/now_club.py の読み取りの回帰テスト（通信なし）。情報欄の書き方の違いと、同名の別人ページの除外を確認する。
  python3 tools/test_now_club.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from now_club import parse

LOAN = """{{Infobox football biography
| name = A
| current_club = [[Borussia Dortmund]]<br/>(on loan from [[Arsenal F.C.|Arsenal]])
| youth_years1 = 2015–2024
| youth_clubs1 = [[Arsenal F.C. Under-21s and Academy|Arsenal]]
| years1 = 2022–
| clubs1 = [[Arsenal F.C.|Arsenal]]
| years2 = 2026
| clubs2 = → [[Olympique de Marseille|Marseille]] (loan)
| years3 = 2026–
| clubs3 = → [[Borussia Dortmund]] (loan)
| club_update = 19:39, 11 November 2026 (UTC)
}}
'''A''' is an English professional footballer."""
ONE_LINE = """{{Infobox football biography
| currentclub = [[SS Lazio|Lazio]]
| years1 = 2019–2021 | clubs1 = [[S.L. Benfica|Benfica]] | caps1 = 25 | goals1 = 1
| years2 = 2021–2025 | clubs2 = [[Arsenal F.C.|Arsenal]] | caps2 = 22
| years3 = 2024–2025 | clubs3 = → [[SS Lazio|Lazio]] (loan) | caps3 = 2
| years4 = 2025– | clubs4 = [[SS Lazio|Lazio]] | caps4 = 34
}}"""
RETIRED = """{{Infobox football biography
| current_club =
| years1 = 1999–2007
| clubs1 = [[Arsenal F.C.|Arsenal]]
| years2 = 2010–2014
| clubs2 = [[New York Red Bulls]]
| years3 = 2012
| clubs3 = → [[Arsenal F.C.|Arsenal]] (loan)
| manager_years1 = 2018–2019
| manager_clubs1 = [[AS Monaco FC|Monaco]]
}}
'''B''' is a French professional football manager, pundit, and former player."""
COACH = """{{Infobox football biography
| current_club = [[Como 1907|Como]] (head coach)
| years1 = 2003–2011
| clubs1 = [[Arsenal F.C.|Arsenal]]
| manager_years1 = 2024–
| manager_clubs1 = [[Como 1907|Como]]
}}"""
FREE = """{{Infobox football biography
| current_club =
| years1 = 2024–2025
| clubs1 = → [[Arsenal F.C.|Arsenal]] (loan)
| years2 = 2026
| clubs2 = [[Feyenoord]]
}}
'''C''' is an English professional footballer who plays as a winger."""
MANAGER_ONLY = """{{Infobox football biography
| years1 = 1978–1981
| clubs1 = [[RC Strasbourg Alsace|RC Strasbourg]]
| manager_years1 = 1996–2018
| manager_clubs1 = [[Arsenal F.C.|Arsenal]]
}}
'''D''' is a French former football manager and player."""
OTHER = """{{Infobox football biography
| current_club = [[Paris Saint-Germain FC|Paris Saint-Germain]]
| years1 = 2013–
| clubs1 = [[Paris Saint-Germain FC|Paris Saint-Germain]]
}}"""
DISAMBIG = "'''Jorginho''' is a name, which may refer to:\n*[[Jorginho (footballer, born 1991)]]"

ok = True
def eq(name, got, want):
    global ok
    bad = {k: (got.get(k) if got else None, v) for k, v in want.items() if (got or {}).get(k) != v}
    print(('OK  ' if not bad else 'NG  ') + name + ('' if not bad else '  ' + repr(bad)))
    ok = ok and not bad

eq('ローン中（所属元・過去のローン・更新日）', parse(LOAN), {'st': 'loan', 'c': 'Borussia Dortmund', 'parent': 'Arsenal', 'y': '2026', 'prev': [['Marseille', '2026']], 'upd': '2026-11-11', 'ars': '2022–'})
eq('1行に複数の項目が並ぶ書き方', parse(ONE_LINE), {'st': 'club', 'c': 'Lazio', 'y': '2025', 'ars': '2021–2025'})
eq('引退（最後の所属はローンを除く）', parse(RETIRED), {'st': 'ret', 'last': ['New York Red Bulls', '2010–2014'], 'ars': '1999–2007, 2012'})
eq('監督・コーチ', parse(COACH), {'st': 'staff', 'c': 'Como', 'role': 'head coach', 'y': '2024'})
eq('無所属', parse(FREE), {'st': 'free', 'last': ['Feyenoord', '2026']})
eq('監督としてだけ在籍', parse(MANAGER_ONLY), {'st': 'ret', 'ars': '1996–2018', 'arsM': 1})
for name, t in (('同名の別人（Arsenal が無い）は載せない', OTHER), ('曖昧さ回避ページは載せない', DISAMBIG)):
    r = parse(t)
    print(('OK  ' if r is None else 'NG  ') + name)
    ok = ok and r is None
sys.exit(0 if ok else 1)
