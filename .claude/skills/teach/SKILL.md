---
name: teach
description: シラバス記載の講座をユーザーに展開します。
disable-model-invocation: true
model: opus
---

## 手順

1. 学習コンテンツの確認

- `artifacts/`配下に当該ディレクトリ（`<テーマ名>`）が存在しない場合、`/generate-syllabus`の使用を促し処理を終了する
- `artifacts/<テーマ名>`を見つけた場合、`AskUserQuestion`で学習コンテンツを選択させ、当該ディレクトリ配下の`syllabus.html`を読み込み2.の手順に進む

2. 開講する講座の確認

`AskUserQuestion`で`syllabus.html`の講座の選択肢を示し、ユーザーの受講講座を確定します。

3. 講座ファイルの作成

確定した内容をレクチャーするhtmlを生成し、`artifacts/<テーマ名>/lecture-<n>/lecture.html`として出力します。

- `lecture.html`を組み立てる前に、`.claude/components/course-structure/course-structure.md`を`Read`で参照し、記載された構造規約に従います。配色・レイアウト・図解の見せ方は規約の対象外なので自由に決めて構いません。
- `syllabus.html`の`id="lecture-<n>"`の要素内にあるリンクを、生成した`lecture.html`へのリンクとして追加・有効化する
  - `id="lecture-<n>"`が無い既存のシラバスの場合は、該当する回のブロックを特定して`id`を付与してからリンクを扱う

4. 講座ファイルの表示

成果物をユーザー既定ブラウザで表示します。

```sh
open artifacts/<テーマ名>/lecture-<n>/lecture.html
```
