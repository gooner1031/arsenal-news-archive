// 掲示板（スレッド・コメント・アンケート）。スレッド・コメント・投票は誰でも（ログインなし）。固定・締め切り・削除は管理人だけ。
//   GET  /api/board                      スレッドの一覧（30秒ずつ使い回す）
//   GET  /api/board/t?id=&dev=&before=   スレッド1件：アンケート、公開中のコメント（新しい順 30件ずつ）、自分の確認待ち
//   POST /api/board/new    {dev, kind, tag, title, body, opts, close, late}   スレッドを立てる（誰でも。10分に1件・1日5件まで）
//   POST /api/board/post   {t, dev, name, body}   コメント。自動チェックを通れば即公開、引っかかれば確認待ち
//   POST /api/board/vote   {t, dev, o}            アンケートに投票（締切まで変更可）
//   POST /api/board/report {c, dev} / {t, dev}    コメント・スレッドの通報。別の回線から3件で自動的に非表示
//   POST /api/board/admin  {key, act, …}          管理人（Secrets の ADMIN_KEY と照合）
// 判定のルールは logic.js（bCheck など）。保存するのはニックネーム・本文・時刻・端末の番号・元に戻せない形にした IP だけ。
import * as L from './logic.js';

const CK = 'https://ana-vote.cache/';
const drop = (...keys) => Promise.all(keys.map(k => caches.default.delete(new Request(CK + k))));
async function cached(key, ttl, fn) {
  const c = caches.default, k = new Request(CK + key);
  const hit = await c.match(k);
  if (hit) return hit.json();
  const v = await fn();
  await c.put(k, new Response(JSON.stringify(v), { headers: { 'cache-control': 'public, max-age=' + ttl } }));
  return v;
}
const tRow = x => ({
  id: x.id, kind: x.kind, tag: x.tag || 'talk', title: x.title, titleEn: x.title_en || '', pin: !!x.pin, locked: !!x.locked, nocom: !!x.nocom,
  close: x.close || null, late: !!x.late, nc: x.nc || 0, nv: x.nv || 0, ts: x.ts, last: x.last || x.ts, adm: !x.own,
});
// スレッドと持ち主（own = 立てた端末。管理人が立てたものは null）
const TSEL = 'SELECT t.*, o.dev AS own, o.okd AS okd, o.why AS why FROM bthread t LEFT JOIN bown o ON o.t = t.id ';
const cRow = x => ({ id: x.id, name: x.name || '', body: x.body, adm: !!x.adm, ts: x.ts });
const validId = n => Number.isInteger(n) && n > 0;

async function recount(env, t) {
  await env.DB.prepare('UPDATE bthread SET nc = (SELECT COUNT(*) FROM bcom WHERE t = ?1 AND st = 0), last = COALESCE((SELECT MAX(ts) FROM bcom WHERE t = ?1 AND st = 0), ts) WHERE id = ?1').bind(t).run();
  await drop('board-list', 'board-t-' + t + '-0');
}

export async function list(env) {
  return cached('board-list', 30, async () => {
    const r = await env.DB.prepare(TSEL + 'WHERE t.del = 0 ORDER BY t.pin DESC, t.last DESC, t.id DESC LIMIT 100').all();
    return { now: Date.now(), threads: r.results.map(tRow) };
  });
}

async function pollState(env, t, dev, now, fresh) {
  const opts = JSON.parse(t.opts || '[]');
  const mine = dev ? await env.DB.prepare('SELECT o FROM bvote WHERE t = ? AND dev = ?').bind(t.id, dev).first() : null;
  const get = async () => L.bPollAgg(opts.length, (await env.DB.prepare('SELECT o, COUNT(*) AS n FROM bvote WHERE t = ? GROUP BY o').bind(t.id).all()).results);
  if (fresh) await drop('board-v-' + t.id);
  const agg = await cached('board-v-' + t.id, 15, get);
  const show = L.bPollShow(t, mine, now);
  return { opts, open: L.bPollOpen(t, now), close: t.close || null, late: !!t.late, mine: mine ? mine.o : null, n: agg.n, c: show ? agg.c : null };
}

export async function thread(env, id, dev, before) {
  // 確認待ち（del = 2）のスレッドは、立てた本人にだけ見える
  const t = await env.DB.prepare(TSEL + 'WHERE t.id = ? AND t.del != 1').bind(id).first();
  if (!t || (t.del === 2 && !(dev && t.own === dev))) return null;
  const now = Date.now();
  const page = await cached('board-t-' + id + '-' + (before || 0), 15, async () => {
    const q = before
      ? env.DB.prepare('SELECT id, name, body, adm, ts FROM bcom WHERE t = ? AND st = 0 AND id < ? ORDER BY id DESC LIMIT ?').bind(id, before, L.B_PAGE + 1)
      : env.DB.prepare('SELECT id, name, body, adm, ts FROM bcom WHERE t = ? AND st = 0 ORDER BY id DESC LIMIT ?').bind(id, L.B_PAGE + 1);
    const rows = (await q.all()).results;
    return { more: rows.length > L.B_PAGE, coms: rows.slice(0, L.B_PAGE).map(cRow) };
  });
  const out = { now, t: { ...tRow(t), body: t.body || '', bodyEn: t.body_en || '', hold: t.del === 2, mine: !!(dev && t.own === dev) }, ...page };
  if (t.kind === 'poll') out.poll = await pollState(env, t, dev, now);
  if (dev && !before) {
    const w = await env.DB.prepare('SELECT id, name, body, adm, ts FROM bcom WHERE t = ? AND dev = ? AND st = 1 ORDER BY id DESC LIMIT 5').bind(id, dev).all();
    out.wait = w.results.map(cRow);
  }
  return out;
}

const banned = async (env, dev, iph) => !!(await env.DB.prepare('SELECT k FROM bban WHERE k = ? OR k = ?').bind(dev, iph).first());

async function notify(env, ctx, msg) {
  if (!env.NTFY_TOPIC) return;
  const p = fetch('https://ntfy.sh/' + encodeURIComponent(env.NTFY_TOPIC), { method: 'POST', body: msg, headers: { Title: 'Arsenal News Archive', Tags: 'speech_balloon', Click: env.SITE + '#board-admin' } }).catch(() => {});
  if (ctx && ctx.waitUntil) ctx.waitUntil(p); else await p;
}

export async function post(env, ctx, b, iph, admin) {
  const t = +b.t, dev = b.dev;
  if (!validId(t) || !L.validDev(dev)) return { err: '入力が正しくありません' };
  const th = await env.DB.prepare('SELECT id, locked, nocom, title FROM bthread WHERE id = ? AND del = 0').bind(t).first();
  if (!th) return { err: 'スレッドが見つかりません', code: 404 };
  if (!admin && (th.locked || th.nocom)) return { err: 'このスレッドは書き込みを締め切りました', code: 409 };
  const chk = L.bCheck(b.name, b.body, admin);
  if (!chk.ok) return { err: chk.err };
  const now = Date.now();
  if (!admin) {
    if (await banned(env, dev, iph)) return { err: 'この端末・回線からは書き込めません', code: 403 };
    const last = await env.DB.prepare('SELECT MAX(ts) AS ts FROM bcom WHERE (dev = ?1 OR iph = ?2) AND ts > ?3').bind(dev, iph, now - L.B_GAP).first();
    if (last && last.ts) return { err: '続けて書き込めるのは1分に1件までです。少し待ってからお試しください', code: 429 };
    const day = await env.DB.prepare('SELECT COUNT(*) AS n FROM bcom WHERE iph = ? AND ts > ?').bind(iph, now - 864e5).first();
    if (day && day.n >= L.B_DAY_MAX) return { err: '同じ回線からの書き込みが多すぎます', code: 429 };
    const dup = await env.DB.prepare('SELECT id FROM bcom WHERE t = ? AND dev = ? AND body = ? AND st != 3 LIMIT 1').bind(t, dev, chk.body).first();
    if (dup) return { err: '同じ内容をすでに書き込んでいます', code: 409 };
  }
  const r = await env.DB.prepare('INSERT INTO bcom (t, dev, iph, name, body, st, adm, why, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)')
    .bind(t, dev, iph, chk.name, chk.body, chk.st, admin ? 1 : 0, chk.why, now).run();
  const id = r.meta && r.meta.last_row_id;
  if (chk.st === 0) await recount(env, t); else await notify(env, ctx, '掲示板：確認待ちのコメントが1件あります（' + th.title + '）');
  return { ok: true, st: chk.st, com: { id, name: chk.name, body: chk.body, adm: !!admin, ts: now } };
}

// 誰でもスレッドを立てられる。自動チェックに引っかかったものは確認待ち（del = 2）で、管理人が公開するまで本人にしか見えない
export async function create(env, ctx, b, iph) {
  const dev = b.dev, now = Date.now();
  if (!L.validDev(dev)) return { err: '入力が正しくありません' };
  if (await banned(env, dev, iph)) return { err: 'この端末・回線からは書き込めません', code: 403 };
  const v = L.bThreadIn(b, now, false);
  if (v.err) return { err: v.err };
  const last = await env.DB.prepare('SELECT MAX(ts) AS ts FROM bown WHERE (dev = ?1 OR iph = ?2) AND ts > ?3').bind(dev, iph, now - L.B_T_GAP).first();
  if (last && last.ts) return { err: 'スレッドを続けて立てるには10分あけてください', code: 429 };
  const day = await env.DB.prepare('SELECT COUNT(*) AS n FROM bown WHERE (dev = ?1 OR iph = ?2) AND ts > ?3').bind(dev, iph, now - 864e5).first();
  if (day && day.n >= L.B_T_DAY) return { err: 'スレッドを立てられるのは1日' + L.B_T_DAY + '件までです', code: 429 };
  const dup = await env.DB.prepare('SELECT id FROM bthread WHERE title = ? AND del != 1 LIMIT 1').bind(v.title).first();
  if (dup) return { err: '同じタイトルのスレッドがすでにあります', code: 409 };
  const r = await env.DB.prepare('INSERT INTO bthread (kind, tag, title, title_en, body, body_en, opts, close, late, pin, nocom, del, ts, last) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?)')
    .bind(v.kind, v.tag, v.title, '', v.body, '', v.opts ? JSON.stringify(v.opts) : null, v.close, v.late, v.hold ? 2 : 0, now, now).run();
  const id = r.meta && r.meta.last_row_id;
  await env.DB.prepare('INSERT INTO bown (t, dev, iph, why, ts) VALUES (?, ?, ?, ?, ?)').bind(id, dev, iph, v.why, now).run();
  if (v.hold) await notify(env, ctx, '掲示板：確認待ちのスレッドが1件あります（' + v.title + '）'); else await drop('board-list');
  return { ok: true, id, hold: !!v.hold };
}

export async function vote(env, b, iph) {
  const t = +b.t, dev = b.dev, o = b.o;
  if (!validId(t) || !L.validDev(dev) || !Number.isInteger(o)) return { err: '入力が正しくありません' };
  const th = await env.DB.prepare('SELECT * FROM bthread WHERE id = ? AND del = 0').bind(t).first();
  if (!th || th.kind !== 'poll') return { err: 'アンケートが見つかりません', code: 404 };
  const now = Date.now(), n = JSON.parse(th.opts || '[]').length;
  if (!L.bPollOpen(th, now)) return { err: 'このアンケートは締め切りました', code: 409 };
  if (o < 0 || o >= n) return { err: '選択肢が正しくありません' };
  if (await banned(env, dev, iph)) return { err: 'この端末・回線からは投票できません', code: 403 };
  const cap = await env.DB.prepare('SELECT COUNT(*) AS n FROM bvote WHERE t = ? AND iph = ? AND dev != ?').bind(t, iph, dev).first();
  if (cap && cap.n >= L.IP_CAP) return { err: '同じ回線からの投票が多すぎます', code: 429 };
  await env.DB.prepare('INSERT INTO bvote (t, dev, iph, o, ts) VALUES (?1, ?2, ?3, ?4, ?5) ON CONFLICT(t, dev) DO UPDATE SET o = ?4, ts = ?5, iph = ?3').bind(t, dev, iph, o, now).run();
  await env.DB.prepare('UPDATE bthread SET nv = (SELECT COUNT(*) FROM bvote WHERE t = ?1) WHERE id = ?1').bind(t).run();
  await drop('board-list');
  return { ok: true, poll: await pollState(env, th, dev, now, true) };
}

export async function report(env, ctx, b, iph) {
  if (b.t != null) return reportThread(env, ctx, b, iph);
  const c = +b.c, dev = b.dev;
  if (!validId(c) || !L.validDev(dev)) return { err: '入力が正しくありません' };
  const com = await env.DB.prepare('SELECT id, t, st, adm, okd, dev FROM bcom WHERE id = ?').bind(c).first();
  if (!com || com.st !== 0 || com.adm) return { ok: true };
  if (com.dev === dev) return { err: '自分のコメントは通報できません' };
  // 同じ回線からの通報は1件と数える（1人で3台使って消すのを防ぐ）
  const same = await env.DB.prepare('SELECT c FROM brep WHERE c = ? AND (dev = ? OR iph = ?) LIMIT 1').bind(c, dev, iph).first();
  if (same) return { ok: true };
  await env.DB.prepare('INSERT OR IGNORE INTO brep (c, dev, iph, ts) VALUES (?, ?, ?, ?)').bind(c, dev, iph, Date.now()).run();
  const n = (await env.DB.prepare('SELECT COUNT(*) AS n FROM brep WHERE c = ?').bind(c).first()).n;
  // 管理人が「問題なし」と戻したコメント（okd）は、通報が増えても自動では隠さない
  const hide = n >= L.B_REPORTS && !com.okd;
  await env.DB.prepare('UPDATE bcom SET rep = ?, st = ? WHERE id = ?').bind(n, hide ? 2 : 0, c).run();
  if (hide) { await recount(env, com.t); await notify(env, ctx, '掲示板：通報が' + n + '件たまったコメントを非表示にしました'); }
  return { ok: true };
}

// スレッドの通報（管理人が立てたスレッドは対象外）。brep には c = -スレッド番号 で入れる
async function reportThread(env, ctx, b, iph) {
  const t = +b.t, dev = b.dev;
  if (!validId(t) || !L.validDev(dev)) return { err: '入力が正しくありません' };
  const th = await env.DB.prepare(TSEL + 'WHERE t.id = ?').bind(t).first();
  if (!th || th.del !== 0 || !th.own) return { ok: true };
  if (th.own === dev) return { err: '自分のスレッドは通報できません' };
  const same = await env.DB.prepare('SELECT c FROM brep WHERE c = ? AND (dev = ? OR iph = ?) LIMIT 1').bind(-t, dev, iph).first();
  if (same) return { ok: true };
  await env.DB.prepare('INSERT OR IGNORE INTO brep (c, dev, iph, ts) VALUES (?, ?, ?, ?)').bind(-t, dev, iph, Date.now()).run();
  const n = (await env.DB.prepare('SELECT COUNT(*) AS n FROM brep WHERE c = ?').bind(-t).first()).n;
  if (n >= L.B_REPORTS && !th.okd) {
    await env.DB.prepare('UPDATE bthread SET del = 2 WHERE id = ?').bind(t).run();
    await env.DB.prepare("UPDATE bown SET why = 'rep' WHERE t = ?").bind(t).run();
    await drop('board-list');
    await notify(env, ctx, '掲示板：通報が' + n + '件たまったスレッドを非表示にしました（' + th.title + '）');
  }
  return { ok: true };
}

// 管理人キーの確認。間違いは回線ごとに数え、15分に5回で締め出す
async function auth(env, key, iph) {
  const want = env.ADMIN_KEY || '';
  if (want.length < L.B_KEY_MIN) return { err: '管理人キーが未設定です（README の「掲示板」を参照）', code: 503 };
  const now = Date.now();
  const tr = await env.DB.prepare('SELECT COUNT(*) AS n FROM btry WHERE iph = ? AND ts > ?').bind(iph, now - L.B_TRY_WIN).first();
  if (tr && tr.n >= L.B_TRY_MAX) return { err: '間違いが続いたため、しばらく受け付けません（15分後にお試しください）', code: 429 };
  if (!L.bKeyEq(String(key || ''), want)) {
    await env.DB.prepare('INSERT INTO btry (iph, ts) VALUES (?, ?)').bind(iph, now).run();
    await env.DB.prepare('DELETE FROM btry WHERE ts < ?').bind(now - 864e5).run();
    return { err: '管理人キーが違います', code: 401 };
  }
  return { ok: true };
}

export async function admin(env, ctx, b, iph) {
  const a = await auth(env, b.key, iph);
  if (!a.ok) return a;
  const now = Date.now(), act = b.act;
  if (act === 'check') return { ok: true };
  if (act === 'queue') {
    const q = await env.DB.prepare('SELECT c.id, c.t, c.name, c.body, c.st, c.why, c.rep, c.ts, t.title FROM bcom c JOIN bthread t ON t.id = c.t WHERE c.st IN (1, 2) OR (c.st = 0 AND c.rep > 0 AND c.okd = 0) ORDER BY c.id DESC LIMIT 100').all();
    const th = await env.DB.prepare(TSEL + 'WHERE t.del = 0 ORDER BY t.pin DESC, t.last DESC, t.id DESC LIMIT 100').all();
    // 確認待ちのスレッド（自動チェック・通報で非表示）と、通報があった公開中のスレッド
    const tq = await env.DB.prepare('SELECT t.id, t.kind, t.title, t.body, t.opts, t.del, t.ts, o.why, (SELECT COUNT(*) FROM brep r WHERE r.c = -t.id) AS rep FROM bthread t JOIN bown o ON o.t = t.id WHERE t.del = 2 OR (t.del = 0 AND o.okd = 0 AND EXISTS (SELECT 1 FROM brep r WHERE r.c = -t.id)) ORDER BY t.id DESC LIMIT 100').all();
    return { ok: true, queue: q.results, tqueue: tq.results, threads: th.results.map(tRow) };
  }
  if (act === 'new') {
    const v = L.bThreadIn(b, now, true);
    if (v.err) return { err: v.err };
    const r = await env.DB.prepare('INSERT INTO bthread (kind, tag, title, title_en, body, body_en, opts, close, late, pin, nocom, ts, last) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
      .bind(v.kind, v.tag, v.title, v.titleEn, v.body, v.bodyEn, v.opts ? JSON.stringify(v.opts) : null, v.close, v.late, v.pin, v.nocom, now, now).run();
    await drop('board-list');
    return { ok: true, id: r.meta && r.meta.last_row_id };
  }
  if (act === 'thread') {
    // スレッドの固定・締め切り・削除（set: pin / locked / del のどれかを 0/1 に）
    const id = +b.id, f = b.set, val = b.val ? 1 : 0;
    if (!validId(id) || !['pin', 'locked', 'del', 'nocom'].includes(f)) return { err: '入力が正しくありません' };
    await env.DB.prepare('UPDATE bthread SET ' + f + ' = ? WHERE id = ?').bind(val, id).run();
    await drop('board-list', 'board-t-' + id + '-0');
    return { ok: true };
  }
  if (act === 'tq') {
    // 一般の人が立てたスレッドの公開（以後は通報で自動非表示にしない）・削除（ban で端末と回線を書き込み禁止に）
    const id = +b.id, to = b.to;
    if (!validId(id) || !['ok', 'del'].includes(to)) return { err: '入力が正しくありません' };
    const o = await env.DB.prepare('SELECT dev, iph FROM bown WHERE t = ?').bind(id).first();
    if (to === 'ok') { await env.DB.prepare('UPDATE bthread SET del = 0 WHERE id = ? AND del != 1').bind(id).run(); await env.DB.prepare('UPDATE bown SET okd = 1 WHERE t = ?').bind(id).run(); }
    else await env.DB.prepare('UPDATE bthread SET del = 1 WHERE id = ?').bind(id).run();
    if (b.ban && o) for (const k of [o.dev, o.iph]) if (k) await env.DB.prepare('INSERT OR IGNORE INTO bban (k, ts) VALUES (?, ?)').bind(k, now).run();
    await drop('board-list', 'board-t-' + id + '-0');
    return { ok: true };
  }
  if (act === 'com') {
    // コメントの公開（確認待ち・通報で非表示 → 公開。以後は通報で自動非表示にしない）・削除
    const c = +b.c, to = b.to;
    if (!validId(c) || !['ok', 'del'].includes(to)) return { err: '入力が正しくありません' };
    const com = await env.DB.prepare('SELECT t FROM bcom WHERE id = ?').bind(c).first();
    if (!com) return { err: 'コメントが見つかりません', code: 404 };
    if (to === 'ok') await env.DB.prepare('UPDATE bcom SET st = 0, okd = 1 WHERE id = ?').bind(c).run();
    else await env.DB.prepare('UPDATE bcom SET st = 3 WHERE id = ?').bind(c).run();
    if (b.ban) {
      const x = await env.DB.prepare('SELECT dev, iph FROM bcom WHERE id = ?').bind(c).first();
      for (const k of [x.dev, x.iph]) if (k) await env.DB.prepare('INSERT OR IGNORE INTO bban (k, ts) VALUES (?, ?)').bind(k, now).run();
    }
    await recount(env, com.t);
    return { ok: true };
  }
  if (act === 'say') return post(env, ctx, b, iph, true);
  return { err: '操作が正しくありません' };
}
