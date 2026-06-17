# ctfd-cli

CTFd 形式の CTF に参加するための、型付き Python API クライアントと CLI ツール。

問題一覧・問題文・ヒント・スコアボード・自分の提出履歴の取得と、フラグ提出、
有料ヒントのアンロックに対応する。

## Skills

```
bunx skills add p1atdev/ctfd-cli
```

## セットアップ

Python 3.12 以上と [uv](https://docs.astral.sh/uv/) を使用する。

```console
uv sync
```

CTFd の設定は環境変数、またはカレントディレクトリの `.env` から読み込む。

```dotenv
CTFD_URL=https://ctf.example.com
CTFD_TOKEN=ctfd_your_api_token
CTFD_TIMEOUT=10
```

`.env.example` を設定例として利用できる。CLI の `--url`、`--token`、`--timeout`
オプションは環境変数や `.env` より優先される。

API トークンは CTFd のユーザー設定画面から発行する。

## CLI

```console
# 問題一覧
uv run ctfd challenges list

# 問題詳細（添付ファイル URL とヒントを含む）
uv run ctfd challenges show 12

# 問題を ./challenges に保存（既存ファイルは上書きしない）
uv run ctfd pull

# フラグ提出
uv run ctfd challenges submit 12 'flag{example}'

# 有料ヒントの確認付きアンロック
uv run ctfd challenges unlock-hint 4

# スコアボードと自分の情報
uv run ctfd scoreboard
uv run ctfd me
uv run ctfd me --show-email
uv run ctfd me solves
uv run ctfd me submissions --challenge-id 12
```

読み取りコマンドと提出コマンドは `--json` に対応する。

```console
uv run ctfd challenges list --json
uv run ctfd challenges show 12 --json
```

AI エージェントから利用する場合は、グローバルの `--short` をコマンドより前に指定する。
装飾、JSON のクォートや括弧、空値、レンダリング用 HTML、メールアドレスを除き、
必要な情報だけを行指向のプレーンテキストで出力する。

```console
uv run ctfd --short challenges list
uv run ctfd --short challenges show 12
uv run ctfd --short pull
uv run ctfd --short me
```

提出結果が正解または既に正解済みなら終了コード `0`、不正解などの競技上の失敗は
`1` を返す。設定、認証、通信、API 応答の問題は別の非ゼロ終了コードを返す。

## Python API

```python
from ctfd import CtfdClient, load_settings

settings = load_settings()

with CtfdClient(settings.url, settings.token, timeout=settings.timeout) as client:
    for challenge in client.list_challenges():
        print(challenge.id, challenge.name, challenge.value)

    challenge = client.get_challenge(12)
    result = client.submit_challenge(challenge.id, "flag{example}")
    print(result.status, result.message)
```

主な公開メソッド:

- `list_challenges()`
- `get_challenge(challenge_id)`
- `submit_challenge(challenge_id, submission)`
- `get_hint(hint_id)` / `unlock_hint(hint_id)`
- `get_scoreboard()`
- `get_me()` / `get_my_solves()` / `get_my_submissions()`

CTFd プラグインがレスポンスに追加した未知フィールドは、Pydantic モデルの追加属性として
保持される。

## 開発

```console
uv run pytest
uv run ruff check .
uv run ty check
```

関連ドキュメント:

- <https://docs.ctfd.io/tutorials/api/using-ctfd-api/>
- <https://docs.ctfd.io/docs/api/redoc/>
