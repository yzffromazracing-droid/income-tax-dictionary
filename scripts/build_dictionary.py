#!/usr/bin/env python3
"""国税庁タックスアンサー（所得税）から所得税の辞書を生成する。

カテゴリ:
  - 非課税     : No.2011「課税される所得と非課税所得」の表から各非課税所得を項目化
  - 所得区分   : No.1300 と 10種類の所得の各ページ
  - 所得控除   : No.1100 と各所得控除のページ
  - 税額控除   : No.1200 と各税額控除のページ

使い方:
  python3 scripts/build_dictionary.py            # 取得（キャッシュ利用）して生成
  python3 scripts/build_dictionary.py --refresh  # キャッシュを使わず再取得
"""

import argparse
import datetime
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

BASE = "https://www.nta.go.jp"
TA = BASE + "/taxes/shiraberu/taxanswer/shotoku/{}.htm"
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
DATA = ROOT / "data"
DOCS = ROOT / "dictionary"
SITE = ROOT / "docs"
TEMPLATE = Path(__file__).resolve().parent / "search_template.html"
YOMI = DATA / "yomi.tsv"
CAT_COLORS = {"hikazei": "hikazei", "shotoku-kubun": "kubun",
              "shotoku-kojo": "shotoku", "zeigaku-kojo": "zeigaku"}

CATEGORIES = [
    {
        "id": "hikazei",
        "name": "非課税",
        "description": "社会政策その他の見地から所得税を課さないこととされている所得（非課税所得）。",
        "overview": "2011",
        "pages": [],  # 表から抽出する
    },
    {
        "id": "shotoku-kubun",
        "name": "所得区分",
        "description": "所得税法上の10種類の所得の区分。",
        "overview": "1300",
        "overview_first": True,  # 概要を目次より前に、出典をページ末尾に置く
        "pages": ["1310", "1330", "1350", "1370", "1400", "1420",
                  "1440", "1460", "1480", "1490", "1500"],
    },
    {
        "id": "shotoku-kojo",
        "name": "所得控除",
        "description": "所得金額から差し引かれる金額（所得控除）。",
        "overview": "1100",
        "pages": ["1110", "1120", "1129", "1130", "1135", "1140", "1145",
                  "1150", "1160", "1170", "1171", "1172", "1175", "1177",
                  "1180", "1191", "1195", "1199"],
    },
    {
        "id": "zeigaku-kojo",
        "name": "税額控除",
        "description": "税金から差し引かれる金額（税額控除）。",
        "overview": "1200",
        "pages": ["1210", "1240", "1241", "1250", "1260", "1263", "1266",
                  "1270", "1284", "1286", "1288"],
    },
]

# 本文として扱わない見出し
STOP_HEADINGS = {"関連リンク", "お問い合わせ先", "QAリンク", "関連コード"}


def fetch(code, refresh=False):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{code}.htm"
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    url = TA.format(code)
    req = urllib.request.Request(url, headers={"User-Agent": "income-tax-dictionary/1.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        if res.geturl().endswith("/error/404.htm"):
            raise RuntimeError(f"not found: {url}")
        html = res.read().decode("utf-8", errors="replace")
    path.write_text(html, encoding="utf-8")
    time.sleep(1)  # 国税庁サーバーへの負荷軽減
    return html


def clean(text):
    text = text.replace("　", "　").replace("\xa0", " ")
    text = re.sub(r"[ \t\r\n]+", " ", text)
    return text.strip()


def inline(node):
    """インライン要素を Markdown 文字列に変換する。"""
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    if node.name == "br":
        return "\n"
    inner = "".join(inline(c) for c in node.children)
    if node.name == "a" and node.get("href"):
        href = node["href"]
        if href.startswith("/"):
            href = BASE + href
        label = clean(inner)
        return f"[{label}]({href})" if label else ""
    if node.name in ("strong", "b"):
        label = clean(inner)
        return f"**{label}**" if label else ""
    return inner


def text_of(node):
    return "\n".join(clean(s) for s in inline(node).split("\n") if clean(s))


def table_to_md(table):
    """rowspan/colspan を展開して Markdown の表にする。"""
    grid = {}
    rows = table.find_all("tr")
    for r, tr in enumerate(rows):
        c = 0
        for cell in tr.find_all(["th", "td"], recursive=False):
            while (r, c) in grid:
                c += 1
            value = text_of(cell).replace("\n", "<br>").replace("|", "｜")
            rs = int(cell.get("rowspan", 1) or 1)
            cs = int(cell.get("colspan", 1) or 1)
            in_head = bool(cell.find_parent("thead")) or (table.thead is None and r == 0)
            for dr in range(rs):
                for dc in range(cs):
                    # 横結合は見出し以外では先頭セルのみに値を入れる（検索ページで colspan に戻す）
                    grid[(r + dr, c + dc)] = value if dc == 0 or in_head else ""
            c += cs
    if not grid:
        return ""
    nrows = max(k[0] for k in grid) + 1
    ncols = max(k[1] for k in grid) + 1
    matrix = [[grid.get((r, c), "") for c in range(ncols)] for r in range(nrows)]
    # 見出し行: thead があればその行数、なければ1行目
    head_n = len(table.thead.find_all("tr")) if table.thead else 1
    if head_n > 1:
        merged = []
        for c in range(ncols):
            parts = []
            for r in range(head_n):
                if matrix[r][c] and matrix[r][c] not in parts:
                    parts.append(matrix[r][c])
            merged.append(" / ".join(parts))
        matrix = [merged] + matrix[head_n:]
    lines = []
    cap = table.find("caption")
    if cap:
        lines.append(text_of(cap))
        lines.append("")
    lines.append("| " + " | ".join(matrix[0]) + " |")
    lines.append("|" + "---|" * ncols)
    for row in matrix[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def block_to_md(el, depth=0):
    name = el.name
    if name in ("h2", "h3", "h4", "h5"):
        level = {"h2": 3, "h3": 4, "h4": 5, "h5": 6}[name]
        return "#" * level + " " + text_of(el)
    if name == "table":
        return table_to_md(el)
    if name in ("ul", "ol"):
        items = []
        for i, li in enumerate(el.find_all("li", recursive=False), 1):
            sub = [c for c in li.children if isinstance(c, Tag) and c.name in ("ul", "ol", "table")]
            for s in sub:
                s.extract()
            body = text_of(li).replace("\n", " ")
            body = re.sub(r"^[・\s　]+", "", body)
            items.append("  " * depth + f"- {body}")
            for s in sub:
                items.append(block_to_md(s, depth + 1))
        return "\n".join(items)
    if name == "div":
        return "\n\n".join(filter(None, (block_to_md(c, depth) for c in el.children if isinstance(c, Tag))))
    if name in ("p", "dl", "dd", "dt", "span", "blockquote"):
        return text_of(el)
    return text_of(el)


def parse_page(code, html):
    soup = BeautifulSoup(html, "lxml")  # 閉じタグ省略の p を正しく扱うため lxml
    h1 = soup.find("h1")
    title = clean(h1.get_text())
    term = re.sub(r"^No\.\d+\s*", "", title)
    as_of = ""
    sections = {}
    order = []
    current = None
    def flatten(nodes):
        # 本文中の div は展開して、見出し（h2）を取りこぼさないようにする
        for el in nodes:
            if not isinstance(el, Tag):
                continue
            if el.name == "div" and "contents-feedback" not in (el.get("class") or []) \
                    and el.find("h2"):
                yield from flatten(el.children)
            else:
                yield el

    for el in flatten(h1.find_parent("div").find_next_siblings()):
        if el.name == "h2":
            current = clean(el.get_text())
            if current in STOP_HEADINGS:
                current = None
                continue
            sections[current] = []
            order.append(current)
            continue
        if el.name == "div" and "contents-feedback" in (el.get("class") or []):
            break
        if current is None:
            m = re.search(r"\[(.+?現在法令等)\]", el.get_text())
            if m:
                as_of = m.group(1)
            continue
        md = block_to_md(el)
        if md:
            sections[current].append(md)
    body_sections = [s for s in order if s not in ("対象税目", "根拠法令等")]
    body = "\n\n".join(
        f"### {s}\n\n" + "\n\n".join(sections[s])
        for s in body_sections if sections[s]
    )
    summary = ""
    for chunk in sections.get("概要", []):
        if not chunk.startswith("#") and not chunk.startswith("|") and not chunk.startswith("-"):
            summary = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", chunk).split("\n")[0]
            break
    return {
        "code": code,
        "term": term,
        "title": title,
        "summary": summary,
        "legal_basis": " ".join(sections.get("根拠法令等", [])),
        "as_of": as_of,
        "source_url": TA.format(code),
        "content_md": body,
    }, soup


def extract_hikazei(soup, refresh):
    """No.2011 の非課税所得の表から項目を抽出する。"""
    entries = []
    table = soup.find("table")
    for tr in table.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) != 2:
            continue
        group = clean(tds[0].get_text())
        for li in tds[1].find_all("li"):
            raw = clean(li.get_text())
            raw = re.sub(r"^[・\s　]+", "", raw)
            # 末尾の括弧書き（根拠条文）を分離
            m = re.search(r"[（(]((?:所法|措法|所令|措規)[^（()）]*)[)）]\s*$", raw)
            basis = m.group(1).strip() if m else ""
            term = raw[: m.start()].strip() if m else raw
            nickname = re.search(r"いわゆる「(.+?)」", term)
            links = []
            for a in li.find_all("a", href=True):
                mm = re.search(r"/shotoku/(\d+)\.htm", a["href"])
                if mm:
                    links.append(mm.group(1))
            entry = {
                "term": term,
                "group": group,
                "alias": nickname.group(1) if nickname else "",
                "legal_basis": basis,
                "source_url": TA.format("2011"),
                "related": [],
            }
            for code in dict.fromkeys(links):
                page, _ = parse_page(code, fetch(code, refresh))
                entry["related"].append({
                    "code": code,
                    "title": page["title"],
                    "summary": page["summary"],
                    "source_url": page["source_url"],
                })
            entries.append(entry)
    return entries


KANJI = re.compile(r"[\u3400-\u9fff々〆]")


def load_yomi():
    """読み辞書（表記と読みの組）を読み込む。"""
    pairs = []
    for n, line in enumerate(YOMI.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        surface, reading = line.split("\t")
        if not re.fullmatch(r"[ぁ-んー]+", reading):
            raise SystemExit(f"{YOMI.name}:{n}: 読みはひらがなで書いてください: {line}")
        pairs.append((surface, reading))
    return pairs


def to_yomi(text, table, maxlen):
    """読み辞書を最長一致で当てて読みを作る。読めなかった漢字も返す。"""
    out, missing, i = [], [], 0
    while i < len(text):
        for n in range(min(maxlen, len(text) - i), 0, -1):
            if text[i:i + n] in table:
                out.append(table[text[i:i + n]])
                i += n
                break
        else:
            ch = text[i]
            if KANJI.match(ch):
                missing.append(ch)
            elif re.match(r"[ァ-ヶ]", ch):
                out.append(chr(ord(ch) - 0x60))
            elif re.match(r"[ぁ-んー]", ch):
                out.append(ch)
            i += 1
    return "".join(out), missing


def add_yomi(pages, table, maxlen):
    missing = {}
    for page in pages:
        page["yomi"], miss = to_yomi(page["term"], table, maxlen)
        if miss:
            missing[page["term"]] = "".join(miss)
    if missing:
        detail = "\n".join(f"  {t}: {m}" for t, m in missing.items())
        raise SystemExit(f"{YOMI.name} に読みがない漢字があります。追加してください。\n{detail}")


def render_md(cat, overview, entries):
    source = (f"出典: 国税庁タックスアンサー [{overview['title']}]({overview['source_url']})"
              + (f"（{overview['as_of']}）" if overview["as_of"] else ""))
    # 本文の「### 概要」はページの「## 概要」と重なるので外す
    summary_md = re.sub(r"\A### 概要\n\n", "", overview["content_md"])
    summary = ["## 概要", "", summary_md, ""]
    if overview["legal_basis"]:
        summary += [f"**根拠法令等**: {overview['legal_basis']}", ""]
    overview_first = cat.get("overview_first", False)

    lines = [f"# {cat['name']}", "", cat["description"], ""]
    if overview_first:
        lines += summary
    else:
        lines += [source, ""]
    lines += ["## 目次", ""]
    if cat["id"] == "hikazei":
        groups = list(dict.fromkeys(e["group"] for e in entries))
        for g in groups:
            lines.append(f"- {g}")
            for e in entries:
                if e["group"] == g:
                    lines.append(f"  - {e['term']}")
    else:
        for e in entries:
            lines.append(f"- [{e['term']}](#no{e['code']}) — No.{e['code']}")
    lines.append("")
    if not overview_first:
        lines += summary

    if cat["id"] == "hikazei":
        lines += ["## 用語", ""]
        for g in dict.fromkeys(e["group"] for e in entries):
            lines += [f"### {g}", ""]
            for e in entries:
                if e["group"] != g:
                    continue
                lines += [f"#### {e['term']}", "", f"- **読み**: {e['yomi']}"]
                if e["alias"]:
                    lines.append(f"- **通称**: {e['alias']}")
                if e["legal_basis"]:
                    lines.append(f"- **根拠法令**: {e['legal_basis']}")
                for r in e["related"]:
                    lines.append(f"- **関連**: [{r['title']}]({r['source_url']})"
                                 + (f" — {r['summary']}" if r["summary"] else ""))
                lines.append("")
    else:
        lines += ["## 用語", ""]
        for e in entries:
            lines += [f'<a id="no{e["code"]}"></a>', "", f"### {e['term']}", "",
                      f"- **読み**: {e['yomi']}"]
            if e["legal_basis"]:
                lines.append(f"- **根拠法令等**: {e['legal_basis']}")
            if e["summary"]:
                lines.append(f"- **要旨**: {e['summary']}")
            lines += ["", "<details><summary>詳細（タックスアンサー本文）</summary>", "",
                      demote(e["content_md"]), "", "</details>", "",
                      f"**タックスアンサー**: [{e['title']}]({e['source_url']})"
                      + (f"（{e['as_of']}）" if e["as_of"] else ""), ""]
    if overview_first:
        lines += ["---", "", source, ""]
    return "\n".join(lines).rstrip() + "\n"


def demote(md):
    return re.sub(r"^(#{3,5}) ", lambda m: "#" * (len(m.group(1)) + 1) + " ", md, flags=re.M)


def search_items(result):
    """検索ページ用に全カテゴリの項目を1つのリストにする。"""
    items = []

    def page_item(cat_id, page, kind):
        return {
            "id": f"no{page['code']}", "cat": cat_id, "kind": kind,
            "term": page["term"], "yomi": page["yomi"], "code": page["code"], "title": page["title"],
            "summary": page["summary"], "basis": page["legal_basis"],
            "asOf": page["as_of"], "url": page["source_url"], "md": page["content_md"],
        }

    for cat in result["categories"]:
        items.append(page_item(cat["id"], cat["overview"], "overview"))
        for i, e in enumerate(cat["entries"], 1):
            if cat["id"] == "hikazei":
                items.append({
                    "id": f"hk{i}", "cat": cat["id"], "kind": "hikazei",
                    "term": e["term"], "yomi": e["yomi"], "alias": e["alias"], "group": e["group"],
                    "basis": e["legal_basis"], "asOf": cat["overview"]["as_of"],
                    "url": e["source_url"], "summary": "",
                    "related": [{"title": r["title"], "summary": r["summary"],
                                 "url": r["source_url"]} for r in e["related"]],
                })
            else:
                items.append(page_item(cat["id"], e, "entry"))
    for n, it in enumerate(items):
        it["order"] = n
    return items


def render_search_page(result, yomi_pairs):
    """1ファイルで動く検索ページ（docs/index.html）を生成する。"""
    as_of = next((c["overview"]["as_of"] for c in result["categories"] if c["overview"]["as_of"]), "")
    data = {
        "source": result["source"],
        "source_url": result["source_url"],
        "generated_at": result["generated_at"],
        "as_of": as_of,
        "categories": [{"id": c["id"], "name": c["name"], "description": c["description"],
                        "color": CAT_COLORS[c["id"]]} for c in result["categories"]],
        "items": search_items(result),
        # ひらがな入力を漢字表記に置き換えるための読み辞書（漢字を含む語のみ）
        "yomi": [[s, r] for s, r in yomi_pairs if KANJI.search(s) or re.search(r"[A-Za-z]", s)],
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    head, body = TEMPLATE.read_text(encoding="utf-8").split("<!--BODY-->")
    body = body.replace("__DATA__", payload)
    html = ('<!doctype html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + head.strip() + "\n</head>\n<body>\n" + body.strip() + "\n</body>\n</html>\n")
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(html, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="キャッシュを使わず再取得する")
    args = ap.parse_args()

    DATA.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    result = {
        "title": "所得税の辞書",
        "source": "国税庁 タックスアンサー（よくある税の質問）所得税",
        "source_url": BASE + "/taxes/shiraberu/taxanswer/code/index.htm",
        "generated_at": datetime.date.today().isoformat(),
        "categories": [],
    }
    yomi_pairs = load_yomi()
    table = dict(yomi_pairs)
    maxlen = max(len(s) for s in table)
    for cat in CATEGORIES:
        overview, soup = parse_page(cat["overview"], fetch(cat["overview"], args.refresh))
        if cat["id"] == "hikazei":
            entries = extract_hikazei(soup, args.refresh)
        else:
            entries = [parse_page(c, fetch(c, args.refresh))[0] for c in cat["pages"]]
        add_yomi([overview] + entries, table, maxlen)
        result["categories"].append({
            "id": cat["id"],
            "name": cat["name"],
            "description": cat["description"],
            "overview": overview,
            "entries": entries,
        })
        (DOCS / f"{cat['id']}.md").write_text(render_md(cat, overview, entries), encoding="utf-8")
        print(f"{cat['name']}: {len(entries)} 項目", file=sys.stderr)

    (DATA / "income_tax_dictionary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_search_page(result, yomi_pairs)


if __name__ == "__main__":
    main()
