"""国税庁の「源泉徴収税額表」（月額表・日額表・賞与に対する源泉徴収税額の算出率の表）を取り込む。

国税庁が公開している Excel を取得して data/zeigakuhyo.json に書き出す（このスクリプトを直接実行する）。
.xls は LibreOffice（soffice）で .xlsx に変換してから読む。辞書のビルドは data/zeigakuhyo.json だけを使う。

  python3 scripts/zeigakuhyo.py            # 取得済みの Excel（.cache/zeigakuhyo/）から作り直す
  python3 scripts/zeigakuhyo.py --refresh  # 国税庁サイトから取り直す
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "zeigakuhyo"
OUT = ROOT / "data" / "zeigakuhyo.json"
BASE = "https://www.nta.go.jp"
PAGE = "/publication/pamph/gensen/zeigakuhyo{}/01.htm"
DATA = "/publication/pamph/gensen/zeigakuhyo{}/data/{}.{}"
YEARS = [("r08", "令和8年分", "2026"), ("r09", "令和9年分", "2027")]
PARTS = [("getsugaku", "01-07", "給与所得の源泉徴収税額表（月額表）"),
         ("nichigaku", "08-14", "給与所得の源泉徴収税額表（日額表）"),
         ("shoyo", "15-16", "賞与に対する源泉徴収税額の算出率の表")]

NUM = r"([\d,]+)"


def _int(s):
    return int(s.replace(",", ""))


def fetch(year, part, refresh=False):
    """Excel を取得し、読める .xlsx のパスを返す。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    for ext in ("xlsx", "xls"):
        path = CACHE / f"z{year}_{part}.{ext}"
        if path.exists() and not refresh:
            break
        try:
            req = urllib.request.Request(BASE + DATA.format(year, part, ext),
                                         headers={"User-Agent": "income-tax-dictionary/1.0"})
            with urllib.request.urlopen(req, timeout=30) as res:
                if res.geturl().endswith("/error/404.htm"):
                    continue
                path.write_bytes(res.read())
            break
        except urllib.error.HTTPError:
            continue
    else:
        raise SystemExit(f"源泉徴収税額表 {year} {part} を取得できませんでした")
    if path.suffix == ".xlsx":
        return path
    conv = CACHE / "conv" / (path.stem + ".xlsx")
    if not conv.exists() or conv.stat().st_mtime < path.stat().st_mtime:
        subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(conv.parent), str(path)],
                       check=True, capture_output=True, timeout=300)
    return conv


def _rows(path):
    import openpyxl
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    return [list(r) + [None] * (13 - len(r)) for r in ws.iter_rows(values_only=True)]


def _notes(rows, start):
    """（注）・（備考）の文章を段落ごとにまとめる。"""
    paras = []
    for r in rows[start:]:
        text = (r[1] or "").strip() if isinstance(r[1], str) else ""
        if not text:
            continue
        if re.match(r"^(\(|（|[１-９]|[⑴-⑼]|\(\d\))", text) or not paras:
            paras.append(text)
        else:
            paras[-1] += text
    return paras


def parse_wage(path, daily):
    """月額表・日額表を読む。

    rows:   [以上, 未満, 甲0人..甲7人, 乙(, 丙)]
    steps:  表の途中・末尾にある「○円」ちょうどの行（甲の税額、乙・丙はある行だけ）
    ko:     甲欄の計算式（over 円を超え under 円に満たない金額 → over 円の場合の税額 + 超える金額 × rate%）
    otsu / hei: 乙欄・丙欄の計算式（base 円 + over 円を超える金額 × rate%）
    """
    rows = _rows(path)
    title, kokuji = rows[0][1].strip(), rows[1][1].strip()
    unit = "日" if daily else "月"
    first = next(i for i, r in enumerate(rows) if isinstance(r[1], (int, float)) and r[2] == "円未満")
    r0 = rows[first]
    below = {"under": int(r0[1]), "ko": [int(v) for v in r0[3:11]],
             "otsu_rate": float(re.search(r"([\d.]+)％", r0[11]).group(1)),
             "hei": int(r0[12]) if daily else None}
    table, steps, col1, col3, otsu, hei = [], [], [], [], [], []
    end = len(rows)
    for i in range(first + 1, len(rows)):
        r = rows[i]
        if isinstance(r[1], str) and r[1].strip().startswith("(注)"):
            end = i
            break
        if isinstance(r[1], (int, float)) and isinstance(r[2], (int, float)):
            table.append([int(r[1]), int(r[2])] + [int(v) for v in r[3:11]] + [int(r[11])] + ([int(r[12])] if daily else []))
            continue
        m = re.fullmatch(r"\s*" + NUM + r"円\s*", r[1]) if isinstance(r[1], str) else None
        if m and isinstance(r[3], (int, float)):
            steps.append({"at": _int(m.group(1)), "ko": [int(v) for v in r[3:11]],
                          "otsu": int(r[11]) if isinstance(r[11], (int, float)) else None,
                          "hei": int(r[12]) if daily and isinstance(r[12], (int, float)) else None})
            continue
        for j, store in ((1, col1), (3, col3)):
            if isinstance(r[j], str):
                store.append(r[j].strip())
        for j, store in ((11, otsu), (12, hei)):
            if isinstance(r[j], str) and "円に、" in r[j]:
                store.append(r[j].strip())
    text1, text3 = "".join(col1), "".join(col3)
    rates = {_int(a): float(c) for a, b, c in re.findall(
        NUM + r"円の場合の税額に、その" + unit + r"の社会保険料等控除後の給与等の金額のうち" + NUM + r"円を超える金額の([\d.]+)％", text3)}
    ko = []
    for m in re.finditer(NUM + r"円を超え(?:" + NUM + r"円に満たない金額|る金額)", text1):
        over = _int(m.group(1))
        ko.append({"over": over, "under": _int(m.group(2)) if m.group(2) else None, "rate": rates[over]})

    def formulas(texts):
        out = {}
        for t in texts:
            m = re.match(NUM + r"円に、その" + unit + r"の社会保険料等控除後の給与等の金額のうち" + NUM + r"円を超える金額の([\d.]+)％", t)
            out[_int(m.group(2))] = {"over": _int(m.group(2)), "base": _int(m.group(1)), "rate": float(m.group(3))}
        return sorted(out.values(), key=lambda f: f["over"])

    over7 = _int(re.search(r"１人ごとに" + NUM + r"円を控除", "".join(col1)).group(1))
    data = {"title": title, "kokuji": kokuji, "unit": unit, "below": below, "rows": table, "steps": steps,
            "ko": ko, "otsu": formulas(otsu), "over7": over7, "notes": _notes(rows, end)}
    if daily:
        data["hei"] = formulas(hei)
    _check_wage(data, path)
    return data


def _check_wage(t, path):
    """読み取った表がつながっているかを確かめる（Excel の形が変わったときに気づくため）。"""
    rows, steps = t["rows"], t["steps"]
    errs = []
    if rows[0][0] != t["below"]["under"]:
        errs.append("最初の行が「○円未満」の行とつながっていません")
    errs += [f"{a[1]} と {b[0]} の間が抜けています" for a, b in zip(rows, rows[1:]) if a[1] != b[0]]
    if not steps or steps[0]["at"] != rows[-1][1]:
        errs.append("表の終わりと計算式の部分がつながっていません")
    at = {s["at"] for s in steps}
    for k, n in zip(t["ko"], t["ko"][1:]):
        if k["under"] != n["over"]:
            errs.append(f"甲欄の計算式 {k['over']}〜{k['under']} の次が {n['over']} です")
    errs += [f"甲欄の計算式の起点 {k['over']} 円の行がありません" for k in t["ko"] if k["over"] not in at]
    if t["ko"] and t["ko"][-1]["under"] is not None:
        errs.append("甲欄の最後の計算式に上限があります")
    if errs:
        raise SystemExit(f"{path.name} を読み取れませんでした。\n  " + "\n  ".join(errs))


def parse_bonus(path):
    """賞与に対する源泉徴収税額の算出率の表を読む（金額の単位は千円）。

    rows: [{rate, ko: [[以上, 未満] × 扶養親族等の数0〜7人以上], otsu: [以上, 未満] または None}]
    """
    rows = _rows(path)
    title, kokuji = rows[0][1].strip(), rows[1][1].strip()

    def pair(lo, hi):
        if hi == "千円未満":
            return [None, int(lo)]
        if hi == "千円以上":
            return [int(lo), None]
        return [int(lo), int(hi)]

    out, end = [], len(rows)
    for i, r in enumerate(rows[8:], 8):
        if isinstance(r[1], str) and r[1].strip().startswith("(注)"):
            end = i
            break
        if not isinstance(r[1], (int, float)):
            continue
        out.append({"rate": float(r[1]), "ko": [pair(r[3 + 2 * k], r[4 + 2 * k]) for k in range(8)],
                    "otsu": pair(r[19], r[20]) if r[19] is not None else None})
    for k in range(8):
        col = [x["ko"][k] for x in out]
        if col[0][0] is not None or col[-1][1] is not None or any(a[1] != b[0] for a, b in zip(col, col[1:])):
            raise SystemExit(f"{path.name} の甲欄（{k}人）を読み取れませんでした")
    return {"title": title, "kokuji": kokuji, "rows": out, "notes": _notes(rows, end)}


def build(refresh=False):
    tables = []
    for yid, label, year in YEARS:
        for kind, part, name in PARTS:
            path = fetch(year, part, refresh)
            data = parse_bonus(path) if kind == "shoyo" else parse_wage(path, kind == "nichigaku")
            ext = "xlsx" if (CACHE / f"z{year}_{part}.xlsx").exists() else "xls"
            data.update(id=f"zh-{yid}-{kind}", kind=kind, year=label, name=name,
                        source_url=BASE + PAGE.format(year), file_url=BASE + DATA.format(year, part, ext))
            tables.append(data)
    return tables


# ---- 税額を求める（検索ページの計算と同じ手順。ビルド時に国税庁の計算例と照合する） ----

def wage_tax(t, amount, n, col="ko"):
    """月額表・日額表で税額を求める。col は ko（甲）・otsu（乙）・hei（丙）。"""
    k, extra = min(n, 7), max(0, n - 7) * t["over7"]
    b = t["below"]
    if amount < b["under"]:
        v = {"ko": b["ko"][k], "otsu": int(amount * b["otsu_rate"] / 100 + 1e-6), "hei": b["hei"]}[col]
    else:
        row = next((r for r in t["rows"] if r[0] <= amount < r[1]), None)
        if row:
            v = {"ko": row[2 + k], "otsu": row[10], "hei": row[11] if len(row) > 11 else None}[col]
        else:
            step = next((s for s in t["steps"] if s["at"] == amount), None)
            if step and (col == "ko" or step[col] is not None):
                v = step["ko"][k] if col == "ko" else step[col]
            elif col == "ko":
                f = next(f for f in t["ko"] if f["over"] < amount and (f["under"] is None or amount < f["under"]))
                base = next(s for s in t["steps"] if s["at"] == f["over"])["ko"][k]
                v = base + int((amount - f["over"]) * f["rate"] / 100 + 1e-6)
            else:
                f = [f for f in t[col] if f["over"] < amount][-1]
                v = f["base"] + int((amount - f["over"]) * f["rate"] / 100 + 1e-6)
    return max(0, v - extra) if col == "ko" else v


def bonus_rate(t, prev, n, col="ko"):
    """賞与の算出率の表で、前月の給与（社会保険料等控除後）に応じた率（%）を求める。"""
    k = min(n, 7)
    for r in t["rows"]:
        lo, hi = r["ko"][k] if col == "ko" else (r["otsu"] or (None, None))
        if col == "otsu" and r["otsu"] is None:
            continue
        if (lo is None or prev >= lo * 1000) and (hi is None or prev < hi * 1000):
            return r["rate"]
    raise ValueError(prev)


def bonus_tax(bonus_t, monthly_t, prev, bonus, n, col="ko", months12=False):
    """賞与の税額。前月の給与がない場合や賞与が前月の給与の10倍を超える場合は月額表を使う（No.2523）。"""
    d = 12 if months12 else 6
    if prev <= 0:
        return wage_tax(monthly_t, bonus // d, n, col) * d
    if bonus > prev * 10:
        return (wage_tax(monthly_t, bonus // d + prev, n, col) - wage_tax(monthly_t, prev, n, col)) * d
    return int(bonus * bonus_rate(bonus_t, prev, n, col) / 100 + 1e-6)


# ---- 出力 ----

def _yen(v):
    return "" if v is None else f"{v:,}"


def render_md(tables):
    lines = ["# 源泉徴収税額表", "",
             "国税庁「源泉徴収税額表」の Excel から作成。最新の内容は出典で確認してください。", ""]
    for year in dict.fromkeys(t["year"] for t in tables):
        lines += [f"## {year}", ""]
        for t in (x for x in tables if x["year"] == year):
            lines += [f'<a id="{t["id"]}"></a>', "", f"### {t['name']}", "", t["kokuji"], ""]
            if t["kind"] == "shoyo":
                head = ["賞与の金額に乗ずべき率"] + [f"甲 {k}人{'以上' if k == 7 else ''}" for k in range(8)] + ["乙"]
                lines += ["前月の社会保険料等控除後の給与等の金額（千円）", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
                for r in t["rows"]:
                    cells = [f"{r['rate']:g}%"] + [_range(p) for p in r["ko"]] + [_range(r["otsu"]) if r["otsu"] else ""]
                    lines.append("| " + " | ".join(cells) + " |")
            else:
                daily = t["kind"] == "nichigaku"
                head = ["以上", "未満"] + [f"甲 {k}人" for k in range(8)] + ["乙"] + (["丙"] if daily else [])
                lines += [f"その{t['unit']}の社会保険料等控除後の給与等の金額（円）と税額（円）", "",
                          "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
                b = t["below"]
                lines.append("| | " + f"{b['under']:,}円未満 | " + " | ".join(_yen(v) for v in b["ko"]) +
                             f" | 金額の{b['otsu_rate']:g}% |" + (f" {_yen(b['hei'])} |" if daily else ""))
                for r in t["rows"]:
                    lines.append("| " + " | ".join(_yen(v) for v in r) + " |")
                lines.append("")
                lines += _formula_lines(t)
            lines += ["", "<details><summary>注・備考</summary>", ""] + [p + "\n" for p in t["notes"]] + ["</details>", "",
                      f"- **出典**: [国税庁 {t['year']}源泉徴収税額表]({t['source_url']})", ""]
    return "\n".join(lines).rstrip() + "\n"


def _range(p):
    lo, hi = p
    if lo is None:
        return f"{hi:,}未満"
    if hi is None:
        return f"{lo:,}以上"
    return f"{lo:,}〜{hi:,}"


def formula_rows(t):
    """表の続き（○円ちょうどの行と計算式）を、表示する順に並べる。"""
    out = []
    unit = t["unit"]
    for s in t["steps"]:
        out.append({"type": "step", "at": s["at"], "ko": s["ko"], "otsu": s["otsu"], "hei": s.get("hei")})
        f = next((f for f in t["ko"] if f["over"] == s["at"]), None)
        if f:
            rng = f"{f['over']:,}円を超え{f['under']:,}円に満たない金額" if f["under"] else f"{f['over']:,}円を超える金額"
            out.append({"type": "ko", "range": rng,
                        "text": f"{f['over']:,}円の場合の税額に、その{unit}の社会保険料等控除後の給与等の金額のうち{f['over']:,}円を超える金額の{f['rate']:g}％に相当する金額を加算した金額"})
        for col, label in (("otsu", "乙欄"), ("hei", "丙欄")):
            for g in t.get(col, []):
                if g["over"] == s["at"]:
                    out.append({"type": col, "range": f"{g['over']:,}円を超える金額（{label}）",
                                "text": f"{g['base']:,}円に、その{unit}の社会保険料等控除後の給与等の金額のうち{g['over']:,}円を超える金額の{g['rate']:g}％に相当する金額を加算した金額"})
    return out


def _formula_lines(t):
    lines = []
    for f in formula_rows(t):
        if f["type"] == "step":
            vals = ", ".join(f"甲{k}人 {v:,}円" for k, v in enumerate(f["ko"]))
            extra = "".join(f"、{lab} {f[c]:,}円" for c, lab in (("otsu", "乙"), ("hei", "丙")) if f.get(c) is not None)
            lines.append(f"- **{f['at']:,}円**: {vals}{extra}")
        else:
            lines.append(f"  - {f['range']}: {f['text']}")
    return lines


def search_items(tables):
    items = []
    for t in tables:
        label = {"getsugaku": "月額表", "nichigaku": "日額表", "shoyo": "賞与の算出率の表"}[t["kind"]]
        cols = "甲欄・乙欄・丙欄" if t["kind"] == "nichigaku" else "甲欄・乙欄"
        summary = (f"{t['year']}の{label}（{cols}）。社会保険料等控除後の金額と扶養親族等の数から税額を求められます。"
                   if t["kind"] != "shoyo" else
                   f"{t['year']}の賞与に対する源泉徴収税額の算出率の表（甲欄・乙欄）。前月の給与と扶養親族等の数から率を求め、賞与の税額を計算できます。")
        tbl = {k: v for k, v in t.items() if k not in ("notes", "title", "name", "source_url", "file_url", "id", "year", "kokuji")}
        if t["kind"] != "shoyo":
            tbl["flow"] = formula_rows(t)
        else:
            tbl["monthly"] = t["id"].replace("shoyo", "getsugaku")
        items.append({
            "id": t["id"], "cat": "nenmatsu", "sub": "nc-zeigakuhyo", "subs": ["nc-zeigakuhyo"], "sub2": [], "kind": "zeigakuhyo",
            "term": f"{t['name']}（{t['year']}）", "label": t["year"], "group": "",
            "summary": summary, "basis": t["kokuji"], "asOf": "",
            "md": summary + "\n\n" + "\n\n".join(t["notes"]), "url": t["source_url"],
            "srcLabel": "源泉徴収税額表", "srcTitle": f"国税庁 {t['year']}源泉徴収税額表", "fileUrl": t["file_url"],
            "tbl": tbl,
        })
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="国税庁サイトから取り直す")
    args = ap.parse_args()
    tables = build(args.refresh)
    OUT.write_text(json.dumps(tables, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for t in tables:
        n = len(t["rows"])
        print(f"{t['year']} {t['name']}: {n} 行", file=sys.stderr)


if __name__ == "__main__":
    main()
