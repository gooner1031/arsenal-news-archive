# r/Gunners-based transfer source tiers (via arsenal-mania list, Jun 2025), adjusted by site owner Nov 2026.
# Internal value: 5=Official, 4=Tier1, 3=Tier2, 2=Tier3, 1=Tier4 (all other news sources).
T = {
5: 'アーセナル公式',
4: 'デイビッド・オーンスタイン|BBC|サミ・モクベル|ハンド・オブ・アーセナル|ジ・アスレチック|ジェームズ・マクニコラス',
3: 'ファブリツィオ・ロマーノ|チャールズ・ワッツ|エイミー・ローレンス|ガーディアン|テレグラフ|サム・ディーン',
2: 'ジャンルカ・ディ・マルツィオ|ジェームズ・オリー|サイモン・コリングス|ジェームズ・ベンジ|ジョン・クロス|スカイスポーツ|インディペンデント|タイムズ|ビルト|レキップ|キッカー|TNAT（Team news and ticks）|TC（Transfer Checker）|ベン・ジェイコブス',
}
TIER = {n: k for k, v in T.items() for n in v.split('|')}
