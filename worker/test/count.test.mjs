// アクセス数のテスト。node --test test/ で実行
import test from 'node:test';
import assert from 'node:assert/strict';
import * as C from '../src/count.js';
import { makeEnv, installCaches } from './local.mjs';

installCaches(false);
const worker = (await import('../src/index.js')).default;
const ORIGIN = 'https://gooner1031.github.io';
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';
const UA2 = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
const realFetch = globalThis.fetch;
function gc(body, ok) { let n = 0; globalThis.fetch = async () => { n++; return new Response(body, { status: ok === false ? 500 : 200 }); }; return () => n; }
const req = (ip, ua) => new Request('https://x/api/hit', { method: 'POST', headers: { 'cf-connecting-ip': ip, 'user-agent': ua === undefined ? UA : ua } });
const at = s => Date.parse(s + '+09:00');

test('日付は日本時間の0時区切り', () => {
  assert.equal(C.jstDay(Date.parse('2026-11-28T14:59:59Z')), '2026-11-28');
  assert.equal(C.jstDay(Date.parse('2026-11-28T15:00:00Z')), '2026-11-29');
});

test('自動アクセスの判別と画面名の形', () => {
  for (const u of ['', 'curl/8.5.0', 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)', 'Twitterbot/1.0', 'Mozilla/5.0 (X11; Linux x86_64) HeadlessChrome/120.0.0.0 Safari/537.36', 'python-requests/2.31.0', 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)', 'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)']) assert.equal(C.isBot(u), true, u);
  for (const u of [UA, UA2, 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Twitter for iPhone/11.40', 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36']) assert.equal(C.isBot(u), false, u);
  assert.equal(C.validPath('player-12'), true); assert.equal(C.validPath('day-2026-11-25'), true);
  assert.equal(C.validPath(''), false); assert.equal(C.validPath('a b'), false); assert.equal(C.validPath('x'.repeat(61)), false); assert.equal(C.validPath(3), false);
});

test('訪問者は1日1人、閲覧数は画面ごと。累計は切り替え前の数を引き継ぐ', async () => {
  const env = makeEnv(), calls = gc('{"count_unique":"27 606", "count":"27 606"}');
  const t = at('2026-11-28T10:00');
  let r = await C.hit(req('1.1.1.1'), env, null, { p: 'home' }, t);
  assert.deepEqual([r.counted, r.today, r.total.v, r.base], [true, { u: 1, v: 1 }, 27607, true]);
  await C.hit(req('1.1.1.1'), env, null, { p: 'latest' }, t + 1000);
  await C.hit(req('1.1.1.1', UA2), env, null, { p: 'home' }, t + 2000);   // 同じ回線の別のブラウザは別の人
  await C.hit(req('2.2.2.2'), env, null, { p: 'home' }, t + 3000);
  r = await C.count(env, t + 4000);
  assert.deepEqual([r.d, r.today, r.total, r.since], ['2026-11-28', { u: 3, v: 4 }, { v: 27610, u: 3 }, C.jstDay(Date.now())]);
  assert.equal(calls(), 1);   // 切り替え前の累計は1回だけ取りに行く
  // 翌日（日本時間0時すぎ）：同じ人もその日の訪問者として数え直す
  await C.hit(req('1.1.1.1'), env, null, { p: 'home' }, at('2026-11-29T00:00') + 5000);
  r = await C.count(env, at('2026-11-29T00:01'));
  assert.deepEqual([r.d, r.today, r.total], ['2026-11-29', { u: 1, v: 1 }, { v: 27611, u: 4 }]);
  // 印に IP は残さない
  const rows = env.raw.prepare('SELECT k FROM cseen').all();
  assert.ok(rows.length === 4 && rows.every(x => /^[0-9a-f]{24}$/.test(x.k)));
  globalThis.fetch = realFetch;
});

test('自動アクセス・おかしな画面名は数えない。同じ人の閲覧数には上限がある', async () => {
  const env = makeEnv(); gc('{"count":"100"}');
  const t = at('2026-11-28T10:00');
  assert.equal((await C.hit(req('1.1.1.1', 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'), env, null, { p: 'home' }, t)).counted, false);
  assert.equal((await C.hit(req('1.1.1.1'), env, null, { p: '<script>' }, t)).counted, false);
  assert.equal((await C.hit(req('1.1.1.1'), env, null, null, t)).counted, false);
  for (let i = 0; i < C.VIEW_CAP + 20; i++) await C.hit(req('3.3.3.3'), env, null, { p: 'home' }, t + i);
  const r = await C.count(env, t + 9999);
  assert.deepEqual([r.today, r.total.v], [{ u: 1, v: C.VIEW_CAP }, 100 + C.VIEW_CAP]);
  globalThis.fetch = realFetch;
});

test('切り替え前の累計が取れない間は base=false。取れたら引き継ぐ', async () => {
  const env = makeEnv(); gc('', false);
  const t = at('2026-11-28T10:00');
  let r = await C.hit(req('1.1.1.1'), env, null, { p: 'home' }, t);
  assert.deepEqual([r.counted, r.base], [true, false]);
  gc('{"count":"5 000"}');
  r = await C.count(env, t + 1000);
  assert.deepEqual([r.base, r.total.v], [true, 5001]);
  globalThis.fetch = realFetch;
});

test('2日より前の印は消す', async () => {
  const env = makeEnv(); gc('{"count":"0"}');
  await C.hit(req('1.1.1.1'), env, null, { p: 'home' }, at('2026-11-25T12:00'));
  await C.hit(req('1.1.1.1'), env, null, { p: 'home' }, at('2026-11-27T12:00'));
  await C.hit(req('1.1.1.1'), env, null, { p: 'home' }, at('2026-11-28T12:00'));
  assert.deepEqual(env.raw.prepare('SELECT d FROM cseen ORDER BY d').all().map(x => x.d), ['2026-11-27', '2026-11-28']);
  assert.equal(env.raw.prepare('SELECT COUNT(*) AS n FROM cday').get().n, 3);   // 日ごとの数は残す
  globalThis.fetch = realFetch;
});

test('サーバー経由：サイト以外からの送信は受け付けない。/api/count は誰でも読める', async () => {
  const env = makeEnv(); gc('{"count":"10"}');
  const call = (method, path, origin, body) => worker.fetch(new Request('https://x' + path, { method, headers: { ...(origin ? { origin } : {}), 'cf-connecting-ip': '9.9.9.9', 'user-agent': UA, 'content-type': 'text/plain;charset=UTF-8' }, body }), env, { waitUntil() {} });
  assert.equal((await call('POST', '/api/hit', 'https://evil.example', '{"p":"home"}')).status, 403);
  const r = await call('POST', '/api/hit', ORIGIN, '{"p":"home"}');
  assert.equal(r.status, 200); assert.equal(r.headers.get('access-control-allow-origin'), ORIGIN);
  const j = await r.json(); assert.deepEqual([j.counted, j.today, j.total.v], [true, { u: 1, v: 1 }, 11]);
  const c = await (await call('GET', '/api/count', ORIGIN)).json();
  assert.deepEqual([c.today, c.total.v], [{ u: 1, v: 1 }, 11]);
  globalThis.fetch = realFetch;
});
