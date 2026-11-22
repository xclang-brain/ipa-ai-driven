"""描画（FR-006）、コマンドライン、外部通信と動作環境（NFR-001、NFR-002）のテスト。"""

import json
import re
from pathlib import Path

from docmig.cli import main
from docmig.render import assign_pages

from conftest import DIAGRAM_SHEET, ROOT, SAMPLE, needs_libreoffice, sheet_of


def test_fr006_pages_are_assigned_to_sheets_in_order():
    pages = ["共通の見出し表紙", "共通の見出し変更履歴", "共通の見出し遷移図A", "共通の見出し凡例B", "共通の見出し遷移図C"]
    sheets = [{"表紙"}, {"変更履歴"}, {"遷移図A", "凡例B"}, {"遷移図C"}]
    assert assign_pages(pages, sheets) == [0, 1, 2, 2, 3]


@needs_libreoffice
def test_fr006_sheets_with_shapes_are_rendered_and_recorded(tmp_path):
    out = tmp_path / "doc"
    assert main(["migrate", str(SAMPLE), "--out", str(out), "--render", "libreoffice"]) == 0
    extract = json.loads((out / "extract.json").read_text(encoding="utf-8"))
    for sheet in extract["sheets"]:
        assert sheet["images"], sheet["name"]
        for image in sheet["images"]:
            assert (out / image).stat().st_size > 1000
    assert sheet_of(extract, DIAGRAM_SHEET)["images"][0] == "figures/sheet-04-p1.png"
    assert "![原本の図](figures/sheet-04-p1.png)" in (out / "document.md").read_text(encoding="utf-8")


def test_nfr002_migration_and_verification_run_without_office(tmp_path, capsys):
    out = tmp_path / "doc"
    assert main(["migrate", str(SAMPLE), "--out", str(out), "--render", "none"]) == 0
    assert main(["verify", str(out)]) == 1  # 図が未記入のため不合格
    printed = capsys.readouterr().out
    assert "判定: 不合格" in printed and "図: 5 件中、未記入 5 件" in printed
    report = json.loads((out / "verify-report.json").read_text(encoding="utf-8"))
    assert report["counts"]["figures_todo"] == 5


def test_existing_document_is_not_overwritten_without_force(tmp_path):
    out = tmp_path / "doc"
    assert main(["migrate", str(SAMPLE), "--out", str(out), "--render", "none"]) == 0
    document = out / "document.md"
    document.write_text(document.read_text(encoding="utf-8") + "\n書き起こした内容\n", encoding="utf-8")
    assert main(["migrate", str(SAMPLE), "--out", str(out), "--render", "none"]) == 2
    assert "書き起こした内容" in document.read_text(encoding="utf-8")
    # 文書を残して、中間データだけ作り直す
    (out / "extract.json").unlink()
    assert main(["migrate", str(SAMPLE), "--out", str(out), "--render", "none", "--keep-document"]) == 0
    assert (out / "extract.json").is_file()
    assert "書き起こした内容" in document.read_text(encoding="utf-8")


def test_nfr001_tool_does_not_use_network_libraries():
    forbidden = re.compile(r"^\s*(?:import|from)\s+(socket|urllib|http|requests|httpx|aiohttp|ftplib|smtplib)\b", re.M)
    for path in (ROOT / "src" / "docmig").glob("*.py"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), path.name


def test_fr014_figure_data_lists_shapes_and_arrow_candidates(tmp_path, capsys):
    out = tmp_path / "doc"
    assert main(["migrate", str(SAMPLE), "--out", str(out), "--render", "none"]) == 0
    capsys.readouterr()
    assert main(["figure", str(out)]) == 0
    listing = capsys.readouterr().out.splitlines()
    assert len(listing) == 5 and listing[3].startswith("fig-s4\t未記入\t図形 57、線 20\t" + DIAGRAM_SHEET)
    assert main(["figure", str(out), "fig-s4"]) == 0
    data = capsys.readouterr().out
    # 画面を表す四角が、節点の名前（s + 図形ID）と原本の文字つきで載る
    assert re.search(r"^\| s\d+ \| rect \| 企業情報登録<br>【W11AA0201】 \|", data, re.M)
    # ファイルに接続の記録がある端点と、位置から求めた候補の両方が載る
    assert "（ファイルに接続の記録あり）" in data and re.search(r"s\d+（0\.0 pt）", data)
    assert main(["figure", str(out), "fig-s9"]) == 2
