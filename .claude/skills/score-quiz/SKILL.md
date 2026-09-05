---
name: score-quiz
description: ユーザーが受講した講座のテストの採点を行い、結果を出力します。
disable-model-invocation: true
model: sonnet
---

1. 採点対象の確認

気さくな口調で`AskUserQuestion`で学習コンテンツを確認します。

- 直前に`quiz`スキルの使用履歴があれば対象を推測してユーザーに確認します。
- 使用履歴がなければ`claude-academy/artifacts/`配下の`<テーマ名>`, `<出題範囲>`を順に確認し、採点対象の`test.html`と`kaitou.json`を確定します。
  - 通常`kaitou.json`は`quiz`のローカルサーバーが講座フォルダへ直接書き出している。
  - `test.html`を`file://`で直接開いた場合はダウンロードフォルダに落ちるフォールバックが働く。講座フォルダに`kaitou.json`が無ければユーザーにその旨を伝え、ダウンロードフォルダから移動してもらう（`kaitou (1).json`など付番がある場合は最も新しいものを採点対象とする）。

対象を確定したら、残っている`quiz`のテスト配信サーバーを停止します。

```sh
python3 ~/claude-academy/.claude/skills/quiz/serve-test.py ~/claude-academy/artifacts/<テーマ名>/<出題範囲> --stop
```

- 起動中のサーバーが無ければ何もせず終了するので、常に実行して構いません（`pkill -f`はシェル自身にもマッチして誤爆するため使わないこと）。

2. 採点

テストの10問を１問10点の100点満点でサブエージェントに並行で採点させます。

- 一意的な回答がある問題は`quiz-scorer-easy`へ、部分点含む自由記述の問題は`quiz-scorer-hard`へそれぞれ採点を依頼する。
  - 渡す情報：確定した`test.html`, `kaitou.json`のパス、問題番号
  - 返却情報：採点結果（問題番号、点数(0-10点)、verdict（`excellent`/`great`/`good`のいずれか、該当なしは省略）、解説）

3. 採点結果の出力

サブエージェントから返却された採点結果を集約し、`claude-academy/artifacts/<テーマ名>/<出題範囲>/score.html`として出力します。

- `score.html`を組み立てる前に、`.claude/components/verdict-badge/verdict-badge.md`を`Read`で参照し、記載されたCSSブロックとHTMLスニペットを改変せずそのまま使用します。サブエージェントから`verdict`（`excellent`/`great`/`good`）が返された設問は、対応するバッジを`q-header`内の`.q-score-pill`と並べて表示します。`verdict`が返されなかった設問（不正解・低得点）にはバッジを表示せず、従来通りpillと解説文のみで表示します。独自の代替バッジスタイルを新規作成しないこと。
- `score.html`の冒頭では全体の結果に対する総評と今後の学習のアドバイスを表示する。
  - ここではユーザーの士気が高まるように優しい口調で鼓舞するようにコメントする。
- `score.html`の末尾に`lecture.html`へのリンクを追加します。
- `score.html`が既に存在していた場合、番号を付加して上書きしないようにする（例：`score(1).html`, `score(2).html`）

4. 採点結果の表示

生成された`score.html`をユーザー既定ブラウザで表示します。

```sh
open ~/claude-academy/artifacts/<テーマ名>/<出題範囲>/score.html
```
