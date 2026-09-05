---
name: share-course
description: コースの成果物を1枚にまとめ、Claudeのアーティファクトとして組織に共有できる形で公開します。
disable-model-invocation: true
model: sonnet
---

## 何をするスキルか

`artifacts/<テーマ名>/`配下に散らばった`syllabus.html`と各回の`lecture.html`を、**1枚の共有用ページ**にバンドルして公開します。共有相手には1本のURLだけを渡せば、シラバスから最終回まで目次付きで読めます。

- 講座ごとにShadow DOMの区画へ収めるため、講座間でCSS・ID・スクリプトが干渉しません。元の成果物は書き換えません。
- 講座内の理解度チェック（inlineの`onclick`）はそのまま動きます。
- ローカル専用の成果物（`test.html`／`score.html`／`kaitou.json`／`memo.md`）は同梱しません。テストはローカルサーバー前提で、採点結果は個人のものだからです。

## 手順

### 1. 共有するコースの確認

気さくな口調で`AskUserQuestion`で共有対象を確認します。

- `artifacts/`配下のディレクトリを一覧し、`<テーマ名>`を選択させる
- 該当ディレクトリに`syllabus.html`が無い場合、`/generate-syllabus`の使用を促し処理を終了する
- `lecture-*/lecture.html`が1つも無い場合、`/teach`の使用を促し処理を終了する

### 2. バンドルの生成

```sh
python3 ~/claude-academy/.claude/skills/share-course/bundle.py ~/claude-academy/artifacts/<テーマ名>
```

`artifacts/<テーマ名>/share.html`が出力されます。標準出力に区画一覧と注意事項が出るので、次を確認します。

- **`リンク先 ... は同梱範囲に無い`** — シラバスには載っているがまだ`/teach`していない回です。ユーザーに伝え、先に`/teach`で埋めるか、そのまま公開するかを確認します（そのまま公開する場合、当該リンクは不活性化されています）。
- **`参照ファイルが見つかりません`** — 講座が参照する画像が欠けています。公開ページでは相対パスの画像を読み込めないため、data URIへの埋め込みに失敗した箇所です。
- **`外部スクリプトは公開ページで読み込めない`** — CDN等からの読み込みは除外されています。その講座の動作を確認してください。

注意が出なければそのまま3.へ進みます。

### 3. アーティファクトとして公開

`Artifact`ツールで`share.html`を公開します。

- `file_path`: `~/claude-academy/artifacts/<テーマ名>/share.html`
- `title`: 指定不要（`share.html`の`<title>`にコース名が入っています）
- `description`: そのコースが何を学べるものかを1文で
- `favicon`: コースの主題に合う絵文字を1つ（例：Docker→🐳、GitHub→🐙）。**2回目以降は渡さない**（アイコンが変わると別ページに見えるため）
- `capabilities`: 指定不要（このページは静的に完結します）

**すでに公開済みの場合**（`artifacts/<テーマ名>/published.json`が存在する場合）は、同じURLを更新します。

1. `published.json`から`url`を読む
2. `Artifact`を`action: "read"`＋その`url`で呼び、公開中の版を確認する
3. `file_path`と`url`の両方を渡して公開する（`url`を渡さないと別のアーティファクトが新規作成されます）

### 4. 公開記録の保存

`artifacts/<テーマ名>/published.json`に記録します。既存ファイルがあれば`url`は変えずに他を更新します。

```json
{
  "url": "<公開URL>",
  "title": "<コース名>",
  "published_at": "<YYYY-MM-DD>",
  "sections": ["syllabus", "lecture-1", "..."],
  "excluded": ["test.html", "score.html", "kaitou.json", "memo.md"]
}
```

### 5. ユーザーへの報告

- 公開URL
- 同梱した講座数と、同梱しなかったもの（テスト・採点結果・メモ）
- アーティファクトは既定で非公開である旨と、共有はユーザー自身が行う旨
- 講座を追加・修正したら、このスキルをもう一度実行すれば同じURLが更新される旨

## 講座を追加・修正したとき

`/teach`で回を増やした後、このスキルを再実行するだけで共有ページ全体が作り直され、同じURLに反映されます。閲覧者のブックマークは変わりません。

## 補足

- 教材本文が固定のダークテーマで作られているため、外枠も単一のダークで統一しています。ライトテーマ側を作ると本文と衝突するための意図的な選択です。
- 「読了」の状態は閲覧者のブラウザにのみ保存されます。誰がどこまで読んだかを集めたい場合は、ページ側に状態を持たせる必要があるため`artifact-capabilities`の確認から始めてください。
