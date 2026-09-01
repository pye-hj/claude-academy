---
name: quizing
description: シラバス記載の講座のテストをユーザーに展開します。
disable-mode-invocation: true
---

1. 学習コンテンツの確認

気さくな口調で`AskUserQuestion`で学習コンテンツを確認します。

- `claude-academy/artifacts/`配下に当該ディレクトリが存在しない場合、`/generating-syllabus`の使用を促し処理を終了する
- `claude-academy/artifacts/`配下に当該ディレクトリを見つけた場合、`syllabus.html`を読み込み2.の手順に進む

2. 出題対象の講座の確認

`AskUserQuestion`で`syllabus.html`の講座の選択肢を示し、出題する範囲を確定します。

- `<出題範囲>`: 講座番号で命名します（例：`lecture-1`, `lecture-2`, `lecture-3`）

3. テストの生成

`quiz-generator`に`<出題範囲>`を渡し、出題範囲の`lecture.html`に沿ったテストを生成します。

4. テストの表示

ローカルサーバーをバックグラウンドで起動します（`run_in_background`で実行）。サーバーが自動でユーザー既定ブラウザを開きます。

```sh
python3 ~/claude-academy/.claude/skills/quizing/serve-test.py ~/claude-academy/artifacts/<テーマ名>/<出題範囲>
```

- `file://`ではなく`http://127.0.0.1:<ポート>/test.html`で開くことで、「回答を保存」時に`kaitou.json`が講座フォルダへ直接書き出される（ダウンロードフォルダを経由しない）
- ポートは8765から順に空きを探す。サーバーは1時間無操作で自動終了する
- ユーザーには「解答して『回答を保存』を押したら`/scoring-quiz`を呼んでほしい」旨を伝える
