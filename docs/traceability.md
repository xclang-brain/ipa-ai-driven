# トレーサビリティ表

このファイルは `tools/render_ledger.py` が台帳から出力したものである。内容を変えるときは台帳を編集し、出力し直す。

## 要求から要件へ

| 要求 | 内容 | 優先度 | 要件 |
|---|---|---|---|
| REQ-001 | 既存ドキュメントの移行 | Must | FR-001、FR-007 |
| REQ-002 | 表の移行 | Must | FR-001、FR-002、FR-007 |
| REQ-003 | 図形で描かれた図の移行 | Must | FR-003、FR-004、FR-006、FR-012、FR-014 |
| REQ-004 | 貼り付け画像の移行 | Should | FR-005 |
| REQ-005 | 移行後の文書を正本とする | Must | FR-007 |
| REQ-006 | 使う AI は GitHub Copilot のみ | Must | FR-014、NFR-001 |
| REQ-007 | AI による実装・修正 | Should | なし（移行した文書ができてから取り組む。FR-016 の案内は、この要求にも使える） |
| REQ-008 | AI による仕様の調査・質問への回答 | Must | FR-016 |
| REQ-009 | AI によるテストの作成 | Should | なし（移行した文書ができてから取り組む） |
| REQ-010 | AI による仕様とコードの整合確認 | Should | なし（移行した文書ができてから取り組む） |
| REQ-011 | 環境整備の期間短縮 | Should | なし（要件にはせず、移行にかかる人の作業時間を記録して評価する（成功の基準 S-4）） |
| REQ-012 | 原本との一致の確認 | Must | FR-010、FR-011、FR-012、FR-015、NFR-003 |
| REQ-013 | 原本の箇所への追跡 | Must | FR-001、FR-003、FR-008、FR-016 |
| REQ-014 | 図の編集 | Must | FR-014 |
| REQ-015 | 原本の保管 | Should | FR-010 |
| REQ-016 | まず1つの文書を移行する | Must | なし（初回の範囲を1つの文書にすることで反映した） |
| REQ-017 | 確認はまず AI が行う | Must | FR-009、FR-015 |
| REQ-018 | 文書の規模 | Should | なし（初回では確かめない。2回目以降で、ページ数の多い文書を使って確かめる） |
| REQ-019 | 移行作業の環境 | Must | FR-006、NFR-002 |
| REQ-020 | 確認の状態の表示 | Must | FR-009 |
| REQ-021 | 読み取れない箇所の扱い | Must | FR-013、FR-014 |
| REQ-022 | 使う AI のモデルの確認と記録 | 未定 | なし（理由の記録がない） |

## 要件からテストへ

| 要件 | 内容 | 由来 | 確かめ方 | 状態 | 自動テスト |
|---|---|---|---|---|---|
| FR-001 | セルの取り出し | REQ-001、REQ-002、REQ-013 | 自動テスト | 検証済み | `test_extract.py::test_fr001_cells_carry_sheet_name_and_reference`<br>`test_extract.py::test_fr001_formula_cell_gives_the_stored_result`<br>`test_extract.py::test_fr001_japanese_date_formats_become_iso_dates` |
| FR-002 | 結合セルの記録 | REQ-002 | 自動テスト | 検証済み | `test_extract.py::test_fr002_merged_cell_is_recorded_once_with_its_range` |
| FR-003 | 図形の取り出し | REQ-003、REQ-013 | 自動テスト | 検証済み | `test_extract.py::test_fr003_all_shape_texts_are_extracted`<br>`test_extract.py::test_fr003_shapes_in_a_group_are_placed_on_the_sheet`<br>`test_extract.py::test_fr003_dashed_outline_is_recorded` |
| FR-004 | 矢印の取り出し | REQ-003 | 自動テスト | 検証済み | `test_extract.py::test_fr004_lines_and_connectors_are_extracted`<br>`test_extract.py::test_fr004_rotation_by_180_degrees_swaps_the_endpoints`<br>`test_extract.py::test_fr004_flip_moves_the_start_to_the_other_corner`<br>`test_extract.py::test_fr004_endpoint_on_a_border_gets_that_shape_as_candidate`<br>`test_extract.py::test_fr004_label_text_box_is_not_preferred_over_a_shape_at_the_same_distance`<br>`test_extract.py::test_fr004_endpoint_far_from_any_shape_gets_no_candidate`<br>`test_extract.py::test_fr004_candidates_agree_with_connections_recorded_in_the_file` |
| FR-005 | 貼り付け画像の保存 | REQ-004 | 自動テスト | 検証済み | `test_extract.py::test_fr005_pasted_pictures_are_saved_as_files` |
| FR-006 | シートの描画 | REQ-003、REQ-019 | 自動テスト（LibreOffice）、依頼者環境（Excel） | 実装済み | `test_render_and_cli.py::test_fr006_pages_are_assigned_to_sheets_in_order`<br>`test_render_and_cli.py::test_fr006_sheets_with_shapes_are_rendered_and_recorded` |
| FR-007 | 下書きの生成 | REQ-001、REQ-002、REQ-005 | 自動テスト | 検証済み | `test_draft_and_verify.py::test_fr007_sections_follow_the_sheet_order`<br>`test_draft_and_verify.py::test_fr007_change_history_becomes_a_table`<br>`test_draft_and_verify.py::test_fr007_repeated_header_block_appears_once`<br>`test_draft_and_verify.py::test_fr007_sheets_with_shapes_get_a_figure_frame_marked_as_todo` |
| FR-008 | 由来の記録 | REQ-013 | 自動テスト、レビュー | 検証済み | `test_draft_and_verify.py::test_fr008_every_block_is_preceded_by_its_origin` |
| FR-009 | 確認の状態 | REQ-020、REQ-017 | 自動テスト | 検証済み | `test_draft_and_verify.py::test_fr009_draft_starts_as_unconfirmed`<br>`test_draft_and_verify.py::test_fr009_failed_document_must_not_be_marked_as_confirmed`<br>`test_draft_and_verify.py::test_fr009_unknown_status_is_an_error`<br>`test_draft_and_verify.py::test_fr009_passing_document_may_be_marked_as_confirmed` |
| FR-010 | 原本の識別 | REQ-015、REQ-012 | 自動テスト | 検証済み | `test_draft_and_verify.py::test_fr010_draft_records_the_source_file_and_hash`<br>`test_draft_and_verify.py::test_fr010_changed_hash_is_an_error`<br>`test_draft_and_verify.py::test_fr010_source_file_is_compared_when_present` |
| FR-011 | 文字の照合 | REQ-012 | 自動テスト | 検証済み | `test_draft_and_verify.py::test_fr011_draft_without_transcription_lacks_the_shape_texts`<br>`test_draft_and_verify.py::test_fr011_removed_string_is_reported_with_its_origin`<br>`test_draft_and_verify.py::test_fr011_occurrences_are_counted`<br>`test_draft_and_verify.py::test_fr011_short_string_is_not_matched_inside_a_longer_one`<br>`test_draft_and_verify.py::test_fr011_attributes_and_comments_do_not_count_as_body`<br>`test_draft_and_verify.py::test_fr011_sheet_name_heading_does_not_stand_in_for_a_cell` |
| FR-012 | 図の検査 | REQ-003、REQ-012 | 自動テスト | 検証済み | `test_draft_and_verify.py::test_fr012_figure_left_as_todo_is_reported`<br>`test_draft_and_verify.py::test_fr012_shape_text_must_be_inside_its_own_figure` |
| FR-013 | 要確認の印 | REQ-021 | 自動テスト | 検証済み | `test_draft_and_verify.py::test_fr013_review_marks_are_listed`<br>`test_draft_and_verify.py::test_fr013_document_with_review_marks_must_not_be_approved` |
| FR-014 | 図を書き起こすエージェント | REQ-003、REQ-006、REQ-014、REQ-021 | 自動テスト（一覧）、レビュー、依頼者環境 | 実装済み | `test_render_and_cli.py::test_fr014_figure_data_lists_shapes_and_arrow_candidates` |
| FR-015 | 確認するエージェント | REQ-017、REQ-012 | レビュー、依頼者環境 | 実装済み | なし |
| FR-016 | 移行後の文書の使い方の案内 | REQ-008、REQ-013 | レビュー、依頼者環境 | 実装済み | なし |
| NFR-001 | 外部と通信しない | REQ-006 | 自動テスト | 検証済み | `test_render_and_cli.py::test_nfr001_tool_does_not_use_network_libraries` |
| NFR-002 | 動作環境 | REQ-019 | 自動テスト（Linux）、依頼者環境（Windows） | 実装済み | `test_render_and_cli.py::test_nfr002_migration_and_verification_run_without_office` |
| NFR-003 | 結果の再現性 | REQ-012 | 自動テスト | 検証済み | `test_extract.py::test_nfr003_same_source_gives_the_same_result` |
