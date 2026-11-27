"""fetch_highlights.py 用：WOWOW（CL）・DAZN（カラバオ杯・FA杯）公式ハイライトのタイトル判定。テスト: python3 tools/test_highlights.py"""
import re
JP_ALT = {'PSG': ['パリ・サンジェルマン', 'パリSG', 'パリ・サン＝ジェルマン', 'パリ'], 'マンチェスター・シティ': ['マンチェスター・C', 'マンC'], 'マンチェスター・ユナイテッド': ['マンチェスター・U', 'マンU'],
          'ブルッヘ': ['クラブ・ブルッヘ', 'クラブ・ブルージュ', 'ブルージュ'], 'レバークーゼン': ['レヴァークーゼン'], 'アスレティック・ビルバオ': ['アスレティック', 'アスレティック・クラブ', 'ビルバオ'],
          'ウルヴァーハンプトン': ['ウルヴス', 'ウォルヴァーハンプトン'], 'ハル・シティ': ['ハル'], 'スラヴィア・プラハ': ['スラビア・プラハ'], 'アストン・ヴィラ': ['アストン・ビラ'], 'ディナモ・ザグレブ': ['ディナモ・ザグレブ', 'ザグレブ']}
JP_SRC = {'チャンピオンズリーグ': ('wowow', 2024), 'カラバオ杯': ('dazn', 2025), 'FA杯': ('dazn', 2026)}   # 大会 → (配信元, 探しはじめるシーズン)
def nk(x): return re.sub(r'[\s　・･.=＝]', '', x or '')
def same_club(team, club):
    t, c = nk(team), nk(club)
    return bool(t) and (t == c or t in [nk(z) for z in JP_ALT.get(club, [])] or (len(t) >= 3 and len(c) >= 3 and (t.startswith(c) or c.startswith(t))))
def parse_jp(t):
    """タイトル → (src, ホーム, アウェイ, 大会, シーズン開始年)。ハイライト動画でなければ None。
       WOWOW:【アーセナル vs ドルトムント】UEFAチャンピオンズリーグ 2026-27 リーグフェーズ MD5／3分ハイライト【WOWOW】
       DAZN :【イプスウィッチ×アーセナル ｜ハイライト】カラバオカップ 3回戦｜2026-27シーズン"""
    if 'ハイライト' not in t: return None
    m = re.search(r'【([^】]*)】\s*(UEFAチャンピオンズリーグ|カラバオカップ|FAカップ)(.*)', t)
    if not m: return None
    y = re.search(r'(20\d{2})\s*[-/‐–−]\s*\d{2}', m.group(3))
    if not y: return None
    cl = m.group(2) == 'UEFAチャンピオンズリーグ'
    for part in re.split(r'[｜|]', m.group(1)):
        pr = re.split(r'\s+(?:vs|VS|ｖｓ|v)\.?\s+|\s*[×✕]\s*', part.strip()) if cl else re.split(r'\s*[×✕]\s*|\s+(?:vs|VS)\.?\s+', part.strip())
        if len(pr) == 2 and pr[0] and pr[1]:
            return ('wowow' if cl else 'dazn', pr[0].strip(), pr[1].strip(), {'UEFAチャンピオンズリーグ': 'チャンピオンズリーグ', 'カラバオカップ': 'カラバオ杯', 'FAカップ': 'FA杯'}[m.group(2)], int(y.group(1)))
    return None
def fits(pj, S, start):
    """parse_jp の結果が matchstats の試合 S（シーズン start）と同じ試合か。"""
    if not pj or JP_SRC.get(S.get('c'), ('',))[0] != pj[0] or pj[3] != S['c'] or pj[4] != start: return False
    _, h, a, _, _ = pj
    ah, aa = nk(h) == 'アーセナル', nk(a) == 'アーセナル'
    if ah == aa: return False
    if S['ha'] != 'N' and ah != (S['ha'] == 'H'): return False
    return same_club(a if ah else h, S['o'])
