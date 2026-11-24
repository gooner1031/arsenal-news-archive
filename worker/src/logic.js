// 集計のルール（サーバーとテストで共通）。D1 や fetch には触らない純粋な関数だけを置く。

export const PRED_OPEN = 24 * 3600e3;    // 予想はキックオフのこの時間前から
export const FT_AFTER = 115 * 60e3;      // キックオフからこの時間で「試合終了」とみなす
export const RATE_HOURS = 12;            // 採点・MOTM の受付時間（試合終了から）
export const EDIT_WINDOW = 3600e3;       // 直せるのは最初の送信から1時間以内
export const EDIT_MAX = 1;               // 直せる回数
export const MIN_SHOW = 10;              // これ未満の票では平均・率を出さない
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
    const avg = kept.length >= MIN_SHOW ? Math.round(kept.reduce((s, v) => s + v, 0) / kept.length * 10) / 10 : null;
    out[p] = { avg, n, ex };
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
