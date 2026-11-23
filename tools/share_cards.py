#!/usr/bin/env python3
"""Xなどに貼ったときのシェアカード（OGP画像つきの共有ページ）を作る。

  python3 tools/share_cards.py

- 移籍トラッカーの各選手（#tr-<i>-<w>）・試合（#match-<id>）・人物（#person-<i>）ごとに
  s/<ハッシュ名>.html を作る。中身は og:title / og:image などのメタタグと、サイトの該当ページへの即時リダイレクトだけ。
  （Xのクローラーは # 以降を見ないので、トップの og.png しか出ない問題をこれで避ける）
- 画像（1200×630）は直近の移籍市場・直近2シーズンの試合・全人物だけ作り、s/img/ に置く。
  それ以外は og.png を使う。画像の中身が変わったときだけ描き直す（s/cards.json に中身のハッシュを記録）。
- 移籍の段階・試合の結果は、サイト本体（index.html の trBuild など）と同じ判定をブラウザで動かして取る。
- 試合はスコア入り（match-<id>.html）と、ネタバレ防止モード用のスコアなし（match-<id>-ns.html）の2つ。
- 生成中はサイトの外への通信（アクセス数カウンターなど）を止め、Googleフォントだけ通す。

必要なもの: pip install playwright pillow && python3 -m playwright install chromium
"""
import hashlib, http.server, io, json, os, re, socketserver, sys, threading
from functools import partial
from html import escape
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 's')
IMG = os.path.join(OUT, 'img')
SITE = 'https://gooner1031.github.io/arsenal-news-archive/'
FORCE = '--force' in sys.argv

# ---- サイトからデータを取る（index.html と同じ判定） ----
EXTRACT = r"""() => {
  const cur = trCurWin(), wins = [...new Set(trBuild().map(r=>r.w))].sort((a,b)=>trWinKey(b)-trWinKey(a));
  const recentW = new Set(wins.filter(w=>trWinKey(w)<=trWinKey(cur)).slice(0,4).concat(wins.filter(w=>trWinKey(w)>trWinKey(cur))));
  const ss = SEASONS.filter(s=>META.matches.some(m=>seasonOf(m.d)===s)).slice(-2);
  const out = {tr:[], m:[], p:[]};
  const enC = c => (CLEN[c]||[])[0] || '';
  trBuild().forEach(r=>{ const pp=META.people[r.i], s=TR_ST.find(x=>x[0]===r.st);
    const D=(TRI&&TRI.w&&TRI.w[r.w]&&TRI.w[r.w][r.dir])||{}, x=D[pp.e]||null;
    out.tr.push({i:r.i, w:r.w, dir:r.dir, st:r.st, dead:!!r.dead, past:!!r.past, n:r.posts.length,
      name:pp.n, en:pp.e, win:trWinLbl(r.w), stl:r.dead?(r.past?'実現せず':'破談・停滞'):(s?s[1]:''), col:r.dead?'#555555':(s?s[2]:'#8A8A8A'),
      steps:TR_ST.map(x=>x[1]), k:r.dead?-1:TR_ST.findIndex(x=>x[0]===r.st),
      club:x&&x.club||'', fee:x?trFee(x.gbp,'gbp'):'', img:recentW.has(r.w)}); });
  META.matches.forEach(m=>{ const [sc,r]=resultOf(m); const c=CLUBCOL[m.club]||null;
    out.m.push({id:m.id, d:m.d, club:m.club, clubEn:enC(m.club), ha:m.ha||'', sc, r, comp:m.comp, n:m.n,
      col:c?c[0]:'#555555', fg:c?c[2]:'#ffffff', img:ss.includes(seasonOf(m.d))&&!/推定/.test(m.comp)}); });
  const pc={}; POSTS.forEach(p=>(p.p||[]).forEach(i=>pc[i]=(pc[i]||0)+1));
  META.people.forEach((pp,i)=>out.p.push({i, name:pp.n, en:pp.e, g:pp.g, n:pc[i]||0, img:true}));
  return out;
}"""

# ---- カードのテンプレート（サイトと同じフォント・色） ----
LOGO = ('<svg viewBox="0 0 40 40" width="46" height="46"><g fill="#fff"><circle cx="34.5" cy="11" r="2.2" opacity=".8"/>'
        '<circle cx="31.5" cy="7.5" r="1.6" opacity=".6"/><circle cx="36" cy="6" r="1.2" opacity=".45"/><g transform="rotate(-22 22 22)">'
        '<rect x="11" y="17.5" width="20" height="8" rx="4"/><rect x="9.5" y="16.6" width="3.4" height="9.8" rx="1.2"/><circle cx="31" cy="21.5" r="2.6"/></g>'
        '<path d="M16 27h14l-2 4H18z"/></g><circle cx="24" cy="29" r="5.2" fill="#DB0007" stroke="#fff" stroke-width="2.2"/>'
        '<circle cx="24" cy="29" r="1.4" fill="#fff"/><path d="M24 24.6v8.8M19.6 29h8.8" stroke="#fff" stroke-width="1.2"/></svg>')
TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Barlow+Condensed:wght@600;700;800&family=Zen+Kaku+Gothic+New:wght@500;700;900&display=block" rel="stylesheet">
<style>
*{box-sizing:border-box}html,body{margin:0}
#c{width:1200px;height:630px;position:relative;overflow:hidden;background:#F5F0E6;color:#17140F;font-family:"Zen Kaku Gothic New",sans-serif}
#c:before{content:"";position:absolute;left:0;top:0;right:0;height:16px;background:#DB0007}
.ac{position:absolute;right:-120px;top:-120px;width:520px;height:520px;border-radius:50%;opacity:.08}
.main{position:absolute;left:72px;right:72px;top:62px;bottom:120px;display:flex;flex-direction:column}
.pill{display:inline-flex;align-items:center;gap:12px;align-self:flex-start;font-weight:900;font-size:26px;color:#fff;background:#17140F;padding:9px 18px;border-radius:999px}
.pill b{font-family:"Barlow Condensed";font-weight:800;letter-spacing:.06em;color:#FF5A5F}
.nm{font-weight:900;line-height:1.08;white-space:nowrap;margin-top:22px;font-size:104px;letter-spacing:-.01em}
.en{font-family:"Barlow Condensed";font-weight:700;font-size:40px;color:#5B5449;letter-spacing:.03em;margin-top:4px;white-space:nowrap}
.row{display:flex;align-items:center;gap:18px}.mid{margin:auto 0}
.dir{font-family:"Barlow Condensed";font-weight:800;font-size:40px;color:#fff;padding:4px 16px;border-radius:8px;letter-spacing:.05em}
.dir.IN{background:#1E7A46}.dir.OUT{background:#8A8A8A}
.st{font-weight:900;font-size:44px;color:#fff;padding:6px 26px;border-radius:12px}
.sub{font-weight:700;font-size:30px;color:#5B5449}
.prog{display:flex;gap:8px;margin-top:20px}.prog i{flex:1;height:14px;border-radius:7px;background:#E3DACA;font-style:normal;position:relative}
.prog i.on{background:var(--pc)}.prog i span{position:absolute;top:20px;left:0;font-weight:700;font-size:21px;color:#8E867A;white-space:nowrap}.prog i.on span{color:#17140F}
.prog.dead i.on{background:#8A8A8A}
.vs{display:flex;align-items:center;gap:28px;margin:auto 0}
.tm{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;text-align:center}
.tm .bd{width:100%;height:16px;border-radius:8px}
.tm b{font-weight:900;font-size:58px;white-space:nowrap;margin-top:14px;line-height:1.1}
.tm small{font-family:"Barlow Condensed";font-weight:700;font-size:30px;color:#5B5449;letter-spacing:.04em}
.sc{font-family:Anton;font-size:136px;line-height:1;flex:none;display:flex;align-items:center;gap:18px}.sc i{font-style:normal;font-size:90px;color:#8E867A}
.sc.q{font-size:72px;color:#8E867A}
.res{font-weight:900;font-size:34px;color:#fff;padding:6px 22px;border-radius:10px}
.foot{position:absolute;left:0;right:0;bottom:0;height:96px;background:#17140F;color:#fff;display:flex;align-items:center;gap:16px;padding:0 72px}
.lg{width:62px;height:62px;border-radius:10px;background:#DB0007;display:flex;align-items:center;justify-content:center}
.foot .bn{font-family:Anton;font-size:38px;letter-spacing:.02em}
.foot .u{margin-left:auto;font-weight:700;font-size:24px;color:#D8D0C2}
</style></head><body><div id="c"></div>
<script>
const LOGO=__LOGO__;
const e=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function fit(el,max){ let f=parseFloat(getComputedStyle(el).fontSize); while(el.scrollWidth>max&&f>20){ f-=2; el.style.fontSize=f+'px'; } }
function foot(){ return '<div class="foot"><div class="lg">'+LOGO+'</div><span class="bn">ARSENAL NEWS ARCHIVE</span><span class="u">gooner1031.github.io/arsenal-news-archive</span></div>'; }
function render(k,d){
  const c=document.getElementById('c'); let h='';
  if(k==='tr'){
    h='<div class="ac" style="background:'+d.col+'"></div><div class="main"><span class="pill"><b>TRANSFER</b>移籍トラッカー · '+e(d.win)+'の移籍市場</span>'+
      '<div class="mid"><div class="nm" id="nm">'+e(d.name)+'</div><div class="en" id="en">'+e(d.en)+'</div></div>'+
      '<div class="row"><span class="dir '+d.dir+'">'+d.dir+'</span><span class="st" style="background:'+d.col+'">'+e(d.stl)+'</span>'+
      (d.club?'<span class="sub">'+e(d.club)+(d.dir==='IN'?'から':'へ')+(d.fee?' · '+e(d.fee):'')+'</span>':'')+'</div>'+
      '<div class="prog'+(d.dead?' dead':'')+'" style="--pc:'+d.col+'">'+d.steps.map((s,j)=>'<i class="'+(j<=d.k||d.dead&&j===0?'on':'')+'"><span>'+e(s)+'</span></i>').join('')+'</div><div style="height:30px"></div></div>';
  } else if(k==='m'){
    const ars={n:'アーセナル',en:'ARSENAL',col:'#DB0007'}, op={n:d.club,en:(d.clubEn||'').toUpperCase(),col:d.col};
    const L=d.ha==='A'?op:ars, R=d.ha==='A'?ars:op;
    const tm=t=>'<div class="tm"><div class="bd" style="background:'+t.col+';'+(t.col.toUpperCase()==='#FFFFFF'?'box-shadow:inset 0 0 0 2px #CFC6B6':'')+'"></div><b class="tn">'+e(t.n)+'</b><small>'+e(t.en)+'</small></div>';
    const show=d.sc&&!d.ns, rc=d.r==='W'?['勝利','#DB0007']:d.r==='L'?['敗戦','#555555']:['引き分け','#8A6D1F'];
    h='<div class="main"><span class="pill"><b>MATCH</b>'+e(d.comp)+' · '+e(d.d.replace(/-/g,'/'))+(d.ha?' · '+(d.ha==='H'?'ホーム':'アウェイ'):'')+'</span>'+
      '<div class="vs">'+tm(L)+'<div class="sc'+(show?'':' q')+'">'+(show?d.sc.split('-').map(e).join('<i>–</i>'):'VS')+'</div>'+tm(R)+'</div>'+
      '<div class="row">'+(show?'<span class="res" style="background:'+rc[1]+'">'+rc[0]+'</span><span class="sub">スタッツと関連ポストまとめ</span>':
        d.sc?'<span class="res" style="background:#17140F">スコアは伏せています</span><span class="sub">スタッツと関連ポストまとめ</span>':'<span class="sub">試合情報と関連ポストまとめ</span>')+'</div></div>';
  } else {
    h='<div class="ac" style="background:#DB0007"></div><div class="main"><span class="pill"><b>PROFILE</b>'+e(d.g)+'</span>'+
      '<div class="mid"><div class="nm" id="nm" style="font-size:124px">'+e(d.name)+'</div><div class="en" id="en">'+e(d.en)+'</div></div>'+
      '<div class="row"><span class="sub">ニュース・移籍・スタッツ・関連ポストをまとめて</span></div></div>';
  }
  c.innerHTML=h+foot();
  document.querySelectorAll('#nm,#en').forEach(x=>fit(x,1056));
  document.querySelectorAll('.tn').forEach(x=>fit(x,x.parentNode.clientWidth));
}
</script></body></html>"""


TPLV = hashlib.sha1((TEMPLATE + LOGO).encode()).hexdigest()[:6]  # デザインを変えたら全部描き直し、画像のURLも変わる


def serve():
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = partial(Q, directory=ROOT)
    s = socketserver.TCPServer(('127.0.0.1', 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def page(slug, title, desc, img, target):
    """共有ページ。クローラーにはメタタグを見せ、人はすぐサイトの該当ページへ移す。"""
    url = SITE + 's/' + slug + '.html'
    imgu = SITE + ('s/img/' + img if img else 'og.png')
    t, d = escape(title), escape(desc)
    tgt = '../' + target
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="{escape(SITE + target)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Arsenal News Archive">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{escape(url)}">
<meta property="og:image" content="{escape(imgu)}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@gooner1031">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{escape(imgu)}">
<meta http-equiv="refresh" content="0;url={escape(tgt)}">
<script>location.replace({json.dumps(tgt)});</script>
<style>body{{margin:0;padding:40px 20px;font-family:system-ui,sans-serif;background:#F5F0E6;color:#17140F;text-align:center}}a{{color:#DB0007;font-weight:700}}</style>
</head><body><p>{t}</p><p><a href="{escape(tgt)}">Arsenal News Archive で開く →</a></p></body></html>
"""


def items(data):
    """(slug, 種類, カードの中身, タイトル, 説明, 画像を作るか, 移動先)"""
    for r in data['tr']:
        verb = '加入' if r['dir'] == 'IN' else '退団'
        yield (f"tr-{r['i']}-{r['w']}", 'tr', {k: r[k] for k in ('name', 'en', 'win', 'dir', 'stl', 'col', 'steps', 'k', 'dead', 'club', 'fee')},
               f"【移籍トラッカー】{r['name']}の{verb}：{r['stl']}",
               f"{r['name']}（{r['en']}）・{r['win']}の移籍市場。報道{r['n']}件を時系列でまとめています。Arsenal News Archive",
               r['img'], f"#tr-{r['i']}-{r['w']}")
    for m in data['m']:
        ttl = ('アーセナル vs ' if m['ha'] == 'H' else '' if m['ha'] == 'A' else 'vs ') + m['club'] + (' vs アーセナル' if m['ha'] == 'A' else '')
        d = m['d'].replace('-', '/')
        res = {'W': '勝利', 'L': '敗戦', 'D': '引き分け'}.get(m['r'], '')
        base = {k: m[k] for k in ('d', 'club', 'clubEn', 'ha', 'sc', 'r', 'comp', 'col', 'fg')}
        yield (f"match-{m['id']}", 'm', dict(base, ns=False),
               f"{d} {ttl}" + (f" {m['sc']}（{res}）" if m['sc'] else ''),
               f"{m['comp']}・{d}。スタッツと関連ポスト{m['n']}件をまとめています。Arsenal News Archive", m['img'], f"#match-{m['id']}")
        if m['sc']:
            yield (f"match-{m['id']}-ns", 'm', dict(base, ns=True),
                   f"{d} {ttl}（スコアは伏せています）",
                   f"{m['comp']}・{d}。結果はリンク先で。スタッツと関連ポストをまとめています。Arsenal News Archive", m['img'], f"#match-{m['id']}")
    for p in data['p']:
        yield (f"person-{p['i']}", 'p', {k: p[k] for k in ('name', 'en', 'g')},
               f"{p['name']}（{p['en']}）｜Arsenal News Archive",
               f"{p['name']}に関するポスト{p['n']}件・プロフィール・スタッツをまとめています。", p['img'], f"#person-{p['i']}")


def shrink(png):
    """平坦な色のカードなので、色数を減らしてファイルを小さくする。"""
    try:
        from PIL import Image
    except ImportError:
        return png
    im = Image.open(io.BytesIO(png)).convert('RGB').quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); return b.getvalue()


def main():
    os.makedirs(IMG, exist_ok=True)
    mf = os.path.join(OUT, 'cards.json')
    try:
        old = json.load(open(mf, encoding='utf-8'))
    except Exception:
        old = {}
    srv = serve(); base = f'http://127.0.0.1:{srv.server_address[1]}/'
    allow = lambda u: u.startswith(base) or 'fonts.googleapis.com' in u or 'fonts.gstatic.com' in u
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=os.environ.get('CHROME') or None)
        ctx = b.new_context(viewport={'width': 1200, 'height': 630})
        ctx.route('**/*', lambda r: r.continue_() if allow(r.request.url) else r.abort())
        pg = ctx.new_page()
        pg.goto(base + '#transfers')
        pg.wait_for_function("typeof POSTS!=='undefined'&&POSTS.length>5000&&typeof TRI!=='undefined'&&TRI&&META", timeout=60000)
        pg.wait_for_load_state('networkidle'); pg.wait_for_timeout(500)
        data = pg.evaluate(EXTRACT)
        cp = ctx.new_page()
        cp.set_content(TEMPLATE.replace('__LOGO__', json.dumps(LOGO)), wait_until='networkidle')
        cp.evaluate("document.fonts.ready")
        man, keep, drawn = {}, set(), 0
        for slug, kind, card, title, desc, mk, target in items(data):
            img = None
            if mk:
                h = hashlib.sha1((TPLV + json.dumps([kind, card], ensure_ascii=False, sort_keys=True)).encode()).hexdigest()[:10]
                img = f'{slug}.{h}.png'; man[slug] = h; keep.add(img)
                if FORCE or old.get(slug) != h or not os.path.exists(os.path.join(IMG, img)):
                    cp.evaluate('([k,d])=>render(k,d)', [kind, card])
                    cp.evaluate("document.fonts.ready")
                    png = cp.locator('#c').screenshot(type='png')
                    open(os.path.join(IMG, img), 'wb').write(shrink(png)); drawn += 1
            keep.add(slug + '.html')
            with open(os.path.join(OUT, slug + '.html'), 'w', encoding='utf-8') as f:
                f.write(page(slug, title, desc, img, target))
        b.close()
    srv.shutdown()
    # 使われなくなったページ・画像を消す
    removed = 0
    for d in (OUT, IMG):
        for fn in os.listdir(d):
            if (fn.endswith('.html') or fn.endswith('.png')) and fn not in keep:
                os.remove(os.path.join(d, fn)); removed += 1
    with open(mf, 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, sort_keys=True, indent=0)
    print(f'pages={len([k for k in keep if k.endswith(".html")])} images={len(man)} drawn={drawn} removed={removed}')


if __name__ == '__main__':
    main()
