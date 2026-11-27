-- スコア予想・選手採点・MOTM投票の保存先（Cloudflare D1）。何度実行しても壊れない形で書く。
-- dev = 端末ごとのランダムな番号（ブラウザの localStorage）、iph = IPアドレスを秘密の値と混ぜて元に戻せない形にしたもの
CREATE TABLE IF NOT EXISTS matches (m TEXT PRIMARY KEY, ko INTEGER NOT NULL, o TEXT, upd INTEGER);
CREATE TABLE IF NOT EXISTS pred (m TEXT NOT NULL, dev TEXT NOT NULL, iph TEXT, h INTEGER NOT NULL, a INTEGER NOT NULL, s TEXT, ts INTEGER, PRIMARY KEY (m, dev));
CREATE TABLE IF NOT EXISTS rate (m TEXT NOT NULL, dev TEXT NOT NULL, iph TEXT, v TEXT NOT NULL, first INTEGER, edits INTEGER DEFAULT 0, ts INTEGER, PRIMARY KEY (m, dev));
CREATE TABLE IF NOT EXISTS motm (m TEXT NOT NULL, dev TEXT NOT NULL, iph TEXT, p1 TEXT, p2 TEXT, p3 TEXT, first INTEGER, edits INTEGER DEFAULT 0, ts INTEGER, PRIMARY KEY (m, dev));
CREATE INDEX IF NOT EXISTS pred_ip ON pred (m, iph);
CREATE INDEX IF NOT EXISTS rate_ip ON rate (m, iph);
CREATE INDEX IF NOT EXISTS motm_ip ON motm (m, iph);
-- 掲示板。bthread = スレッド（kind: talk 語り合う / poll アンケート）、bcom = コメント（st: 0 公開 / 1 確認待ち / 2 通報で非表示 / 3 削除）、
-- bvote = アンケートの票、brep = 通報、bban = 書き込み禁止（k = 端末の番号か iph）、btry = 管理人キーの入力失敗
CREATE TABLE IF NOT EXISTS bthread (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, tag TEXT, title TEXT NOT NULL, title_en TEXT, body TEXT, body_en TEXT, opts TEXT, close INTEGER, late INTEGER DEFAULT 0, pin INTEGER DEFAULT 0, locked INTEGER DEFAULT 0, nocom INTEGER DEFAULT 0, del INTEGER DEFAULT 0, nc INTEGER DEFAULT 0, nv INTEGER DEFAULT 0, ts INTEGER, last INTEGER);
CREATE TABLE IF NOT EXISTS bcom (id INTEGER PRIMARY KEY AUTOINCREMENT, t INTEGER NOT NULL, dev TEXT NOT NULL, iph TEXT, name TEXT, body TEXT NOT NULL, st INTEGER DEFAULT 0, adm INTEGER DEFAULT 0, why TEXT, rep INTEGER DEFAULT 0, okd INTEGER DEFAULT 0, ts INTEGER);
CREATE TABLE IF NOT EXISTS bvote (t INTEGER NOT NULL, dev TEXT NOT NULL, iph TEXT, o INTEGER NOT NULL, ts INTEGER, PRIMARY KEY (t, dev));
CREATE TABLE IF NOT EXISTS brep (c INTEGER NOT NULL, dev TEXT NOT NULL, iph TEXT, ts INTEGER, PRIMARY KEY (c, dev));
CREATE TABLE IF NOT EXISTS bban (k TEXT PRIMARY KEY, ts INTEGER);
CREATE TABLE IF NOT EXISTS btry (id INTEGER PRIMARY KEY AUTOINCREMENT, iph TEXT, ts INTEGER);
CREATE INDEX IF NOT EXISTS bcom_t ON bcom (t, st, id);
CREATE INDEX IF NOT EXISTS bcom_ip ON bcom (iph, ts);
CREATE INDEX IF NOT EXISTS bcom_dev ON bcom (dev, ts);
CREATE INDEX IF NOT EXISTS bcom_st ON bcom (st, id);
CREATE INDEX IF NOT EXISTS bvote_ip ON bvote (t, iph);
CREATE INDEX IF NOT EXISTS btry_ip ON btry (iph, ts);
-- bre = 返信先（c = 返信したコメント、re = 返信先のコメント。同じスレッドの中だけ）
CREATE TABLE IF NOT EXISTS bre (c INTEGER PRIMARY KEY, re INTEGER NOT NULL);
-- bown = 管理人以外が立てたスレッドの持ち主（行がなければ管理人が立てたスレッド）。why = 確認待ちになった理由、okd = 管理人が確認済み（通報で自動非表示にしない）。
-- スレッドの del は 0 公開 / 1 削除 / 2 確認待ち（自動チェック・通報で非表示）。スレッドへの通報は brep に c = -スレッド番号 で入れる。
CREATE TABLE IF NOT EXISTS bown (t INTEGER PRIMARY KEY, dev TEXT NOT NULL, iph TEXT, why TEXT, okd INTEGER DEFAULT 0, ts INTEGER);
CREATE INDEX IF NOT EXISTS bown_dev ON bown (dev, ts);
CREATE INDEX IF NOT EXISTS bown_ip ON bown (iph, ts);
