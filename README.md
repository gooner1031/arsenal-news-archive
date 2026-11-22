# arsenal-news-archive
## 移籍トラッカーの品質管理
- `tools/test_tracker.py` … 過去の誤判定（ヴィニシウスの否定報道、スコット/クルピの取りこぼし、ムドリクの過去発言）の回帰テスト。判定ロジック（index.html の trBuild / TR_RX / trCtx）を触ったら必ず実行。
- `tools/audit_transfers.py` … 直近の移籍ポストに出る未登録の選手名を `pending_players.json` に出力（毎時の fetch-x で自動更新）。候補は確認のうえ `tools/people.py` と meta.json に追加。
- 判定は「その選手が出てくる文（見出しなら次の文まで）」だけで行う。投稿全体で判定しない。
