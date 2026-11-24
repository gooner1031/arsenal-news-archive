// スコア予想・選手採点・MOTM投票の受付と集計（Cloudflare Worker）。
//   GET  /api/m?m=YYYY-MM-DD&dev=…   その試合の状態・自分の入力・みんなの集計
//   POST /api/predict {m, dev, h, a, s:[得点者]}   キックオフまで。何度でも上書き
//   POST /api/rate    {m, dev, v:{選手: 点}}       試合終了から12時間。直しは1時間以内に1回
//   POST /api/motm    {m, dev, p:[1位, 2位, 3位]}   同上
// 試合の情報（キックオフ・結果・出場選手）はサイトの next.json / lineup.json / matchstats.json を読む。
import * as L from './logic.js';

const json = (body, status, cors) => new Response(JSON.stringify(body), {
  status: status || 200,
  headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...(cors || {}) },
});

function corsFor(req, env) {
  const o = req.headers.get('origin') || '';
  const ok = (env.ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean);
  const allow = ok.includes(o) || /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(o);
  return allow ? { 'access-control-allow-origin': o, 'access-control-allow-methods': 'GET,POST,OPTIONS', 'access-control-allow-headers': 'content-type', 'vary': 'origin' } : {};
}

async function siteJson(env, name, ttl) {
  try {
    const r = await fetch(env.SITE + name, { cf: { cacheTtl: ttl, cacheEverything: true } });
    return r.ok ? await r.json() : null;
  } catch (e) { return null; }
}

async function sha(s) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(b)].slice(0, 12).map(x => x.toString(16).padStart(2, '0')).join('');
}
const ipHash = (req, env, m) => sha((req.headers.get('cf-connecting-ip') || '') + '|' + m + '|' + (env.IP_SALT || 'ana'));

// 試合の情報。キックオフは next.json / lineup.json で見えている間に D1 に控えておく（試合後は next.json から消えるため）
async function matchInfo(env, m) {
  const [nx, lu, ms] = await Promise.all([siteJson(env, 'next.json', 300), siteJson(env, 'lineup.json', 60), siteJson(env, 'matchstats.json', 300)]);
  const seen = [];
  for (const x of (nx && nx.matches) || []) if (x.d && x.ko) seen.push([x.d, Date.parse(x.ko), x.o || '']);
  if (lu && lu.d && lu.ko) seen.push([lu.d, Date.parse(lu.ko), lu.o || '']);
  const now = Date.now();
  const mine = seen.filter(s => s[0] === m && !isNaN(s[1]));
  if (mine.length) {
    await env.DB.prepare('INSERT INTO matches (m, ko, o, upd) VALUES (?1, ?2, ?3, ?4) ON CONFLICT(m) DO UPDATE SET ko = ?2, o = ?3, upd = ?4 WHERE matches.ko != ?2')
      .bind(m, mine[0][1], mine[0][2], now).run();
  }
  const row = mine.length ? { ko: mine[0][1], o: mine[0][2] } : await env.DB.prepare('SELECT ko, o FROM matches WHERE m = ?').bind(m).first();
  const st = ms && ms[m];
  return { ko: row ? row.ko : null, o: row ? row.o : '', final: L.finalOf(st), players: L.playersOf(st, lu, m) };
}

// 集計は30秒ずつ使い回す（同じ地域の閲覧者で共有）
async function cached(key, ttl, fn) {
  const c = caches.default, k = new Request('https://ana-vote.cache/' + key);
  const hit = await c.match(k);
  if (hit) return hit.json();
  const v = await fn();
  await c.put(k, new Response(JSON.stringify(v), { headers: { 'cache-control': 'public, max-age=' + ttl } }));
  return v;
}

async function getState(env, m, dev) {
  const info = await matchInfo(env, m), now = Date.now(), ph = L.phase(info.ko, now);
  const [p, r, mo] = await Promise.all([
    dev ? env.DB.prepare('SELECT h, a, s FROM pred WHERE m = ? AND dev = ?').bind(m, dev).first() : null,
    dev ? env.DB.prepare('SELECT v, first, edits FROM rate WHERE m = ? AND dev = ?').bind(m, dev).first() : null,
    dev ? env.DB.prepare('SELECT p1, p2, p3, first, edits FROM motm WHERE m = ? AND dev = ?').bind(m, dev).first() : null,
  ]);
  const out = { m, now, ko: info.ko, ft: ph.ft || null, close: ph.close || null };

  // 予想：締切前は人数だけ。締切後は分布、結果が入れば的中
  const predAgg = await cached('pred-' + m + '-' + (ph.pred === 'open' ? 'n' : info.final ? 'f' + info.final.h + info.final.a + info.final.scorers.join(',') : 'c'), 30, async () => {
    if (ph.pred === 'open') {
      const c = await env.DB.prepare('SELECT COUNT(*) AS n FROM pred WHERE m = ?').bind(m).first();
      return { n: c ? c.n : 0 };
    }
    const rows = (await env.DB.prepare('SELECT h, a, s FROM pred WHERE m = ?').bind(m).all()).results.map(x => ({ h: x.h, a: x.a, s: JSON.parse(x.s || '[]') }));
    return L.aggPred(rows, info.final);
  });
  out.pred = { phase: ph.pred, mine: p ? { h: p.h, a: p.a, s: JSON.parse(p.s || '[]') } : null, ...predAgg };

  // 採点・MOTM：自分が送信するか、受付が終わるまで平均・順位は出さない（人数だけ）
  const showRate = !!r || ph.rate === 'closed', showMotm = !!mo || ph.rate === 'closed';
  const rateAgg = ph.rate === 'before' || ph.rate === 'none' ? null : await cached('rate-' + m, 30, async () => {
    const rows = (await env.DB.prepare('SELECT v FROM rate WHERE m = ?').bind(m).all()).results.map(x => JSON.parse(x.v));
    return L.aggRatings(rows);
  });
  const motmAgg = ph.rate === 'before' || ph.rate === 'none' ? null : await cached('motm-' + m, 30, async () => {
    const rows = (await env.DB.prepare('SELECT p1, p2, p3 FROM motm WHERE m = ?').bind(m).all()).results;
    return L.aggMotm(rows);
  });
  out.rate = {
    phase: ph.rate, players: info.players.list, src: info.players.src,
    mine: r ? JSON.parse(r.v) : null, canEdit: ph.rate === 'open' && L.canEdit(r, now), edits: r ? r.edits : 0, first: r ? r.first : null,
    n: rateAgg ? rateAgg.n : 0, agg: showRate && rateAgg ? rateAgg.players : null,
  };
  out.motm = {
    phase: ph.rate, mine: mo ? [mo.p1, mo.p2, mo.p3] : null, canEdit: ph.rate === 'open' && L.canEdit(mo, now), edits: mo ? mo.edits : 0, first: mo ? mo.first : null,
    n: motmAgg ? motmAgg.n : 0, rank: showMotm && motmAgg ? motmAgg.rank.slice(0, 10) : null,
  };
  return out;
}

async function ipCap(env, table, m, iph, dev) {
  const c = await env.DB.prepare('SELECT COUNT(*) AS n FROM ' + table + ' WHERE m = ? AND iph = ? AND dev != ?').bind(m, iph, dev).first();
  return c && c.n >= L.IP_CAP;
}

const err = (msg, code, cors) => json({ error: msg }, code || 400, cors);

async function postPredict(req, env, b, cors) {
  const { m, dev } = b, h = b.h, a = b.a;
  if (!L.validMatch(m) || !L.validDev(dev) || !L.validScore(h) || !L.validScore(a)) return err('入力が正しくありません', 400, cors);
  const s = Array.isArray(b.s) ? [...new Set(b.s)] : [];
  if (s.length > Math.min(3, h) || !s.every(L.validName)) return err('得点者は最大3人（アーセナルの得点数まで）です', 400, cors);
  const info = await matchInfo(env, m), now = Date.now();
  if (L.phase(info.ko, now).pred !== 'open') return err('この試合の予想は締め切りました', 409, cors);
  const iph = await ipHash(req, env, m);
  if (await ipCap(env, 'pred', m, iph, dev)) return err('同じ回線からの送信が多すぎます', 429, cors);
  await env.DB.prepare('INSERT INTO pred (m, dev, iph, h, a, s, ts) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7) ON CONFLICT(m, dev) DO UPDATE SET h = ?4, a = ?5, s = ?6, ts = ?7, iph = ?3')
    .bind(m, dev, iph, h, a, JSON.stringify(s), now).run();
  return json({ ok: true }, 200, cors);
}

async function postBallot(req, env, b, cors, kind) {
  const { m, dev } = b;
  if (!L.validMatch(m) || !L.validDev(dev)) return err('入力が正しくありません', 400, cors);
  const info = await matchInfo(env, m), now = Date.now();
  if (L.phase(info.ko, now).rate !== 'open') return err('受付時間外です（試合終了から12時間）', 409, cors);
  const P = new Set(info.players.list);
  let vals;
  if (kind === 'rate') {
    const v = b.v && typeof b.v === 'object' ? b.v : {}, keys = Object.keys(v);
    if (!keys.length || keys.length > 30 || !keys.every(k => P.has(k) && L.validRating(v[k]))) return err('点数は出場した選手に1〜10点（0.5点刻み）で付けてください', 400, cors);
    vals = JSON.stringify(Object.fromEntries(keys.map(k => [k, v[k]])));
  } else {
    const p = Array.isArray(b.p) ? b.p : [];
    if (p.length !== 3 || new Set(p).size !== 3 || !p.every(x => P.has(x))) return err('出場した選手から違う3人を選んでください', 400, cors);
    vals = p;
  }
  const table = kind === 'rate' ? 'rate' : 'motm';
  const cur = await env.DB.prepare('SELECT first, edits FROM ' + table + ' WHERE m = ? AND dev = ?').bind(m, dev).first();
  if (cur && !L.canEdit(cur, now)) return err('直せるのは最初の送信から1時間以内に1回だけです', 409, cors);
  const iph = await ipHash(req, env, m);
  if (!cur && await ipCap(env, table, m, iph, dev)) return err('同じ回線からの送信が多すぎます', 429, cors);
  if (kind === 'rate') {
    if (cur) await env.DB.prepare('UPDATE rate SET v = ?, edits = edits + 1, ts = ? WHERE m = ? AND dev = ?').bind(vals, now, m, dev).run();
    else await env.DB.prepare('INSERT INTO rate (m, dev, iph, v, first, edits, ts) VALUES (?, ?, ?, ?, ?, 0, ?)').bind(m, dev, iph, vals, now, now).run();
  } else {
    if (cur) await env.DB.prepare('UPDATE motm SET p1 = ?, p2 = ?, p3 = ?, edits = edits + 1, ts = ? WHERE m = ? AND dev = ?').bind(vals[0], vals[1], vals[2], now, m, dev).run();
    else await env.DB.prepare('INSERT INTO motm (m, dev, iph, p1, p2, p3, first, edits, ts) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)').bind(m, dev, iph, vals[0], vals[1], vals[2], now, now).run();
  }
  await caches.default.delete(new Request('https://ana-vote.cache/' + table + '-' + m));
  return json({ ok: true, edited: !!cur }, 200, cors);
}

export default {
  async fetch(req, env) {
    const cors = corsFor(req, env), url = new URL(req.url);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    try {
      if (req.method === 'GET' && url.pathname === '/api/m') {
        const m = url.searchParams.get('m'), dev = url.searchParams.get('dev') || '';
        if (!L.validMatch(m)) return err('試合の指定が正しくありません', 400, cors);
        return json(await getState(env, m, L.validDev(dev) ? dev : ''), 200, cors);
      }
      if (req.method === 'POST') {
        if (!cors['access-control-allow-origin']) return err('このサイトからだけ受け付けます', 403, cors);
        const len = +(req.headers.get('content-length') || 0);
        if (len > 4000) return err('送信内容が大きすぎます', 413, cors);
        let b; try { b = await req.json(); } catch (e) { return err('送信内容が読めません', 400, cors); }
        if (url.pathname === '/api/predict') return postPredict(req, env, b, cors);
        if (url.pathname === '/api/rate') return postBallot(req, env, b, cors, 'rate');
        if (url.pathname === '/api/motm') return postBallot(req, env, b, cors, 'motm');
      }
      if (url.pathname === '/') return json({ ok: true, name: 'ana-vote' }, 200, cors);
      return err('見つかりません', 404, cors);
    } catch (e) {
      return err('サーバーで問題が起きました', 500, cors);
    }
  },
};
