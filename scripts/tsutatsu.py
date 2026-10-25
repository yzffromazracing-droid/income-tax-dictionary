"""国税庁ホームページの法令解釈通達（所得税）を取得して項目に分ける。

  - 所得税基本通達: 「9-3」などの通達番号ごとに1項目
  - 個別通達（所得税関係）: 通達ごとに1項目。5ページを超える通達はページごとに1項目
  - 措置法通達: 租税特別措置法関係の主な4つの通達を、「31・32共-1」などの通達番号ごとに1項目（個別通達からは除く）
"""

import posixpath
import re
import time
import urllib.request

from bs4 import BeautifulSoup, Tag

from build_dictionary import BASE, CACHE, block_to_md, clean

KIHON_INDEX = "/law/tsutatsu/kihon/shotoku/01.htm"
KOBETSU_GROUPS = [
    ("申告所得税関係", "/law/tsutatsu/kobetsu/shotoku/shinkoku/sinkoku.htm"),
    ("源泉所得税関係", "/law/tsutatsu/kobetsu/shotoku/gensen/gensen.htm"),
    ("譲渡・山林所得関係", "/law/tsutatsu/kobetsu/shotoku/joto-sanrin/sanrin.htm"),
    ("租税特別措置法関係", "/law/tsutatsu/kobetsu/shotoku/sochiho/sotihou.htm"),
]
# 措置法通達として通達番号ごとに分ける通達（個別通達の「租税特別措置法関係」の名前、下のタブの id・名前）
SOCHIHO = [
    ("租税特別措置法に係る所得税の取扱いについて", "so-shotoku", "所得税関係"),
    ("租税特別措置法に係る所得税の取扱い《源泉所得税関係》について", "so-gensen", "源泉所得税関係"),
    ("租税特別措置法（株式等に係る譲渡所得等関係）の取扱いについて", "so-kabu", "株式等に係る譲渡所得等関係"),
    ("租税特別措置法（山林所得・譲渡所得関係）の取扱いについて", "so-joto", "山林所得・譲渡所得関係"),
]
SPLIT_PAGES = 5  # これを超えるページ数の個別通達はページごとに分ける
MAX_PAGES = 400

NUMBER = re.compile(r"^\s*([0-9０-９][0-9０-９・共の\-－‐]*[－\-‐][0-9０-９][0-9０-９の]*)[\s　]")


def fetch_path(path, refresh=False):
    """国税庁サイトのページを取得する（Shift_JIS のページも UTF-8 にして保存）。"""
    cache = CACHE / "law" / (path.strip("/").replace("/", "_"))
    if cache.exists() and not refresh:
        return cache.read_text(encoding="utf-8")
    cache.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "income-tax-dictionary/1.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        if res.geturl().endswith("/error/404.htm"):
            raise RuntimeError(f"not found: {BASE + path}")
        raw = res.read()
    m = re.search(rb'charset=["\']?([\w-]+)', raw[:3000])
    enc = m.group(1).decode().lower() if m else "utf-8"
    html = raw.decode("cp932" if enc in ("shift_jis", "shift-jis", "sjis", "x-sjis") else enc, errors="replace")
    cache.write_text(html, encoding="utf-8")
    time.sleep(0.5)  # 国税庁サーバーへの負荷軽減
    return html


def body_soup(html):
    """テンプレートの本文領域（bodyArea）だけを取り出す。"""
    i = html.find('name="bodyArea"')
    if i < 0:
        i = html.find("<h1")
    j = html.find("InstanceEndEditable", i)
    return BeautifulSoup(html[html.find(">", i) + 1 if i >= 0 else 0: j if j > 0 else None], "lxml")


def flatten(nodes):
    for el in nodes:
        if not isinstance(el, Tag):
            continue
        if el.name in ("div", "body", "html", "section") and el.find(["h1", "h2", "p", "table"]):
            yield from flatten(el.children)
        else:
            yield el


def resolve(base, href):
    href = href.split("#")[0]
    if not href or href.startswith(("http", "mailto")):
        return href
    return href if href.startswith("/") else posixpath.normpath(posixpath.join(posixpath.dirname(base), href))


# ---- 所得税基本通達 ----

def kihon_index(refresh):
    """目次から、各ページの見出し（編・章・「法第○条関係」）を集める。"""
    soup = body_soup(fetch_path(KIHON_INDEX, refresh))
    pages, labels, hen, sho, law = {}, {}, "", "", ""
    for el in soup.find_all(["h2", "h3", "p", "li"]):
        text = clean(el.get_text())
        if el.name == "h2":
            hen, law = text, ""
        elif el.name == "h3":
            sho, law = text, ""
        elif el.name == "p" and "関係" in text:
            law = text
            m = re.match(r"法第(\d+)条(の\d+)?", text)
            if m:
                labels.setdefault(m.group(1) + (m.group(2) or ""), {"hen": hen, "sho": sho, "group": text})
        for a in el.find_all("a", href=True) if el.name in ("p", "li") else []:
            path = resolve(KIHON_INDEX, a["href"])
            if re.match(r"/law/tsutatsu/kihon/shotoku/\d\d/\d\d\.htm$", path) and path not in pages:
                group = law if el.name == "li" or not text.endswith("関係") else text
                pages[path] = {"hen": hen, "sho": sho, "group": group or clean(a.get_text())}
    return pages, labels


def parse_kihon_page(path, meta, refresh):
    soup = body_soup(fetch_path(path, refresh))
    items, cur, title, last_title, section, anchor = [], None, "", "", "", ""

    def close():
        nonlocal cur
        if cur:
            items.append(cur)
        cur = None

    for el in flatten(soup.children):
        text = clean(el.get_text())
        if el.name == "hr":
            close()
            continue
        if el.name == "h1" or (el.name == "p" and "txt-big" in (el.get("class") or [])):
            close()
            if text.startswith("〔"):
                section, anchor = text, el.get("id") or anchor
            continue
        if el.name in ("h2", "h3"):
            close()
            title = last_title = re.sub(r"^[（(]\s*|\s*[）)]$", "", text)
            continue
        first_child = next((c for c in el.children if not (isinstance(c, str) and not c.strip())), None) \
            if el.name == "p" else None
        m = NUMBER.match(text + " ") if isinstance(first_child, Tag) and first_child.name == "strong" else None
        if m:
            close()
            no = m.group(1).translate(str.maketrans("０１２３４５６７８９－‐", "0123456789--"))
            # 見出しのない番号は直前の見出しの続き（「削除」は除く）
            deleted = text[len(m.group(1)):].strip().startswith("削除")
            cur = {"no": no, "title": "" if deleted else (title or last_title),
                   "section": section, "anchor": anchor, "paras": []}
            title = ""
            # 通達番号は複数の <strong> に分かれていることがあるので、番号の分だけ取り除く
            taken = ""
            for c in list(el.children):
                if len(re.sub(r"\s", "", taken)) >= len(m.group(1)):
                    break
                if isinstance(c, Tag) and c.name == "strong" or isinstance(c, str) and not c.strip():
                    taken += c.get_text() if isinstance(c, Tag) else ""
                    c.extract()
                else:
                    break
            first = block_to_md(el).strip()
            if first:
                cur["paras"].append(first)
            continue
        if cur is not None:
            md = block_to_md(el).strip()
            if md:
                indent = re.search(r"indent(\d)", " ".join(el.get("class") or []))
                if indent and int(indent.group(1)) >= 2 and not md.startswith(("|", "-")):
                    md = "　" * (int(indent.group(1)) - 1) + md
                cur["paras"].append(md)
    close()
    out = []
    for it in items:
        deleted = not it["title"] and it["paras"] and it["paras"][0].startswith("削除")
        out.append({
            "no": it["no"],
            "term": f"{it['no']} {it['title'] or ('削除' if deleted else '')}".strip(),
            "title": it["title"],
            "hen": meta["hen"], "sho": meta["sho"], "group": meta["group"], "section": it["section"],
            "content_md": "\n\n".join(it["paras"]),
            "source_url": BASE + path + (f"#{it['anchor']}" if it["anchor"] else ""),
        })
    return out


def build_kihon(refresh=False):
    entries = []
    pages, labels = kihon_index(refresh)
    for path, meta in pages.items():
        entries.extend(parse_kihon_page(path, meta, refresh))
    # 1ページに複数の条の通達が載っていることがあるので、「24-1」の「24」のように番号から条を引き直す
    for e in entries:
        label = labels.get(e["no"].split("-")[0])
        if label:
            e.update(label)
    return entries


# ---- 個別通達 ----

def kobetsu_page(path, refresh):
    """個別通達の1ページを、見出し・発遣日等・本文（Markdown）・同じ通達内のリンクに分ける。"""
    html = fetch_path(path, refresh)
    soup = body_soup(html)
    h1 = soup.find("h1")
    header, blocks, seen_h1 = "", [], h1 is None
    for el in flatten(soup.children):
        if el.name == "h1":
            if seen_h1:  # 別紙などの見出し
                blocks.append("### " + clean(el.get_text(" ")))
            seen_h1 = True
            continue
        if not seen_h1:
            # 題名より前は発遣番号・日付と宛先。右寄せの最初の段落（番号・日付）だけ残す
            right = el.get("align") == "right" or "right" in (el.get("class") or [])
            if el.name == "p" and right and not header:
                header = clean(el.get_text(" "))
            continue
        md = block_to_md(el).strip()
        if md:
            blocks.append(md)
    links = [resolve(path, a["href"]) for a in soup.find_all("a", href=True)]
    return {
        "title": clean(h1.get_text()) if h1 else "",
        "header": header,
        "md": "\n\n".join(blocks),
        "links": [l for l in links if l.endswith(".htm")],
    }


def build_kobetsu(refresh=False):
    entries, seen = [], set()
    for group, index in KOBETSU_GROUPS:
        soup = body_soup(fetch_path(index, refresh))
        for a in soup.find_all("a", href=True):
            path = resolve(index, a["href"])
            if not path.startswith("/law/tsutatsu/kobetsu/shotoku/") or "kaisei" in path or path in seen:
                continue
            seen.add(path)
            name = clean(a.get_text())
            # 同じディレクトリ内のページをたどって、通達の全ページを集める
            folder = posixpath.dirname(path) + "/"
            pages, queue = [], [path]
            while queue and len(pages) < MAX_PAGES:
                p = queue.pop(0)
                if any(p == q for q, _ in pages):
                    continue
                page = kobetsu_page(p, refresh)
                pages.append((p, page))
                for l in page["links"]:
                    if l.startswith(folder) and "kaisei" not in l and l not in queue \
                            and not any(l == q for q, _ in pages):
                        queue.append(l)
            first = pages[0][1]
            base = {"group": group, "circular": name, "header": first["header"]}
            if len(pages) <= SPLIT_PAGES:
                md = "\n\n".join(pg["md"] for _, pg in pages if pg["md"])
                entries.append(dict(base, term=name, page_title="", content_md=md,
                                    source_url=BASE + path, pages=len(pages)))
            else:
                for i, (p, pg) in enumerate(pages, 1):
                    entries.append(dict(base, term=pg["title"] if pg["title"] and pg["title"] != name else f"{name}（{i}）",
                                        page_title=pg["title"], content_md=pg["md"],
                                        source_url=BASE + p, pages=1))
    return entries


def build_sochiho(kobetsu, refresh=False):
    """個別通達のうち措置法通達（SOCHIHO）のページを通達番号ごとに分ける。

    戻り値は（措置法通達の項目, それを除いた個別通達）。各ページの題名（「措置法第31条…関係」）を条の見出しにする。
    """
    names = {name: (sid, label) for name, sid, label in SOCHIHO}
    entries, rest, last, linked = [], [], {}, {}
    for e in kobetsu:
        if e["circular"] not in names:
            rest.append(e)
            continue
        sid, label = names[e["circular"]]
        path = e["source_url"][len(BASE):]
        # 通達の目次（最初のページ）からリンクされているページだけを使う（改正前の旧版のページへのリンクをたどったものは除く）
        if sid not in linked:
            linked[sid] = {path} | {l.split("#")[0] for l in kobetsu_page(path, refresh)["links"]}
        if path not in linked[sid]:
            continue
        # 題名のない続きのページは、直前のページの条の見出しを引き継ぐ
        group = last[sid] = e["page_title"] if e["page_title"] and e["page_title"] != e["circular"] else last.get(sid, "")
        if not group:  # 最初の条の見出しより前（目次・前文）のページ
            continue
        meta = {"hen": e["circular"], "sho": label, "group": group}
        for it in parse_kihon_page(path, meta, refresh):
            # 目次のページの「番号＋リンク」だけの行は通達本文ではないので除く
            if re.fullmatch(r"\[[^\]]+\]\([^)]+\)", it["content_md"].strip()):
                continue
            it.update(sub2=sid, header=e["header"])
            entries.append(it)
    missing = [name for name in names if not any(x["hen"] == name for x in entries)]
    if missing:
        raise SystemExit("措置法通達が見つかりません: " + "、".join(missing))
    return entries, rest


# ---- 出力 ----

KIHON_URL = BASE + KIHON_INDEX
KOBETSU_URL = BASE + "/law/tsutatsu/menu.htm"
ISSUED = re.compile(r"(明治|大正|昭和|平成|令和)\s*[0-9０-９元]+年\s*[0-9０-９]+月\s*[0-9０-９]+日")


def render_kihon_md(entries):
    lines = ["# 所得税基本通達", ""]
    hen = sho = group = None
    for e in entries:
        if (e["hen"], e["sho"]) != (hen, sho):
            hen, sho, group = e["hen"], e["sho"], None
            lines += [f"## {hen}　{sho}".strip(), ""]
        if e["group"] != group:
            group = e["group"]
            lines += [f"### {group}", ""]
        lines += [f"#### {e['term']}", ""]
        if e["section"]:
            lines += [f"*{e['section']}*", ""]
        lines += [e["content_md"], "", f"出典: [所得税基本通達 {e['no']}]({e['source_url']})", ""]
    lines += ["---", "", f"出典: 国税庁 [法令解釈通達 所得税基本通達]({KIHON_URL})", ""]
    return "\n".join(lines)


def render_sochiho_md(entries):
    lines = ["# 措置法通達（所得税関係）", ""]
    hen = group = None
    for e in entries:
        if e["hen"] != hen:
            hen, group = e["hen"], None
            lines += [f"## {hen}", ""] + ([e["header"], ""] if e["header"] else [])
        if e["group"] != group:
            group = e["group"]
            lines += [f"### {group}", ""]
        lines += [f"#### {e['term']}", ""]
        if e["section"]:
            lines += [f"*{e['section']}*", ""]
        lines += [e["content_md"], "", f"出典: [{e['hen']} {e['no']}]({e['source_url']})", ""]
    lines += ["---", "", f"出典: 国税庁 [法令解釈通達]({KOBETSU_URL})", ""]
    return "\n".join(lines)


def render_kobetsu_md(entries):
    lines = ["# 個別通達（所得税関係）", "", f"{SPLIT_PAGES}ページを超える通達はページごとに分けています。", ""]
    group = circular = None
    for e in entries:
        if e["group"] != group:
            group, circular = e["group"], None
            lines += [f"## {group}", ""]
        if e["pages"] == 1 and e["page_title"]:
            if e["circular"] != circular:
                circular = e["circular"]
                lines += [f"### {circular}", ""]
                if e["header"]:
                    lines += [e["header"], ""]
            lines += [f"#### {e['term']}", ""]
        else:
            lines += [f"### {e['term']}", ""]
            if e["header"]:
                lines += [e["header"], ""]
        lines += ["<details><summary>本文</summary>", "", e["content_md"], "", "</details>", "",
                  f"出典: [{e['circular']}]({e['source_url']})", ""]
    lines += ["---", "", f"出典: 国税庁 [法令解釈通達]({KOBETSU_URL})", ""]
    return "\n".join(lines)


def search_items(kihon, kobetsu, sochiho):
    """検索ページ用の項目（タブ「通達」）。"""
    items = []
    for i, e in enumerate(kihon, 1):
        items.append({
            "id": f"tk{i}", "cat": "tsutatsu", "sub": "kihon", "kind": "tsutatsu",
            "term": e["term"], "label": "所基通" + e["no"], "group": e["group"], "section": e["section"],
            "summary": "", "md": e["content_md"], "url": e["source_url"],
            "srcLabel": "所得税基本通達", "srcTitle": f"所得税基本通達 {e['no']}",
        })
    for i, e in enumerate(sochiho, 1):
        items.append({
            "id": f"ts{i}", "cat": "tsutatsu", "sub": "sochiho", "sub2": [e["sub2"]], "kind": "tsutatsu",
            "term": e["term"], "label": "措通" + e["no"], "group": e["group"], "section": e["section"],
            "summary": "", "md": e["content_md"], "url": e["source_url"],
            "srcLabel": "措置法通達", "srcTitle": f"{e['hen']} {e['no']}",
        })
    for i, e in enumerate(kobetsu, 1):
        issued = ISSUED.search(e["header"])
        split = e["pages"] == 1 and e["page_title"]
        items.append({
            "id": f"tb{i}", "cat": "tsutatsu", "sub": "kobetsu", "kind": "tsutatsu",
            "term": e["term"], "label": issued.group(0) if issued else "", "group": e["group"],
            "section": e["circular"] if split else "", "issued": e["header"],
            "summary": "", "md": e["content_md"], "url": e["source_url"],
            "srcLabel": "個別通達", "srcTitle": e["circular"],
        })
    return items
