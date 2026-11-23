// Arsenal News Archive「次の試合」ウィジェット（iPhone の無料アプリ Scriptable 用）
// 使い方：https://gooner1031.github.io/arsenal-news-archive/widget.html
// ・ホーム画面（小・中）とロック画面のウィジェットに対応
// ・ウィジェットの Parameter に en と入れると英語表示
// ・スコアは表示しません（ネタバレなし）
const SITE = 'https://gooner1031.github.io/arsenal-news-archive/';
const EN = String(args.widgetParameter || '').trim().toLowerCase() === 'en';
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
    const g = new LinearGradient(); g.colors = [RED, RED_D]; g.locations = [0.45, 1]; g.startPoint = new Point(0, 0); g.endPoint = new Point(1, 1);
    w.backgroundGradient = g; w.setPadding(12, 14, 12, 14);
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

const widget = await build();
if (config.runsInWidget) Script.setWidget(widget);
else await widget.presentMedium();
Script.complete();
