# ipa-ai-driven

ファームウェア開発部門の既存ドキュメント（Word / Excel）を、AI が参照できる知識にするための取り組み。

開発は、IPA「[AI時代の要求管理ハンドブック](https://www.ipa.go.jp/digital/kaihatsu/rqr7mi000000f5up-att/req-mgmt-hb.pdf)」Version 1.0.0 の第7章が示す12の工程に沿って進める。

## 最初に読むもの

| 文書 | 内容 |
|---|---|
| [docs/process.md](docs/process.md) | 開発の進め方。ハンドブックに沿うための決まりと手順 |
| [docs/handoff.md](docs/handoff.md) | 今の状態と、次に行うこと |
| [docs/handbook-summary.md](docs/handbook-summary.md) | ハンドブックの要点 |
| [AGENTS.md](AGENTS.md) | 作業する AI への案内 |

## 使い方

移行の手順は [docs/runbook.md](docs/runbook.md) にある。

```
pip install -e ".[dev]"
python -m docmig migrate 原本.xlsx --out migrated/文書ID   # 下書きと図の画像を作る
python -m docmig figure migrated/文書ID                    # 図の一覧
python -m docmig verify migrated/文書ID                    # 原本と照合する
pytest                                                     # テスト
```

図の書き起こしと確認は、Copilot CLI のエージェント（`.github/agents/`）が行う。

## 要求の管理

要求は `requirements/requirements.yaml`、要件は `requirements/system-requirements.yaml` を正本とする。`docs/requirements.md`、`docs/system-requirements.md`、`docs/traceability.md` は次のコマンドで出力したもので、直接は編集しない。

```
python tools/render_ledger.py
```

## 検証に使うサンプル文書

依頼者の文書は使えないため、公開されている「[Nablarch 開発標準](https://github.com/nablarch-development-standards/nablarch-development-standards)」の設計ドキュメントのサンプル（クリエイティブ・コモンズ 表示 - 継承 4.0 国際）を使う。

## 進み具合

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
| 9. 実現手段への接続 | `src/docmig/`、`tests/`、`.github/agents/`、[docs/traceability.md](docs/traceability.md)、[docs/runbook.md](docs/runbook.md) | プログラムは実装とテスト済み。Copilot CLI を使う部分は未確認 |
| 10. 運用・監視 | 未着手 | 依頼者の実際の文書を移行し始めるときに着手する |
| 11. フィードバック・変更管理 | [docs/change-log.md](docs/change-log.md) | ベースラインのあとの変更を記録している |
| 12. 廃止・移行 | 未着手 | 原本を正本でなくすときに着手する |
