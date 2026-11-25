// node --test worker/test/  で実行（依存なし）
import test from 'node:test';
import assert from 'node:assert/strict';
import * as L from '../src/logic.js';

test('外れ値（中央値から3点以上）と全員同じ点の採点を除いて平均する', () => {
  const B = [];
  for (let i = 0; i < 12; i++) B.push({ Saka: 7 + (i % 3) * 0.5, Rice: 6.5 });
  B.push({ Saka: 1, Rice: 6.5 });                                  // サカだけ極端に低い → サカの票だけ除外
  B.push({ Saka: 10, Rice: 10, A: 10, B: 10, C: 10 });              // 5人全員10点 → 丸ごと除外
  const r = L.aggRatings(B);
  assert.equal(r.n, 14);
  assert.equal(r.players.Saka.n, 14);
  assert.equal(r.players.Saka.ex, 2);
  assert.equal(r.players.Saka.avg, 7.5);
  assert.equal(r.players.Rice.avg, 6.5);
  assert.equal(r.players.A.avg, null);                              // 有効な票がなければ出さない
});

test('採点の平均は3票から出す', () => {
  assert.equal(L.aggRatings([{ X: 6 }, { X: 7 }]).players.X.avg, null);
  assert.equal(L.aggRatings([{ X: 6 }, { X: 7 }, { X: 8 }]).players.X.avg, 7);
});

test('中央値ちょうど3点差は除外、2.5点差は残す', () => {
  const B = Array.from({ length: 10 }, () => ({ X: 6 }));
  B.push({ X: 9 }, { X: 8.5 });
  const r = L.aggRatings(B);
  assert.equal(r.players.X.ex, 1);
  assert.equal(r.players.X.avg, Math.round((60 + 8.5) / 11 * 10) / 10);
});

test('MOTM は 3-2-1 点、同点は1位票の多い方が上', () => {
  const r = L.aggMotm([
    { p1: 'Eze', p2: 'Rice', p3: 'Saka' },
    { p1: 'Rice', p2: 'Saka', p3: 'Eze' },
    { p1: 'Saka', p2: 'Eze', p3: 'Rice' },
    { p1: 'Eze', p2: 'Saka', p3: 'Rice' },
  ]);
  assert.deepEqual(r.rank.map(x => [x.p, x.pts]), [['Eze', 9], ['Saka', 8], ['Rice', 7]]);
  const t = L.aggMotm([{ p1: 'A', p2: 'B', p3: 'C' }, { p1: 'B', p2: 'C', p3: 'D' }, { p1: 'D', p2: 'C', p3: 'A' }]);
  // A=3+1=4、B=2+3=5、C=1+2+2=5、D=1+3=4 → 同点は1位票の多い方：B(1)>C(0)、A(1)=D(1) は2位票も0同士 → 名前順
  assert.deepEqual(t.rank.map(x => x.p), ['B', 'C', 'A', 'D']);
});

test('予想の的中：スコア・勝敗・得点者（1人以上）', () => {
  const rows = [
    { h: 2, a: 2, s: ['Eze'] }, { h: 1, a: 2, s: ['Havertz'] }, { h: 3, a: 3, s: [] }, { h: 2, a: 1, s: ['Madueke', 'Saka'] },
  ];
  const r = L.aggPred(rows, { h: 2, a: 2, scorers: ['Eze', 'Madueke'] });
  assert.equal(r.res.exact, 1);
  assert.equal(r.res.outcome, 2);
  assert.equal(r.res.scorerN, 3);
  assert.equal(r.res.scorer, 2);
  assert.equal(r.top[0][1], 1);
});

test('受付時間：キックオフ24時間前から予想、キックオフで締切、試合終了から12時間が採点', () => {
  const ko = Date.UTC(2026, 10, 24, 20);
  assert.equal(L.phase(ko, ko - 24 * 3600e3 - 1).pred, 'early');
  assert.equal(L.phase(ko, ko - 24 * 3600e3).pred, 'open');
  assert.equal(L.phase(ko, ko).opens, ko - 24 * 3600e3);
  assert.equal(L.phase(ko, ko - 1).pred, 'open');
  assert.equal(L.phase(ko, ko).pred, 'closed');
  assert.equal(L.phase(ko, ko + 60 * 60e3).rate, 'before');
  assert.equal(L.phase(ko, ko + L.FT_AFTER).rate, 'open');
  assert.equal(L.phase(ko, ko + L.FT_AFTER + 12 * 3600e3 - 1).rate, 'open');
  assert.equal(L.phase(ko, ko + L.FT_AFTER + 12 * 3600e3).rate, 'closed');
});

test('直しは最初の送信から1時間以内に1回だけ', () => {
  const t = 1e12;
  assert.equal(L.canEdit(null, t), true);
  assert.equal(L.canEdit({ first: t, edits: 0 }, t + 3599e3), true);
  assert.equal(L.canEdit({ first: t, edits: 0 }, t + 3601e3), false);
  assert.equal(L.canEdit({ first: t, edits: 1 }, t + 60e3), false);
});

test('点数は1〜10の0.5刻み', () => {
  assert.ok(L.validRating(1) && L.validRating(10) && L.validRating(6.5));
  assert.ok(!L.validRating(0.5) && !L.validRating(10.5) && !L.validRating(6.3) && !L.validRating('7'));
});

test('得点者の候補：スタメン11人＋ベンチが発表されたらそれだけ', () => {
  const xi = Array.from({ length: 11 }, (_, i) => 'P' + i);
  assert.equal(L.squadOf(null, 'x'), null);
  assert.equal(L.squadOf({ d: 'x', xi: xi.slice(0, 10), bench: ['B'] }, 'x'), null);
  assert.equal(L.squadOf({ d: 'x', xi, bench: [] }, 'x'), null);
  assert.equal(L.squadOf({ d: 'y', xi, bench: ['B'] }, 'x'), null);
  assert.deepEqual(L.squadOf({ d: 'x', xi, bench: ['B', 'C'] }, 'x'), [...xi, 'B', 'C']);
});

test('試合データから結果と出場選手を取り出す', () => {
  const ms = { sc: '2-2', goals: [{ t: 'A', p: 'Eze' }, { t: 'O', p: 'Barnes' }, { t: 'A', p: 'Madueke' }], xi: ['A', 'B'], subs: [{ on: 'C', off: 'A' }] };
  assert.deepEqual(L.finalOf(ms), { h: 2, a: 2, scorers: ['Eze', 'Madueke'] });
  assert.deepEqual(L.playersOf(ms, null, 'x').list, ['A', 'B', 'C', L.MANAGER]);  // 最後に監督
  assert.deepEqual(L.playersOf(null, { d: 'x', xi: ['A'], bench: ['Z'] }, 'x'), { src: 'lineup', list: ['A', 'Z', L.MANAGER] });
});

test('シーズン通算：試合ごとの平均を1試合1票で平均し、MOTMは1位の回数で並べる', () => {
  const g = (n, v) => Array.from({ length: n }, () => v);
  const m1 = L.seasonMatch('2026-09-06', 'チェルシー',
    [...g(10, { Saka: 8, Rice: 7, 'Mikel Arteta': 9 }), { Saka: 7, Rice: 7 }],
    [...g(4, { p1: 'Saka', p2: 'Rice', p3: 'Odegaard' })]);
  assert.equal(m1.r.Saka, Math.round(87 / 11 * 1000) / 1000);
  assert.deepEqual(m1.top, ['Saka', 'Rice', 'Odegaard']);
  const m2 = L.seasonMatch('2026-09-13', '', [{ Saka: 6 }, { Saka: 6 }, { Saka: 6 }, { Rice: 9 }, { Rice: 9 }], g(2, { p1: 'Rice', p2: 'Saka', p3: 'White' }));
  assert.equal(m2.r.Rice, undefined);              // 3票未満の選手は入れない
  assert.deepEqual(m2.top, []);                    // 投票が3人未満の試合はMOTMに数えない
  const m3 = L.seasonMatch('2026-09-20', '', g(3, { Rice: 8, Saka: 6 }), g(3, { p1: 'Rice', p2: 'Saka', p3: 'White' }));
  const s = L.aggSeason([m1, m2, m3]);
  assert.equal(s.matches, 3);
  assert.equal(s.motmMatches, 2);
  const saka = s.players.find(x => x.p === 'Saka');
  assert.equal(saka.n, 3);
  assert.equal(saka.avg, Math.round((m1.r.Saka + 6 + 6) / 3 * 100) / 100);
  assert.equal(s.cells, 5);                         // 監督は全体平均に入れない
  assert.equal(s.overall, Math.round((m1.r.Saka + 7 + 6 + 8 + 6) / 5 * 100) / 100);
  assert.equal(s.players.find(x => x.p === 'Mikel Arteta').avg, 9);
  assert.deepEqual(s.motm.map(x => [x.p, x.m1, x.m2, x.m3]), [['Rice', 1, 1, 0], ['Saka', 1, 1, 0], ['Odegaard', 0, 0, 1], ['White', 0, 0, 1]]);
});

test('シーズンの区切りは8月', () => {
  assert.equal(L.seasonOf('2026-08-01'), 2026);
  assert.equal(L.seasonOf('2027-07-31'), 2026);
  assert.deepEqual(L.seasonRange(2026), ['2026-08-01', '2027-07-31']);
});
