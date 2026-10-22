# 所得税区分辞書（income-tax-dictionary）

## 検索

公開ページ: **[https://yzffromazracing-droid.github.io/income-tax-dictionary/](https://yzffromazracing-droid.github.io/income-tax-dictionary/)**

全カテゴリの用語をまとめて検索できます（GitHub Pages で公開。中身は [docs/index.html](docs/index.html) の1ファイルで、手元でブラウザで開いても使えます）。

- 用語名・通称・要旨・本文・根拠法令（例: `所法9`）・タックスアンサー番号（例: `1199`）を対象に検索
- ひらがなの読みでも検索できます（例: `ふよう` → 扶養控除、`じゅうたく` → 本文中の「住宅」「住宅借入金」も対象）
- スペース区切りで AND 検索、全角/半角・カタカナ/ひらがなの違いは無視
- 先頭の「辞書」タブでは全カテゴリをまとめて検索できます（下のタブでカテゴリに絞り込み。検索結果にはカテゴリ名を表示）
- 非課税・所得区分・青色申告・所得控除・年末調整・税額控除・国税庁の記事・通達をタブで切り替え（検索中は各タブに一致件数を表示）
- 通達タブの下には基本通達・個別通達のタブがあり、`36-30` や `所基通9-3` のように通達番号でも検索できる
- 非課税タブの下には No.2011 の表の区分（利子・配当所得関係、給与所得・公的年金関係、譲渡（山林）所得関係、その他）のタブ、所得区分タブの下には利子所得から雑所得までの10種類の所得のタブ（利子所得・配当所得・譲渡所得・一時所得・雑所得の下にはさらに総合課税・分離課税のタブ、退職所得・山林所得の下には分離課税のタブ、不動産所得・事業所得・給与所得の下には総合課税のタブ）、所得控除タブの下には雑損控除から基礎控除までの各控除のタブ、年末調整タブの下には対象となる人・対象となる給与・控除の申告・精算・やり直し・確定申告が必要な場合・源泉徴収税額表のタブ、税額控除タブの下には配当控除から公益社団法人等寄附金特別控除までの各控除のタブがある
- `#no1199` のようなリンクで用語を、`#shotoku-kojo` や `#kyuyo`（給与所得）のようなリンクでタブを直接開ける

## カテゴリ

| カテゴリ | ファイル | 出典（概要ページ） | 項目数 |
|---|---|---|---|
| 非課税 | [dictionary/hikazei.md](dictionary/hikazei.md) | [No.2011 課税される所得と非課税所得](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2011.htm) | 24 |
| 所得区分 | [dictionary/shotoku-kubun.md](dictionary/shotoku-kubun.md) | [No.1300 所得の区分のあらまし](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1300.htm) | 21 |
| 青色申告 | [dictionary/aoiro.md](dictionary/aoiro.md) | [No.2070 青色申告制度](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2070.htm) | 4 |
| 所得控除 | [dictionary/shotoku-kojo.md](dictionary/shotoku-kojo.md) | [No.1100 所得控除のあらまし](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1100.htm) | 18 |
| 年末調整 | [dictionary/nenmatsu.md](dictionary/nenmatsu.md) | [No.2662 年末調整のしかた](https://www.nta.go.jp/taxes/shiraberu/taxanswer/gensen/2662.htm) | 14 |
| 源泉徴収税額表（年末調整タブ） | [dictionary/gensen-zeigakuhyo.md](dictionary/gensen-zeigakuhyo.md) | [令和8年分](https://www.nta.go.jp/publication/pamph/gensen/zeigakuhyo2026/01.htm)・[令和9年分](https://www.nta.go.jp/publication/pamph/gensen/zeigakuhyo2027/01.htm)の源泉徴収税額表 | 6 表 |
| 税額控除 | [dictionary/zeigaku-kojo.md](dictionary/zeigaku-kojo.md) | [No.1200 税額控除](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1200.htm) | 11 |
| 国税庁の記事（タックスアンサー） | [dictionary/kiji-taxanswer.md](dictionary/kiji-taxanswer.md) | [タックスアンサー コード一覧](https://www.nta.go.jp/taxes/shiraberu/taxanswer/code/index.htm)の所得税・源泉所得税・譲渡所得 | 346 |
| 国税庁の記事（質疑応答事例） | [dictionary/kiji-shitsugi.md](dictionary/kiji-shitsugi.md) | [質疑応答事例](https://www.nta.go.jp/law/shitsugi/01.htm)の所得税・源泉所得税・譲渡所得 | 669 |
| 通達（基本通達） | [dictionary/tsutatsu-kihon.md](dictionary/tsutatsu-kihon.md) | [所得税基本通達](https://www.nta.go.jp/law/tsutatsu/kihon/shotoku/01.htm) | 1,183 |
| 通達（個別通達） | [dictionary/tsutatsu-kobetsu.md](dictionary/tsutatsu-kobetsu.md) | [法令解釈通達（所得税関係の個別通達）](https://www.nta.go.jp/law/tsutatsu/menu.htm) | 318 |

- 非課税は No.2011 の「主な非課税所得」の表の各項目を1語として収録し、区分・通称・根拠条文・関連するタックスアンサーを付けています。
- 所得区分・所得控除・年末調整・税額控除は、各タックスアンサーのページを1語として収録し、要旨・根拠法令等・本文（表を含む）を載せています。
- 検索ページは `scripts/search_template.html` をもとに生成されます。
- 読みは [data/yomi.tsv](data/yomi.tsv)（表記と読みの対応表）から作ります。用語名はこの表で区切って読みを組み立て、読めない漢字が残るとビルドがエラーで止まるので、その語を表に追加してください。本文を読みで検索できるのも、この表にある語に限られます。
- 非課税の各項目、所得区分の各所得、青色申告の各ページ、所得控除・税額控除の各控除、年末調整の各ページには具体例（当たらない例、課税方法が異なる例を含む）を載せています。例は [data/hikazei_examples.json](data/hikazei_examples.json)・[data/shotoku_examples.json](data/shotoku_examples.json)・[data/aoiro_examples.json](data/aoiro_examples.json)・[data/kojo_examples.json](data/kojo_examples.json)・[data/zeigaku_examples.json](data/zeigaku_examples.json)・[data/nenmatsu_examples.json](data/nenmatsu_examples.json) に、出典（タックスアンサーまたは所得税基本通達）とその本文の文言を添えて書いてあり、ビルド時に文言が出典の本文に実在するかを照合します（見つからなければエラーで止まります）。
- 青色申告には、対象者・申請期限・帳簿・特典などの要点（[data/aoiro_points.json](data/aoiro_points.json)、出典の文言を照合）と、関連する所得税基本通達（法第52条・57条・143条〜151条関係）の一覧を付けています。
- 年末調整には、対象者・時期・計算の順序・精算などの要点（[data/nenmatsu_points.json](data/nenmatsu_points.json)、出典の文言を照合）と、関連する所得税基本通達（法第183条〜198条関係のうち年末調整と給与所得者の申告書に関するもの）の一覧を付けています。年末調整のページの多くはタックスアンサーの「源泉所得税」に載っています。
- 源泉徴収税額表（月額表・日額表・賞与に対する源泉徴収税額の算出率の表、令和8年分・令和9年分）は、国税庁が公開している Excel を `scripts/zeigakuhyo.py` で読み取って [data/zeigakuhyo.json](data/zeigakuhyo.json) にしたものです。検索ページでは表の全行と、金額・扶養親族等の数を入れると甲欄・乙欄（日額表は丙欄も）の税額を求める計算フォームを表示します。賞与は前月の給与がない場合や10倍を超える場合の月額表による計算（No.2523）にも対応しています。ビルド時に No.2523 の計算例（令和8年分）と同じ税額になるかを照合します。
- 国税庁の記事は `scripts/kiji.py` で取得します。タックスアンサーはコード一覧の「所得税」「源泉所得税」「譲渡所得」に載っているページ、質疑応答事例は同じ3分野の目次に載っている事例です。検索ページでは「国税庁の記事」タブの下にタックスアンサー・質疑応答事例のタブ、さらにその下に分野のタブがあります（ほかのタブと重なるタックスアンサーもあります）。
- 通達は `scripts/tsutatsu.py` で取得します。基本通達は「2-1」などの通達番号ごとに1語、個別通達は通達ごとに1語です（申告所得税・源泉所得税・譲渡・山林所得・租税特別措置法の各関係。5ページを超える通達はページごとに分けています。一部改正通達は含みません）。
- 機械処理用のデータは [data/income_tax_dictionary.json](data/income_tax_dictionary.json) にあります。

収録内容は各ページに記載の「令和8年4月1日現在法令等」に基づきます。最新の内容・個別の判断は必ず出典ページをご確認ください。

## 再生成

```sh
pip install beautifulsoup4 lxml
python3 scripts/build_dictionary.py            # 取得したHTMLは .cache/ に保存され再利用されます
python3 scripts/build_dictionary.py --refresh  # 国税庁サイトから取り直す
```

源泉徴収税額表（data/zeigakuhyo.json）を作り直すときは、openpyxl と LibreOffice（.xls の変換に使います）を用意して次を実行します。

```sh
pip install openpyxl
python3 scripts/zeigakuhyo.py --refresh
```

収録するページは `scripts/build_dictionary.py` の `CATEGORIES` で変更できます。
