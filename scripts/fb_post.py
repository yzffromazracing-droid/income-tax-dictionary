"""Facebook ページに「所得税豆知識」を1日1件投稿する。

前日に投稿案（本文と図）を作って確認してもらい、確認済み（main に入った）ものだけを当日投稿する。

  python3 scripts/fb_post.py prepare --date=2026-11-20   # posts/2026-11-20.{json,png,md} を作る
  python3 scripts/fb_post.py publish --date=2026-11-20   # posts/2026-11-20.json があれば投稿する
  python3 scripts/fb_post.py check [--online]            # 1年分の投稿を作れるか、出典の文言を確かめる
  python3 scripts/fb_post.py show --date=2026-11-20      # 本文を表示するだけ

publish の環境変数:
  FB_PAGE_ID           : 投稿先の Facebook ページ ID
  FB_PAGE_ACCESS_TOKEN : ページアクセストークン（pages_manage_posts 権限）
  FB_GRAPH_VERSION     : Graph API のバージョン（任意。既定 v23.0）
  SITE_URL             : 投稿に添える辞書の URL（任意。既定は GitHub Pages）

投稿する項目は日付で決まる。data/fb_topics.json の calendar にある月（行事の1か月前）は奇数日に時期のテーマ、
それ以外の日は辞書の項目を順番に出す。図は SVG を作り、rsvg-convert（なければ Chromium）で PNG にする。
"""

import argparse
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICT = ROOT / "data" / "income_tax_dictionary.json"
TOPICS = ROOT / "data" / "fb_topics.json"
POSTS = ROOT / "posts"
SITE_URL = "https://yzffromazracing-droid.github.io/income-tax-dictionary/"
TA_URL = "https://www.nta.go.jp/taxes/shiraberu/taxanswer/{}/{}.htm"
JST = datetime.timezone(datetime.timedelta(hours=9))

# 検索ページ（scripts/search_template.html）のカテゴリの色
COLORS = {"zeiritsu": "#0b6aa2", "hikazei": "#0b7466", "shotoku-kubun": "#1f4d8c", "aoiro": "#3f3fb8",
          "shotoku-kojo": "#8d4a08", "nenmatsu": "#a8323e", "zeigaku-kojo": "#7b2c6c"}
NAMES = {"zeiritsu": "税率", "hikazei": "非課税", "shotoku-kubun": "所得区分", "aoiro": "青色申告",
         "shotoku-kojo": "所得控除", "nenmatsu": "年末調整", "zeigaku-kojo": "税額控除"}
DISCLAIMER = "※一般的な情報です。個別の判断は国税庁の出典や税理士にご確認ください。"


def _plain(s):
    return re.sub(r"\s|\*\*", "", re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s))


# ---- 投稿のもと（辞書の項目と時期のテーマ） ----

def _first_sentence(text, limit=120):
    """括弧の外にある最初の「。」までを返す。長すぎるときは空にする（要旨なしで投稿する）。"""
    depth = 0
    for i, ch in enumerate(text):
        depth += ch in "（「『("
        depth -= ch in "）」』)"
        if ch == "。" and depth <= 0:
            return text[:i + 1] if i + 1 <= limit else ""
    return text if len(text) <= limit else ""


def _example_bullets(exs):
    plain = [x for x in exs if not x.get("other") and not x.get("tax")]
    tax = [x for x in exs if x.get("tax")]
    other = [x for x in exs if x.get("other")]
    picked = plain[:3] + other[:1]
    picked += [x for x in tax if x not in picked][:max(0, 4 - len(picked))]
    picked += [x for x in plain[3:] if x not in picked][:max(0, 4 - len(picked))]
    # 並びは 具体例 → 取扱い → 当たらない例
    picked = [x for x in plain + tax + other if x in picked]
    out = []
    for x in picked:
        to = x.get("other") or x.get("tax")
        out.append({"text": x["text"] + (f" → {to}" if to else ""), "kind": "other" if x.get("other") else ""})
    return out


def load_items():
    """辞書から投稿に使える項目（要点・具体例・税率の行が2つ以上あるもの）を、辞書の並び順で返す。"""
    d = json.loads(DICT.read_text(encoding="utf-8"))
    items = []

    def page(cat, p):
        bullets = ([{"text": x["text"], "kind": ""} for x in p.get("points", [])][:4]
                   or _example_bullets(p.get("examples", [])))
        summary = _first_sentence(p.get("summary") or "")
        return {"id": f"no{p['code']}", "term": p["term"], "category": cat, "summary": summary,
                "bullets": bullets, "source": f"国税庁タックスアンサー No.{p['code']}", "url": p["source_url"]}

    for z in d.get("zeiritsu", []):
        items.append({"id": z["id"], "term": z["term"], "category": "zeiritsu", "summary": z["summary"],
                      "bullets": [{"text": re.sub(r"から(.+?)まで$", r"〜\1", r["label"]) + f"：{r['rate']}"
                                   + (f"（{z['head'][2] + ' ' if z['head'][2] == '控除額' else ''}{r['note']}）" if r["note"] else ""),
                                   "kind": ""} for r in z["rows"]],
                      "source": "国税庁タックスアンサー " + "・".join(dict.fromkeys(r["source"] for r in z["rows"])),
                      "url": z["rows"][0]["url"]})
    for c in d["categories"]:
        cid = c["id"]
        if cid == "hikazei":
            for p in c.get("pages", []):
                items.append(page(cid, p))
            for i, e in enumerate(c["entries"], 1):
                srcs = list(dict.fromkeys(x["source"] for x in e.get("examples", [])))
                items.append({"id": f"hk{i}", "term": e["alias"] or e["term"], "category": cid,
                              "summary": "所得税がかからない「非課税所得」の一つです。" + (f"（{e['term']}）" if e["alias"] else ""),
                              "bullets": _example_bullets(e.get("examples", [])),
                              "source": "国税庁タックスアンサー No.2011" + ("・" + "・".join(srcs) if srcs else ""),
                              "url": e["source_url"]})
            continue
        items.append(page(cid, c["overview"]))
        items += [page(cid, e) for e in c["entries"]]
    return [it for it in items if len(it["bullets"]) >= 2]


def load_topics(items, online=False):
    """時期のテーマ（data/fb_topics.json）を項目の形にする。各行の quote が出典にあるかを確かめる。"""
    cfg = json.loads(TOPICS.read_text(encoding="utf-8"))
    d = json.loads(DICT.read_text(encoding="utf-8"))
    pages = {e["code"]: e for e in d["kiji"]["taxanswer"]}
    fetched, errors, topics = {}, [], {}
    for tid, t in cfg["topics"].items():
        bullets = []
        for b in t["bullets"]:
            src = b.get("src") or t.get("src")
            if src:
                body = _plain(pages[src]["content_md"]) if src in pages else None
            elif online:
                if t["url"] not in fetched:
                    fetched[t["url"]] = _fetch_text(t["url"])
                body = fetched[t["url"]]
            else:
                body = ""  # URL の出典は --online のときだけ照合する
            if body is not None and body != "" and _plain(b["quote"]) not in body:
                errors.append(f"  {tid}: 「{b['quote']}」が出典（{src or t['url']}）にありません")
            elif body is None:
                errors.append(f"  {tid}: タックスアンサー No.{src} が辞書のデータにありません")
            bullets.append({"text": b["text"], "kind": ""})
        codes = list(dict.fromkeys(b.get("src") or t.get("src") for b in t["bullets"] if b.get("src") or t.get("src")))
        source = t.get("source") or "国税庁タックスアンサー " + "・".join(f"No.{c}" for c in codes)
        url = t.get("url") or (pages[codes[0]]["source_url"] if codes and codes[0] in pages else SITE_URL)
        link_id = f"ta-{pages[codes[0]]['folder']}{codes[0]}" if codes and codes[0] in pages else ""
        topics[tid] = {"id": link_id, "term": t["term"], "category": t["category"], "summary": "",
                       "bullets": bullets, "source": source, "url": url, "seasonal": True}
    by_id = {it["id"]: it for it in items}
    for month, ids in cfg["calendar"].items():
        for i in ids:
            if i not in topics and i not in by_id:
                errors.append(f"  calendar {month}月: {i} がありません")
    if errors:
        raise SystemExit("data/fb_topics.json を確認してください。\n" + "\n".join(errors))
    return cfg["calendar"], topics


def _fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "income-tax-dictionary/1.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        raw = res.read()
    m = re.search(rb'charset=["\']?([\w-]+)', raw[:3000])
    enc = m.group(1).decode().lower() if m else "utf-8"
    text = raw.decode("cp932" if enc in ("shift_jis", "shift-jis", "sjis", "x-sjis") else enc, errors="replace")
    return _plain(re.sub(r"<[^>]+>", "", text))


def pick(date, items, calendar, topics):
    """その日（日本時間）の投稿の項目。時期のテーマのある月は奇数日にテーマを順に、ほかは辞書の項目を順に。"""
    by_id = {it["id"]: it for it in items}
    ids = calendar.get(str(date.month))
    if ids and date.day % 2 == 1:
        tid = ids[(date.day // 2) % len(ids)]
        it = dict(topics.get(tid) or by_id[tid])
        it["seasonal"] = True
        return it
    n = (date - datetime.date(2026, 1, 1)).days
    return items[n % len(items)]


# ---- 本文 ----

def build_message(it, site_url=SITE_URL):
    lines = [f"【所得税豆知識】{it['term']}", f"（{NAMES[it['category']]}）", ""]
    if it["summary"]:
        lines += [it["summary"], ""]
    lines.append("■ ポイント")
    lines += [f"・{b['text']}" for b in it["bullets"]]
    lines += ["", f"出典：{it['source']}", it["url"]]
    if it["id"]:
        lines += ["", "詳しくは「所得税区分辞書」で：", site_url + "#" + it["id"]]
    lines += ["", DISCLAIMER, "", f"#所得税豆知識 #所得税 #{NAMES[it['category']]} #税金"]
    return "\n".join(lines)


# ---- 図（1080×1080 の SVG → PNG） ----

def _width(s):
    return sum(0.55 if ord(ch) < 0x2E80 else 1.0 for ch in s)


def _wrap(text, max_em):
    """max_em 幅で折り返す。最後の行が2文字以下になるときは、行の長さをそろえて折り返し直す。"""
    lines = _wrap_greedy(text, max_em)
    if len(lines) >= 2 and _width(lines[-1]) <= 2:
        target = _width(text) / len(lines) + 1
        balanced = _wrap_greedy(text, target)
        if len(balanced) == len(lines):
            return balanced
    return lines


def _wrap_greedy(text, max_em):
    lines, cur = [], ""
    for ch in text:
        if _width(cur + ch) > max_em:
            # 句読点や閉じ括弧で行を始めない
            if ch in "、。）」』，．・ー" and cur:
                cur += ch
                lines.append(cur)
                cur = ""
                continue
            # 「2,796,000円」のような数字の途中では切らず、数字ごと次の行へ送る
            num = re.search(r"[0-9,.]+$", cur) if re.match(r"[0-9,.円%％]", ch) else None
            if num and num.start() > 0:
                lines.append(cur[:num.start()])
                cur = num.group(0) + ch
                continue
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def build_svg(it):
    color = COLORS[it["category"]]
    e = html.escape
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" viewBox="0 0 1080 1080" '
             f'font-family="Noto Sans CJK JP, Noto Sans JP, WenQuanYi Zen Hei, sans-serif">',
             '<rect width="1080" height="1080" fill="#f3f6fa"/>',
             '<rect x="48" y="48" width="984" height="984" rx="28" fill="#ffffff"/>',
             f'<rect x="48" y="48" width="984" height="14" rx="7" fill="{color}"/>']
    # ラベル
    parts.append(f'<rect x="104" y="104" width="232" height="52" rx="26" fill="{color}"/>'
                 f'<text x="220" y="140" font-size="28" font-weight="700" fill="#fff" text-anchor="middle">所得税豆知識</text>')
    name = NAMES[it["category"]]
    w = 40 + 28 * len(name)
    parts.append(f'<rect x="352" y="104" width="{w}" height="52" rx="26" fill="{color}" fill-opacity="0.12"/>'
                 f'<text x="{352 + w / 2}" y="140" font-size="26" font-weight="700" fill="{color}" text-anchor="middle">{e(name)}</text>')
    y = 200
    # 見出し（最大3行）
    size = 54 if _width(it["term"]) <= 15 * 2 else 46
    for line in _wrap(it["term"], 872 / size)[:3]:
        y += size + 10
        parts.append(f'<text x="104" y="{y}" font-size="{size}" font-weight="800" fill="#18212d">{e(line)}</text>')
    y += 22
    parts.append(f'<rect x="104" y="{y}" width="872" height="3" fill="{color}" fill-opacity="0.35"/>')
    y += 24
    # ポイント（収まる分だけ。行数が多いときは文字を小さくする）
    n_lines = sum(len(_wrap(b["text"], 836 / 32)) for b in it["bullets"])
    size = 32 if n_lines <= 11 else 28 if n_lines <= 14 else 25
    room = 900 - y
    for b in it["bullets"]:
        wrapped = _wrap(b["text"], 836 / size)
        need = len(wrapped) * (size + 12) + 14
        if need > room:
            break
        room -= need
        y += size + 12
        mark = "#c2410c" if b["kind"] == "other" else color
        parts.append(f'<circle cx="{116}" cy="{y - size * 0.35}" r="7" fill="{mark}"/>')
        for k, line in enumerate(wrapped):
            if k:
                y += size + 12
            parts.append(f'<text x="140" y="{y}" font-size="{size}" fill="#18212d">{e(line)}</text>')
        y += 14
    # 出典
    src = _wrap("出典：" + it["source"], 872 / 22)[:2]
    for k, line in enumerate(src):
        parts.append(f'<text x="104" y="{962 - (len(src) - 1 - k) * 30}" font-size="22" fill="#586373">{e(line)}</text>')
    parts.append('<text x="976" y="1000" font-size="22" fill="#586373" text-anchor="end">所得税区分辞書</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def svg_to_png(svg_path, png_path):
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-w", "1080", "-h", "1080", "-o", str(png_path), str(svg_path)], check=True)
        return
    # rsvg-convert がないとき（手元の確認など）は Playwright の Chromium で描く
    js = ("const { chromium } = require('playwright');(async()=>{const b=await chromium.launch("
          + (f"{{executablePath:'{os.environ['CHROMIUM']}'}}" if os.environ.get("CHROMIUM") else "") + ");"
          "const p=await b.newPage({viewport:{width:1080,height:1080}});"
          f"await p.goto('file://{Path(svg_path).resolve()}');await p.screenshot({{path:'{Path(png_path).resolve()}'}});"
          "await b.close();})();")
    subprocess.run(["node", "-e", js], check=True)


# ---- 投稿 ----

def _multipart(fields, files):
    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, (name, data, ctype) in files.items():
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                 f"Content-Type: {ctype}\r\n\r\n").encode() + data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def _graph(path, params=None, data=None, ctype=None):
    url = f"https://graph.facebook.com/{os.environ.get('FB_GRAPH_VERSION', 'v23.0')}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as err:
        return json.loads(err.read() or b"{}")


def resolve_token(page_id, token):
    """個人（ユーザー）のトークンなら、管理しているページのトークンに入れ替える（消費税豆知識と同じ扱い）。"""
    me = _graph("me", {"fields": "id", "access_token": token})
    if "error" in me or str(me.get("id")) == str(page_id).strip():
        return token
    acc = _graph("me/accounts", {"fields": "id,access_token", "limit": 100, "access_token": token})
    for a in acc.get("data", []):
        if str(a["id"]) == str(page_id).strip():
            print("ユーザーのトークンです。管理しているページのトークンを取り出して投稿します。")
            return a["access_token"]
    return token


def publish(date_str, dry_run=False):
    meta_path = POSTS / f"{date_str}.json"
    if not meta_path.exists():
        print(f"{meta_path.relative_to(ROOT)} がない（前日の投稿案が確認・マージされていない）ため投稿しません。")
        return
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    png = POSTS / meta["image"]
    page_id, token = os.environ.get("FB_PAGE_ID"), os.environ.get("FB_PAGE_ACCESS_TOKEN")
    if dry_run or not page_id or not token:
        if not dry_run:
            print("FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN が未設定のため投稿せず本文を表示します。")
        print(meta["message"])
        return
    token = resolve_token(page_id, token)
    if png.exists():
        body, ctype = _multipart({"caption": meta["message"], "access_token": token},
                                 {"source": (png.name, png.read_bytes(), "image/png")})
        res = _graph(f"{page_id}/photos", data=body, ctype=ctype)
    else:
        res = _graph(f"{page_id}/feed", data=urllib.parse.urlencode({"message": meta["message"], "access_token": token}).encode(),
                     ctype="application/x-www-form-urlencoded")
    if "error" in res:
        raise SystemExit("Facebook API error: " + res["error"].get("message", json.dumps(res)))
    print(f"posted: {res.get('post_id') or res.get('id')} ({meta['term']})")


def prepare(date, items, calendar, topics, site_url):
    it = pick(date, items, calendar, topics)
    POSTS.mkdir(exist_ok=True)
    stem = date.isoformat()
    message = build_message(it, site_url)
    svg = POSTS / f"{stem}.svg"
    svg.write_text(build_svg(it), encoding="utf-8")
    svg_to_png(svg, POSTS / f"{stem}.png")
    svg.unlink()
    meta = {"date": stem, "id": it["id"], "term": it["term"], "category": it["category"],
            "seasonal": bool(it.get("seasonal")), "image": f"{stem}.png", "message": message}
    (POSTS / f"{stem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (POSTS / f"{stem}.md").write_text(
        f"# {stem} の所得税豆知識\n\n![図]({stem}.png)\n\n```text\n{message}\n```\n", encoding="utf-8")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["prepare", "publish", "check", "show"])
    ap.add_argument("--date", help="YYYY-MM-DD（日本時間。既定は prepare が明日、ほかは今日）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--online", action="store_true", help="check で URL の出典も取得して照合する")
    args = ap.parse_args()
    today = datetime.datetime.now(JST).date()
    date = datetime.date.fromisoformat(args.date) if args.date else (
        today + datetime.timedelta(days=1) if args.command == "prepare" else today)
    if args.command == "publish":
        publish(date.isoformat(), args.dry_run)
        return
    items = load_items()
    calendar, topics = load_topics(items, online=args.online or args.command == "prepare")
    site_url = os.environ.get("SITE_URL") or SITE_URL
    if args.command == "check":
        seen = {}
        for k in range(366):
            dd = datetime.date(date.year, 1, 1) + datetime.timedelta(days=k)
            it = pick(dd, items, calendar, topics)
            build_message(it, site_url)
            seen[it["term"]] = seen.get(it["term"], 0) + 1
        print(f"辞書の項目 {len(items)} 件、時期のテーマ {len(topics)} 件。1年で {len(seen)} 種類を投稿します。")
        return
    if args.command == "show":
        print(build_message(pick(date, items, calendar, topics), site_url))
        return
    meta = prepare(date, items, calendar, topics, site_url)
    print(f"posts/{meta['date']}.json を作りました：{meta['term']}")


if __name__ == "__main__":
    main()
