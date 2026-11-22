"""取り出し（FR-001〜FR-005）と結果の再現性（NFR-003）のテスト。

テスト名には、確かめる要件のIDを含める。
"""

from docmig.geometry import EMU_PER_PT, connector_endpoints, nearest_shape
from docmig.xlsx_extract import extract_xlsx

from conftest import DIAGRAM_SHEET, SAMPLE, SAMPLE_WITH_PICTURES, draft_of, sheet_of


def cell_of(sheet, ref):
    return next(c for c in sheet["cells"] if c["ref"] == ref)


def test_fr001_cells_carry_sheet_name_and_reference(extract):
    history = sheet_of(extract, "変更履歴")
    assert cell_of(history, "A7")["text"] == "No."
    assert {"B8": "1.0版", "G8": "新規"}.items() <= {c["ref"]: c["text"] for c in history["cells"]}.items()


def test_fr001_formula_cell_gives_the_stored_result(extract):
    # 表紙の I25 は数式で、保存されている計算結果は日付である
    assert cell_of(sheet_of(extract, "表紙"), "I25")["text"] == "2018-08-24"


def test_fr001_japanese_date_formats_become_iso_dates(extract):
    # 変更履歴の変更日は、日本語環境の組み込みの日付形式で保存されている
    assert cell_of(sheet_of(extract, "変更履歴"), "D8")["text"] == "2018-08-24"
    assert not any(c["text"] == "43336" for s in extract["sheets"] for c in s["cells"])


def test_fr002_merged_cell_is_recorded_once_with_its_range(extract):
    history = sheet_of(extract, "変更履歴")
    assert cell_of(history, "J7")["merge"] == "J7:P7"
    assert not any(c["ref"] in ("K7", "L7", "P7") for c in history["cells"])


def test_fr003_all_shape_texts_are_extracted(extract):
    diagram = sheet_of(extract, DIAGRAM_SHEET)
    with_text = [s for s in diagram["shapes"] if s["text"]]
    assert len(with_text) == 46
    assert any("【W11AA0201】" in s["text"] for s in with_text)
    assert all(s["id"] and s["kind"] and len(s["bbox"]) == 4 for s in diagram["shapes"])


def test_fr003_shapes_in_a_group_are_placed_on_the_sheet(extract):
    for sheet in extract["sheets"]:
        groups = {g["id"]: g["bbox"] for g in sheet["groups"]}
        for shape in sheet["shapes"]:
            if shape["group"] not in groups:
                continue
            gx, gy, gw, gh = groups[shape["group"]]
            x, y, w, h = shape["bbox"]
            tolerance = EMU_PER_PT  # 丸めの誤差
            assert gx - tolerance <= x and x + w <= gx + gw + tolerance
            assert gy - tolerance <= y and y + h <= gy + gh + tolerance
    assert any(sheet["groups"] for sheet in extract["sheets"])


def test_fr004_lines_and_connectors_are_extracted(extract):
    diagram = sheet_of(extract, DIAGRAM_SHEET)
    # コネクタ19本と、線として描かれた矢印1本
    assert len(diagram["connectors"]) == 20
    assert sum(1 for c in diagram["connectors"] if c["kind"] != "line") == 19


def test_fr004_rotation_by_180_degrees_swaps_the_endpoints():
    bbox = (100, 200, 50, 0)
    start, end = connector_endpoints(bbox, False, False, 0)
    rotated_start, rotated_end = connector_endpoints(bbox, False, False, 180 * 60000)
    assert (round(rotated_start[0]), round(rotated_start[1])) == end
    assert (round(rotated_end[0]), round(rotated_end[1])) == start


def test_fr004_flip_moves_the_start_to_the_other_corner():
    start, end = connector_endpoints((0, 0, 10, 20), True, False, 0)
    assert start == (10, 0) and end == (0, 20)


def test_fr004_endpoint_on_a_border_gets_that_shape_as_candidate():
    pt = EMU_PER_PT
    shapes = [
        {"id": "outer", "bbox": [0, 0, 500 * pt, 500 * pt]},
        {"id": "inner", "bbox": [100 * pt, 100 * pt, 50 * pt, 50 * pt]},
    ]
    assert nearest_shape((150 * pt, 125 * pt), shapes) == {"shape": "inner", "distance_pt": 0.0}


def test_fr004_endpoint_far_from_any_shape_gets_no_candidate():
    pt = EMU_PER_PT
    shapes = [{"id": "a", "bbox": [0, 0, 10 * pt, 10 * pt]}]
    assert nearest_shape((100 * pt, 100 * pt), shapes) is None


def test_fr004_candidates_agree_with_connections_recorded_in_the_file(extract):
    checked = 0
    for sheet in extract["sheets"]:
        for connector in sheet["connectors"]:
            for end in ("start", "end"):
                recorded = connector[f"attached_{end}"]
                if recorded:
                    assert connector[f"near_{end}"]["shape"] == recorded
                    checked += 1
    assert checked >= 8


def test_fr005_pasted_pictures_are_saved_as_files(tmp_path):
    result = extract_xlsx(SAMPLE_WITH_PICTURES, media_dir=tmp_path / "media")
    pictures = [p for sheet in result["sheets"] for p in sheet["pictures"]]
    assert pictures
    for picture in pictures:
        assert picture["anchor"]
        assert (tmp_path / picture["file"]).is_file()


def test_nfr003_same_source_gives_the_same_result(extract):
    again = extract_xlsx(SAMPLE)
    assert again == extract
    assert draft_of(again) == draft_of(extract)
