# ctfd-cli

CTFd 形式の CTF のユーザー側 API を叩くための CLI ツール。

## 機能

問題一覧の取得、問題文の取得などの読み取り機能や、回答提出機能なども含めて対応する。

サーバーURLやトークンなどは環境変数だったり .env から読み込めるようにする。


関連ドキュメント:
- https://docs.ctfd.io/tutorials/api/using-ctfd-api/
- https://docs.ctfd.io/docs/api/redoc/


### pull

`pull` サブコマンドを実行すると、リモートにある問題をダウンロードしてこれるようにしたい。

例えば、


- /
  - /challenges
    - /briefing
      - /01_The_first_problem
        - problem.md
      - /02_second
        - problem.md
    - /recon
      - /04_easy_recon
        - problem.md
        - image.png
    - /OPERATION_ALPHA
      - /15_preparation 
        - problem.md

みたいな感じで一気にローカルにファイルを作成できるようにしたい。
すでにファイルがある場合は上書きしない。

