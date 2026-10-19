"""国税庁ホームページの記事（タックスアンサーと質疑応答事例）を取得して項目に分ける。

  - タックスアンサー: コード一覧の「所得税」「源泉所得税」「譲渡所得」に載っているページ
  - 質疑応答事例: 「所得税」「源泉所得税」「譲渡所得」の目次に載っている事例
"""

import re

from bs4 import BeautifulSoup

from build_dictionary import BASE, clean, parse_page
from tsutatsu import body_soup, fetch_path, kobetsu_page, resolve

TA_INDEX = "/taxes/shiraberu/taxanswer/code/index.htm"
TA_SECTIONS = [("code01", "ta-shotoku", "所得税"), ("code02", "ta-gensen", "源泉所得税"), ("code03", "ta-joto", "譲渡所得")]
QA_INDEXES = [("/law/shitsugi/shotoku/01.htm", "qa-shotoku", "所得税"),
              ("/law/shitsugi/gensen/01.htm", "qa-gensen", "源泉所得税"),
              ("/law/shitsugi/joto/01.htm", "qa-joto", "譲渡所得")]


def build_taxanswer(refresh=False):
    """タックスアンサーのコード一覧から、所得税関係のページを集めて解析する。"""
    soup = BeautifulSoup(fetch_path(TA_INDEX, refresh), "lxml")
    found, order = {}, []
    for sec_id, field, field_name in TA_SECTIONS:
        h2 = soup.find("h2", id=sec_id)
        group = ""
        for el in h2.find_all_next():
            if el.name == "h2" and (el.get("id") or "").startswith("code"):
                break
            if el.name == "h3":
                group = clean(el.get_text())
            if el.name == "a" and el.get("href"):
                m = re.search(r"/taxanswer/(\w+)/(\d+)\.htm", el["href"])
                if m and (m.group(1), m.group(2)) not in found:
                    key = (m.group(1), m.group(2))
                    found[key] = {"field": field, "field_name": field_name, "group": group}
                    order.append(key)
    entries = []
    for folder, code in order:
        path = f"/taxes/shiraberu/taxanswer/{folder}/{code}.htm"
        try:
            page, _ = parse_page(code, fetch_path(path, refresh))
        except Exception as e:  # ページの形が違うものは飛ばす
            print(f"  タックスアンサー {path} を読めませんでした: {e}")
            continue
        page.update(found[(folder, code)], folder=folder, source_url=BASE + path)
        entries.append(page)
    return entries


def build_shitsugi(refresh=False):
    """質疑応答事例の目次から事例を集め、各事例の照会要旨・回答要旨などを取り出す。"""
    entries = []
    for index, field, field_name in QA_INDEXES:
        soup = body_soup(fetch_path(index, refresh))
        group, seen = "", set()
        for p in soup.find_all("p"):
            if p.find("a", id=True):  # 目次の分類（「（総則）」など）
                group = re.sub(r"^[（(]|[）)]$", "", clean(p.get_text()))
                continue
            for a in p.find_all("a", href=True):
                path = resolve(index, a["href"])
                if not re.match(r"/law/shitsugi/\w+/\d+/\d+\.htm$", path) or path in seen:
                    continue
                seen.add(path)
                try:
                    page = kobetsu_page(path, refresh)
                except Exception as e:
                    print(f"  質疑応答事例 {path} を読めませんでした: {e}")
                    continue
                md = page["md"]
                # 末尾の注記（「令和○年○月○日現在の法令・通達等に基づいて作成」）から基準日を取り出す
                as_of = re.search(r"(令和|平成)[0-9０-９元]+年[0-9０-９]+月[0-9０-９]+日現在の法令・通達等", md)
                basis = re.search(r"### 【関係法令通達】\n\n(.+?)(\n\n|$)", md, re.S)
                entries.append({
                    "term": page["title"] or clean(a.get_text()),
                    "field": field, "field_name": field_name, "group": group,
                    "summary": _first_para(md, "【照会要旨】"),
                    "legal_basis": clean(basis.group(1)) if basis else "",
                    "as_of": as_of.group(0) if as_of else "",
                    "content_md": md,
                    "source_url": BASE + path,
                })
    return entries


def _first_para(md, heading):
    m = re.search(re.escape(heading) + r"\n\n(.+?)(\n\n|$)", md, re.S)
    text = m.group(1) if m else ""
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text).replace("<br>", " ").strip()


# ---- 出力 ----

def render_md(title, entries, kind):
    lines = [f"# {title}", ""]
    field = group = None
    for e in entries:
        if e["field_name"] != field:
            field, group = e["field_name"], None
            lines += [f"## {field}", ""]
        if e["group"] != group:
            group = e["group"]
            if group:
                lines += [f"### {group}", ""]
        label = f"No.{e['code']} " if kind == "ta" else ""
        lines += [f"#### {label}{e['term']}", ""]
        if e.get("summary"):
            lines += [f"- **要旨**: {e['summary']}", ""]
        lines += ["<details><summary>本文</summary>", "", e["content_md"], "", "</details>", ""]
        if e.get("legal_basis"):
            lines.append(f"- **根拠法令等**: {e['legal_basis']}")
        if e.get("as_of"):
            lines.append(f"- **基準**: {e['as_of']}")
        lines += [f"- **出典**: [{e.get('title') or e['term']}]({e['source_url']})", ""]
    return "\n".join(lines).rstrip() + "\n"


def search_items(taxanswer, shitsugi):
    """検索ページ用の項目（タブ「国税庁の記事」）。"""
    items = []
    for e in taxanswer:
        items.append({
            "id": f"ta-{e['folder']}{e['code']}", "cat": "kiji", "sub": "taxanswer", "subs": ["taxanswer"],
            "sub2": [e["field"]], "kind": "kiji",
            "term": e["term"], "code": e["code"], "title": e["title"], "group": e["group"],
            "summary": e["summary"], "basis": e["legal_basis"], "asOf": e["as_of"],
            "md": e["content_md"], "url": e["source_url"],
            "srcLabel": "タックスアンサー", "srcTitle": e["title"],
        })
    for i, e in enumerate(shitsugi, 1):
        items.append({
            "id": f"qa{i}", "cat": "kiji", "sub": "shitsugi", "subs": ["shitsugi"],
            "sub2": [e["field"]], "kind": "kiji",
            "term": e["term"], "label": "質疑応答", "group": e["group"],
            "summary": e["summary"], "basis": e["legal_basis"], "asOf": e["as_of"],
            "md": e["content_md"], "url": e["source_url"],
            "srcLabel": "質疑応答事例", "srcTitle": e["term"],
        })
    return items
