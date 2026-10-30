#!/usr/bin/env python3
"""国税庁タックスアンサー（所得税）と法令解釈通達から「所得税区分辞書」を生成する。

カテゴリ:
  - 非課税     : No.2011「課税される所得と非課税所得」の表から各非課税所得を項目化
  - 所得区分   : No.1300 と 10種類の所得の各ページ
  - 青色申告   : No.2070 と青色申告特別控除・青色事業専従者給与・届出などのページ（要点と関連通達つき）
  - 所得控除   : No.1100 と各所得控除のページ
  - 税額控除   : No.1200 と各税額控除のページ
  - 国税庁の記事: タックスアンサーと質疑応答事例（所得税・源泉所得税・譲渡所得）。scripts/kiji.py
  - 通達       : 法令解釈通達の所得税基本通達と個別通達（所得税関係）。scripts/tsutatsu.py

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
TA = BASE + "/taxes/shiraberu/taxanswer/{}/{}.htm"
# 「所得税」以外の分野に載っているタックスアンサー（年末調整は「源泉所得税」）
TA_FOLDERS = {code: "gensen" for code in ["2662", "2665", "2668", "2671", "2672", "2674", "2675", "2676", "2517", "2518",
                                           "2511", "2523"]}
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
DATA = ROOT / "data"
DOCS = ROOT / "dictionary"
SITE = ROOT / "docs"
TEMPLATE = Path(__file__).resolve().parent / "search_template.html"
YOMI = DATA / "yomi.tsv"
EXAMPLES = DATA / "shotoku_examples.json"
POINTS = DATA / "aoiro_points.json"
KOJO_EXAMPLES = DATA / "kojo_examples.json"
ZEIGAKU_EXAMPLES = DATA / "zeigaku_examples.json"
AOIRO_EXAMPLES = DATA / "aoiro_examples.json"
HIKAZEI_EXAMPLES = DATA / "hikazei_examples.json"
NENMATSU_POINTS = DATA / "nenmatsu_points.json"
NENMATSU_EXAMPLES = DATA / "nenmatsu_examples.json"
ZEIGAKUHYO = DATA / "zeigakuhyo.json"
ZEIRITSU = DATA / "zeiritsu.json"
CAT_COLORS = {"hikazei": "hikazei", "shotoku-kubun": "kubun", "aoiro": "aoiro",
              "shotoku-kojo": "shotoku", "nenmatsu": "nenmatsu", "zeigaku-kojo": "zeigaku", "tsutatsu": "tsutatsu"}
KIJI_TAB = {
    "id": "kiji", "name": "国税庁の記事", "color": "kiji",
    "subtabs": [
        {"id": "taxanswer", "name": "タックスアンサー", "children": [
            {"id": "ta-shotoku", "name": "所得税"}, {"id": "ta-gensen", "name": "源泉所得税"}, {"id": "ta-joto", "name": "譲渡所得"}]},
        {"id": "shitsugi", "name": "質疑応答事例", "children": [
            {"id": "qa-shotoku", "name": "所得税"}, {"id": "qa-gensen", "name": "源泉所得税"}, {"id": "qa-joto", "name": "譲渡所得"}]},
    ],
}
TSUTATSU_TAB = {
    "id": "tsutatsu", "name": "通達", "color": "tsutatsu",
    "subtabs": [{"id": "kihon", "name": "基本通達", "children": []}, {"id": "kobetsu", "name": "個別通達"},
                {"id": "sochiho", "name": "措置法通達", "children": []}],
}

CATEGORIES = [
    {
        "id": "hikazei",
        "name": "非課税",
        "overview": "2011",
        "pages": [],  # 表から抽出する
        # No.2011 の表の「区分」ごとのタブ（pages の代わりに group で振り分ける）
        "subtabs": [
            {"id": "hk-rishi", "name": "利子・配当所得関係", "group": "利子・配当所得関係", "pages": []},
            {"id": "hk-kyuyo", "name": "給与所得・公的年金関係", "group": "給与所得・公的年金関係", "pages": []},
            {"id": "hk-joto", "name": "譲渡（山林）所得関係", "group": "譲渡(山林)所得関係", "pages": []},
            {"id": "hk-sonota", "name": "その他", "group": "その他", "pages": []},
        ],
    },
    {
        "id": "shotoku-kubun",
        "name": "所得区分",
        "overview": "1300",
        # 所得税法（23条〜35条）の順
        "pages": ["1310", "2230", "1330", "1331", "1370", "1350", "1400", "2220", "1420",
                  "1480", "2240", "1460", "1440", "1463", "1490", "1755", "1520", "1500", "1522", "1521", "1523"],
        # 検索ページで「所得区分」タブの下に出すタブ
        "subtabs": [
            {"id": "rishi", "name": "利子所得", "pages": ["1310", "2230"],
             "children": [
                 {"id": "rishi-sogo", "name": "総合課税", "pages": ["1310"]},
                 {"id": "rishi-bunri", "name": "分離課税", "pages": ["1310", "2230"]},
             ]},
            {"id": "haito", "name": "配当所得", "pages": ["1330", "1331"],
             "children": [
                 {"id": "haito-sogo", "name": "総合課税", "pages": ["1330"]},
                 {"id": "haito-bunri", "name": "分離課税", "pages": ["1331"]},
             ]},
            {"id": "fudosan", "name": "不動産所得", "pages": ["1370", "2220"],
             "children": [{"id": "fudosan-sogo", "name": "総合課税", "pages": ["1370", "2220"]}]},
            {"id": "jigyo", "name": "事業所得", "pages": ["1350", "2220"],
             "children": [{"id": "jigyo-sogo", "name": "総合課税", "pages": ["1350", "2220"]}]},
            {"id": "kyuyo", "name": "給与所得", "pages": ["1400", "2220"],
             "children": [{"id": "kyuyo-sogo", "name": "総合課税", "pages": ["1400", "2220"]}]},
            {"id": "taishoku", "name": "退職所得", "pages": ["1420", "2240"],
             "children": [
                 {"id": "taishoku-bunri", "name": "分離課税", "pages": ["1420", "2240"]},
             ]},
            {"id": "sanrin", "name": "山林所得", "pages": ["1480", "2240"],
             "children": [
                 {"id": "sanrin-bunri", "name": "分離課税", "pages": ["1480", "2240"]},
             ]},
            {"id": "joto", "name": "譲渡所得", "pages": ["1460", "1440", "1463"],
             # 譲渡所得の下のタブ（課税方法）
             "children": [
                 {"id": "joto-sogo", "name": "総合課税", "pages": ["1460"]},
                 {"id": "joto-bunri", "name": "分離課税", "pages": ["1440", "1463"]},
             ]},
            {"id": "ichiji", "name": "一時所得", "pages": ["1490", "1755", "1520"],
             "children": [
                 {"id": "ichiji-sogo", "name": "総合課税", "pages": ["1490", "1755"]},
                 {"id": "ichiji-bunri", "name": "分離課税", "pages": ["1520"]},
             ]},
            {"id": "zatsu", "name": "雑所得", "pages": ["1500", "1522", "1521", "1523"],
             "children": [
                 {"id": "zatsu-sogo", "name": "総合課税", "pages": ["1500"]},
                 {"id": "zatsu-bunri", "name": "分離課税", "pages": ["1522", "1521", "1523"]},
             ]},
        ],
    },
    {
        "id": "aoiro",
        "name": "青色申告",
        "overview": "2070",
        "pages": ["2072", "2075", "2090", "2080"],
        "subtabs": [
            {"id": "aoiro-kojo", "name": "青色申告特別控除", "pages": ["2072"]},
            {"id": "senjusha", "name": "青色事業専従者給与", "pages": ["2075"]},
            {"id": "aoiro-tetsuzuki", "name": "届出・手続", "pages": ["2090"]},
            {"id": "shiroiro", "name": "白色申告者の記帳・帳簿保存", "pages": ["2080"]},
        ],
        # 関連する所得税基本通達（「法第○条《…》関係」の条番号で選ぶ）
        "related_tsutatsu": r"^法第(52|57|14[3-9]|15[01])条《",
    },
    {
        "id": "shotoku-kojo",
        "name": "所得控除",
        "overview": "1100",
        # 所得税法（72条〜86条）の順
        "pages": ["1110", "1120", "1129", "1130", "1135", "1140", "1145",
                  "1150", "1160", "1170", "1171", "1172", "1175", "1191",
                  "1195", "1180", "1177", "1199"],
        "subtabs": [
            {"id": "zasson", "name": "雑損控除", "pages": ["1110"]},
            {"id": "iryohi", "name": "医療費控除", "pages": ["1120", "1129"]},
            {"id": "shakaihoken", "name": "社会保険料控除", "pages": ["1130"]},
            {"id": "shokibo", "name": "小規模企業共済等掛金控除", "pages": ["1135"]},
            {"id": "seimeihoken", "name": "生命保険料控除", "pages": ["1140"]},
            {"id": "jishinhoken", "name": "地震保険料控除", "pages": ["1145"]},
            {"id": "kifukin", "name": "寄附金控除", "pages": ["1150"]},
            {"id": "shogaisha", "name": "障害者控除", "pages": ["1160"]},
            {"id": "kafu", "name": "寡婦控除", "pages": ["1170"]},
            {"id": "hitorioya", "name": "ひとり親控除", "pages": ["1171"]},
            {"id": "kafu-otto", "name": "寡夫控除", "pages": ["1172"]},
            {"id": "kinrogakusei", "name": "勤労学生控除", "pages": ["1175"]},
            {"id": "haigusha", "name": "配偶者控除", "pages": ["1191"]},
            {"id": "haigusha-tokubetsu", "name": "配偶者特別控除", "pages": ["1195"]},
            {"id": "fuyo", "name": "扶養控除", "pages": ["1180"]},
            {"id": "tokutei-shinzoku", "name": "特定親族特別控除", "pages": ["1177"]},
            {"id": "kiso", "name": "基礎控除", "pages": ["1199"]},
        ],
    },
    {
        "id": "nenmatsu",
        "name": "年末調整",
        "overview": "2662",
        "pages": ["2665", "2674", "2517", "2518", "2668", "2672", "2676", "1230", "2675", "2671", "1900", "1910",
                  "2511", "2523"],
        "subtabs": [
            {"id": "nc-taisho", "name": "対象となる人", "pages": ["2665", "2674", "2517", "2518"]},
            {"id": "nc-kyuyo", "name": "対象となる給与", "pages": ["2668"]},
            {"id": "nc-kojo", "name": "控除の申告", "pages": ["2672", "2676", "1230"]},
            {"id": "nc-seisan", "name": "精算・やり直し", "pages": ["2675", "2671"]},
            {"id": "nc-shinkoku", "name": "確定申告が必要な場合", "pages": ["1900", "1910"]},
            # 税額表の使い方のページと、源泉徴収税額表そのもの（data/zeigakuhyo.json、scripts/zeigakuhyo.py）
            {"id": "nc-zeigakuhyo", "name": "源泉徴収税額表", "pages": ["2511", "2523"]},
        ],
        # 年末調整と給与所得者の源泉徴収に関する申告書の通達（法183条〜198条）
        "related_tsutatsu": r"^法第(183条から第193条まで|19[0-2]条《|194条から第198条まで|195条の[2-4]《|196条《)",
    },
    {
        "id": "zeigaku-kojo",
        "name": "税額控除",
        "overview": "1200",
        # 所得税法（92条・95条）、租税特別措置法（10条〜41条の18の3）の順
        "pages": ["1250", "1240", "1241", "1270", "1284", "1286", "1288",
                  "1210", "1260", "1263", "1266"],
        "subtabs": [
            {"id": "haito-kojo", "name": "配当控除", "pages": ["1250"]},
            {"id": "gaikoku", "name": "外国税額控除", "pages": ["1240", "1241"]},
            {"id": "shiken", "name": "試験研究の特別控除", "pages": ["1270"]},
            {"id": "koyo", "name": "雇用者の数が増加した場合の特別控除", "pages": ["1284"]},
            {"id": "kyuyo-zoka", "name": "給与等が増加した場合の特別控除", "pages": ["1286", "1288"]},
            {"id": "jutaku", "name": "マイホームの取得等の税額控除", "pages": ["1210"]},
            {"id": "seito", "name": "政党等寄附金特別控除", "pages": ["1260"]},
            {"id": "npo", "name": "認定NPO法人等寄附金特別控除", "pages": ["1263"]},
            {"id": "koeki", "name": "公益社団法人等寄附金特別控除", "pages": ["1266"]},
        ],
    },
]

# 本文として扱わない見出し
STOP_HEADINGS = {"関連リンク", "お問い合わせ先", "QAリンク", "関連コード"}


def ta_url(code):
    return TA.format(TA_FOLDERS.get(code, "shotoku"), code)


def fetch(code, refresh=False):
    CACHE.mkdir(exist_ok=True)
    folder = TA_FOLDERS.get(code, "shotoku")
    path = CACHE / (f"{code}.htm" if folder == "shotoku" else f"{folder}-{code}.htm")
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    url = ta_url(code)
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
    if node.name == "img":  # 表や図が画像のときは代替テキストを残す
        alt = clean(node.get("alt") or "")
        # 番号のアイコン（「1」など）のような短いものは、そのまま文字として残す
        return alt if len(alt) <= 3 else f"［図：{alt}］"
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
        "source_url": ta_url(code),
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
                "source_url": ta_url("2011"),
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


def _plain(md):
    return re.sub(r"\s|\*\*", "", re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md))


def add_examples(pages, ta_pages, kihon, path=EXAMPLES, key="examples", data=None, key_of=lambda p: p["code"]):
    """各ページに出典付きの箇条書き（所得区分の具体例、青色申告の要点など）を付ける。

    各項目の quote が出典の本文に実在するかを照合し、見つからなければ止める。
    """
    if data is None:
        data = json.loads(path.read_text(encoding="utf-8"))
    sources = {code: (f"No.{code}", p["source_url"], p["content_md"]) for code, p in ta_pages.items()}
    sources.update({f"所基通{e['no']}": (f"所基通{e['no']}", e["source_url"], e["content_md"]) for e in kihon})
    errors = []
    for page in pages:
        page[key] = []
        for ex in data.get(key_of(page), []):
            if ex["src"] not in sources and re.fullmatch(r"\d{4}", ex["src"]):
                # カテゴリ外のタックスアンサー（No.1122 など）も出典にできる
                p, _ = parse_page(ex["src"], fetch(ex["src"]))
                sources[ex["src"]] = (f"No.{ex['src']}", p["source_url"], p["content_md"])
            label, url, md = sources.get(ex["src"], (None, None, ""))
            if label is None or _plain(ex["quote"]) not in _plain(md):
                errors.append(f"  {key_of(page)} {ex['text']}: {ex['src']} に「{ex['quote']}」が見つかりません")
                continue
            page[key].append({"text": ex["text"], "source": label, "url": url,
                              "other": ex.get("other", ""), "tax": ex.get("tax", "")})
    if errors:
        raise SystemExit(f"{path.name} の出典を確認してください。\n" + "\n".join(errors))


def add_hikazei_examples(entries, overview, kihon):
    """非課税の各項目（No.2011 の表の行）に具体例を付ける。行の順番と用語が data と合っているかも確かめる。"""
    raw = json.loads(HIKAZEI_EXAMPLES.read_text(encoding="utf-8"))
    for i, e in enumerate(entries, 1):
        e["hk_id"] = f"hk{i}"
        if e["hk_id"] in raw and raw[e["hk_id"]]["_term"] != e["term"]:
            raise SystemExit(f"{HIKAZEI_EXAMPLES.name}: {e['hk_id']} の用語が No.2011 の表と違います: {e['term']}")
    data = {k: v["examples"] for k, v in raw.items() if not k.startswith("_")}
    add_examples(entries, {overview["code"]: overview}, kihon, HIKAZEI_EXAMPLES, data=data, key_of=lambda p: p["hk_id"])


def _example_lines(exs, indent="", tax_heading="課税方法"):
    lines = []
    for heading, items in (("具体例", [x for x in exs if not x["other"] and not x.get("tax")]),
                           (tax_heading, [x for x in exs if x.get("tax")]),
                           ("当たらない例", [x for x in exs if x["other"]])):
        if items:
            lines.append(f"{indent}- **{heading}**:")
            lines += [f"{indent}  - {x['text']}" + (f" → {x['other'] or x.get('tax')}" if x["other"] or x.get("tax") else "")
                      + f"（[{x['source']}]({x['url']})）" for x in items]
    return lines


def render_md(cat, overview, entries):
    source = (f"出典: 国税庁タックスアンサー [{overview['title']}]({overview['source_url']})"
              + (f"（{overview['as_of']}）" if overview["as_of"] else ""))
    # 本文の「### 概要」はページの「## 概要」と重なるので外す
    summary_md = re.sub(r"\A### 概要\n\n", "", overview["content_md"])
    summary = ["## 概要", "", summary_md, ""]
    if overview.get("points"):
        summary = ["## 要点", ""] + [f"- {x['text']}（[{x['source']}]({x['url']})）" for x in overview["points"]] + [""] + summary

    # 並び: 説明 → 概要 → 目次 → 用語 → 根拠法令等・出典
    lines = [f"# {cat['name']}", ""] + summary + ["## 目次", ""]
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
                lines += _example_lines(e.get("examples", []))
                for r in e["related"]:
                    lines.append(f"- **関連**: [{r['title']}]({r['source_url']})")
                if e["legal_basis"]:
                    lines.append(f"- **根拠法令**: {e['legal_basis']}")
                lines.append("")
    else:
        lines += ["## 用語", ""]
        for e in entries:
            lines += [f'<a id="no{e["code"]}"></a>', "", f"### {e['term']}", "",
                      f"- **読み**: {e['yomi']}"]
            if e["summary"]:
                lines.append(f"- **要旨**: {e['summary']}")
            lines += _example_lines(e.get("examples", []), tax_heading="取扱い" if cat["id"] == "nenmatsu" else "課税方法")
            lines += ["", "<details><summary>詳細（タックスアンサー本文）</summary>", "",
                      demote(e["content_md"]), "", "</details>", ""]
            if e["legal_basis"]:
                lines.append(f"- **根拠法令等**: {e['legal_basis']}")
            if e["as_of"]:
                lines.append(f"- **基準**: {e['as_of']}")
            lines += [f"- **タックスアンサー**: [{e['title']}]({e['source_url']})", ""]
    if overview.get("related_tsutatsu"):
        lines += ["## 関連する通達", ""] + [f"- [所得税基本通達 {t['term']}]({t['url']})" for t in overview["related_tsutatsu"]] + [""]
    lines += ["---", ""]
    if overview["legal_basis"]:
        lines += [f"**根拠法令等**: {overview['legal_basis']}", ""]
    lines += [source, ""]
    return "\n".join(lines).rstrip() + "\n"


def demote(md):
    return re.sub(r"^(#{3,5}) ", lambda m: "#" * (len(m.group(1)) + 1) + " ", md, flags=re.M)


def search_items(result):
    """検索ページ用に全カテゴリの項目を1つのリストにする。"""
    items = []
    # 1つのページが複数の下のタブに属することがある（No.2240 は退職所得と山林所得の両方）
    subs_of = {}
    for cat in CATEGORIES:
        for t in cat.get("subtabs", []):
            for code in t["pages"]:
                subs_of.setdefault(code, []).append(t["id"])
    # 3段目のタブは、1つのページが複数のタブに属することがある（No.1310 は総合課税と分離課税の両方）
    sub2_of = {}
    for cat in CATEGORIES:
        for t in cat.get("subtabs", []):
            for c in t.get("children", []):
                for code in c["pages"]:
                    sub2_of.setdefault(code, []).append(c["id"])
    sub_ids = [t["id"] for cat in CATEGORIES for t in cat.get("subtabs", [])] + \
        [c["id"] for cat in CATEGORIES for t in cat.get("subtabs", []) for c in t.get("children", [])]
    assert len(sub_ids) == len(set(sub_ids)), "下のタブの id が重複しています"
    sub_of_group = {t["group"]: t["id"] for cat in CATEGORIES for t in cat.get("subtabs", []) if "group" in t}

    def page_item(cat_id, page, kind):
        return {
            "id": f"no{page['code']}", "cat": cat_id, "sub": subs_of.get(page["code"], [""])[0], "subs": subs_of.get(page["code"], []),
            "sub2": sub2_of.get(page["code"], []), "kind": kind,
            "term": page["term"], "yomi": page["yomi"], "code": page["code"], "title": page["title"],
            "summary": page["summary"], "basis": page["legal_basis"],
            "asOf": page["as_of"], "url": page["source_url"], "md": page["content_md"],
            "examples": page.get("examples", []), "points": page.get("points", []),
            "relatedTsutatsu": page.get("related_tsutatsu", []),
        }

    for cat in result["categories"]:
        items.append(page_item(cat["id"], cat["overview"], "overview"))
        for i, e in enumerate(cat["entries"], 1):
            if cat["id"] == "hikazei":
                items.append({
                    "id": f"hk{i}", "cat": cat["id"], "sub": sub_of_group[e["group"]], "kind": "hikazei",
                    "term": e["term"], "yomi": e["yomi"], "alias": e["alias"], "group": e["group"],
                    "basis": e["legal_basis"], "asOf": cat["overview"]["as_of"],
                    "url": e["source_url"], "summary": "",
                    "related": [{"title": r["title"], "summary": r["summary"],
                                 "url": r["source_url"]} for r in e["related"]],
                    "examples": e.get("examples", []),
                })
            else:
                items.append(page_item(cat["id"], e, "entry"))
    for n, it in enumerate(items):
        it["order"] = n
    return items


def check_zeigakuhyo(tables, page):
    """源泉徴収税額表から求めた税額が、No.2523 の計算例（令和8年分）と一致するかを確かめる。"""
    import zeigakuhyo as z
    t = {x["id"]: x for x in tables}
    m, b = t["zh-r08-getsugaku"], t["zh-r08-shoyo"]
    cases = [  # （求めた値, No.2523 の本文にある値）
        (z.wage_tax(m, 444541, 1), "16,100円"), (z.wage_tax(m, 166531, 1), "1,510円"),
        (z.wage_tax(m, 128216, 0), "1,300円"), (z.bonus_rate(b, 285454, 3), "2.042％"),
        (z.bonus_tax(b, m, 285454, 389558, 3), "7,954円"), (z.bonus_tax(b, m, 166531, 1668062, 1), "87,540円"),
        (z.bonus_tax(b, m, 0, 769300, 0), "7,800円"),
    ]
    body = _plain(page["content_md"])
    errors = []
    for got, want in cases:
        text = f"{got:g}％" if isinstance(got, float) else f"{got:,}円"
        if text != want or want not in body:
            errors.append(f"  {text}（No.2523 では {want}）")
    if errors:
        raise SystemExit("源泉徴収税額表の計算が No.2523 の計算例と合いません。\n" + "\n".join(errors))


def build_zeiritsu(taxanswer, item_ids):
    """税率のまとめ（data/zeiritsu.json）に出典を付ける。各行の quote がタックスアンサーの本文にあるかを照合する。"""
    pages = {e["code"]: e for e in taxanswer}
    items, errors = [], []

    def source(x):
        page = pages.get(x["src"])
        if page is None or _plain(x["quote"]) not in _plain(page["content_md"]):
            errors.append(f"  {x.get('label') or x['text']}: No.{x['src']} に「{x['quote']}」が見つかりません")
            return {}
        jump = f"no{page['code']}" if f"no{page['code']}" in item_ids else f"ta-{page['folder']}{page['code']}"
        return {"source": f"No.{page['code']}", "url": page["source_url"], "jump": jump, "title": page["title"]}

    for it in json.loads(ZEIRITSU.read_text(encoding="utf-8"))["items"]:
        rows = [{k: r[k] for k in ("label", "rate", "note")} | source(r) for r in it["rows"]]
        notes = [{"text": n["text"]} | source(n) for n in it["notes"]]
        items.append({"id": it["id"], "term": it["term"], "summary": it["summary"], "head": it["head"],
                      "rows": rows, "notes": notes})
    if errors:
        raise SystemExit(f"{ZEIRITSU.name} の出典を確認してください。\n" + "\n".join(errors))
    return items


def zeiritsu_search_items(items):
    out = []
    for it in items:
        srcs = list({x["url"]: {"title": x["title"], "url": x["url"]} for x in it["rows"] + it["notes"]}.values())
        md = "\n\n".join([it["summary"]] + [f"{r['label']} {r['rate']} {r['note']}" for r in it["rows"]] +
                          [n["text"] for n in it["notes"]])
        out.append({"id": it["id"], "cat": "zeiritsu", "sub": "", "subs": [], "sub2": [], "kind": "zeiritsu",
                    "term": it["term"], "yomi": it["yomi"], "summary": it["summary"], "md": md, "head": it["head"],
                    "rows": it["rows"], "notes": it["notes"], "sources": srcs, "url": srcs[0]["url"],
                    "srcLabel": "タックスアンサー", "srcTitle": srcs[0]["title"]})
    return out


def render_zeiritsu_md(items):
    lines = ["# 税率", "", "国税庁タックスアンサーをもとに、所得税の税率を整理したもの。", ""]
    for it in items:
        lines += [f"## {it['term']}", "", it["summary"], "", "| " + " | ".join(it["head"] + ["出典"]) + " |",
                  "|" + "---|" * (len(it["head"]) + 1)]
        lines += [f"| {r['label']} | {r['rate']} | {r['note']} | [{r['source']}]({r['url']}) |" for r in it["rows"]]
        lines.append("")
        lines += [f"- {n['text']}（[{n['source']}]({n['url']})）" for n in it["notes"]]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_search_page(result, yomi_pairs, extra_items):
    """1ファイルで動く検索ページ（docs/index.html）を生成する。"""
    as_of = next((c["overview"]["as_of"] for c in result["categories"] if c["overview"]["as_of"]), "")
    data = {
        "source": result["source"],
        "source_url": result["source_url"],
        "generated_at": result["generated_at"],
        "as_of": as_of,
        "categories": [{"id": c["id"], "name": c["name"],
                        "color": CAT_COLORS[c["id"]],
                        "subtabs": [{"id": t["id"], "name": t["name"],
                                     "children": [{"id": c["id"], "name": c["name"]} for c in t.get("children", [])]}
                                    for t in conf.get("subtabs", [])]}
                       for c, conf in zip(result["categories"], CATEGORIES)] + [KIJI_TAB, TSUTATSU_TAB],
        "items": search_items(result) + extra_items,
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
        "title": "所得税区分辞書",
        "source": "国税庁 タックスアンサー（よくある税の質問）所得税・法令解釈通達",
        "source_url": BASE + "/taxes/shiraberu/taxanswer/code/index.htm",
        "generated_at": datetime.date.today().isoformat(),
        "categories": [],
    }
    import tsutatsu
    kihon = tsutatsu.build_kihon(args.refresh)
    kobetsu = tsutatsu.build_kobetsu(args.refresh)
    sochiho, kobetsu = tsutatsu.build_sochiho(kobetsu, args.refresh)
    TSUTATSU_TAB["subtabs"][0]["children"] = [{"id": kid, "name": name} for kid, name, _ in tsutatsu.KIHON_KUBUN]
    TSUTATSU_TAB["subtabs"][2]["children"] = [{"id": sid, "name": label} for _, sid, label in tsutatsu.SOCHIHO]
    yomi_pairs = load_yomi()
    table = dict(yomi_pairs)
    maxlen = max(len(s) for s in table)
    for cat in CATEGORIES:
        overview, soup = parse_page(cat["overview"], fetch(cat["overview"], args.refresh))
        if cat["id"] == "hikazei":
            entries = extract_hikazei(soup, args.refresh)
            add_hikazei_examples(entries, overview, kihon)
        else:
            entries = [parse_page(c, fetch(c, args.refresh))[0] for c in cat["pages"]]
        add_yomi([overview] + entries, table, maxlen)
        if cat["id"] == "shotoku-kubun":
            add_examples(entries, {p["code"]: p for p in [overview] + entries}, kihon)
        if cat["id"] == "shotoku-kojo":
            add_examples(entries, {p["code"]: p for p in [overview] + entries}, kihon, KOJO_EXAMPLES)
        if cat["id"] == "zeigaku-kojo":
            add_examples(entries, {p["code"]: p for p in [overview] + entries}, kihon, ZEIGAKU_EXAMPLES)
        if cat["id"] == "aoiro":
            add_examples([overview], {p["code"]: p for p in [overview] + entries}, kihon, POINTS, "points")
            add_examples(entries, {p["code"]: p for p in [overview] + entries}, kihon, AOIRO_EXAMPLES)
        if cat["id"] == "nenmatsu":
            add_examples([overview], {p["code"]: p for p in [overview] + entries}, kihon, NENMATSU_POINTS, "points")
            add_examples(entries, {p["code"]: p for p in [overview] + entries}, kihon, NENMATSU_EXAMPLES)
        if cat.get("related_tsutatsu"):
            overview["related_tsutatsu"] = [
                {"id": f"tk{i}", "term": e["term"], "url": e["source_url"]}
                for i, e in enumerate(kihon, 1) if re.match(cat["related_tsutatsu"], e["group"])]
        result["categories"].append({
            "id": cat["id"],
            "name": cat["name"],
            "overview": overview,
            "entries": entries,
        })
        (DOCS / f"{cat['id']}.md").write_text(render_md(cat, overview, entries), encoding="utf-8")
        print(f"{cat['name']}: {len(entries)} 項目", file=sys.stderr)

    import zeigakuhyo
    tables = json.loads(ZEIGAKUHYO.read_text(encoding="utf-8"))
    nenmatsu = next(c for c in result["categories"] if c["id"] == "nenmatsu")
    check_zeigakuhyo(tables, next(e for e in nenmatsu["entries"] if e["code"] == "2523"))
    result["zeigakuhyo"] = tables
    (DOCS / "gensen-zeigakuhyo.md").write_text(zeigakuhyo.render_md(tables), encoding="utf-8")
    print(f"源泉徴収税額表: {len(tables)} 表", file=sys.stderr)

    result["tsutatsu"] = {"kihon": kihon, "kobetsu": kobetsu, "sochiho": sochiho}
    (DOCS / "tsutatsu-kihon.md").write_text(tsutatsu.render_kihon_md(kihon), encoding="utf-8")
    (DOCS / "tsutatsu-kobetsu.md").write_text(tsutatsu.render_kobetsu_md(kobetsu), encoding="utf-8")
    (DOCS / "tsutatsu-sochiho.md").write_text(tsutatsu.render_sochiho_md(sochiho), encoding="utf-8")
    print(f"通達: 基本通達 {len(kihon)} 項目、個別通達 {len(kobetsu)} 項目、措置法通達 {len(sochiho)} 項目", file=sys.stderr)

    import kiji
    taxanswer = kiji.build_taxanswer(args.refresh)
    shitsugi = kiji.build_shitsugi(args.refresh)
    result["kiji"] = {"taxanswer": taxanswer, "shitsugi": shitsugi}
    (DOCS / "kiji-taxanswer.md").write_text(kiji.render_md(
        "タックスアンサー（所得税・源泉所得税・譲渡所得）",
        taxanswer, "ta"), encoding="utf-8")
    (DOCS / "kiji-shitsugi.md").write_text(kiji.render_md(
        "質疑応答事例（所得税・源泉所得税・譲渡所得）",
        shitsugi, "qa"), encoding="utf-8")
    print(f"国税庁の記事: タックスアンサー {len(taxanswer)} 件、質疑応答事例 {len(shitsugi)} 件", file=sys.stderr)

    item_ids = {it["id"] for it in search_items(result)}
    zeiritsu = build_zeiritsu(taxanswer, item_ids)
    add_yomi(zeiritsu, table, maxlen)
    result["zeiritsu"] = zeiritsu
    (DOCS / "zeiritsu.md").write_text(render_zeiritsu_md(zeiritsu), encoding="utf-8")
    print(f"税率: {len(zeiritsu)} 項目", file=sys.stderr)

    (DATA / "income_tax_dictionary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_search_page(result, yomi_pairs, zeiritsu_search_items(zeiritsu) + zeigakuhyo.search_items(tables) +
                       kiji.search_items(taxanswer, shitsugi) + tsutatsu.search_items(kihon, kobetsu, sochiho))


if __name__ == "__main__":
    main()
