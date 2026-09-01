---
name: generate-syllabus
description: 特定の技術トピックについての体系的な学習のシラバスを構成・出力します。
disable-mode-invocation: true
model: sonnet
---

## 手順

1. 学習コンテンツの確認

気さくな口調で`AskUserQuestion`で学習コンテンツを確認します。

- `<テーマ名>`を確定する。

2. シラバスの提案

### プロットの作成

ユーザーから確認した学習コンテンツの入門講座のシラバスのプロットを作成します。

- 内容のボリュームに応じて全5〜10回の講座で構成する。
- 各回の内容の難しさをbeginner, standard, advancedの３段階でラベルする。

### ユーザーとの調整

作成したプロットを`AskUserQuestion`でユーザーに確認します。

- `header`: "シラバスのプロットを確認"
- `question`: "シラバスのプロットを作成しました。このプロットに沿ってシラバスを作成してよろしいですか？"
- `options`:
  - `label`: "OK" / `description`: "3.のステップに進みます"
  - `label`: "ちょっと待って" / `description`: "ユーザーにフィードバックの入力を求め、プロットを調整します"

3. シラバスの生成

プロットをベースにシラバスを作成します。

- `claude-academy/artifacts/`配下に`<テーマ名>`ディレクトリを作成する
- `claude-academy/artifacts/<テーマ名>/`配下に`syllabus.html`としてシラバスを出力する

4. シラバスの表示

成果物をユーザー既定ブラウザで表示します。

```sh
open ~/claude-academy/artifacts/<テーマ名>/syllabus.html
```
