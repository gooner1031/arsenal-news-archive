"""posts.json から直近分だけを取り出して posts-new.json を作る（ホームの初期表示用）。

ホームは posts-new.json（小さい）で先に描画し、そのあと posts.json → posts-old.json を後から読み込んで合流する。
posts-new.json は posts.json の写しの一部なので手で編集しない。posts.json が main に入ると
.github/workflows/posts-new.yml が自動で作り直す（fix-cut.yml でも作り直す）。

使い方: python3 tools/split_posts.py          # posts-new.json を書き出す
        python3 tools/split_posts.py --check  # posts-new.json が最新か確認（ずれていたら終了コード1）
"""
import json, sys, datetime, os

DAYS = 60  # posts.json の最新ポストから何日前までを入れるか（今の移籍ウィンドウとNEWの判定をまかなえる長さ）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build():
    posts = json.load(open(os.path.join(ROOT, 'posts.json'), encoding='utf-8'))
    if not posts:
        return '[\n]\n'
    newest = max(p['d'] for p in posts)
    cut = (datetime.datetime.strptime(newest[:10], '%Y-%m-%d') - datetime.timedelta(days=DAYS)).strftime('%Y-%m-%d')
    keep = [p for p in posts if p['d'] >= cut]  # 並び順は posts.json のまま
    return '[\n' + ',\n'.join(json.dumps(p, ensure_ascii=False, separators=(',', ':')) for p in keep) + '\n]\n'


if __name__ == '__main__':
    out = build()
    path = os.path.join(ROOT, 'posts-new.json')
    if '--check' in sys.argv:
        cur = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
        if cur != out:
            print('posts-new.json が posts.json と合っていません。python3 tools/split_posts.py を実行してください'); sys.exit(1)
        print('posts-new.json OK'); sys.exit(0)
    open(path, 'w', encoding='utf-8').write(out)
    print('posts-new.json', out.count('\n{'), 'posts', len(out.encode()), 'bytes')
