// 手元で集計サーバーを動かすための代用品（Cloudflare の D1・キャッシュを Node の SQLite とメモリで置き換える）。
//   テスト：node --test test/        手元で起動：node test/local.mjs [ポート]   （管理人キーは環境変数 ADMIN_KEY、既定は local-admin-key-0000）
// 本番には入らない（wrangler が公開するのは src/ だけ）。
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';

export function makeEnv(extra) {
  const db = new DatabaseSync(':memory:');
  db.exec(readFileSync(new URL('../schema.sql', import.meta.url), 'utf8'));
  const stmt = (sql, args) => ({
    bind: (...a) => stmt(sql, a.map(v => v === undefined ? null : typeof v === 'boolean' ? +v : v)),
    first: async () => db.prepare(sql).get(...args) || null,
    all: async () => ({ results: db.prepare(sql).all(...args) }),
    run: async () => { const r = db.prepare(sql).run(...args); return { meta: { last_row_id: Number(r.lastInsertRowid), changes: Number(r.changes) } }; },
  });
  return { raw: db, DB: { prepare: sql => stmt(sql, []) }, SITE: 'http://localhost:1/', ORIGINS: 'https://gooner1031.github.io', IP_SALT: 'test', ADMIN_KEY: 'local-admin-key-0000', ...extra };
}
// キャッシュは使い回さない（テストでは毎回読み直す）か、メモリに置く
export function installCaches(keep) {
  const m = new Map();
  globalThis.caches = { default: {
    match: async k => { const v = m.get(k.url); return keep && v ? new Response(v) : undefined; },
    put: async (k, r) => { m.set(k.url, await r.text()); },
    delete: async k => m.delete(k.url),
  } };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  installCaches(true);
  const worker = (await import('../src/index.js')).default;
  const env = makeEnv(process.env.ADMIN_KEY ? { ADMIN_KEY: process.env.ADMIN_KEY } : {}), port = +process.argv[2] || 8787;
  createServer(async (q, s) => {
    const chunks = []; for await (const c of q) chunks.push(c);
    const headers = new Headers(q.headers); // 回線の区別：x-test-ip ヘッダーか、User-Agent に入れた testip=…（ブラウザでの確認用）
    headers.set('cf-connecting-ip', headers.get('x-test-ip') || ((headers.get('user-agent') || '').match(/testip=(\S+)/) || [])[1] || q.socket.remoteAddress || '');
    const r = await worker.fetch(new Request('http://localhost:' + port + q.url, { method: q.method, headers, body: ['GET', 'HEAD'].includes(q.method) ? undefined : Buffer.concat(chunks) }), env, { waitUntil() {} });
    s.writeHead(r.status, Object.fromEntries(r.headers)); s.end(Buffer.from(await r.arrayBuffer()));
  }).listen(port, () => console.log('http://localhost:' + port));
}
