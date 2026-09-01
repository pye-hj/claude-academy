#!/usr/bin/env python3
"""コース成果物を1枚の共有用HTMLへバンドルする（skill: share-course）。

artifacts/<テーマ名>/ 配下の syllabus.html と lecture-*/lecture.html を読み取り、
Claudeのアーティファクトとして公開できる単一ファイル share.html を生成する。

各講座は Shadow DOM の区画に収める。これにより
  - 講座ごとのCSS（:root変数・* リセット・同名クラス）が互いに干渉しない
  - 講座ごとに重複するID（q1, fb1 など）が衝突しない
  - 理解度チェックの inline onclick が、その講座の区画だけを見て動く
という3点を、元の成果物を書き換えずに成立させる。

usage:
    python3 bundle.py <コースディレクトリ> [-o 出力先] [--title タイトル]
"""

import argparse
import base64
import html
import json
import mimetypes
import re
import sys
from pathlib import Path

FALLBACK_ACCENT = "#58a6ff"

# 共有物に含めないローカル専用の成果物（テストはローカルサーバー前提、採点結果は個人のもの）
LOCAL_ONLY_HREF = re.compile(r'^(?:\./)?(?:test|score(?:\(\d+\))?)\.html(?:[?#].*)?$', re.I)


# --------------------------------------------------------------------------
# 抽出
# --------------------------------------------------------------------------

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_title(doc: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", doc, re.S | re.I)
    return html.unescape(m.group(1)).strip() if m else ""


def extract_styles(doc: str) -> str:
    """<head> 側も含めた全 <style> を連結して返す。"""
    return "\n".join(
        m.group(1) for m in re.finditer(r"<style[^>]*>(.*?)</style>", doc, re.S | re.I)
    )


def extract_body(doc: str) -> str:
    m = re.search(r"<body[^>]*>(.*)</body>", doc, re.S | re.I)
    if m:
        return m.group(1)
    # <body> が無い断片はそのまま本文として扱う
    return re.sub(r"(?is)<!doctype[^>]*>|</?html[^>]*>|<head\b.*?</head>", "", doc)


def pop_inline_scripts(body: str):
    """本文から <script> を取り除き、インラインのソースだけを返す。

    <template> に入れた要素は実行されないため、スクリプトは後から
    区画ごとの名前空間で評価し直す。
    """
    sources, externals = [], []

    def take(m):
        tag, src = m.group(0), m.group(1)
        if re.search(r'\bsrc\s*=', tag, re.I):
            externals.append(tag)
        elif src.strip():
            sources.append(src)
        return ""

    body = re.sub(r"<script[^>]*>(.*?)</script>", take, body, flags=re.S | re.I)
    return body, sources, externals


# --------------------------------------------------------------------------
# CSS のスコープ変換
# --------------------------------------------------------------------------

def _rewrite_selector(sel: str) -> str:
    """Shadow root 内で意味を持つセレクタへ書き換える。

    :root / html はシャドウツリー内では何にもマッチしないため :host に、
    body は本文ラッパの .page に寄せる。
    """
    sel = sel.replace(":root", ":host")
    sel = re.sub(r"(?<![\w\-.#:\[])html(?![\w\-])", ":host", sel)
    sel = re.sub(r"(?<![\w\-.#:\[])body(?![\w\-])", ".page", sel)
    return sel


def scope_css(css: str) -> str:
    """波括弧を数えながらセレクタ部分だけを書き換える（宣言部には触れない）。"""
    out, buf = [], []
    i, n = 0, len(css)
    while i < n:
        c = css[i]
        if c == "/" and css[i + 1:i + 2] == "*":
            j = css.find("*/", i + 2)
            j = n if j == -1 else j + 2
            buf.append(css[i:j])
            i = j
            continue
        if c in "\"'":
            q, j = c, i + 1
            while j < n:
                if css[j] == "\\":
                    j += 2
                    continue
                if css[j] == q:
                    j += 1
                    break
                j += 1
            buf.append(css[i:j])
            i = j
            continue
        if c == "{":
            prelude = "".join(buf)
            buf = []
            # @media / @supports / @keyframes のプレリュードはセレクタではない
            out.append(prelude if prelude.lstrip().startswith("@") else _rewrite_selector(prelude))
            out.append("{")
            i += 1
            continue
        if c == "}":
            out.append("".join(buf))
            buf = []
            out.append("}")
            i += 1
            continue
        buf.append(c)
        i += 1
    out.append("".join(buf))
    return "".join(out)


# --------------------------------------------------------------------------
# リンク・画像の解決
# --------------------------------------------------------------------------

def rewrite_links(body: str, section_ids, warnings, where: str) -> str:
    """講座間リンクを区画遷移に、ローカル専用リンクを不活性に変換する。"""

    def target_of(href: str):
        href = href.strip()
        m = re.match(r"^(?:\.\./)?(lecture-\d+)/lecture\.html(?:[?#].*)?$", href, re.I)
        if m:
            return m.group(1)
        if re.match(r"^(?:\.\./)?syllabus\.html(?:[?#].*)?$", href, re.I):
            return "syllabus"
        if re.match(r"^(?:\./)?lecture\.html(?:[?#].*)?$", href, re.I):
            return "__self__"
        return None

    def fix_anchor(m):
        attrs, href = m.group(0), html.unescape(m.group(2))
        if LOCAL_ONLY_HREF.match(href.strip()):
            # テスト/採点はローカル環境専用。リンクを外して不活性な表示にする
            return re.sub(r'\s*href\s*=\s*(["\'])[^"\']*\1', ' data-local-only="1"', attrs, count=1)
        dest = target_of(href)
        if dest is None:
            return attrs  # 外部URLや #anchor はそのまま
        if dest == "__self__" or dest in section_ids:
            dest = where if dest == "__self__" else dest
            return re.sub(
                r'\s*href\s*=\s*(["\'])[^"\']*\1',
                f' data-goto="{html.escape(dest, quote=True)}"',
                attrs, count=1,
            )
        warnings.append(f"{where}: リンク先 {href} は同梱範囲に無いため、リンクを外しました")
        return re.sub(r'\s*href\s*=\s*(["\'])[^"\']*\1', ' data-unavailable="1"', attrs, count=1)

    body = re.sub(r'<a\b[^>]*?\bhref\s*=\s*(["\'])(.*?)\1[^>]*>', fix_anchor, body, flags=re.I | re.S)

    # リンクを外した結果、中身が空になった導線ブロックを畳む
    body = re.sub(
        r'<section[^>]*>\s*<a\b[^>]*data-local-only="1"[^>]*>.*?</a>\s*</section>',
        "", body, flags=re.I | re.S,
    )
    return body


def inline_assets(body: str, base: Path, warnings, where: str) -> str:
    """相対パスの画像などを data URI に埋め込む（外部参照はCSPで遮断されるため）。"""

    def to_data_uri(rel: str):
        rel = html.unescape(rel).split("?")[0].split("#")[0]
        if not rel or re.match(r"^(?:https?:|data:|//|#)", rel, re.I):
            return None
        path = (base / rel).resolve()
        if not path.is_file():
            warnings.append(f"{where}: 参照ファイルが見つかりません（{rel}）")
            return None
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"

    def fix_src(m):
        uri = to_data_uri(m.group(2))
        return f'{m.group(1)}{uri}{m.group(3)}' if uri else m.group(0)

    body = re.sub(r'(<img\b[^>]*?\bsrc\s*=\s*")([^"]*)(")', fix_src, body, flags=re.I)
    body = re.sub(r'(url\(\s*["\']?)([^"\')]+)(["\']?\s*\))',
                  lambda m: (f'{m.group(1)}{to_data_uri(m.group(2))}{m.group(3)}'
                             if to_data_uri(m.group(2)) else m.group(0)),
                  body, flags=re.I)
    return body


# --------------------------------------------------------------------------
# スクリプトの名前空間化
# --------------------------------------------------------------------------

TOP_LEVEL_FN = re.compile(
    r"^[ \t]*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|"
    r"^[ \t]*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)",
    re.M,
)


def collect_globals(sources):
    names = []
    for src in sources:
        for m in TOP_LEVEL_FN.finditer(src):
            name = m.group(1) or m.group(2)
            if name not in names:
                names.append(name)
    return names


HANDLER_ATTR = re.compile(r'\b(on[a-z]+)\s*=\s*"([^"]*)"', re.I)


def namespace_handlers(body: str, names, ns: str) -> str:
    """inline の onclick="answer(...)" を onclick="NS.answer(...)" へ寄せる。

    inline ハンドラは window しか参照できないため、区画ごとの名前空間に載せる。
    """
    if not names:
        return body
    call = re.compile(r"(?<![\w$.])(" + "|".join(map(re.escape, names)) + r")\s*\(")
    return HANDLER_ATTR.sub(
        lambda m: f'{m.group(1)}="{call.sub(lambda c: f"{ns}.{c.group(1)}(", m.group(2))}"',
        body,
    )


# --------------------------------------------------------------------------
# コースの読み取り
# --------------------------------------------------------------------------

def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return 0.0
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def pick_accent(syllabus_css: str) -> str:
    """シラバスのアクセント色を引き継ぐ。暗すぎて陰影に埋もれる色は使わない。"""
    for m in re.finditer(r"--accent[a-z-]*\s*:\s*(#[0-9a-fA-F]{3,8})", syllabus_css):
        color = m.group(1)
        if 0.18 <= luminance(color) <= 0.8:
            return color
    return FALLBACK_ACCENT


def course_name(syllabus_title: str, fallback: str) -> str:
    name = re.sub(r"\s*(シラバス|Syllabus|syllabus)\s*$", "", syllabus_title).strip()
    return name or fallback


def lecture_label(title: str, number: int) -> str:
    """<title> の「講座02 — 見出し」から見出しだけを取り出す。"""
    stripped = re.sub(r"^\s*(?:講座|第|Lecture)\s*0*\d+\s*(?:回)?\s*[—–\-:：]?\s*", "", title)
    return stripped.strip() or title.strip() or f"講座 {number}"


def collect_sections(course_dir: Path, warnings):
    sections = []

    syllabus = course_dir / "syllabus.html"
    if not syllabus.is_file():
        sys.exit(f"エラー: {syllabus} が見つかりません。先に /generate-syllabus を実行してください。")

    lectures = []
    for d in course_dir.iterdir():
        m = re.fullmatch(r"lecture-(\d+)", d.name)
        if m and (d / "lecture.html").is_file():
            lectures.append((int(m.group(1)), d))
    lectures.sort()
    if not lectures:
        sys.exit(f"エラー: {course_dir} に lecture-*/lecture.html がありません。先に /teach を実行してください。")

    sections.append({"id": "syllabus", "index": "00", "path": syllabus, "dir": course_dir})
    for num, d in lectures:
        sections.append({"id": f"lecture-{num}", "index": f"{num:02d}",
                         "path": d / "lecture.html", "dir": d, "number": num})
    return sections


def build_sections(sections, warnings):
    ids = {s["id"] for s in sections}
    for s in sections:
        doc = read_text(s["path"])
        body = extract_body(doc)
        body, scripts, externals = pop_inline_scripts(body)
        for tag in externals:
            warnings.append(f"{s['id']}: 外部スクリプトは公開ページで読み込めないため除外しました（{tag[:60]}）")

        body = rewrite_links(body, ids, warnings, s["id"])
        body = inline_assets(body, s["dir"], warnings, s["id"])

        ns = "__ns_" + s["id"].replace("-", "_")
        names = collect_globals(scripts)
        body = namespace_handlers(body, names, "window." + ns)

        if "</template" in body.lower():
            warnings.append(f"{s['id']}: 本文に </template> が含まれるため描画が崩れる可能性があります")

        s["title"] = extract_title(doc)
        s["css"] = scope_css(extract_styles(doc))
        s["html"] = body
        s["ns"] = ns
        s["script"] = "\n".join(scripts)
        s["exports"] = names
    return sections


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------

SHELL = r"""<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500&family=IBM+Plex+Sans+JP:wght@400;500;600&display=swap">
<style>
  /* 教材本文が固定のダークテーマで作られているため、外枠も単一のダークで通す。
     色は全てここで明示し、ホスト側の地色を透かさない。 */
  :root {
    --ground: #05080d;
    --rail: #0b1017;
    --raised: #131b25;
    --line: #1d2733;
    --line-soft: #141c26;
    --text: #e6edf3;
    --muted: #8b98a9;
    --faint: #5c6875;
    --accent: __ACCENT__;
    --sans: "IBM Plex Sans JP", -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", Meiryo, sans-serif;
    --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    --rail-w: 268px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--ground);
    color: var(--text);
    font-family: var(--sans);
    -webkit-font-smoothing: antialiased;
  }
  .app { display: flex; min-height: 100vh; align-items: stretch; }

  /* ===== 目次レール ===== */
  .rail {
    width: var(--rail-w);
    flex: 0 0 var(--rail-w);
    background: var(--rail);
    border-right: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    gap: 18px;
    padding: 26px 0 18px;
    position: sticky;
    top: 0;
    height: 100vh;
  }
  .rail-head { padding: 0 22px; display: flex; flex-direction: column; gap: 10px; }
  .eyebrow {
    margin: 0;
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--faint);
  }
  .course { margin: 0; font-size: 17px; font-weight: 600; line-height: 1.35; text-wrap: balance; }
  .progress {
    margin: 2px 0 0;
    font-size: 11px;
    color: var(--muted);
    font-family: var(--mono);
    font-variant-numeric: tabular-nums;
  }
  .pbar { height: 2px; background: var(--line); border-radius: 2px; overflow: hidden; }
  .pbar span { display: block; height: 100%; width: 0; background: var(--accent); transition: width .3s ease; }

  .rail-nav { flex: 1; overflow-y: auto; padding: 0 12px; display: flex; flex-direction: column; gap: 1px; }
  .row {
    display: grid;
    grid-template-columns: 26px 1fr 14px;
    align-items: baseline;
    gap: 10px;
    width: 100%;
    text-align: left;
    padding: 9px 10px 9px 9px;
    border: 0;
    border-left: 2px solid transparent;
    border-radius: 5px;
    background: none;
    color: var(--muted);
    font-family: var(--sans);
    font-size: 12.5px;
    line-height: 1.45;
    cursor: pointer;
  }
  .row:hover { background: var(--line-soft); color: var(--text); }
  .row:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .row .idx {
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--faint);
    font-variant-numeric: tabular-nums;
  }
  .row[aria-current="true"] {
    background: var(--raised);
    border-left-color: var(--accent);
    color: var(--text);
    font-weight: 500;
  }
  .row[aria-current="true"] .idx { color: var(--accent); }
  .row .dot {
    justify-self: end;
    align-self: center;
    width: 6px; height: 6px;
    border-radius: 50%;
    border: 1px solid var(--line);
  }
  .row.read .dot { background: var(--accent); border-color: var(--accent); }
  .rail-sep {
    margin: 8px 10px 4px;
    padding-top: 12px;
    border-top: 1px solid var(--line-soft);
    font-family: var(--mono);
    font-size: 9.5px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--faint);
  }
  .rail-foot { margin: 0; padding: 0 22px; font-size: 10.5px; line-height: 1.6; color: var(--faint); }

  /* ===== 本文側 ===== */
  .stage { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .topbar {
    position: sticky;
    top: 0;
    z-index: 5;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 20px;
    background: color-mix(in srgb, var(--ground) 88%, transparent);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--line-soft);
  }
  .crumb {
    flex: 1;
    min-width: 0;
    font-size: 12px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .crumb b { color: var(--text); font-weight: 500; }
  .chip {
    flex: 0 0 auto;
    border: 1px solid var(--line);
    background: transparent;
    color: var(--muted);
    font-family: var(--sans);
    font-size: 11.5px;
    padding: 5px 11px;
    border-radius: 999px;
    cursor: pointer;
  }
  .chip:hover { border-color: var(--accent); color: var(--text); }
  .chip:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .chip[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); }
  .menu { display: none; }

  .sec { display: block; }
  .sec[hidden] { display: none !important; }
  @media (prefers-reduced-motion: no-preference) {
    .sec { animation: rise .22s ease both; }
    @keyframes rise { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
  }

  .pager {
    display: flex;
    gap: 10px;
    justify-content: space-between;
    padding: 22px 20px 40px;
    border-top: 1px solid var(--line-soft);
  }
  .pager button {
    flex: 0 1 300px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 12px 16px;
    background: var(--rail);
    border: 1px solid var(--line);
    border-radius: 8px;
    color: var(--text);
    font-family: var(--sans);
    font-size: 13px;
    text-align: left;
    cursor: pointer;
  }
  .pager button:last-child { text-align: right; }
  .pager button:hover { border-color: var(--accent); }
  .pager button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .pager button[hidden] { display: none; }
  .pager .dir { font-family: var(--mono); font-size: 10px; letter-spacing: 0.14em; color: var(--faint); text-transform: uppercase; }

  /* 元の講座内リンクのうち、共有版で行き先を持たないもの */
  .scrim { display: none; }
  @media (max-width: 920px) {
    .rail {
      position: fixed;
      z-index: 20;
      left: 0; top: 0;
      transform: translateX(-100%);
      transition: transform .2s ease;
      box-shadow: 0 0 40px rgba(0,0,0,.55);
    }
    .app.open .rail { transform: none; }
    .app.open .scrim { display: block; position: fixed; inset: 0; z-index: 15; background: rgba(0,0,0,.5); }
    .menu {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .rail, .pbar span { transition: none; }
  }
</style>

<div class="app" id="app">
  <div class="scrim" id="scrim"></div>
  <aside class="rail" id="rail">
    <div class="rail-head">
      <p class="eyebrow">Claude Academy</p>
      <h1 class="course">__COURSE__</h1>
      <p class="progress"><span id="pcount">0 / __LECTURE_COUNT__</span> 読了</p>
      <div class="pbar"><span id="pfill"></span></div>
    </div>
    <nav class="rail-nav" id="nav" aria-label="講座一覧"></nav>
    <p class="rail-foot">この教材は Claude Academy で生成し、1枚のページにまとめたものです。理解度テストと採点はローカル環境でのみ実行できます。</p>
  </aside>

  <main class="stage">
    <div class="topbar">
      <button class="chip menu" id="menu" aria-expanded="false">≡ 目次</button>
      <p class="crumb" id="crumb"></p>
      <button class="chip" id="mark" aria-pressed="false">読了にする</button>
    </div>
    <div id="sections"></div>
    <nav class="pager">
      <button id="prev" hidden><span class="dir">← 前の講座</span><span id="prevTitle"></span></button>
      <button id="next" hidden><span class="dir">次の講座 →</span><span id="nextTitle"></span></button>
    </nav>
  </main>
</div>

__TEMPLATES__

<script>
(function () {
  var SECTIONS = __MANIFEST__;
  var STORE_KEY = "claude-academy:read:__SLUG__";
  var host = document.getElementById("sections");
  var nav = document.getElementById("nav");
  var app = document.getElementById("app");
  var current = null;

  /* 区画スクリプトからの document 参照を、その区画の shadow root に向ける */
  function scopedDoc(root) {
    return new Proxy(document, {
      get: function (target, prop) {
        if (prop === "getElementById") return function (id) { return root.getElementById(id); };
        if (prop === "querySelector") return function (s) { return root.querySelector(s); };
        if (prop === "querySelectorAll") return function (s) { return root.querySelectorAll(s); };
        if (prop === "getElementsByClassName") return function (s) { return root.querySelectorAll("." + s); };
        var value = target[prop];
        return typeof value === "function" ? value.bind(target) : value;
      },
      set: function (target, prop, value) { target[prop] = value; return true; }
    });
  }

  function readState() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) { return []; }
  }
  function writeState(ids) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(ids)); } catch (e) { /* 保存できなくても閲覧は続く */ }
  }
  var read = readState();

  function isRead(id) { return read.indexOf(id) !== -1; }

  function renderProgress() {
    var lectures = SECTIONS.filter(function (s) { return s.id !== "syllabus"; });
    var done = lectures.filter(function (s) { return isRead(s.id); }).length;
    document.getElementById("pcount").textContent = done + " / " + lectures.length;
    document.getElementById("pfill").style.width =
      (lectures.length ? (done / lectures.length) * 100 : 0) + "%";
    SECTIONS.forEach(function (s) {
      if (s.row) s.row.classList.toggle("read", isRead(s.id));
    });
    var mark = document.getElementById("mark");
    var done_ = current && isRead(current.id);
    mark.setAttribute("aria-pressed", done_ ? "true" : "false");
    mark.textContent = done_ ? "✓ 読了" : "読了にする";
  }

  /* 目次 */
  SECTIONS.forEach(function (s, i) {
    if (i === 1) {
      var sep = document.createElement("p");
      sep.className = "rail-sep";
      sep.textContent = "Lectures";
      nav.appendChild(sep);
    }
    var row = document.createElement("button");
    row.className = "row";
    row.type = "button";
    row.innerHTML =
      '<span class="idx"></span><span class="ttl"></span><span class="dot"></span>';
    row.querySelector(".idx").textContent = s.id === "syllabus" ? "—" : s.index;
    row.querySelector(".ttl").textContent = s.label;
    row.addEventListener("click", function () { go(s.id); });
    nav.appendChild(row);
    s.row = row;
  });

  /* 区画の生成：本文・CSS・スクリプトを Shadow DOM に閉じ込める */
  SECTIONS.forEach(function (s) {
    var section = document.createElement("section");
    section.className = "sec";
    section.id = "sec-" + s.id;
    section.hidden = true;
    var root = section.attachShadow({ mode: "open" });

    var style = document.createElement("style");
    style.textContent = ":host{display:block}[data-goto]{cursor:pointer}" +
      "[data-unavailable],[data-local-only]{opacity:.45;cursor:not-allowed;pointer-events:none}" + s.css;
    root.appendChild(style);

    var page = document.createElement("div");
    page.className = "page";
    page.appendChild(document.getElementById("tpl-" + s.id).content.cloneNode(true));
    root.appendChild(page);

    /* <template> から複製した要素は、環境によっては inline ハンドラが未登録のまま残る。
       同じ値で設定し直して確実に有効化する（eval を使わないためCSPに触れない）。 */
    var nodes = page.querySelectorAll("*");
    for (var n = 0; n < nodes.length; n++) {
      var attrs = nodes[n].attributes;
      for (var a = 0; a < attrs.length; a++) {
        if (attrs[a].name.indexOf("on") === 0) nodes[n].setAttribute(attrs[a].name, attrs[a].value);
      }
    }

    root.addEventListener("click", function (event) {
      var path = event.composedPath();
      for (var i = 0; i < path.length; i++) {
        var el = path[i];
        if (!el.getAttribute) continue;
        var goto_ = el.getAttribute("data-goto");
        if (goto_) { event.preventDefault(); go(goto_); return; }
        var href = el.getAttribute("href");
        if (href && href.charAt(0) === "#") {
          var target = root.getElementById(href.slice(1));
          if (target) { event.preventDefault(); target.scrollIntoView({ behavior: "smooth", block: "start" }); }
          return;
        }
      }
    });

    host.appendChild(section);
    s.el = section;
    s.root = root;

    var init = window.__SECTION_INIT && window.__SECTION_INIT[s.id];
    if (init) {
      try { init(scopedDoc(root), root); }
      catch (e) { console.error("[share-course] " + s.id + " の初期化に失敗しました", e); }
    }
  });

  function find(id) {
    for (var i = 0; i < SECTIONS.length; i++) if (SECTIONS[i].id === id) return SECTIONS[i];
    return null;
  }

  function go(id, keepScroll) {
    var s = find(id);
    if (!s) return;
    if (current) { current.el.hidden = true; current.row.setAttribute("aria-current", "false"); }
    current = s;
    s.el.hidden = false;
    s.row.setAttribute("aria-current", "true");

    document.getElementById("crumb").innerHTML = "";
    var crumb = document.getElementById("crumb");
    if (s.id === "syllabus") {
      crumb.innerHTML = "<b></b>";
      crumb.querySelector("b").textContent = "シラバス";
    } else {
      crumb.appendChild(document.createTextNode("講座 " + s.index + " / "));
      var b = document.createElement("b");
      b.textContent = s.label;
      crumb.appendChild(b);
    }

    var idx = SECTIONS.indexOf(s);
    setPager("prev", SECTIONS[idx - 1]);
    setPager("next", SECTIONS[idx + 1]);

    app.classList.remove("open");
    document.getElementById("menu").setAttribute("aria-expanded", "false");
    if (!keepScroll) window.scrollTo({ top: 0, behavior: "auto" });
    try { localStorage.setItem(STORE_KEY + ":last", id); } catch (e) { /* noop */ }
    renderProgress();
  }

  function setPager(which, target) {
    var btn = document.getElementById(which);
    if (!target) { btn.hidden = true; return; }
    btn.hidden = false;
    document.getElementById(which + "Title").textContent = target.label;
    btn.onclick = function () { go(target.id); };
  }

  document.getElementById("mark").addEventListener("click", function () {
    if (!current) return;
    if (isRead(current.id)) read = read.filter(function (x) { return x !== current.id; });
    else read = read.concat([current.id]);
    writeState(read);
    renderProgress();
  });

  document.getElementById("menu").addEventListener("click", function () {
    var open = app.classList.toggle("open");
    this.setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.getElementById("scrim").addEventListener("click", function () {
    app.classList.remove("open");
    document.getElementById("menu").setAttribute("aria-expanded", "false");
  });

  var start = "syllabus";
  try {
    var last = localStorage.getItem(STORE_KEY + ":last");
    if (last && find(last)) start = last;
  } catch (e) { /* noop */ }
  go(start);
})();
</script>
"""


def render(course, sections, accent, slug):
    templates, scripts = [], []
    for s in sections:
        templates.append(f'<template id="tpl-{s["id"]}">{s["html"]}</template>')
        if s["script"].strip():
            exports = ", ".join(
                f'"{n}": (typeof {n} === "function" ? {n} : undefined)' for n in s["exports"]
            )
            scripts.append(
                "window.__SECTION_INIT = window.__SECTION_INIT || {};\n"
                f'window.__SECTION_INIT["{s["id"]}"] = function (document, __root) {{\n'
                f'{s["script"]}\n'
                f"window.{s['ns']} = {{{exports}}};\n"
                "};"
            )

    manifest = json.dumps(
        [{"id": s["id"], "index": s["index"],
          "label": "シラバス" if s["id"] == "syllabus" else lecture_label(s["title"], s.get("number", 0)),
          "css": s["css"]}
         for s in sections],
        ensure_ascii=False,
    ).replace("</", "<\\/")  # CSS中の "</script>" 相当でスクリプトが閉じないように

    body = SHELL
    if scripts:
        body = body.replace("__TEMPLATES__", "\n".join(templates) + "\n<script>\n" + "\n".join(scripts) + "\n</script>")
    else:
        body = body.replace("__TEMPLATES__", "\n".join(templates))

    lecture_count = sum(1 for s in sections if s["id"] != "syllabus")
    return (body
            .replace("__TITLE__", html.escape(course))
            .replace("__COURSE__", html.escape(course))
            .replace("__ACCENT__", accent)
            .replace("__LECTURE_COUNT__", str(lecture_count))
            .replace("__SLUG__", slug)
            .replace("__MANIFEST__", manifest))


def main():
    ap = argparse.ArgumentParser(description="コース成果物を1枚の共有用HTMLへバンドルする")
    ap.add_argument("course_dir", help="artifacts/<テーマ名> のパス")
    ap.add_argument("-o", "--out", help="出力先（既定: <コースディレクトリ>/share.html）")
    ap.add_argument("--title", help="ページ名（既定: シラバスの <title> から決定）")
    args = ap.parse_args()

    course_dir = Path(args.course_dir).expanduser().resolve()
    if not course_dir.is_dir():
        sys.exit(f"エラー: {course_dir} はディレクトリではありません")

    warnings = []
    sections = build_sections(collect_sections(course_dir, warnings), warnings)

    syllabus = sections[0]
    course = args.title or course_name(syllabus["title"], course_dir.name)
    accent = pick_accent(syllabus["css"])
    slug = re.sub(r"[^\w\-]+", "-", course_dir.name).strip("-").lower() or "course"

    out = Path(args.out).expanduser().resolve() if args.out else course_dir / "share.html"
    out.write_text(render(course, sections, accent, slug), encoding="utf-8")

    print(f"ページ名   : {course}")
    print(f"アクセント : {accent}")
    print(f"区画       : {len(sections)}（シラバス + 講座{len(sections) - 1}）")
    for s in sections:
        note = f"  script:{len(s['exports'])}関数" if s["exports"] else ""
        print(f"  - {s['id']:<12} {lecture_label(s['title'], 0)[:38]}{note}")
    print(f"出力       : {out}  ({out.stat().st_size / 1024:.0f} KB)")
    if warnings:
        print("\n注意:")
        for w in warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
