// アクセス数（フッターの「今日の訪問者・閲覧数・累計」）。
//   POST /api/hit {p: 画面の名前}   画面を1つ開くたびに1回。返事に最新の数を入れる
//   GET  /api/count                 数だけ（「この端末を数えない」にした端末・表示専用）
// 数え方
//   ・1日は日本時間の0時区切り。
//   ・訪問者＝その日に来た人の数。回線（IP）とブラウザの種類をその日の日付・秘密の値と混ぜて元に戻せない形にし、同じ印は1日1人と数える。
//     印は翌々日に消す（日をまたいで同じ人を追わない。Cookie も使わない）。
//   ・閲覧数＝開いた画面の数。同じ人は1日 VIEW_CAP 回まで（連打・自動アクセスで増えすぎないように）。
//   ・検索エンジンなどの自動アクセス（User-Agent で判別）は数えない。
//   ・累計の閲覧数は、切り替え前の GoatCounter の累計（最初の1回だけ取りに行って控える）に、切り替え後の閲覧数を足す。
export const VIEW_CAP = 300;      // 同じ人の1日の閲覧数の上限
export const DAY_CAP = 40000;     // 1日に記録する閲覧数の上限（無料枠の書き込み数を、投票・掲示板のために残す）
const GC = 'https://arsenal-archive.goatcounter.com/counter/TOTAL.json';
const BOT = /bot\b|bot[\/;)_-]|crawl|spider|slurp|headless|lighthouse|pagespeed|preview|scrap|monitor|uptime|pingdom|curl|wget|python|java\/|go-http|node-fetch|axios|okhttp|libwww|httpclient|facebookexternalhit|embedly|quora|whatsapp|phantom|selenium|puppeteer|playwright|gtmetrix|ia_archiver|feedfetcher|mediapartners|bingpreview|yandex|baidu|semrush|ahrefs|mj12|dataprovider|chrome-lighthouse/i;

export const jstDay = now => new Date(now + 9 * 3600e3).toISOString().slice(0, 10);
export const isBot = ua => !ua || ua.length < 20 || BOT.test(ua);
export const validPath = p => typeof p === 'string' && /^[A-Za-z0-9_.-]{1,60}$/.test(p);

async function sha(s) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(b)].slice(0, 12).map(x => x.toString(16).padStart(2, '0')).join('');
}

// 切り替え前の累計（GoatCounter）。一度控えたら二度と取りに行かない。取れなかったときは1分あけてやり直す
async function base(env) {
  const row = await env.DB.prepare("SELECT v FROM ckv WHERE k = 'base'").first();
  if (row) return row.v;
  const c = caches.default, k = new Request('https://ana-vote.cache/count-base-try');
  if (await c.match(k)) return null;
  await c.put(k, new Response('1', { headers: { 'cache-control': 'public, max-age=60' } }));
  try {
    // start を毎回変えるのは、GoatCounter が同じ URL の結果を何時間も使い回すため（計測開始より前の日付なら全期間の数になる）
    const old = new Date(Date.UTC(2000, 0, 1) + (Math.floor(Date.now() / 600000) % 8000) * 864e5).toISOString().slice(0, 10);
    const r = await fetch(GC + '?start=' + old), j = r.ok ? await r.json() : null;
    const n = j && j.count != null ? String(j.count).replace(/[^\d]/g, '') : '';
    if (!n) return null;
    await env.DB.prepare("INSERT OR IGNORE INTO ckv (k, v) VALUES ('base', ?)").bind(+n).run();
    await env.DB.prepare("INSERT OR IGNORE INTO ckv (k, v) VALUES ('since', ?)").bind(Date.now()).run();
    return +n;
  } catch (e) { return null; }
}

async function totals(env, now) {
  const d = jstDay(now), b = await base(env);
  const [t, a, s] = await Promise.all([
    env.DB.prepare('SELECT u, v FROM cday WHERE d = ?').bind(d).first(),
    env.DB.prepare('SELECT COALESCE(SUM(u), 0) AS u, COALESCE(SUM(v), 0) AS v FROM cday').first(),
    env.DB.prepare("SELECT v FROM ckv WHERE k = 'since'").first(),
  ]);
  return { d, today: { u: t ? t.u : 0, v: t ? t.v : 0 }, total: { v: (b || 0) + a.v, u: a.u }, since: s ? jstDay(s.v) : d, base: b != null };
}

// 数は20秒ずつ使い回す（同じ地域の閲覧者で共有）。控えがまだ取れていない間は使い回さない
export async function count(env, now) {
  const c = caches.default, k = new Request('https://ana-vote.cache/count-' + jstDay(now || Date.now()));
  const hit = await c.match(k);
  if (hit) return hit.json();
  const v = await totals(env, now || Date.now());
  if (v.base) await c.put(k, new Response(JSON.stringify(v), { headers: { 'cache-control': 'public, max-age=20' } }));
  return v;
}

export async function hit(req, env, ctx, b, nowIn) {
  const now = nowIn || Date.now(), ua = req.headers.get('user-agent') || '', d = jstDay(now);
  const cur = await count(env, now);
  if (!b || !validPath(b.p) || isBot(ua) || cur.today.v >= DAY_CAP) return { ...cur, counted: false };
  const k = await sha((req.headers.get('cf-connecting-ip') || '') + '|' + ua + '|' + d + '|' + (env.IP_SALT || 'ana'));
  const r = await env.DB.prepare('INSERT INTO cseen (d, k, n) VALUES (?1, ?2, 1) ON CONFLICT(d, k) DO UPDATE SET n = n + 1 RETURNING n').bind(d, k).first();
  const n = r ? r.n : 1;
  if (n > VIEW_CAP) return { ...cur, counted: false };
  await env.DB.prepare('INSERT INTO cday (d, u, v) VALUES (?1, ?2, 1) ON CONFLICT(d) DO UPDATE SET v = v + 1, u = u + ?2').bind(d, n === 1 ? 1 : 0).run();
  // その日の最初の何人かが来たときに、2日より前の印を消す
  if (n === 1 && cur.today.u < 3) {
    const p = env.DB.prepare('DELETE FROM cseen WHERE d < ?').bind(jstDay(now - 2 * 864e5)).run().catch(() => {});
    if (ctx && ctx.waitUntil) ctx.waitUntil(p); else await p;
  }
  // 返事には、いま数えた分を足しておく（使い回しの数にはまだ入っていないため）
  const u = n === 1 ? 1 : 0;
  const out = { ...cur, today: { u: Math.max(cur.today.u + u, 1), v: cur.today.v + 1 }, total: { u: cur.total.u + u, v: cur.total.v + 1 }, counted: true };
  return out;
}
