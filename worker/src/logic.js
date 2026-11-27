// 集計のルール（サーバーとテストで共通）。D1 や fetch には触らない純粋な関数だけを置く。

export const PRED_OPEN = 24 * 3600e3;    // 予想はキックオフのこの時間前から
export const FT_AFTER = 115 * 60e3;      // キックオフからこの時間で「試合終了」とみなす
export const RATE_HOURS = 12;            // 採点・MOTM の受付時間（試合終了から）
export const EDIT_WINDOW = 3600e3;       // 直せるのは最初の送信から1時間以内
export const EDIT_MAX = 1;               // 直せる回数
export const MIN_SHOW = 3;               // 採点がこの票数未満の選手は平均を出さない
export const OUTLIER = 3;                // 中央値からこの点数以上離れた票は除外
export const FLAT_MIN = 5;               // この人数以上に全員同じ点を付けた採点は丸ごと除外
export const MANAGER = 'Mikel Arteta';  // 採点の対象に加える監督（MOTMには入れない）
export const IP_CAP = 20;                // 同じ回線から1試合で受け付ける端末数

export function phase(ko, now) {
  if (!ko) return { pred: 'none', rate: 'none' };
  const ft = ko + FT_AFTER, close = ft + RATE_HOURS * 3600e3;
  return {
    pred: now < ko - PRED_OPEN ? 'early' : now < ko ? 'open' : 'closed',
    opens: ko - PRED_OPEN,
    rate: now < ft ? 'before' : now < close ? 'open' : 'closed',
    ft, close,
  };
}

export const validScore = n => Number.isInteger(n) && n >= 0 && n <= 9;
export const validRating = v => typeof v === 'number' && v >= 1 && v <= 10 && Number.isInteger(v * 2);
export const validName = s => typeof s === 'string' && s.length > 0 && s.length <= 60;
export const validDev = s => typeof s === 'string' && /^[A-Za-z0-9-]{16,64}$/.test(s);
export const validMatch = s => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s);

// 直せるかどうか：最初の送信から1時間以内、かつ直した回数が上限未満
export function canEdit(row, now) {
  if (!row) return true;
  return (row.edits || 0) < EDIT_MAX && now - row.first <= EDIT_WINDOW;
}

export function median(a) {
  const s = a.slice().sort((x, y) => x - y), n = s.length;
  if (!n) return null;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

// 採点の集計。ballots = [{player: 点数, ...}, ...]
export function aggRatings(ballots) {
  const per = {}, flat = {};
  let used = 0;
  for (const b of ballots) {
    const vals = Object.values(b);
    const isFlat = vals.length >= FLAT_MIN && vals.every(v => v === vals[0]);
    if (!isFlat) used++;
    for (const [p, v] of Object.entries(b)) {
      if (isFlat) { flat[p] = (flat[p] || 0) + 1; continue; }
      (per[p] = per[p] || []).push(v);
    }
  }
  const out = {};
  const names = new Set([...Object.keys(per), ...Object.keys(flat)]);
  for (const p of names) {
    const vs = per[p] || [], md = median(vs);
    const kept = md == null ? [] : vs.filter(v => Math.abs(v - md) < OUTLIER);
    const n = vs.length + (flat[p] || 0), ex = n - kept.length;
    const mean = kept.length >= MIN_SHOW ? kept.reduce((s, v) => s + v, 0) / kept.length : null;
    out[p] = { avg: mean == null ? null : Math.round(mean * 10) / 10, n, ex, raw: mean == null ? null : Math.round(mean * 1000) / 1000 };
  }
  return { n: ballots.length, used, players: out };
}

// MOTM：1位3点・2位2点・3位1点。同点は1位票、次に2位票の多い方が上
export function aggMotm(rows) {
  const t = {};
  const add = (p, k) => { if (!p) return; const x = t[p] = t[p] || { p, pts: 0, r1: 0, r2: 0, r3: 0 }; x.pts += 4 - k; x['r' + k]++; };
  for (const r of rows) { add(r.p1, 1); add(r.p2, 2); add(r.p3, 3); }
  const rank = Object.values(t).sort((a, b) => b.pts - a.pts || b.r1 - a.r1 || b.r2 - a.r2 || a.p.localeCompare(b.p));
  return { n: rows.length, rank };
}

// 予想の集計。rows = [{h, a, s:[names]}]。final = {h, a, scorers:[names]}（試合後のみ）
export function aggPred(rows, final) {
  const sc = {}, pk = {};
  for (const r of rows) {
    const k = r.h + '-' + r.a; sc[k] = (sc[k] || 0) + 1;
    for (const p of r.s || []) pk[p] = (pk[p] || 0) + 1;
  }
  const top = Object.entries(sc).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).slice(0, 5);
  const picks = Object.entries(pk).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).slice(0, 8);
  const out = { n: rows.length, top, picks };
  if (final) {
    const S = new Set(final.scorers || []);
    const res = x => Math.sign(x.h - x.a);
    const withS = rows.filter(r => (r.s || []).length);
    out.res = {
      exact: rows.filter(r => r.h === final.h && r.a === final.a).length,
      outcome: rows.filter(r => res(r) === res(final)).length,
      scorerN: withS.length,
      scorer: withS.filter(r => r.s.some(p => S.has(p))).length,
      scorers: [...S],
      sc: final.h + '-' + final.a,
    };
    // 当たった得点者の印（選んだ人数の上位に、実際の得点者も必ず入れる）
    for (const p of S) if (pk[p] && !picks.some(x => x[0] === p)) picks.push([p, pk[p]]);
  }
  return out;
}

// 発表済みのメンバー（スタメン11人＋ベンチ）。まだ発表されていなければ null。ここに入らない選手は得点者予想の候補から外す
export function squadOf(lu, m) {
  if (!lu || lu.d !== m || !Array.isArray(lu.xi) || lu.xi.length !== 11 || !Array.isArray(lu.bench) || !lu.bench.length) return null;
  return [...lu.xi, ...lu.bench];
}

// matchstats.json の1試合から結果（アーセナル側のスコアが先）と得点者を取り出す
export function finalOf(ms) {
  if (!ms || !ms.sc || !/^\d+-\d+$/.test(ms.sc)) return null;
  const [h, a] = ms.sc.split('-').map(Number);
  const scorers = [...new Set((ms.goals || []).filter(g => g.t === 'A' && g.p).map(g => g.p))];
  return { h, a, scorers };
}

// 採点の対象選手：試合データ（スタメン＋途中出場）があればそれ、なければ発表されたスタメン＋ベンチ
export function playersOf(ms, lu, m) {
  if (ms && ms.xi && ms.xi.length) return { src: 'stats', list: [...ms.xi, ...(ms.subs || []).map(s => s.on).filter(Boolean), MANAGER] };
  if (lu && lu.d === m && lu.xi && lu.xi.length) return { src: 'lineup', list: [...lu.xi, ...(lu.bench || []), MANAGER] };
  return { src: 'none', list: [] };
}

// ---- シーズン通算 ----
// サッカーのシーズン（8月〜翌7月）。サイトの sYear と同じ区切り
export const seasonOf = m => +m.slice(5, 7) >= 8 ? +m.slice(0, 4) : +m.slice(0, 4) - 1;
export const seasonRange = y => [y + '-08-01', (y + 1) + '-07-31'];

// 1試合分をシーズン通算用に縮める。採点は平均が出た選手だけ（3票以上）、MOTMは3人以上が投票した試合の上位3人
export function seasonMatch(m, o, rateRows, motmRows) {
  const R = aggRatings(rateRows), M = aggMotm(motmRows), r = {};
  for (const [p, x] of Object.entries(R.players)) if (x.raw != null) r[p] = x.raw;
  return { m, o: o || '', n: R.n, r, mn: M.n, top: M.n >= MIN_SHOW ? M.rank.slice(0, 3).map(x => x.p) : [] };
}

// シーズン通算の集計（サイト側と同じ計算。サイトはネタバレ防止中の試合を除いてから同じことをする）
//   選手の平均 = 平均が出た試合ごとの平均を、1試合1票として平均（試合ごとの人数の差で偏らないように）
//   全体平均 = 全試合・全選手（監督を除く）の試合ごとの平均をすべて平均
//   みんなのMOTM = 試合ごとの1位の回数（同数は2位、3位の回数の多い方が上）
export function aggSeason(list) {
  const P = {}, all = [];
  for (const x of list) {
    for (const [p, v] of Object.entries(x.r || {})) {
      const t = P[p] = P[p] || { p, sum: 0, n: 0, m1: 0, m2: 0, m3: 0 };
      t.sum += v; t.n++;
      if (p !== MANAGER) all.push(v);
    }
    (x.top || []).forEach((p, k) => { const t = P[p] = P[p] || { p, sum: 0, n: 0, m1: 0, m2: 0, m3: 0 }; t['m' + (k + 1)]++; });
  }
  const r1 = v => Math.round(v * 100) / 100;
  const players = Object.values(P).filter(t => t.n).map(t => ({ p: t.p, avg: r1(t.sum / t.n), n: t.n })).sort((a, b) => b.avg - a.avg || b.n - a.n || a.p.localeCompare(b.p));
  const motm = Object.values(P).filter(t => t.m1 + t.m2 + t.m3).map(t => ({ p: t.p, m1: t.m1, m2: t.m2, m3: t.m3 })).sort((a, b) => b.m1 - a.m1 || b.m2 - a.m2 || b.m3 - a.m3 || a.p.localeCompare(b.p));
  return {
    matches: list.filter(x => Object.keys(x.r || {}).length).length,
    motmMatches: list.filter(x => (x.top || []).length).length,
    overall: all.length ? r1(all.reduce((s, v) => s + v, 0) / all.length) : null,
    cells: all.length, players, motm,
  };
}

// ===== 掲示板（スレッド・コメント・アンケート）の判定 =====
export const B_BODY_MAX = 200;           // コメントの文字数
export const B_NAME_MAX = 20;            // ニックネームの文字数
export const B_GAP = 60e3;               // 同じ端末・回線の連投はこの間隔をあける
export const B_DAY_MAX = 40;             // 同じ回線から1日に受け付けるコメント数
export const B_REPORTS = 3;              // 通報がこの件数（別の端末・回線）で自動的に非表示
export const B_PAGE = 30;                // 1回に返すコメント数
export const B_TAGS = ['talk', 'match', 'transfer', 'site'];
export const B_KEY_MIN = 16;             // 管理人キーの最低文字数
export const B_TRY_MAX = 5;              // 管理人キーを間違えられる回数（B_TRY_WIN の間）
export const B_TRY_WIN = 15 * 60e3;

const chars = s => [...s].length;
// 保存する形：制御文字・見えない文字を消し、行末の空白と3行以上の空行を詰める（全角の「？」「！」はそのまま残す）
export function bClean(s, oneLine) {
  if (typeof s !== 'string') return '';
  let t = s.normalize('NFC').replace(/[\u0000-\u0009\u000B-\u001F\u007F​-‏‪-‮⁠-⁩﻿]/g, '');
  t = oneLine ? t.replace(/\s+/g, ' ') : t.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n');
  return t.trim();
}
// 照合用：空白・記号を抜き、カタカナ→ひらがな、小文字にする（「死 ね」「シ.ネ」のような崩しに当てる）
export function bFold(s) {
  return bClean(s, true).normalize('NFKC').toLowerCase().replace(/[ァ-ヶ]/g, c => String.fromCharCode(c.charCodeAt(0) - 0x60))
    .replace(/[\s\p{P}\p{S}ー〜~_]/gu, '');
}
const B_LINK = /(https?:\/\/|www\.|[a-z0-9-]+\.(com|net|org|jp|io|co|me|ly|tv|cc|xyz|info|biz|shop|site|link|app|gg)(?![a-z]))/i;
// 確認待ちに回す言葉。足すときはここに。
// B_NG = 崩した書き方（空白・記号入り、カタカナ/ひらがな違い）にも当てる言葉（bFold 後の形で照合）
export const B_NG = [
  '死ね', '氏ね', 'タヒね', '殺す', 'ころす', '殺して', '消えろ', 'くたばれ', '自殺しろ',
  '無能', 'ばか', '馬鹿', 'まぬけ', 'きもい', 'きしょい', 'うざい', 'がいじ', '池沼', '障害者', 'きちがい', '基地外',
  '八百長', '詐欺', '犯罪者', '晒す', '晒し', '住所', '特定した', '土人', 'くろんぼ', 'にがー', 'おかま',
].map(w => bFold(w));
// 普通の言葉に含まれてしまうもの（「勝ったばかり」など）は照合の前に抜く
const B_NG_SAFE = ['ばかり', 'ばかし', 'ばかで', 'おおばか'].slice(0, 2).map(w => bFold(w));
// B_NG_RAW = カタカナのまま書かれたときだけ当てる短い言葉（ひらがなだと「生かす」「崩れ」などに当たるため）
const B_NG_RAW = /(カス|クズ|ゴミ|バカ|アホ|ホモ野郎|シネ(?![ァ-ヶー])|しね[よ。！!]*$)/m;
// 英語は単語の区切りで当てる（grape / skys などに当たらないように）
const B_NG_EN = /\b(fuck\w*|shit\w*|cunts?|bitch(es)?|bastards?|wankers?|twats?|retard(ed|s)?|nigg\w+|fagg?ots?|paki|monkeys?|kys|kill\s+yourself|rap(e|ist)|nonces?)\b/i;
const B_CONTACT = /((?<!\d)0\d{1,3}[-\s]?\d{2,4}[-\s]?\d{3,4}(?!\d)|[\w.+-]+@[\w-]+\.[a-z]{2,}|line\s*id|ライン\s*id|dm\s*ください|稼げ|副業|儲か|無料で配|当選しました)/i;
const B_ADMIN_NAME = /(管理人|管理者|かんりにん|運営|公式|ぐな島|ぐなしま|gooner1031|admin|official|moderator)/;

// コメントの判定。{ok:false, err} は受け付けない（直せば送れる）、{ok:true, st, why} は st=0 即公開 / 1 確認待ち
export function bCheck(nameRaw, bodyRaw, isAdmin) {
  const name = bClean(nameRaw || '', true), body = bClean(bodyRaw || '', false);
  if (!body) return { ok: false, err: 'コメントを入力してください' };
  if (chars(body) > B_BODY_MAX) return { ok: false, err: 'コメントは' + B_BODY_MAX + '文字までです' };
  if (chars(name) > B_NAME_MAX) return { ok: false, err: 'ニックネームは' + B_NAME_MAX + '文字までです' };
  if (body.split('\n').length > 8) return { ok: false, err: '改行が多すぎます' };
  if (isAdmin) return { ok: true, st: 0, why: '', name, body };
  if (B_ADMIN_NAME.test(bFold(name))) return { ok: false, err: 'そのニックネームは使えません' };
  const raw = (name + '\n' + body).normalize('NFKC');   // 判定は全角英数を半角にそろえてから
  if (B_LINK.test(raw)) return { ok: false, err: 'リンクは貼れません' };
  let f = bFold(name + ' ' + body);
  for (const w of B_NG_SAFE) f = f.split(w).join('');
  const ng = B_NG.some(w => f.includes(w)) || B_NG_RAW.test(raw) || B_NG_EN.test(raw);
  if (ng) return { ok: true, st: 1, why: 'ng', name, body };
  if (B_CONTACT.test(raw)) return { ok: true, st: 1, why: 'contact', name, body };
  if (/(.)\1{14,}/u.test(raw) || /(.{2,10})\1{5,}/u.test(raw)) return { ok: true, st: 1, why: 'repeat', name, body };
  return { ok: true, st: 0, why: '', name, body };
}

// スレッド作成の入力を確かめて整える。opts はアンケートの選択肢 [{ja, en}]
export function bThreadIn(b, now) {
  const kind = b.kind === 'poll' ? 'poll' : 'talk', tag = B_TAGS.includes(b.tag) ? b.tag : 'talk';
  const title = bClean(b.title || '', true), titleEn = bClean(b.titleEn || '', true);
  const body = bClean(b.body || '', false), bodyEn = bClean(b.bodyEn || '', false);
  if (!title || chars(title) > 80 || chars(titleEn) > 120) return { err: 'タイトルは1〜80文字です' };
  if (chars(body) > 400 || chars(bodyEn) > 600) return { err: '説明は400文字までです' };
  let opts = null, close = null;
  if (kind === 'poll') {
    opts = (Array.isArray(b.opts) ? b.opts : []).map(o => ({ ja: bClean((o && o.ja) || '', true), en: bClean((o && o.en) || '', true) })).filter(o => o.ja);
    if (opts.length < 2 || opts.length > 8) return { err: '選択肢は2〜8個です' };
    if (!opts.every(o => chars(o.ja) <= 40 && chars(o.en) <= 60)) return { err: '選択肢は40文字までです' };
    if (new Set(opts.map(o => o.ja)).size !== opts.length) return { err: '同じ選択肢があります' };
    if (b.close != null && b.close !== '') {
      close = +b.close;
      if (!Number.isFinite(close) || close <= now || close > now + 366 * 864e5) return { err: '締切は今より後の日時にしてください' };
    }
  }
  return { kind, tag, title, titleEn, body, bodyEn, opts, close, pin: b.pin ? 1 : 0, nocom: b.nocom ? 1 : 0, late: kind === 'poll' && b.late ? 1 : 0 };
}

export const bPollOpen = (t, now) => t.kind === 'poll' && !t.locked && !t.del && (!t.close || now < t.close);
// アンケートの結果を見せてよいか：締切後は誰でも。受付中は投票した人だけ（「結果は締切後に公開」なら締切まで見せない）
export function bPollShow(t, voted, now) {
  if (!bPollOpen(t, now)) return true;
  return !t.late && !!voted;
}
export function bPollAgg(n, rows) {
  const c = Array.from({ length: n }, () => 0);
  for (const r of rows) if (Number.isInteger(r.o) && r.o >= 0 && r.o < n) c[r.o] += r.n || 0;
  return { n: c.reduce((a, b) => a + b, 0), c };
}
// 管理人キーの照合（長さの違いも含めて時間差が出ないように）
export function bKeyEq(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  let d = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) d |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return d === 0;
}
