#!/usr/bin/env python3
"""新着ポストを載せるかどうかの判定（自動取得 fetch_x.py 用。毎日の正式タグ付けもこれに従う）。
アーカイブ本体（2022〜）を作ったときの基準（tools/load.py の keep）と同じ考え方:
  載せる: 引用RP / URL・リンクカード付き / 画像・動画付き / 【媒体】見出しや（@媒体）の出典表記つき
          / 載せたポストに自分で続けたスレッドの続き
  載せない: 他人へのリプライ / 上のどれにも当たらない一言・私的な発言 / サイト自体の宣伝（promo.py）"""
import re, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import promo

CITE = re.compile(r'[（(]\s*@\w+|^\s*【[^】]+】')

def has_info(text, urls=(), media=0, quoted=False):
    """情報ポストの目印があるか。"""
    return bool(quoted or urls or media or CITE.search((text or '').replace('\u200b', '')))

def keep(text, urls=(), media=0, quoted=False, reply_to=None, me=None, parent_kept=False, pid=None):
    """reply_to: 返信先のユーザーID（返信でなければ None）。parent_kept: 自分への返信（スレッド）の親が載っているか。"""
    if promo.is_promo(text, urls, pid): return False
    if reply_to is not None and reply_to != me: return False      # 他人へのリプライ
    if reply_to is not None and parent_kept: return True           # 載せたポストのスレッドの続き
    return has_info(text, urls, media, quoted)
