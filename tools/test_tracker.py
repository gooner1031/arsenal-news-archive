#!/usr/bin/env python3
"""移籍トラッカーの回帰テスト（Playwright）。実行: python3 -m http.server 8766 & python3 tools/test_tracker.py
過去に起きた誤判定を固定し、判定ロジックを触るたびに確認する。"""
import sys
from playwright.sync_api import sync_playwright
BASE=sys.argv[1] if len(sys.argv)>1 else 'http://localhost:8766/'
def rows(pg,w): return {r[0]:r for r in pg.evaluate("(w)=>trBuild().filter(r=>r.w===w).map(r=>[META.people[r.i].e,r.dir,r.st,r.dead,r.n])",w)}
fails=[]
def chk(c,msg):
    print(('OK  ' if c else 'NG  ')+msg)
    if not c: fails.append(msg)
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(); pg.goto(BASE+'#transfers'); pg.wait_for_timeout(2500)
    cur=pg.evaluate("trCurWin()"); R=rows(pg,cur)
    chk('Alex Scott' in R,'他クラブ選手の「新契約」を含む記事でも候補に載る(Scott)')
    chk('Eli Junior Kroupi' in R,'登録済みの候補はトラッカーに載る(Kroupi)')
    chk('Vinícius Júnior' not in R or R['Vinícius Júnior'][3],'「絶対にない」と否定された選手は噂として生きない(Vinícius)')
    chk('Mykhailo Mudryk' not in rows(pg,cur),'過去の希望発言(インタビュー)は移籍噂に出ない(Mudryk)')
    chk(not R.get('Alex Scott',[0,0,0,True])[3],'他選手の「撤退」「合意」に巻き込まれない(Scott)')
    # 登録漏れ: 移籍・噂ポストの人物タグなし件数が増えていないか（参考値）
    n=pg.evaluate("POSTS.filter(p=>(p.k||[]).includes(0)&&!(p.p||[]).length&&p.d>'2026-10').length")
    print('INFO 直近の移籍・噂で人物タグなし:',n,'件（audit_transfers.py で候補を確認）')
    b.close()
sys.exit(1 if fails else 0)
