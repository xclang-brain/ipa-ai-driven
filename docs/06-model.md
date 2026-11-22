# モデル

| 項目 | 内容 |
|---|---|
| 文書ID | DOC-06 |
| 工程 | 6. モデリング |
| 版 | 1.0 |
| 作成日 | 2026-11-22 |

ハンドブック 7.2.6 節に従い、業務の流れ、データ、AI の利用箇所、確認の状態を図にした。図の中の FR は [要件台帳](../requirements/system-requirements.yaml) の要件ID である。

## 1. 移行の流れ

誰が何を行い、何が次の段階に渡るかを示す。

```mermaid
flowchart TD
    source[("原本<br>Word / Excel")]
    subgraph tool["移行ツール docmig（プログラム）"]
        extract["取り出し<br>FR-001〜005"]
        render["描画<br>FR-006"]
        draft["下書きの生成<br>FR-007、FR-008"]
        figure["図のデータの出力<br>FR-014"]
        verify["検査<br>FR-009〜013、FR-017"]
    end
    subgraph ai["AI（Copilot CLI）"]
        transcribe["図の書き起こし<br>FR-014"]
        review["確認<br>FR-015"]
    end
    human["人による承認"]
    data[("中間データ<br>extract.json")]
    images[("図の画像<br>figures/")]
    document[("移行後の文書<br>document.md")]

    source --> extract --> data
    source --> render --> images
    data --> draft --> document
    data --> figure --> transcribe
    images --> transcribe --> document
    document --> verify
    data --> verify
    verify -->|"不合格"| transcribe
    verify -->|"合格"| review
    images --> review
    review -->|"食い違いあり<br>要確認の印を付ける"| transcribe
    review -->|"食い違いなし<br>AI確認済みにする"| human
    human -->|"承認済みにする"| document
```

## 2. AI を使う箇所と、人に引き継ぐ条件

| 箇所 | AI が行うこと | AI に渡すもの | 人に引き継ぐ条件 |
|---|---|---|---|
| 図の書き起こし | 図のつながりを読み取り、Mermaid で書く | 図の画像、図形と矢印の一覧 | 読み取れない箇所がある（要確認の印）。検査の欠落を3回直しても解消できない。画像を見られない |
| 確認 | 画像と書き起こしを見比べ、食い違いを報告する | 図の画像、図形と矢印の一覧、移行後の文書 | 食い違いがある（要確認の印）。検査に不合格 |
| 移行後の利用 | 文書を根拠に、質問に答え、実装する | 移行後の文書 | 要確認の印がある箇所に依存する。文書に書かれていない |

文字の取り出しと照合には AI を使わない。同じ入力から常に同じ結果が得られ、規則で書けるためである（[要求分析](04-analysis.md) 5章）。

## 3. 確認の状態

`review_status` の値と、変えられる担い手を示す（FR-009、FR-013、FR-015）。

```mermaid
stateDiagram-v2
    [*] --> 未確認: 下書きの生成（プログラム）
    未確認 --> AI確認済み: 検査に合格し、食い違いがなく、要確認の印がない（確認するエージェント）
    AI確認済み --> 承認済み: 人が内容を確かめた（人）
    AI確認済み --> 未確認: 文書を変更した
    承認済み --> 未確認: 文書を変更した
```

- `承認済み` に変えられるのは人だけである。
- 検査は、状態と内容の矛盾（不合格なのに `AI確認済み`、要確認の印が残っているのに `承認済み`）を誤りとして報告する。
- 文書を変更したときに状態を `未確認` に戻すことは、初回は運用の決まりとする。道具による強制は行っていない。

## 4. データ

中間データ（extract.json）と、移行後の文書との関係を示す。

```mermaid
erDiagram
    SOURCE ||--|{ SHEET : "含む"
    SHEET ||--o{ CELL : "含む"
    SHEET ||--o{ BLOCK : "含む"
    BLOCK ||--|{ CELL : "まとめる"
    SHEET ||--o{ SHAPE : "含む"
    SHEET ||--o{ CONNECTOR : "含む"
    SHEET ||--o{ PICTURE : "含む"
    CONNECTOR }o--o| SHAPE : "始点側の候補"
    CONNECTOR }o--o| SHAPE : "終点側の候補"
    DOCUMENT ||--|| SOURCE : "ハッシュ値で対応"
    DOCUMENT ||--o{ FIGURE : "含む"
    FIGURE ||--|| SHEET : "シート名で対応"

    SOURCE {
        string file "ファイル名"
        string sha256 "ハッシュ値"
    }
    SHEET {
        int index "順番"
        string name "シート名"
        string state "表示か非表示か"
    }
    CELL {
        string ref "セル番地"
        string text "内容"
        string merge "結合範囲"
        string header "繰り返される見出し欄か"
    }
    BLOCK {
        string id "ブロックID"
        string kind "表か文章か"
        string range "セル範囲"
    }
    SHAPE {
        string id "図形ID"
        string kind "種類"
        string text "文字"
        string bbox "位置と大きさ"
    }
    CONNECTOR {
        string id "図形ID"
        string start "始点の座標"
        string end "終点の座標"
        bool arrow_end "終点に矢じりがあるか"
        string attached_end "ファイルに記録された接続先"
    }
    PICTURE {
        string id "図形ID"
        string file "保存先"
    }
    DOCUMENT {
        string doc_id "文書ID"
        string source_sha256 "原本のハッシュ値"
        string review_status "確認の状態"
    }
    FIGURE {
        string id "図のID"
        string sheet "シート名"
    }
```
