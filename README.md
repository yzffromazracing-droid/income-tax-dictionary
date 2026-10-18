# 所得税区分辞書（income-tax-dictionary）

国税庁ホームページの[タックスアンサー（所得税）](https://www.nta.go.jp/taxes/shiraberu/taxanswer/code/index.htm)と[法令解釈通達](https://www.nta.go.jp/law/tsutatsu/menu.htm)をもとに作成した「所得税区分辞書」です。

## 検索

[docs/index.html](docs/index.html) をブラウザで開くと、全カテゴリの用語をまとめて検索できます（1ファイルで動作し、サーバー不要）。

- 用語名・通称・要旨・本文・根拠法令（例: `所法9`）・タックスアンサー番号（例: `1199`）を対象に検索
- ひらがなの読みでも検索できます（例: `ふよう` → 扶養控除、`じゅうたく` → 本文中の「住宅」「住宅借入金」も対象）
- スペース区切りで AND 検索、全角/半角・カタカナ/ひらがなの違いは無視
- 非課税・所得区分・青色申告・所得控除・税額控除・通達をタブで切り替え（検索中は各タブに一致件数を表示）
- 通達タブの下には基本通達・個別通達のタブがあり、`36-30` や `所基通9-3` のように通達番号でも検索できる
- 非課税タブの下には No.2011 の表の区分（利子・配当所得関係、給与所得・公的年金関係、譲渡（山林）所得関係、その他）のタブ、所得区分タブの下には利子所得から雑所得までの10種類の所得のタブ（利子所得・配当所得・譲渡所得・一時所得・雑所得の下にはさらに総合課税・分離課税のタブ、退職所得の下には分離課税のタブ）、所得控除タブの下には雑損控除から基礎控除までの各控除のタブ、税額控除タブの下には配当控除から公益社団法人等寄附金特別控除までの各控除のタブがある
- `#no1199` のようなリンクで用語を、`#shotoku-kojo` や `#kyuyo`（給与所得）のようなリンクでタブを直接開ける
- GitHub Pages を「main ブランチの /docs」で公開すれば Web 上でも使えます

## カテゴリ

| カテゴリ | ファイル | 出典（概要ページ） | 項目数 |
|---|---|---|---|
| 非課税 | [dictionary/hikazei.md](dictionary/hikazei.md) | [No.2011 課税される所得と非課税所得](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2011.htm) | 24 |
| 所得区分 | [dictionary/shotoku-kubun.md](dictionary/shotoku-kubun.md) | [No.1300 所得の区分のあらまし](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1300.htm) | 20 |
| 青色申告 | [dictionary/aoiro.md](dictionary/aoiro.md) | [No.2070 青色申告制度](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2070.htm) | 4 |
| 所得控除 | [dictionary/shotoku-kojo.md](dictionary/shotoku-kojo.md) | [No.1100 所得控除のあらまし](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1100.htm) | 18 |
| 税額控除 | [dictionary/zeigaku-kojo.md](dictionary/zeigaku-kojo.md) | [No.1200 税額控除](https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1200.htm) | 11 |
| 通達（基本通達） | [dictionary/tsutatsu-kihon.md](dictionary/tsutatsu-kihon.md) | [所得税基本通達](https://www.nta.go.jp/law/tsutatsu/kihon/shotoku/01.htm) | 1,183 |
| 通達（個別通達） | [dictionary/tsutatsu-kobetsu.md](dictionary/tsutatsu-kobetsu.md) | [法令解釈通達（所得税関係の個別通達）](https://www.nta.go.jp/law/tsutatsu/menu.htm) | 318 |

- 非課税は No.2011 の「主な非課税所得」の表の各項目を1語として収録し、区分・通称・根拠条文・関連するタックスアンサーを付けています。
- 所得区分・所得控除・税額控除は、各タックスアンサーのページを1語として収録し、要旨・根拠法令等・本文（表を含む）を載せています。
- 検索ページは `scripts/search_template.html` をもとに生成されます。
- 読みは [data/yomi.tsv](data/yomi.tsv)（表記と読みの対応表）から作ります。用語名はこの表で区切って読みを組み立て、読めない漢字が残るとビルドがエラーで止まるので、その語を表に追加してください。本文を読みで検索できるのも、この表にある語に限られます。
- 所得区分の各所得、所得控除・税額控除の各控除には具体例（当たらない例、課税方法が異なる例を含む）を載せています。例は [data/shotoku_examples.json](data/shotoku_examples.json)・[data/kojo_examples.json](data/kojo_examples.json)・[data/zeigaku_examples.json](data/zeigaku_examples.json) に、出典（タックスアンサーまたは所得税基本通達）とその本文の文言を添えて書いてあり、ビルド時に文言が出典の本文に実在するかを照合します（見つからなければエラーで止まります）。
- 青色申告には、対象者・申請期限・帳簿・特典などの要点（[data/aoiro_points.json](data/aoiro_points.json)、出典の文言を照合）と、関連する所得税基本通達（法第52条・57条・143条〜151条関係）の一覧を付けています。
- 通達は `scripts/tsutatsu.py` で取得します。基本通達は「2-1」などの通達番号ごとに1語、個別通達は通達ごとに1語です（申告所得税・源泉所得税・譲渡・山林所得・租税特別措置法の各関係。5ページを超える通達はページごとに分けています。一部改正通達は含みません）。
- 機械処理用のデータは [data/income_tax_dictionary.json](data/income_tax_dictionary.json) にあります。

収録内容は各ページに記載の「令和8年4月1日現在法令等」に基づきます。最新の内容・個別の判断は必ず出典ページをご確認ください。

## 再生成

```sh
pip install beautifulsoup4 lxml
python3 scripts/build_dictionary.py            # 取得したHTMLは .cache/ に保存され再利用されます
python3 scripts/build_dictionary.py --refresh  # 国税庁サイトから取り直す
```

収録するページは `scripts/build_dictionary.py` の `CATEGORIES` で変更できます。
