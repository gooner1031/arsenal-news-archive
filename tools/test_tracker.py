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
    z=R.get('Martín Zubimendi')
    chk(z is None or z[3],'本人がインタビューで移籍を否定したら破談・停滞(Zubimendi, MARCA 11/11)')
    chk(z is None or z[2]=='rumor','「交渉のレバレッジ」は交渉中ではない(Zubimendi)')
    ids=pg.evaluate("(w)=>{const r=trBuild().find(r=>r.w===w&&META.people[r.i].e==='Martín Zubimendi'); return r?r.posts.map(x=>x.p.id):[]}",cur)
    chk('2119929800584519686' in ids,'他選手の「契約延長」が書かれた記事でも本人の売却報道は拾う(Zubimendi, AS 11/10)')
    k=R.get('Eli Junior Kroupi')
    chk(k is not None and k[2]=='rumor','括弧内の別選手の「オファー」で交渉中にならない(Kroupi)')
    chk(k is not None and k[3],'「1月の売却は否定」は破談・停滞(Kroupi)')
    # 4人以上が出てくるまとめ記事（The Athletic「2027年の移籍計画」11/27）
    W=rows(pg,'2027W'); f=W.get('Iván Fresneda'); bo=W.get('David Boly'); nu=W.get('Antonio Nusa')
    chk(f is not None and f[1]=='IN' and f[2]=='talks','まとめ記事の獲得候補も載る・「代理人と接触」は交渉中(Fresneda)')
    chk(bo is not None and bo[2]=='rumor' and not bo[3],'同じ文の別選手の「接触」で交渉中にならない(Boly)')
    chk(nu is not None and nu[2]=='rumor' and not nu[3],'過去の他クラブ移籍の「メディカルで破談」に巻き込まれない(Nusa)')
    chk('Julián Álvarez' not in W,'「◯◯級の選手」というたとえ話は候補にしない(Álvarez)')
    chk(not any(n in W for n in ['Declan Rice','Kepa Arrizabalaga','Ethan Nwaneri','Ben White']),'まとめ記事に名前が出ただけの所属選手は退団候補にしない')
    # 登録漏れ: 移籍・噂ポストの人物タグなし件数が増えていないか（参考値）
    n=pg.evaluate("POSTS.filter(p=>(p.k||[]).includes(0)&&!(p.p||[]).length&&p.d>'2026-10').length")
    print('INFO 直近の移籍・噂で人物タグなし:',n,'件（audit_transfers.py で候補を確認）')
    b.close()
sys.exit(1 if fails else 0)
