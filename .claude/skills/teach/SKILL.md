---
name: teach
description: シラバス記載の講座をユーザーに展開します。
disable-mode-invocation: true
model: opus
---

## 手順

1. 学習コンテンツの確認

- `claude-academy/artifacts/`配下に当該ディレクトリ（`<テーマ名>`）が存在しない場合、`/generate-syllabus`の使用を促し処理を終了する
- `claude-academy/artifacts/<テーマ名>`を見つけた場合、`AskUserQuestion`で学習コンテンツを選択させ、当該ディレクトリ配下の`syllabus.html`を読み込み2.の手順に進む

2. 開講する講座の確認

`AskUserQuestion`で`syllabus.html`の講座の選択肢を示し、ユーザーの受講講座を確定します。

3. 講座ファイルの作成

確定した内容をレクチャーするhtmlを生成し、`claude-academy/artifacts/<テーマ名>/lecture-<n>/lecture.html`として出力します。

- syllabus.htmlの講座番号のコンポーネントに生成した`lecture.html`へのリンクを追加する

4. 講座ファイルの表示

成果物をユーザー既定ブラウザで表示します。

```sh
open ~/claude-academy/artifacts/<テーマ名>/lecture-<n>/lecture.html
```
