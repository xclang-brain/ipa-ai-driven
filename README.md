# ipa-ai-driven

Word や Excel で書かれた設計書を、AI が読める文章（Markdown）に作り直すための道具と、その開発の記録です。

## 何に困っていて、何をするのか

設計書の多くは Word と Excel で書かれています。GitHub Copilot などの AI は、これらのファイルをそのままでは読めません。既存の変換ツールを使うと、図形で描いた図（画面遷移図など）が消えてしまいます。

このリポジトリの道具は、図を文字で書いた図（Mermaid）に置き換えて、内容を落とさずに Markdown へ移します。

| 原本にあるもの | 移し方 |
|---|---|
| 文章と表 | プログラムが取り出す |
| 図形で描いた図 | AI（GitHub Copilot）が Mermaid に書き起こす |
| 移したあとの確認 | プログラムが原本と照合し、AI がもう一度見比べ、最後に人が承認する |

たとえば、Excel の図形で描かれた画面遷移図は、次のような文字の図になります。

```mermaid
flowchart LR
    s1["顧客情報登録"] -->|"確認"| s2["顧客情報登録確認"]
    s2 -->|"戻る"| s1
    s2 -->|"確定"| s3["顧客情報登録完了"]
```

移行した文書の実例は [migrated/screen-transition/document.md](migrated/screen-transition/document.md) にあります。

## 今できること、まだできないこと

開発の途中です。実際の業務にはまだ使えません。

| 項目 | 状態 |
|---|---|
| Excel の文書の文章と表を取り出す | できる |
| 移行後の文書を原本と照合する | できる |
| 図を Copilot に書き起こさせる | 仕組みは動いた。精度は確認の途中 |
| Word の文書 | まだできない |
| 貼り付けた画像の中の文字 | まだできない |
| 実際の設計書での確認 | まだ。公開されているサンプルだけで試している |

詳しい状態と、次に行うことは [docs/handoff.md](docs/handoff.md) にあります。

## 試してみる

Python 3.10 以上が必要です。図の画像を作るには、Excel（Windows）か LibreOffice が要ります。

```
pip install -e ".[excel,dev]"
python -m docmig migrate "samples/nablarch/画面遷移図_サンプル.xlsx" --out migrated/trial-01
python -m docmig verify migrated/trial-01
```

- 2行目で、`migrated/trial-01/` に下書き（`document.md`）と図の画像ができます。
- 3行目で、原本と照合します。この時点では、図をまだ書き起こしていないため「不合格」と表示されます。
- 図の書き起こしから承認までの手順は [docs/runbook.md](docs/runbook.md) にあります。

サンプルは、公開されている「[Nablarch 開発標準](https://github.com/nablarch-development-standards/nablarch-development-standards)」の設計書です（クリエイティブ・コモンズ 表示 - 継承 4.0 国際）。

## フォルダの見方

| 場所 | 内容 |
|---|---|
| `migrated/` | 移行した文書。仕様を調べるときはここを読む |
| `samples/` | 試すための原本（Excel） |
| `src/docmig/` | 移行の道具のプログラム |
| `.github/agents/` | 図の書き起こしと確認を Copilot に任せるための指示 |
| `docs/` | 開発の記録（目的、聞き取り、要求、仕様、評価） |
| `requirements/` | 要求と要件の台帳 |

## 開発に参加する人へ

開発は、IPA「[AI時代の要求管理ハンドブック](https://www.ipa.go.jp/digital/kaihatsu/rqr7mi000000f5up-att/req-mgmt-hb.pdf)」Version 1.0.0 に沿って進めています。依頼された内容をすぐに実装せず、目的、要求、要件を台帳に書いてから作ります。

| 最初に読む文書 | 内容 |
|---|---|
| [docs/process.md](docs/process.md) | 開発の進め方と決まり |
| [docs/handoff.md](docs/handoff.md) | 今の状態と、次に行うこと |
| [docs/handbook-summary.md](docs/handbook-summary.md) | ハンドブックの要点 |
| [AGENTS.md](AGENTS.md) | 作業する AI への案内 |

要求は `requirements/requirements.yaml`、要件は `requirements/system-requirements.yaml` が正本です。`docs/requirements.md`、`docs/system-requirements.md`、`docs/traceability.md` は次のコマンドで出力したもので、直接は編集しません。

```
pytest
python tools/render_ledger.py
```

### 工程ごとの進み具合

| 工程 | 成果物 | 状態 |
|---|---|---|
| 1. 目的・ミッションの確認 | [docs/01-purpose.md](docs/01-purpose.md) | 暫定版。リスクの候補は依頼者の確認待ち |
| 2. ステークホルダーの特定 | [docs/02-stakeholders.md](docs/02-stakeholders.md) | 暫定版。依頼者以外は想定で、確認待ち |
| 3. 要求獲得 | [docs/03-hearing-001.md](docs/03-hearing-001.md)、[docs/03-hearing-002.md](docs/03-hearing-002.md) | 第2回まで実施 |
| 4. 要求分析 | [docs/04-analysis.md](docs/04-analysis.md)、[要求管理台帳](requirements/requirements.yaml)（一覧は [docs/requirements.md](docs/requirements.md)） | 依頼者が合意済み |
| 5. 要求仕様化 | [docs/05-specification.md](docs/05-specification.md)、[要件台帳](requirements/system-requirements.yaml)（一覧は [docs/system-requirements.md](docs/system-requirements.md)） | 初回の範囲を定義済み |
| 6. モデリング | [docs/06-model.md](docs/06-model.md) | 作成済み |
| 7. 要求評価・妥当性確認 | [docs/07-evaluation.md](docs/07-evaluation.md) | 開発環境での評価まで。依頼者の環境での確認が残っている |
| 8. 要求ベースライン化 | 要求管理台帳の版 1.0（その後の変更を含めた現在の版は 1.1） | 設定済み |
| 9. 実現手段への接続 | `src/docmig/`、`tests/`、`.github/agents/`、[docs/traceability.md](docs/traceability.md)、[docs/runbook.md](docs/runbook.md) | プログラムは実装とテスト済み。Copilot CLI を使う部分は、開発環境で一度試した。依頼者の環境では未確認 |
| 10. 運用・監視 | 未着手 | 依頼者の実際の文書を移行し始めるときに着手する |
| 11. フィードバック・変更管理 | [docs/change-log.md](docs/change-log.md) | ベースラインのあとの変更を記録している |
| 12. 廃止・移行 | 未着手 | 原本を正本でなくすときに着手する |
