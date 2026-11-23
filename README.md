# arsenal-news-archive
## 移籍トラッカーの品質管理
- `tools/test_tracker.py` … 過去の誤判定（ヴィニシウスの否定報道、スコット/クルピの取りこぼし、ムドリクの過去発言、スビメンディ本人の否定、クルピの括弧内「オファー」）の回帰テスト。判定ロジック（index.html の trBuild / TR_RX / trCtx）を触ったら必ず実行。
- `tools/promo.py` … サイト自体の宣伝・告知ポスト（サイトの URL・サイト名・「ホーム画面に追加」・CONTACT の案内・「このアカウントで毎日発信」など）の判定。自動取得（fetch_x.py）で除外し、毎日の正式タグ付けでも同じ判定を使う。目印のない告知は `tools/promo_ids.txt` に ID を追記。回帰テストは `tools/test_promo.py`。
- `tools/post_rule.py` … 自動取得で載せるポストの判定。引用RP・URL・画像/動画・出典表記（【媒体】/（@媒体））つきと、そのスレッドの続きだけ載せ、他人へのリプライ・私的な一言・宣伝は除外。既存データには適用しない。
- 本人・クラブの否定は「インタビュー・コメント」等のポストに入っていても、トラッカーに載っている選手なら破談・停滞として反映する。
- `tools/audit_transfers.py` … 直近の移籍ポストに出る未登録の選手名を `pending_players.json` に出力（毎時の fetch-x で自動更新）。候補は確認のうえ `tools/people.py` と meta.json に追加。
- 判定は「その選手が出てくる文（見出しなら次の文まで）」だけで行う。投稿全体で判定しない。

## 試合スタッツ
- `tools/match_stats.md` … matchstats.json の項目と、試合後に追加するベンチ（`bench`）・欠場者（`abs`）の取り方。欠場者は試合時点で確認できたものだけ入れる。

## 文字サイズ（小・標準・大）
- メニューとフッターの「文字サイズ」で切替。選択は `localStorage` の `ana-fz`（`s`＝小 / `l`＝大、なし＝標準）。
- 文字の大きさは `font-size:calc(13px*var(--fz,1))` の形で書く（`--fz` は小 0.9・標準 1・大 1.2）。新しく px で文字サイズを書くときもこの形にすると設定が効く。

## 出典・最終更新・訂正履歴
- 各データ画面の下に「出典・最終更新・訂正・更新履歴・間違いを指摘」の1行を出す（index.html の `dsrc('<キー>')`）。
- 最終更新は手書きしない。`tools/stamp.py` がデータごとの中身の変化を見て、main に入った時刻（日本時間）を `updated.json` に書く。main への push のたびに `.github/workflows/stamp.yml` が自動で実行する。
- 新しいデータ画面を足すときは `tools/stamp.py` の `SECTIONS` に1行（キー・ファイル・取り出し方・表示名・出典）を足し、画面で `dsrc('<キー>')` を呼ぶ。出典の文言もここで直す。
- 間違いを直したら `corrections.json` の先頭に1件足す：`{"d":"YYYY-MM-DD","k":"訂正|更新","t":"日本語","en":"English","p":["選手の英語名"],"h":"関連ページのハッシュ"}`（`p`・`h` は任意）。「訂正・更新履歴」ページ（#corrections）に新しい順で出る。

## 読み込みの速さ（ホームの初期表示）
- ホームは `posts-new.json`（posts.json の直近60日分）だけで先に描画し、そのあと `posts.json` → `posts-old.json` の順に読み込んで合流する。ホーム以外から開いたときは最初から全ポストを読む。
- `posts-new.json` は手で編集しない。`tools/split_posts.py` が posts.json から作る。posts.json が main に入ると `.github/workflows/posts-new.yml` が自動で作り直す（fix-cut.yml でも作り直す）。ずれていても、posts.json が届いた時点で正しい内容に置き換わる。
- 最初に使うデータは `<head>` で先読み（preload）している。ファイル名を変えるときは index.html の先読みの一覧も合わせて直す。
