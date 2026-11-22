import copy
import shutil
from pathlib import Path

import pytest

from docmig.document import TODO_MARK
from docmig.draft import build_draft
from docmig.xlsx_extract import extract_xlsx, has_figure

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "samples" / "nablarch" / "画面遷移図_サンプル.xlsx"
SAMPLE_WITH_PICTURES = ROOT / "samples" / "nablarch" / "システム機能設計書(画面)_照会機能_サンプル.xlsx"
DIAGRAM_SHEET = "1. 企業情報管理(11AA)"

needs_libreoffice = pytest.mark.skipif(
    not (shutil.which("soffice") or shutil.which("libreoffice")), reason="LibreOffice がない"
)


@pytest.fixture(scope="session")
def _extract_once():
    return extract_xlsx(SAMPLE)


@pytest.fixture
def extract(_extract_once):
    return copy.deepcopy(_extract_once)


def sheet_of(extract, name):
    return next(s for s in extract["sheets"] if s["name"] == name)


def draft_of(extract):
    return build_draft(extract, "screen-transition", "画面遷移図_サンプル", SAMPLE.relative_to(ROOT).as_posix())


def fill_figures(markdown, extract):
    """図の枠の未記入の印を、その図の図形の文字を並べた文章に置き換える。

    図の書き起こしが済んだ状態を、テストの中で作るために使う。
    """
    for sheet in extract["sheets"]:
        if not has_figure(sheet):
            continue
        texts = [s["text"].replace("\n", " ") for s in sheet["shapes"] + sheet["connectors"] if s["text"]]
        body = "\n\n".join(texts) or "図形に文字はない。"
        marker = f'<!-- figure:begin id="fig-s{sheet["index"]}"'
        head, tail = markdown.split(marker, 1)
        markdown = head + marker + tail.replace(TODO_MARK, body, 1)
    return markdown


@pytest.fixture
def complete_document(extract):
    """検査に合格する文書。"""
    return fill_figures(draft_of(extract), extract)
