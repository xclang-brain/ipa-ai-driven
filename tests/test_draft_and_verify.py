"""下書き（FR-007〜FR-010）と検査（FR-009〜FR-013、FR-017）のテスト。"""

import re

from docmig.document import consume_all, mermaid_arrows, parse
from docmig.verify import verify

from conftest import DIAGRAM_SHEET, ROOT, draft_of, sheet_of


def kinds(report):
    return [e["kind"] for e in report["errors"]]


# --- 下書き --------------------------------------------------------------------


def test_fr007_sections_follow_the_sheet_order(extract):
    headings = re.findall(r"^## (.+)$", draft_of(extract), re.M)
    assert headings == ["文書の属性", "表紙", "変更履歴", "目次", DIAGRAM_SHEET, "2. 顧客情報管理(11AB)"]


def test_fr007_change_history_becomes_a_table(extract):
    assert "| 1 | 1.0版 | 2018-08-24 | 新規 | - | (新規作成) | TIS |" in draft_of(extract)


def test_fr007_repeated_header_block_appears_once(extract):
    draft = draft_of(extract)
    assert draft.count("サンプルサブシステム |") == 1
    assert draft.count("| PJ名 |") == 1


def test_fr007_sheets_with_shapes_get_a_figure_frame_marked_as_todo(extract):
    document = parse(draft_of(extract))
    assert {f.sheet for f in document.figures} == {s["name"] for s in extract["sheets"]}
    assert all(f.is_todo for f in document.figures)


def test_fr008_every_block_is_preceded_by_its_origin(extract):
    lines = draft_of(extract).splitlines()
    tables = [i for i, line in enumerate(lines) if line.startswith("| ") and not lines[i - 1].startswith("|")]
    assert tables
    for i in tables:
        assert re.match(r'<!-- src: sheet="[^"]+" range="[A-Z]+\d+:[A-Z]+\d+" -->', lines[i - 1])
    assert '<!-- src: sheet="変更履歴" range="A7:AI8" -->' in lines


def test_fr009_draft_starts_as_unconfirmed(extract):
    assert parse(draft_of(extract)).attributes["review_status"] == "未確認"


def test_fr010_draft_records_the_source_file_and_hash(extract):
    attributes = parse(draft_of(extract)).attributes
    assert attributes["source_file"] == "samples/nablarch/画面遷移図_サンプル.xlsx"
    assert attributes["source_sha256"] == extract["source"]["sha256"]


# --- 検査 ----------------------------------------------------------------------


def test_complete_document_passes(complete_document, extract):
    report = verify(complete_document, extract)
    assert report["passed"], report["errors"]


def test_fr009_failed_document_must_not_be_marked_as_confirmed(extract):
    draft = draft_of(extract).replace("review_status: 未確認", "review_status: AI確認済み")
    assert "状態の矛盾" in kinds(verify(draft, extract))


def test_fr009_unknown_status_is_an_error(complete_document, extract):
    document = complete_document.replace("review_status: 未確認", "review_status: 確認中")
    assert kinds(verify(document, extract)) == ["状態が不正"]


def test_fr009_passing_document_may_be_marked_as_confirmed(complete_document, extract):
    document = complete_document.replace("review_status: 未確認", "review_status: AI確認済み")
    assert verify(document, extract)["passed"]


def test_fr010_changed_hash_is_an_error(complete_document, extract):
    document = complete_document.replace(extract["source"]["sha256"], "0" * 64)
    assert kinds(verify(document, extract)) == ["原本の不一致"]


def test_fr010_source_file_is_compared_when_present(complete_document, extract, tmp_path):
    other = tmp_path / "other.xlsx"
    other.write_bytes(b"not the original")
    assert "原本の不一致" in kinds(verify(complete_document, extract, source=other))


def test_fr011_draft_without_transcription_lacks_the_shape_texts(extract):
    report = verify(draft_of(extract), extract)
    missing = [e for e in report["errors"] if e["kind"] == "文字の欠落"]
    assert any("【W11AA0201】" in e["text"] and e["sheet"] == DIAGRAM_SHEET for e in missing)
    assert all("shape" in e for e in missing)


def test_fr011_removed_string_is_reported_with_its_origin(complete_document, extract):
    document = complete_document.replace("(新規作成)", "")
    errors = verify(document, extract)["errors"]
    assert errors == [{"kind": "文字の欠落", "text": "(新規作成)", "sheet": "変更履歴", "cell": "Q8"}]


def test_fr011_occurrences_are_counted():
    origin = [("戻る", {"n": i}) for i in range(3)]
    assert consume_all("戻る・戻る", origin) == [{"text": "戻る", "n": 2}]


def test_fr011_short_string_is_not_matched_inside_a_longer_one():
    needles = [("確認", {"shape": "1"}), ("企業情報登録確認", {"shape": "2"})]
    assert consume_all("企業情報登録確認", needles) == [{"text": "確認", "shape": "1"}]
    assert consume_all("企業情報登録確認／確認", needles) == []


def test_fr011_attributes_and_comments_do_not_count_as_body(complete_document, extract):
    # 「画面遷移図」は属性の title と文書名の見出しにも含まれるが、本文から消せば欠落になる
    document = complete_document.replace("| 画面遷移図 |", "|  |")
    assert [e["text"] for e in verify(document, extract)["errors"]] == ["画面遷移図"]


def test_fr012_figure_left_as_todo_is_reported(complete_document, extract):
    draft = draft_of(extract)
    report = verify(draft, extract)
    assert kinds(report).count("図が未記入") == 5
    assert report["counts"]["figures_todo"] == 5


def test_fr012_shape_text_must_be_inside_its_own_figure(complete_document, extract):
    text = "企業情報登録確認 【W11AA0202】"
    diagram = sheet_of(extract, DIAGRAM_SHEET)
    assert any(s["text"].replace("\n", " ") == text for s in diagram["shapes"])
    marker = f'<!-- figure:begin id="fig-s{diagram["index"]}"'
    head, tail = complete_document.split(marker, 1)
    figure, rest = tail.split("<!-- figure:end -->", 1)
    moved = head + marker + figure.replace(text, "", 1) + "<!-- figure:end -->" + rest + f"\n{text}\n"
    report = verify(moved, extract)
    assert kinds(report) == ["図の文字の欠落"]
    assert report["errors"][0]["figure"] == "fig-s4"


def test_fr013_review_marks_are_listed(complete_document, extract):
    document = complete_document + "\n【要確認: 矢印の行き先が読み取れない】\n"
    report = verify(document, extract)
    assert report["passed"]
    assert report["review_marks"] == ["矢印の行き先が読み取れない"]


def test_fr013_document_with_review_marks_must_not_be_approved(complete_document, extract):
    document = complete_document.replace("review_status: 未確認", "review_status: 承認済み")
    assert verify(document, extract)["passed"]
    marked = document + "\n【要確認: 矢印の行き先が読み取れない】\n"
    assert kinds(verify(marked, extract)) == ["状態の矛盾"]


def test_fr011_sheet_name_heading_does_not_stand_in_for_a_cell(complete_document, extract):
    # シート名の見出しは道具が付けたもので、同じ文字のセル（B5）の代わりにはならない
    document = complete_document.replace("\n1. 企業情報管理(11AA)\n\n<!-- figure", "\n\n<!-- figure", 1)
    assert document != complete_document
    errors = verify(document, extract)["errors"]
    assert [(e["kind"], e.get("cell")) for e in errors] == [("文字の欠落", "B5")]


def test_fr011_missing_string_is_attributed_to_the_figure_left_as_todo(extract):
    # 「戻る」「確定」「SAMPLE」などは、2つの図の両方にある。片方の図だけを書き起こした場合に、
    # 書き起こした図の図形が欠落として報告されると、どの図を直せばよいかを誤解する。
    done = sheet_of(extract, "2. 顧客情報管理(11AB)")
    texts = [s["text"].replace("\n", " ") for s in done["shapes"] + done["connectors"] if s["text"]]
    marker = f'<!-- figure:begin id="fig-s{done["index"]}"'
    head, tail = draft_of(extract).split(marker, 1)
    document = head + marker + tail.replace("<!-- transcription:todo -->", "\n\n".join(texts), 1)
    report = verify(document, extract)
    missing = [e for e in report["errors"] if e["kind"] == "文字の欠落"]
    assert missing
    assert [e for e in missing if e["sheet"] == done["name"]] == []
    assert "図の文字の欠落" not in kinds(report)


# --- 原本にない矢印（FR-017） --------------------------------------------------

SUBWINDOW_SHEET = "2. 顧客情報管理(11AB)"

# サンプル文書のシート「2. 顧客情報管理(11AB)」にある、凡例を除く6本の線
ORIGINAL_ARROWS = """\
    s26761 -->|"顧客情報登録"| s26684
    s26684 -->|"確認"| s26690
    s26690 -->|"戻る"| s26684
    s26690 -->|"確定"| s26693
    s26684 -->|"住所検索"| s26715
    s26715 -->|"閉じる、選択"| s26684
"""


def with_mermaid(document, extract, arrows):
    """シート「2. 顧客情報管理(11AB)」の図の枠に、Mermaid の図を足す。"""
    sheet = sheet_of(extract, SUBWINDOW_SHEET)
    marker = f'<!-- figure:begin id="fig-s{sheet["index"]}"'
    head, tail = document.split(marker, 1)
    figure, rest = tail.split("<!-- figure:end -->", 1)
    mermaid = "```mermaid\nflowchart LR\n" + arrows + "```\n"
    return head + marker + figure + mermaid + "<!-- figure:end -->" + rest


def arrow_errors(report):
    return [e["detail"] for e in report["errors"] if e["kind"] == "原本にない矢印"]


def test_fr017_arrows_that_match_the_original_lines_pass(complete_document, extract):
    report = verify(with_mermaid(complete_document, extract, ORIGINAL_ARROWS), extract)
    assert report["passed"]


def test_fr017_arrow_without_an_original_line_is_reported(complete_document, extract):
    # Copilot CLI（gpt-4.1）の試行で、実際に書かれた2本
    added = ORIGINAL_ARROWS + '    s26693 -- "一覧照会へ" --> s26694["一覧照会へ"]\n    s26698 -- "" --> s26761\n'
    report = verify(with_mermaid(complete_document, extract, added), extract)
    assert not report["passed"]
    assert arrow_errors(report) == ["s26693 から s26694 への矢印", "s26698 から s26761 への矢印"]
    assert all(e["figure"] == "fig-s5" for e in report["errors"])


def test_fr017_reversed_arrow_is_reported(complete_document, extract):
    reversed_arrow = ORIGINAL_ARROWS.replace('s26690 -->|"確定"| s26693', 's26693 -->|"確定"| s26690')
    report = verify(with_mermaid(complete_document, extract, reversed_arrow), extract)
    assert arrow_errors(report) == ["s26693 から s26690 への矢印"]


def test_fr017_second_arrow_for_the_same_line_is_reported(complete_document, extract):
    doubled = ORIGINAL_ARROWS + '    s26690 -->|"確定"| s26693\n'
    report = verify(with_mermaid(complete_document, extract, doubled), extract)
    assert arrow_errors(report) == ["s26690 から s26693 への矢印"]


def test_fr017_line_without_arrowheads_matches_either_direction(complete_document, extract):
    line = next(c for c in sheet_of(extract, SUBWINDOW_SHEET)["connectors"] if c["id"] == "26755")
    line["arrow_end"] = False
    reversed_arrow = ORIGINAL_ARROWS.replace('s26690 -->|"確定"| s26693', "s26693 --- s26690")
    report = verify(with_mermaid(complete_document, extract, reversed_arrow), extract)
    assert report["passed"]


def test_fr017_arrow_notations_are_read():
    mermaid = """\
    s1["画面A<br>【ID】"] -->|"次へ"| s2
    s2 -- "戻る" --> s1
    s2 -.-> s3 ==> s4
    s5 & s6 --> s7
    s8 <--> s9
    s10 --- s11
    subgraph s20["A --> B という見出し"]
    end
"""
    assert mermaid_arrows(mermaid) == [
        ("s1", "s2", True),
        ("s2", "s1", True),
        ("s2", "s3", True),
        ("s3", "s4", True),
        ("s5", "s7", True),
        ("s6", "s7", True),
        ("s8", "s9", False),
        ("s10", "s11", False),
    ]


def test_fr017_sample_transcription_passes():
    folder = ROOT / "migrated" / "screen-transition"
    import json

    extract = json.loads((folder / "extract.json").read_text(encoding="utf-8"))
    report = verify((folder / "document.md").read_text(encoding="utf-8"), extract)
    assert arrow_errors(report) == []
    assert report["passed"]

