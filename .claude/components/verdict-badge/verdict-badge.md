# verdict-badge コンポーネント

`score.html`（`scoring-quiz`スキル）で、正解系の採点評価（GOOD / GREAT / EXCELLENT）をリッチなバッジとして表示するための標準コンポーネントです。

**使い方**：`score.html`を組み立てる前にこのファイルを`Read`で読み込み、下記のCSSブロックとHTMLスニペットを**改変せずそのまま**使用してください。独自に代替のバッジスタイルを新規作成しないでください。

## Tier表

| tier | 発生条件 | ラベル | アイコン | アニメーション |
|---|---|---|---|---|
| `excellent` | 自由記述（quiz-scorer-hard）が10点 | EXCELLENT! | 🏆 | シャイン＋パルス |
| `great` | 自由入力（quiz-scorer-easy）が正解 | GREAT! | ✨ | シャイン |
| `good` | 選択式（quiz-scorer-easy）が正解、または自由記述が5-9点 | GOOD! | 👍 | なし（静的） |

不正解・0点・低得点（自由記述0-4点含む）の設問には`verdict`は存在せず、バッジも表示しません。この場合は従来通り`.q-score-pill`（点数の色分け表示）と解説文のみで表示してください。

## CSS

そのまま`<style>`ブロックにコピーしてください。ページ側の`--green`/`--accent`等の変数には一切依存しない自己完結スタイルです。

```css
.v-badge {
  --v-fg: #0d1117;
  display: inline-flex;
  align-items: center;
  gap: 0.35em;
  padding: 0.28em 0.85em 0.28em 0.6em;
  border-radius: 999px;
  font-weight: 700;
  font-size: 0.85em;
  letter-spacing: 0.02em;
  line-height: 1.4;
  position: relative;
  overflow: hidden;
  isolation: isolate;
  white-space: nowrap;
}
.v-badge__icon { font-size: 1.1em; line-height: 1; }

.v-badge--excellent {
  --v-fg: #f8ecd4;
  background: linear-gradient(135deg, #b98a46 0%, #9c6a3a 55%, #7d4a42 100%);
  color: var(--v-fg);
  box-shadow: 0 0 0 1px rgba(185,138,70,0.3), 0 2px 8px rgba(125,74,66,0.25);
  animation: v-badge-pulse 1.8s ease-in-out infinite;
}
.v-badge--great {
  --v-fg: #e6f7f2;
  background: linear-gradient(135deg, #2f8f7a 0%, #2d6f96 55%, #3c58a0 100%);
  color: var(--v-fg);
  box-shadow: 0 0 0 1px rgba(45,143,150,0.3), 0 2px 8px rgba(60,88,160,0.25);
}
.v-badge--good {
  --v-fg: #e7f5eb;
  background: #276b3a;
  color: var(--v-fg);
}

.v-badge--excellent::after,
.v-badge--great::after {
  content: "";
  position: absolute;
  top: 0; left: -60%;
  width: 40%; height: 100%;
  background: linear-gradient(120deg, transparent, rgba(255,255,255,0.35), transparent);
  transform: skewX(-20deg);
  animation: v-badge-shine 2.6s ease-in-out infinite;
}

@keyframes v-badge-shine {
  0%   { left: -60%; }
  55%  { left: 130%; }
  100% { left: 130%; }
}
@keyframes v-badge-pulse {
  0%, 100% { transform: scale(1); }
  50%      { transform: scale(1.045); }
}
```

## HTMLスニペット

該当する`verdict`ごとに、そのままコピーして`.q-header`内（`.q-score-pill`の隣）に配置してください。

```html
<span class="v-badge v-badge--excellent"><span class="v-badge__icon">🏆</span>EXCELLENT!</span>
```

```html
<span class="v-badge v-badge--great"><span class="v-badge__icon">✨</span>GREAT!</span>
```

```html
<span class="v-badge v-badge--good"><span class="v-badge__icon">👍</span>GOOD!</span>
```

配置例（`q-header`内、`.q-title`の後・`.q-score-pill`の前）：

```html
<div class="q-header">
  <span class="q-title">問1. ...</span>
  <span class="v-badge v-badge--good"><span class="v-badge__icon">👍</span>GOOD!</span>
  <span class="q-score-pill pill-full">8 / 8点</span>
</div>
```

## Do / Don't

- Do: クラス名（`v-badge`, `v-badge--excellent`, `v-badge--great`, `v-badge--good`, `v-badge__icon`）をそのまま使う。
- Do: `.q-score-pill`と併用し、バッジは点数表示の代替ではなく「評価」として追加する。
- Don't: 色やグラデーション、アイコンを生成のたびに変更しない。
- Don't: `excellent`/`great`/`good`以外の新しいtier（例：不正解用バッジ）を独自に作らない。
- Don't: `.q-comment.ok/.warn/.err`のような代替の色分けスタイルを新規作成しない。
