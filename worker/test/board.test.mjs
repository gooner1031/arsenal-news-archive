// 掲示板のテスト。node --test test/ で実行（依存なし。D1 は Node の SQLite で代用）
import test from 'node:test';
import assert from 'node:assert/strict';
import * as L from '../src/logic.js';
import { readFileSync } from 'node:fs';
import { makeEnv, installCaches } from './local.mjs';

installCaches(false);
const worker = (await import('../src/index.js')).default;
const ORIGIN = 'https://gooner1031.github.io', KEY = 'local-admin-key-0000';
const dev = n => 'device-' + String(n).padStart(12, '0');
function api(env) {
  const call = async (method, path, body, ip, origin) => {
    const r = await worker.fetch(new Request('https://x' + path, { method, headers: { origin: origin === undefined ? ORIGIN : origin, 'cf-connecting-ip': ip || '10.0.0.1', 'content-type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }), env, { waitUntil() {} });
    return { status: r.status, ...(await r.json()) };
  };
  return { get: (p, ip) => call('GET', p, null, ip), post: (p, b, ip, o) => call('POST', '/api/board/' + p, b, ip, o), adm: (b, ip) => call('POST', '/api/board/admin', { key: KEY, ...b }, ip || '10.9.9.9') };
}
const pollIn = { act: 'new', kind: 'poll', tag: 'transfer', title: '補強してほしいポジションは？', opts: [{ ja: '左ウイング', en: 'Left wing' }, { ja: 'CF' }, { ja: '中盤' }] };

test('自動チェック：普通の感想は即公開、暴言・連絡先・連打は確認待ち、リンクとなりすましは受け付けない', () => {
  const ok = ['ウーデゴールの反応、あれがキャプテン。', '勝ったばかりだけど次が大事', 'サカを生かす形が見たい', '守備が崩れなかった', 'Great win, Raya solid again. Grapes of wrath!', '移籍金は100000000ポンドらしい', '2026-11-27の試合'];
  for (const s of ok) assert.deepEqual([s, L.bCheck('N5', s).st], [s, 0]);
  const wait = ['審判 死 ね', 'あいつは無能', 'このクズが', 'バ カ', 'he is a fucking disgrace', 'kill yourself', '090-1234-5678 に連絡して', 'LINE ID は abc123 です', 'ああああああああああああああああああ', '副業で稼げます'];
  for (const s of wait) assert.deepEqual([s, L.bCheck('', s).st], [s, 1]);
  assert.equal(L.bCheck('', 'https://example.com 見て').ok, false);
  assert.equal(L.bCheck('', 'example.com を見て').ok, false);
  assert.equal(L.bCheck('管理人', 'こんにちは').ok, false);
  assert.equal(L.bCheck('グナ島', 'こんにちは').ok, false);
  assert.equal(L.bCheck('Ａdmin', 'hello').ok, false);
  assert.equal(L.bCheck('管理人', 'こんにちは', true).st, 0);
  assert.equal(L.bCheck('', 'ｈｔｔｐｓ：／／ｅｘａｍｐｌｅ．ｃｏｍ').ok, false);
  assert.equal(L.bCheck('', 'ＦＵＣＫ').st, 1);
  assert.equal(L.bCheck('', 'ほんとに？！（笑）').body, 'ほんとに？！（笑）');           // 全角の記号は書いたまま残す
  assert.equal(L.bCheck('', '   ').ok, false);
  assert.equal(L.bCheck('', 'あ'.repeat(201)).ok, false);
  assert.equal(L.bCheck('', '😀'.repeat(200)).ok, true);
  assert.equal(L.bCheck('あ'.repeat(21), 'x').ok, false);
});

test('管理人キー：なければ管理の操作はできない。5回間違えた回線は締め出す', async () => {
  const env = makeEnv(), A = api(env);
  assert.equal((await A.post('admin', { key: 'wrong', act: 'new', title: 'x' }, '10.1.1.1')).status, 401);
  assert.equal((await A.get('/api/board')).threads.length, 0);
  for (let i = 0; i < 4; i++) await A.post('admin', { key: 'wrong' + i, act: 'check' }, '10.1.1.1');
  assert.equal((await A.post('admin', { key: KEY, act: 'check' }, '10.1.1.1')).status, 429);   // 正しいキーでも締め出し中
  assert.equal((await A.post('admin', { key: KEY, act: 'check' }, '10.1.1.2')).ok, true);       // 別の回線は通る
  assert.equal((await api(makeEnv({ ADMIN_KEY: 'short' })).post('admin', { key: 'short', act: 'check' })).status, 503);
  assert.equal((await api(makeEnv({ ADMIN_KEY: '' })).post('admin', { key: '', act: 'check' })).status, 503);
  assert.equal(L.bKeyEq('abc', 'abc'), true); assert.equal(L.bKeyEq('abc', 'abd'), false); assert.equal(L.bKeyEq('abc', 'abcd'), false);
});

test('サイト以外からの送信は断る', async () => {
  const A = api(makeEnv());
  assert.equal((await A.post('admin', { key: KEY, act: 'check' }, '10.0.0.1', 'https://evil.example')).status, 403);
});

test('スレッド作成 → 一覧 → コメント → 連投制限 → 確認待ち → 管理人が公開', async () => {
  const env = makeEnv(), A = api(env);
  const t = (await A.adm({ act: 'new', kind: 'talk', tag: 'match', title: 'ドルトムント戦の感想', titleEn: 'Dortmund thoughts', pin: 1 })).id;
  assert.ok(t > 0);
  let ls = (await A.get('/api/board')).threads;
  assert.deepEqual([ls.length, ls[0].title, ls[0].titleEn, ls[0].pin, ls[0].nc], [1, 'ドルトムント戦の感想', 'Dortmund thoughts', true, 0]);

  const p1 = await A.post('post', { t, dev: dev(1), name: 'N5', body: 'ラヤ今日も安定' }, '10.0.0.1');
  assert.deepEqual([p1.ok, p1.st], [true, 0]);
  assert.equal((await A.post('post', { t, dev: dev(1), body: 'もう1件' }, '10.0.0.1')).status, 429);        // 同じ端末は1分に1件
  assert.equal((await A.post('post', { t, dev: dev(2), body: '別の端末・同じ回線' }, '10.0.0.1')).status, 429);
  assert.equal((await A.post('post', { t, dev: dev(3), body: 'ラヤ今日も安定' }, '10.0.0.3')).ok, true);
  const bad = await A.post('post', { t, dev: dev(4), body: '審判は無能' }, '10.0.0.4');
  assert.deepEqual([bad.ok, bad.st], [true, 1]);

  let th = await A.get('/api/board/t?id=' + t + '&dev=' + dev(4));
  assert.deepEqual(th.coms.map(c => c.body), ['ラヤ今日も安定', 'ラヤ今日も安定']);     // 確認待ちはほかの人に見えない
  assert.deepEqual(th.wait.map(c => c.body), ['審判は無能']);                             // 書いた本人には「確認中」で見える
  assert.equal(th.coms[0].dev, undefined); assert.equal(th.coms[0].iph, undefined);       // 端末の番号・回線の印は外に出さない
  assert.equal((await A.get('/api/board')).threads[0].nc, 2);

  const q = (await A.adm({ act: 'queue' })).queue;
  assert.deepEqual([q.length, q[0].why, q[0].st], [1, 'ng', 1]);
  await A.adm({ act: 'com', c: q[0].id, to: 'ok' });
  th = await A.get('/api/board/t?id=' + t);
  assert.equal(th.coms.length, 3);
  await A.adm({ act: 'com', c: q[0].id, to: 'del' });
  assert.equal((await A.get('/api/board/t?id=' + t)).coms.length, 2);

  const say = await A.adm({ act: 'say', t, dev: dev(9), name: 'グナ島', body: 'ありがとうございます https://example.com' });
  assert.deepEqual([say.ok, say.com.adm], [true, true]);                                  // 管理人は名前・リンクの制限なし、印が付く
  assert.equal((await A.get('/api/board/t?id=' + t)).coms[0].adm, true);
});

test('通報：別の回線から3件で自動的に非表示。管理人が戻したら、もう隠さない', async () => {
  const env = makeEnv(), A = api(env);
  const t = (await A.adm({ act: 'new', title: '雑談' })).id;
  const c = (await A.post('post', { t, dev: dev(1), body: 'ふつうの感想です' }, '10.0.0.1')).com.id;
  assert.equal((await A.post('report', { c, dev: dev(1) }, '10.0.0.1')).status, 400);     // 自分のは通報できない
  await A.post('report', { c, dev: dev(2) }, '10.0.0.2');
  await A.post('report', { c, dev: dev(2) }, '10.0.0.2');                                  // 同じ端末は1件
  await A.post('report', { c, dev: dev(3) }, '10.0.0.2');                                  // 同じ回線も1件
  await A.post('report', { c, dev: dev(4) }, '10.0.0.4');
  assert.equal((await A.get('/api/board/t?id=' + t)).coms.length, 1);
  await A.post('report', { c, dev: dev(5) }, '10.0.0.5');
  assert.equal((await A.get('/api/board/t?id=' + t)).coms.length, 0);
  assert.equal((await A.get('/api/board')).threads[0].nc, 0);
  assert.deepEqual((await A.adm({ act: 'queue' })).queue.map(x => [x.st, x.rep]), [[2, 3]]);
  await A.adm({ act: 'com', c, to: 'ok' });
  await A.post('report', { c, dev: dev(6) }, '10.0.0.6');
  assert.equal((await A.get('/api/board/t?id=' + t)).coms.length, 1);
  assert.equal((await A.adm({ act: 'queue' })).queue.length, 0);
});

test('書き込み禁止：削除と同時に端末と回線を止められる', async () => {
  const env = makeEnv(), A = api(env);
  const t = (await A.adm({ act: 'new', title: '雑談' })).id;
  const c = (await A.post('post', { t, dev: dev(1), body: 'あらし' }, '10.0.0.1')).com.id;
  await A.adm({ act: 'com', c, to: 'del', ban: 1 });
  env.DB.prepare('UPDATE bcom SET ts = 0').run();
  assert.equal((await A.post('post', { t, dev: dev(1), body: 'また来た' }, '10.0.0.7')).status, 403);   // 同じ端末・別の回線
  assert.equal((await A.post('post', { t, dev: dev(8), body: 'また来た' }, '10.0.0.1')).status, 403);   // 別の端末・同じ回線
  assert.equal((await A.post('post', { t, dev: dev(8), body: '無関係の人' }, '10.0.0.8')).ok, true);
});

test('アンケート：1端末1票・変更可、結果は投票した人だけ、締切後は誰でも見られて投票は不可', async () => {
  const env = makeEnv(), A = api(env);
  assert.equal((await A.adm({ ...pollIn, opts: [{ ja: 'ひとつだけ' }] })).status, 400);
  assert.equal((await A.adm({ ...pollIn, close: Date.now() - 1 })).status, 400);
  const t = (await A.adm({ ...pollIn, close: Date.now() + 3600e3 })).id;
  let th = await A.get('/api/board/t?id=' + t + '&dev=' + dev(1));
  assert.deepEqual([th.poll.open, th.poll.mine, th.poll.c, th.poll.opts[0].en], [true, null, null, 'Left wing']);
  let v = await A.post('vote', { t, dev: dev(1), o: 0 }, '10.0.0.1');
  assert.deepEqual([v.poll.mine, v.poll.n, v.poll.c], [0, 1, [1, 0, 0]]);
  await A.post('vote', { t, dev: dev(2), o: 1 }, '10.0.0.2');
  v = await A.post('vote', { t, dev: dev(1), o: 2 }, '10.0.0.1');                          // 入れ直しは上書き
  assert.deepEqual([v.poll.n, v.poll.c], [2, [0, 1, 1]]);
  assert.equal((await A.post('vote', { t, dev: dev(3), o: 3 }, '10.0.0.3')).status, 400);
  th = await A.get('/api/board/t?id=' + t + '&dev=' + dev(9));
  assert.deepEqual([th.poll.n, th.poll.c], [2, null]);                                      // 未投票の人には票数だけ
  assert.equal((await A.get('/api/board')).threads[0].nv, 2);
  env.DB.prepare('UPDATE bthread SET close = 1').run();
  th = await A.get('/api/board/t?id=' + t + '&dev=' + dev(9));
  assert.deepEqual([th.poll.open, th.poll.c], [false, [0, 1, 1]]);
  assert.equal((await A.post('vote', { t, dev: dev(9), o: 0 }, '10.0.0.9')).status, 409);
});

test('アンケート「結果は締切後に公開」：投票しても締切まで結果は出ない', async () => {
  const env = makeEnv(), A = api(env);
  const t = (await A.adm({ ...pollIn, late: 1, close: Date.now() + 3600e3 })).id;
  const v = await A.post('vote', { t, dev: dev(1), o: 0 }, '10.0.0.1');
  assert.deepEqual([v.poll.mine, v.poll.n, v.poll.c], [0, 1, null]);
});

test('スレッドの締め切り・削除、同じ回線からの大量投票の制限', async () => {
  const env = makeEnv(), A = api(env);
  const t = (await A.adm({ ...pollIn })).id;
  for (let i = 1; i <= L.IP_CAP; i++) assert.equal((await A.post('vote', { t, dev: dev(i), o: 0 }, '10.0.0.1')).ok, true);
  assert.equal((await A.post('vote', { t, dev: dev(99), o: 0 }, '10.0.0.1')).status, 429);
  await A.adm({ act: 'thread', id: t, set: 'locked', val: 1 });
  assert.equal((await A.post('post', { t, dev: dev(50), body: '締め切り後' }, '10.0.0.50')).status, 409);
  assert.equal((await A.post('vote', { t, dev: dev(50), o: 0 }, '10.0.0.50')).status, 409);
  await A.adm({ act: 'thread', id: t, set: 'del', val: 1 });
  assert.equal((await A.get('/api/board')).threads.length, 0);
  assert.equal((await A.get('/api/board/t?id=' + t)).status, 404);
});

test('コメントは30件ずつ、古い分は before で続きを読む', async () => {
  const env = makeEnv(), A = api(env);
  const t = (await A.adm({ act: 'new', title: '雑談' })).id;
  for (let i = 1; i <= 35; i++) assert.equal((await A.post('post', { t, dev: dev(i), body: 'コメント' + i }, '10.0.1.' + i)).ok, true);
  const a = await A.get('/api/board/t?id=' + t);
  assert.deepEqual([a.coms.length, a.more, a.coms[0].body], [30, true, 'コメント35']);
  const b = await A.get('/api/board/t?id=' + t + '&before=' + a.coms[29].id);
  assert.deepEqual([b.coms.length, b.more, b.coms[4].body], [5, false, 'コメント1']);
});

test('誰でもスレッドを立てられる：10分に1件・1日5件まで、固定や英語の文は管理人だけ', async () => {
  const env = makeEnv(), A = api(env);
  const adm = (await A.adm({ act: 'new', title: '管理人のスレッド' })).id;
  const r = await A.post('new', { dev: dev(1), kind: 'talk', tag: 'match', title: '今日の試合どうだった？', body: '感想をどうぞ', pin: 1, nocom: 1, titleEn: 'x' }, '10.0.0.1');
  assert.deepEqual([r.ok, r.hold], [true, false]);
  const ls = (await A.get('/api/board')).threads;
  assert.deepEqual(ls.map(t => [t.title, t.adm, t.pin, t.nocom, t.titleEn]), [['今日の試合どうだった？', false, false, false, ''], ['管理人のスレッド', true, false, false, '']]);
  assert.equal(adm > 0, true);
  assert.equal((await A.post('new', { dev: dev(1), title: 'もう1本' }, '10.0.0.1')).status, 429);         // 10分あける
  assert.equal((await A.post('new', { dev: dev(2), title: '別の端末・同じ回線' }, '10.0.0.1')).status, 429);
  assert.equal((await A.post('new', { dev: dev(3), title: '今日の試合どうだった？' }, '10.0.0.3')).status, 409);  // 同じタイトル
  assert.equal((await A.post('new', { dev: dev(3), title: '見て https://example.com' }, '10.0.0.3')).status, 400);
  assert.equal((await A.post('new', { dev: dev(3), title: '【管理人】お知らせ' }, '10.0.0.3')).status, 400);
  assert.equal((await A.post('new', { dev: dev(3), title: '' }, '10.0.0.3')).status, 400);
  assert.equal((await A.post('new', { dev: dev(3), kind: 'poll', title: '誰がMVP？', opts: [{ ja: 'サカ', en: 'Saka' }, { ja: 'ライス' }] }, '10.0.0.3')).ok, true);
  assert.equal((await A.get('/api/board/t?id=3')).poll.opts[0].en, '');
  for (let i = 0; i < L.B_T_DAY - 1; i++) { env.DB.prepare('UPDATE bown SET ts = ts - ? WHERE dev = ?').bind(11 * 60e3, dev(1)).run(); assert.equal((await A.post('new', { dev: dev(1), title: '追加' + i }, '10.0.0.1')).ok, true); }
  env.DB.prepare('UPDATE bown SET ts = ts - ? WHERE dev = ?').bind(11 * 60e3, dev(1)).run();
  assert.equal((await A.post('new', { dev: dev(1), title: '上限の次' }, '10.0.0.1')).status, 429);           // 1日5件まで
});

test('スレッドの自動チェック：引っかかったものは本人にだけ見え、管理人が公開すると一覧に出る', async () => {
  const env = makeEnv(), A = api(env);
  const r = await A.post('new', { dev: dev(1), kind: 'poll', title: '一番ひどかった選手は？', opts: [{ ja: 'あの無能' }, { ja: 'ほか' }] }, '10.0.0.1');
  assert.deepEqual([r.ok, r.hold], [true, true]);                                         // 選択肢の中の言葉も見る
  assert.equal((await A.get('/api/board')).threads.length, 0);
  assert.equal((await A.get('/api/board/t?id=' + r.id + '&dev=' + dev(2))).status, 404);
  const mine = await A.get('/api/board/t?id=' + r.id + '&dev=' + dev(1));
  assert.deepEqual([mine.t.hold, mine.t.mine], [true, true]);
  assert.equal((await A.post('post', { t: r.id, dev: dev(2), body: 'こんにちは' }, '10.0.0.2')).status, 404);   // 確認待ちの間は書き込めない
  assert.equal((await A.post('vote', { t: r.id, dev: dev(2), o: 0 }, '10.0.0.2')).status, 404);
  const q = (await A.adm({ act: 'queue' })).tqueue;
  assert.deepEqual(q.map(x => [x.id, x.del, x.why]), [[r.id, 2, 'ng']]);
  await A.adm({ act: 'tq', id: r.id, to: 'ok' });
  assert.equal((await A.get('/api/board')).threads.length, 1);
  assert.equal((await A.adm({ act: 'queue' })).tqueue.length, 0);
});

test('スレッドの通報：別の回線から3件で非表示。管理人のスレッドは対象外。削除＋書き込み禁止', async () => {
  const env = makeEnv(), A = api(env);
  const adm = (await A.adm({ act: 'new', title: '管理人のスレッド' })).id;
  const t = (await A.post('new', { dev: dev(1), title: 'ふつうのスレッド' }, '10.0.0.1')).id;
  assert.equal((await A.post('report', { t, dev: dev(1) }, '10.0.0.1')).status, 400);
  for (let i = 2; i <= 4; i++) { await A.post('report', { t: adm, dev: dev(i) }, '10.0.0.' + i); await A.post('report', { t, dev: dev(i) }, '10.0.0.' + i); }
  assert.deepEqual((await A.get('/api/board')).threads.map(x => x.id), [adm]);
  assert.deepEqual((await A.adm({ act: 'queue' })).tqueue.map(x => [x.id, x.del, x.why, x.rep]), [[t, 2, 'rep', 3]]);
  await A.adm({ act: 'tq', id: t, to: 'ok' });
  await A.post('report', { t, dev: dev(5) }, '10.0.0.5');
  assert.equal((await A.get('/api/board')).threads.length, 2);                              // 確認済みはもう隠さない
  await A.adm({ act: 'tq', id: t, to: 'del', ban: 1 });
  assert.equal((await A.get('/api/board/t?id=' + t + '&dev=' + dev(1))).status, 404);
  env.DB.prepare('UPDATE bown SET ts = 0').run();
  assert.equal((await A.post('new', { dev: dev(1), title: 'また立てる' }, '10.0.0.9')).status, 403);
  assert.equal((await A.post('post', { t: adm, dev: dev(8), body: '同じ回線' }, '10.0.0.1')).status, 403);
});

test('返信：同じスレッドの公開中のコメントにだけ付けられ、返信先の名前と本文の先頭が付く', async () => {
  const env = makeEnv(), A = api(env);
  const t = (await A.adm({ act: 'new', title: '雑談' })).id, t2 = (await A.adm({ act: 'new', title: '別のスレッド' })).id;
  const a = (await A.post('post', { t, dev: dev(1), name: 'N5', body: 'ラヤ今日も安定。' + 'クリーンシートは素直にうれしいし、後ろからのつなぎも落ち着いていた。次のチャンピオンズリーグでも同じ形で入ってほしいと思う。' }, '10.0.0.1')).com.id;
  const other = (await A.post('post', { t: t2, dev: dev(2), body: '別のスレッドのコメント' }, '10.0.0.2')).com.id;
  const r = await A.post('post', { t, dev: dev(3), name: '赤白', body: '同感です', re: a }, '10.0.0.3');
  assert.deepEqual([r.ok, r.com.re.id, r.com.re.name, [...r.com.re.body].length], [true, a, 'N5', 61]);   // 60文字＋「…」
  assert.equal((await A.post('post', { t, dev: dev(4), body: '別スレへの返信', re: other }, '10.0.0.4')).status, 404);
  assert.equal((await A.post('post', { t, dev: dev(4), body: 'ない番号', re: 9999 }, '10.0.0.4')).status, 404);
  assert.equal((await A.post('post', { t, dev: dev(4), body: '変な値', re: 'x' }, '10.0.0.4')).status, 400);
  let th = await A.get('/api/board/t?id=' + t);
  assert.deepEqual(th.coms.map(c => [c.body.slice(0, 4), c.re ? c.re.id : null, c.re ? c.re.name : null]), [['同感です', a, 'N5'], ['ラヤ今日', null, null]]);
  assert.equal(th.coms[0].re.dev, undefined);
  const adm = await A.adm({ act: 'say', t, dev: dev(9), body: '管理人からも', re: r.com.id });
  assert.deepEqual([adm.com.re.id, adm.com.re.name], [r.com.id, '赤白']);
  await A.adm({ act: 'com', c: a, to: 'del' });                                            // 返信先が消えたら中身は出さない
  th = await A.get('/api/board/t?id=' + t);
  assert.deepEqual(th.coms.find(c => c.id === r.com.id).re, { id: a, gone: true });
  assert.equal((await A.post('post', { t, dev: dev(5), body: '消えたコメントへ', re: a }, '10.0.0.5')).status, 404);
});

test('最初から置いておくスレッド（seed.sql）：何度実行しても増えず、消したものは復活しない', async () => {
  const env = makeEnv(), A = api(env), seed = readFileSync(new URL('../seed.sql', import.meta.url), 'utf8');
  env.raw.exec(seed); env.raw.exec(seed);
  let ls = (await A.get('/api/board')).threads;
  assert.equal(ls.length, 6);
  assert.deepEqual([ls[0].title, ls[0].pin, ls.every(t => t.adm), ls.every(t => t.titleEn)], ['はじめに：掲示板の使い方', true, true, true]);
  assert.ok(/シティ戦/.test(ls[1].title));
  for (const t of ls) {
    const th = await A.get('/api/board/t?id=' + t.id);
    assert.ok(th.t.body.length > 10 && th.t.bodyEn.length > 10);
    assert.equal(L.bThreadIn({ kind: t.kind, tag: t.tag, title: t.title, titleEn: t.titleEn, body: th.t.body, bodyEn: th.t.bodyEn, opts: th.poll ? th.poll.opts : undefined, close: t.close || undefined }, Date.parse('2026-11-28T00:00:00Z'), true).err, undefined);   // 管理画面から立てるときと同じ決まりに収まる
    if (th.poll) assert.ok(th.poll.open && th.poll.opts.every(o => o.ja && o.en));
  }
  const intro = await A.get('/api/board/t?id=' + ls[0].id);
  assert.ok(/\n/.test(intro.t.body) && /健全/.test(intro.t.body));
  // お手本コメント：5件・すべて管理人・200文字以内・自動チェックにかからない・返信の引用が2件。2回実行しても増えない
  assert.deepEqual([intro.coms.length, ls[0].nc, intro.coms.every(c => c.adm && [...c.body].length <= 200 && !L.bScan(c.body)), intro.coms.filter(c => c.re && /デモ①/.test(c.re.body)).length], [5, 5, true, 2]);
  await A.adm({ act: 'thread', id: ls[5].id, set: 'del', val: 1 });
  env.raw.exec(seed);
  assert.equal((await A.get('/api/board')).threads.length, 5);
  assert.equal((await A.post('post', { t: ls[1].id, dev: dev(1), body: '楽しみ' }, '10.0.0.1')).ok, true);
});
