// Arsenal News Archive「次の試合」ウィジェット（iPhone の無料アプリ Scriptable 用）
// 使い方：https://gooner1031.github.io/arsenal-news-archive/widget.html
// ・ホーム画面（小・中）とロック画面のウィジェットに対応
// ・ウィジェットの Parameter に en と入れると英語表示
// ・Parameter に clear と入れると背景が透過風（壁紙を切り出して背景にする）。英語と一緒なら en,clear
//   準備：このスクリプトを Scriptable のアプリ内で実行 →「透過の背景を設定」
// ・スコアは表示しません（ネタバレなし）
const SITE = 'https://gooner1031.github.io/arsenal-news-archive/';
const OPT = String(args.widgetParameter || '').toLowerCase().split(/[\s,、，]+/).filter(Boolean);
const EN = OPT.includes('en');
const CLEAR = OPT.includes('clear');
const FAM = config.widgetFamily || 'medium';
const WDJ = ['日', '月', '火', '水', '木', '金', '土'], WDE = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const RED = new Color('#DB0007'), RED_D = new Color('#9C0006'), WHITE = Color.white(), GOLD = new Color('#FFE9A8');

// 日本時間で表示（端末のタイムゾーンに関係なく）
function jst(ms, wd) {
  const d = new Date(ms + 9 * 3600e3), mo = d.getUTCMonth() + 1, da = d.getUTCDate(), w = d.getUTCDay();
  const hm = String(d.getUTCHours()).padStart(2, '0') + ':' + String(d.getUTCMinutes()).padStart(2, '0');
  if (EN) return (wd === false ? '' : WDE[w] + ' ') + da + ' ' + MON[mo - 1] + ' ' + hm;
  return mo + '/' + da + (wd === false ? '' : '(' + WDJ[w] + ')') + ' ' + hm;
}
function dOnly(s) {
  const [y, m, d] = s.split('-').map(Number), w = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return EN ? WDE[w] + ' ' + d + ' ' + MON[m - 1] : m + '/' + d + '(' + WDJ[w] + ')';
}
function until(ms) {
  const s = Math.floor((ms - Date.now()) / 1000);
  if (s <= 0) return EN ? 'Kicked off' : 'キックオフ済み';
  const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
  if (EN) return 'in ' + (d ? d + 'd ' : '') + (d || h ? h + 'h' : m + 'm');
  return 'あと' + (d ? d + '日' : '') + (d || h ? h + '時間' : m + '分');
}

async function getData() {
  const fm = FileManager.local(), cache = fm.joinPath(fm.cacheDirectory(), 'ana-next.json');
  try {
    const r = new Request(SITE + 'next.json'); r.timeoutInterval = 15;
    const j = await r.loadJSON();
    if (j && j.matches) { fm.writeString(cache, JSON.stringify(j)); return j; }
  } catch (e) {}
  // 通信できないときは前回のデータで表示する
  if (fm.fileExists(cache)) { try { return JSON.parse(fm.readString(cache)); } catch (e) {} }
  return null;
}

function text(stack, s, size, opt) {
  const t = stack.addText(s); opt = opt || {};
  t.font = opt.weight === 'heavy' ? Font.heavySystemFont(size) : opt.weight === 'regular' ? Font.systemFont(size) : Font.boldSystemFont(size);
  t.textColor = opt.color || WHITE; t.lineLimit = opt.lines || 1; t.minimumScaleFactor = 0.6;
  // 透過のときは明るい壁紙でも読めるよう影を付ける
  if (CLEAR && !FAM.startsWith('accessory')) { t.shadowColor = new Color('#000000', 0.75); t.shadowRadius = 3; t.shadowOffset = new Point(0, 1); }
  if (opt.center) t.centerAlignText();
  return t;
}

async function build() {
  const data = await getData(), now = Date.now();
  const ms = data ? data.matches.filter(m => m.ko ? Date.parse(m.ko) + 2 * 3600e3 > now : Date.parse(m.d + 'T23:59:59Z') > now) : [];
  const w = new ListWidget();
  w.url = SITE + 'widget.html';
  const acc = FAM.startsWith('accessory');
  if (!acc) {
    const bg = CLEAR ? clearBg() : null;
    if (bg) w.backgroundImage = bg;
    else {
      const g = new LinearGradient(); g.colors = [RED, RED_D]; g.locations = [0.45, 1]; g.startPoint = new Point(0, 0); g.endPoint = new Point(1, 1);
      w.backgroundGradient = g;
    }
    w.setPadding(12, 14, 12, 14);
  }
  if (!ms.length) {
    text(w, data ? (EN ? 'No upcoming fixtures' : '今後の日程はまだありません') : (EN ? 'Could not load' : '読み込めませんでした'), 13, { lines: 2 });
    w.refreshAfterDate = new Date(now + 3 * 3600e3);
    return w;
  }
  const n = ms[0], opp = EN ? n.o_en : n.o, ha = n.ha === 'H' ? 'vs' : '@';
  const when = n.ko ? jst(Date.parse(n.ko)) : dOnly(n.d) + (EN ? ' TBC' : ' 時間未定');
  const comp = EN ? n.cs_en : n.cs;

  // ロック画面
  if (FAM === 'accessoryInline') { text(w, '⚽ ' + ha + ' ' + opp + ' ' + when, 12); return finish(w, n); }
  if (acc) {
    text(w, (EN ? 'NEXT · ' : '次の試合 · ') + comp, 11, { color: WHITE });
    text(w, ha + ' ' + opp, 14, { weight: 'heavy' });
    text(w, when + (n.ko ? (EN ? ' JST' : '') : ''), 12, { weight: 'regular' });
    return finish(w, n);
  }

  // ホーム画面（小・中・大）
  text(w, 'NEXT MATCH · ' + comp, 10, { color: GOLD });
  w.addSpacer(4);
  text(w, ha + ' ' + opp, FAM === 'small' ? 17 : 20, { weight: 'heavy', lines: 2 });
  text(w, n.ha === 'H' ? (EN ? 'Home' : 'ホーム') : (EN ? 'Away' : 'アウェイ'), 11, { weight: 'regular' });
  w.addSpacer(6);
  text(w, when, FAM === 'small' ? 15 : 17, { weight: 'heavy' });
  text(w, n.ko ? (EN ? 'Japan time · ' : '日本時間・') + until(Date.parse(n.ko)) : (EN ? 'Kick-off time TBC' : 'キックオフ時間は未定'), 11, { color: GOLD });
  if (FAM !== 'small') {
    const rest = ms.slice(1, FAM === 'large' ? 6 : 3);
    if (rest.length) {
      w.addSpacer(8);
      rest.forEach(m => {
        const s = (m.ko ? jst(Date.parse(m.ko), false) : dOnly(m.d)) + '  ' + (m.ha === 'H' ? 'vs ' : '@ ') + (EN ? m.o_en : m.o) + '（' + (EN ? m.cs_en : m.cs) + '）';
        text(w, s, 11, { weight: 'regular' });
      });
    }
  }
  w.addSpacer();
  return finish(w, n);
}
function finish(w, n) {
  // 次に描き直す時刻：キックオフが近いほど細かく（最短15分）。iOS の都合で多少遅れることがある
  const now = Date.now(), ko = n.ko ? Date.parse(n.ko) : now + 6 * 3600e3, left = ko - now;
  const next = left > 2 * 86400e3 ? 6 * 3600e3 : left > 3 * 3600e3 ? 1 * 3600e3 : 15 * 60e3;
  w.refreshAfterDate = new Date(now + next);
  return w;
}

// ---- 透過風の背景（壁紙の切り出し）
// iPhone は本当の透過ができないので、ホーム画面のスクショからウィジェットの位置を切り出して背景にする。
// 位置の表は mzeryck/Widget-Blur（MIT License, Copyright (c) 2022 Maxwell Zeryck）の値を使用。
// キーはスクショの高さ（px）。アイコンの名前を表示している標準の配置。
const PHONES = {
  2868: { small: 510, medium: 1092, large: 1146, left: 114, right: 696, top: 276, middle: 912, bottom: 1548 }, // 16 Pro Max など
  2796: { small: 510, medium: 1092, large: 1146, left: 98, right: 681, top: 252, middle: 888, bottom: 1524 },  // 16 Plus, 15 Plus, 15 Pro Max, 14 Pro Max
  2778: { small: 510, medium: 1092, large: 1146, left: 96, right: 678, top: 246, middle: 882, bottom: 1518 },  // 14 Plus, 13/12 Pro Max
  2688: { small: 507, medium: 1080, large: 1137, left: 81, right: 654, top: 228, middle: 858, bottom: 1488 },  // 11 Pro Max, XS Max
  2622: { small: 486, medium: 1032, large: 1098, left: 87, right: 633, top: 261, middle: 872, bottom: 1485 },  // 16 Pro など
  2556: { small: 474, medium: 1017, large: 1062, left: 81, right: 624, top: 240, middle: 828, bottom: 1416 },  // 16, 15, 15 Pro, 14 Pro
  2532: { small: 474, medium: 1014, large: 1062, left: 78, right: 618, top: 231, middle: 819, bottom: 1407 },  // 14, 13, 13 Pro, 12, 12 Pro
  2436: { small: 465, medium: 987, large: 1035, left: 69, right: 591, top: 231, middle: 801, bottom: 1371 },   // 13 mini, 12 mini（11 Pro, XS, X は上下が18px ずれることあり）
  2208: { small: 471, medium: 1044, large: 1071, left: 99, right: 672, top: 114, middle: 696, bottom: 1278 },  // ホームボタンの Plus
  1792: { small: 338, medium: 720, large: 758, left: 55, right: 437, top: 159, middle: 579, bottom: 999 },     // 11, XR
  1334: { small: 296, medium: 642, large: 648, left: 54, right: 400, top: 60, middle: 412, bottom: 764 },      // SE（第2・第3世代）, 8, 7
};
function bgPath(fam, mode) { const fm = FileManager.local(); return fm.joinPath(fm.documentsDirectory(), 'ana-widget-bg-' + fam + '-' + mode + '.jpg'); }
function clearBg() {
  const fm = FileManager.local(), fam = FAM === 'large' ? 'large' : FAM === 'small' ? 'small' : 'medium';
  // ライト/ダークは Parameter の light / dark で固定もできる（自動の切替が効かない端末向け）
  const mode = OPT.includes('dark') ? 'dark' : OPT.includes('light') ? 'light' : (Device.isUsingDarkAppearance() ? 'dark' : 'light');
  for (const m of [mode, mode === 'dark' ? 'light' : 'dark']) {
    const p = bgPath(fam, m);
    if (fm.fileExists(p)) return fm.readImage(p);
  }
  return null; // 未設定ならいつもの赤い背景
}
async function pick(title, msg, opts, cancel) {
  const a = new Alert(); a.title = title; if (msg) a.message = msg;
  opts.forEach(o => a.addAction(o)); a.addCancelAction(cancel || (EN ? 'Cancel' : 'キャンセル'));
  const i = await a.presentSheet(); return i < 0 ? -1 : i;
}
async function say(title, msg) { const a = new Alert(); a.title = title; a.message = msg; a.addAction('OK'); await a.present(); }
async function setupBg() {
  const ok = await pick(EN ? 'Transparent background' : '透過の背景を設定',
    EN ? 'First take a screenshot of an empty home-screen page: long-press the home screen until the icons jiggle, swipe to the empty page on the far right, and take the screenshot. Do it once in Light mode and once in Dark mode if you use both.'
       : '先にホーム画面のスクショを用意してください。ホーム画面を長押ししてアイコンが揺れている状態で、いちばん右の何もないページを撮ります。ライトとダークを両方使うなら、それぞれ1枚ずつ撮ってください。',
    [EN ? 'I have the screenshot' : 'スクショを用意した']);
  if (ok < 0) return;
  const md = await pick(EN ? 'Which appearance is this screenshot?' : 'どちらのスクショを使いますか', null, [EN ? 'Light mode' : 'ライトモード用', EN ? 'Dark mode' : 'ダークモード用']);
  if (md < 0) return;
  const img = await Photos.fromLibrary();
  const H = Math.round(img.size.height), P = PHONES[H];
  if (!P) { await say(EN ? 'Not supported' : 'この端末は未対応です', (EN ? 'Unknown screenshot height: ' : 'スクショの高さが表にありません：') + H + 'px'); return; }
  const fi = await pick(EN ? 'Widget size' : 'ウィジェットの大きさ', null, [EN ? 'Small' : '小', EN ? 'Medium' : '中', EN ? 'Large' : '大']);
  if (fi < 0) return;
  const fam = ['small', 'medium', 'large'][fi];
  let x, y, wd, ht;
  if (fam === 'small') {
    const names = EN ? ['Top left', 'Top right', 'Middle left', 'Middle right', 'Bottom left', 'Bottom right'] : ['上・左', '上・右', '真ん中・左', '真ん中・右', '下・左', '下・右'];
    const k = await pick(EN ? 'Where is the widget?' : 'ウィジェットの位置', null, names); if (k < 0) return;
    x = k % 2 ? P.right : P.left; y = [P.top, P.middle, P.bottom][Math.floor(k / 2)]; wd = ht = P.small;
  } else if (fam === 'medium') {
    const k = await pick(EN ? 'Where is the widget?' : 'ウィジェットの位置', null, EN ? ['Top', 'Middle', 'Bottom'] : ['上', '真ん中', '下']); if (k < 0) return;
    x = P.left; y = [P.top, P.middle, P.bottom][k]; wd = P.medium; ht = P.small;
  } else {
    const k = await pick(EN ? 'Where is the widget?' : 'ウィジェットの位置', null, EN ? ['Top', 'Bottom'] : ['上', '下']); if (k < 0) return;
    x = P.left; y = k ? P.middle : P.top; wd = P.medium; ht = P.large;
  }
  const dc = new DrawContext(); dc.size = new Size(wd, ht); dc.opaque = true;
  dc.drawImageAtPoint(img, new Point(-x, -y));
  const mode = md ? 'dark' : 'light';
  FileManager.local().writeImage(bgPath(fam, mode), dc.getImage());
  await say(EN ? 'Saved' : '保存しました',
    EN ? 'Long-press the widget → Edit Widget → set Parameter to clear (or en,clear). If you use both Light and Dark mode, run this setup again for the other one.'
       : 'ウィジェットを長押し →「ウィジェットを編集」→ Parameter に clear（英語なら en,clear）と入れてください。ライトとダークの両方を使う場合は、もう一方のスクショでもう一度設定してください。');
}
async function removeBg() {
  const fm = FileManager.local();
  ['small', 'medium', 'large'].forEach(f => ['light', 'dark'].forEach(m => { const p = bgPath(f, m); if (fm.fileExists(p)) fm.remove(p); }));
  await say(EN ? 'Removed' : '削除しました', EN ? 'The widget is back to the red background.' : 'ウィジェットは赤い背景に戻ります。');
}

if (config.runsInWidget) Script.setWidget(await build());
else {
  // アプリ内で実行したとき：プレビューか、透過の背景の設定
  const k = await pick('Arsenal News Archive', null, EN ? ['Preview widget', 'Set transparent background', 'Remove transparent background']
    : ['ウィジェットをプレビュー', '透過の背景を設定', '透過の背景を削除'], EN ? 'Close' : '閉じる');
  if (k === 0) await (await build()).presentMedium();
  else if (k === 1) await setupBg();
  else if (k === 2) await removeBg();
}
Script.complete();
