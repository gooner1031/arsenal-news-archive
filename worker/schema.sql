-- スコア予想・選手採点・MOTM投票の保存先（Cloudflare D1）。何度実行しても壊れない形で書く。
-- dev = 端末ごとのランダムな番号（ブラウザの localStorage）、iph = IPアドレスを秘密の値と混ぜて元に戻せない形にしたもの
CREATE TABLE IF NOT EXISTS matches (m TEXT PRIMARY KEY, ko INTEGER NOT NULL, o TEXT, upd INTEGER);
CREATE TABLE IF NOT EXISTS pred (m TEXT NOT NULL, dev TEXT NOT NULL, iph TEXT, h INTEGER NOT NULL, a INTEGER NOT NULL, s TEXT, ts INTEGER, PRIMARY KEY (m, dev));
CREATE TABLE IF NOT EXISTS rate (m TEXT NOT NULL, dev TEXT NOT NULL, iph TEXT, v TEXT NOT NULL, first INTEGER, edits INTEGER DEFAULT 0, ts INTEGER, PRIMARY KEY (m, dev));
CREATE TABLE IF NOT EXISTS motm (m TEXT NOT NULL, dev TEXT NOT NULL, iph TEXT, p1 TEXT, p2 TEXT, p3 TEXT, first INTEGER, edits INTEGER DEFAULT 0, ts INTEGER, PRIMARY KEY (m, dev));
CREATE INDEX IF NOT EXISTS pred_ip ON pred (m, iph);
CREATE INDEX IF NOT EXISTS rate_ip ON rate (m, iph);
CREATE INDEX IF NOT EXISTS motm_ip ON motm (m, iph);
