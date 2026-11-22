# 手順書：1つの文書を移行する

依頼者の環境（Windows、Office、Python、Copilot CLI）で、1つの Excel 文書を移行する手順である。

この手順のうち、Copilot CLI と Excel を使う部分は、開発環境に両者がないため、まだ実行して確かめていない。該当する手順には「未確認」と書いた。うまく動かなかった箇所は、起きたことをそのまま教えてほしい。

## 0. 準備（最初の1回）

PowerShell で、このリポジトリのフォルダに移動して実行する。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[excel,dev]"
pytest
```

`pytest` がすべて合格すれば、移行ツールは動く状態である。LibreOffice を使うテスト1件は、LibreOffice がなければ飛ばされる。

## 1. 下書きを作る

```powershell
python -m docmig migrate "samples\nablarch\画面遷移図_サンプル.xlsx" --out migrated\trial-01
```

- `migrated\trial-01\` に、`document.md`（下書き）、`extract.json`、`figures\`（図の画像）ができる。
- 描画には Excel を使う（未確認）。Excel が一瞬起動し、原本を読み取り専用で開いて閉じる。原本は変更しない。
- 描画で失敗する場合は、`--render none` を付けると、画像なしで先に進める。その場合、図の書き起こしはできない。

出力先のフォルダに `document.md` が既にあると、上書きせずに止まる。書き起こした内容を失わないためである。作り直すときは `--force` を付ける。

## 2. 図の一覧を見る

```powershell
python -m docmig figure migrated\trial-01
```

図のID（`fig-s4` など）、記入の状態、シート名、画像のファイルが表示される。

## 3. 図を書き起こす（Copilot CLI、未確認）

図を1つずつ書き起こす。最初は、図形の少ない図で試すとよい。

```powershell
copilot --agent figure-transcriber `
  --attachment migrated\trial-01\figures\sheet-04-p1.png `
  --allow-tool='write, shell(python:*)' `
  -p "文書のフォルダ migrated/trial-01 の図 fig-s4 を書き起こしてください。"
```

- `--attachment` に、その図の画像を指定する。画像が複数ある図は、`--attachment` を画像の数だけ並べる。
- 画像の入力に対応したモデルを使う。モデルは `--model` で指定できる。
- `--allow-tool` の書き方は、Copilot CLI の版で変わる可能性がある。許可が足りないと、ファイルを書けずに終わる。

最初に確かめてほしいこと（[要求分析](04-analysis.md) の V-1）:

1. 添付した画像を、エージェントが見られているか。報告に「画像を見られない」とあれば、見られていない。
2. 対話なし（`-p`）でうまくいかない場合、`copilot --agent figure-transcriber` で対話モードを開き、同じ依頼文を入力して試す。

## 4. 検査する

```powershell
python -m docmig verify migrated\trial-01
```

- 「判定: 合格」になるまで、3 と 4 を繰り返す。
- 「文字の欠落」「図の文字の欠落」には、欠けている文字と、原本の場所（シート名、セル番地または図形ID）が表示される。

## 5. AI に確認させる（Copilot CLI、未確認）

書き起こしとは別の実行で行う。

```powershell
copilot --agent migration-reviewer `
  --attachment migrated\trial-01\figures\sheet-04-p1.png `
  --allow-tool='write, shell(python:*)' `
  -p "文書のフォルダ migrated/trial-01 を確認してください。"
```

- 結果は `migrated\trial-01\review-notes.md` に書かれる。
- 食い違いがなければ、`document.md` の `review_status` が `AI確認済み` になる。
- 食い違いがあれば、`document.md` に `【要確認: ...】` が足される。内容を見て、3 からやり直す。

## 6. 人が承認する

`review_status` が `AI確認済み` になった文書を、人が原本と見比べる。問題がなければ、`document.md` の `review_status` を `承認済み` に書き換え、検査を実行する。

```powershell
python -m docmig verify migrated\trial-01
```

## 7. 結果を記録する

初回は、次の4点を記録してほしい（[要求分析](04-analysis.md) 6章の成功の基準）。

| 記録すること | 対応する基準 |
|---|---|
| 検査の結果（欠落の件数） | S-1 |
| 書き起こした図と原本の図の、矢印の食い違いの件数と内容 | S-2 |
| 移行後の文書について Copilot に質問した結果（質問、回答、正誤） | S-3 |
| 人が作業した時間 | S-4 |

## クラウドの開発環境で動かすとき

Claude のクラウド環境では、Copilot CLI の通常のログインが通らない。起動時の利用者の確認（`api.github.com/copilot_internal/user`）を、環境の GitHub 用プロキシが拒否するためである。次の設定を入れてから `copilot` を実行すると、Copilot のサービスに直接つながる（2026-11-22、Copilot CLI 1.0.114 で確認）。

```bash
export COPILOT_PROVIDER_BASE_URL=https://api.githubcopilot.com
export COPILOT_PROVIDER_BEARER_TOKEN="$COPILOT_GITHUB_TOKEN"
export COPILOT_PROVIDER_HEADERS=$'Copilot-Integration-Id: copilot-developer-cli\nCopilot-Vision-Request: true'
export COPILOT_PROVIDER_VISION=true
export COPILOT_MODEL=gpt-4.1
```

- `COPILOT_GITHUB_TOKEN` は、「Copilot Requests」の権限を付けた fine-grained PAT で、環境の設定に入れておく。
- GitHub の文書にない使い方である。使うかどうかは依頼者が決める。
- このつなぎ方で送ったデータが、通常の使い方と同じ扱いになるかは確かめていない。実際の設計書には、依頼者が判断するまで使わない。
- モデルの自動選択は使えない。確認した時点で応答したモデルは gpt-4.1 だけだった。結果は [要求評価](07-evaluation.md) の 3.3 にある。

## 自分の文書で試すとき

`samples\...` の部分を、自分の Excel ファイルの場所に変える。出力先（`--out`）は、文書ごとに別のフォルダにする。

設計情報を扱うことになるため、移行した結果をこのリポジトリにコミットしてよいかは、社内の決まりに従って判断する。移行ツールは外部と通信しない。Copilot CLI には、図の画像と文書の内容が送られる。
