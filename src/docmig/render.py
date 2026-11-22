"""図形を含むシートを画像にする。

Excel ファイルを PDF にし、PDF のページを画像にする。PDF にする方法は2つある。
- excel: Excel を操作する（Windows。pywin32 が必要）。シートごとに PDF を作る。
- libreoffice: LibreOffice を使う。ブック全体が1つの PDF になるため、
  ページの文字とシートの文字を突き合わせて、ページがどのシートのものかを決める。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from docmig.document import normalize
from docmig.xlsx_extract import has_figure

DPI = 150


def choose_backend() -> str:
    if sys.platform == "win32":
        try:
            import win32com.client  # noqa: F401

            return "excel"
        except ImportError:
            pass
    if shutil.which("soffice") or shutil.which("libreoffice"):
        return "libreoffice"
    raise RuntimeError("描画に使える Excel（pywin32）も LibreOffice も見つからない")


def _save_pages(pdf_path: Path, page_numbers: list[int], figures_dir: Path, sheet_index: int) -> list[str]:
    import pypdfium2

    pdf = pypdfium2.PdfDocument(str(pdf_path))
    saved = []
    try:
        for order, page_number in enumerate(page_numbers, start=1):
            image = pdf[page_number].render(scale=DPI / 72).to_pil()
            name = f"sheet-{sheet_index:02d}-p{order}.png"
            image.save(figures_dir / name)
            saved.append(f"{figures_dir.name}/{name}")
    finally:
        pdf.close()
    return saved


def assign_pages(page_texts: list[str], sheet_texts: list[set[str]]) -> list[int]:
    """PDF の各ページが、どのシートのものかを決める。

    ページはシートの順に並ぶ。その順序を保ったまま、ページの文字とシートの文字が
    最もよく合う割り当てを求める。返すのは、ページごとのシートの位置。
    """
    scores = [
        [sum(len(text) for text in texts if text in page) for texts in sheet_texts]
        for page in page_texts
    ]
    pages, sheets = len(page_texts), len(sheet_texts)
    if not pages or not sheets:
        return []
    best = [[0.0] * sheets for _ in range(pages)]
    back = [[0] * sheets for _ in range(pages)]
    for p in range(pages):
        for s in range(sheets):
            if p == 0:
                previous, origin = 0.0, s
            else:
                origin = max(range(s + 1), key=lambda k: best[p - 1][k])
                previous = best[p - 1][origin]
            best[p][s] = previous + scores[p][s]
            back[p][s] = origin
    assignment = [0] * pages
    current = max(range(sheets), key=lambda k: best[pages - 1][k])
    for p in range(pages - 1, -1, -1):
        assignment[p] = current
        current = back[p][current]
    return assignment


def _render_libreoffice(source: Path, extract: dict, figures_dir: Path) -> None:
    import pypdfium2

    command = shutil.which("soffice") or shutil.which("libreoffice")
    with tempfile.TemporaryDirectory() as work:
        copy = Path(work) / ("source" + source.suffix)
        shutil.copyfile(source, copy)
        subprocess.run(
            [
                command,
                # 実行ごとに別の設定フォルダを使う。同時に複数を実行しても衝突しないようにする
                f"-env:UserInstallation={(Path(work) / 'profile').as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                work,
                str(copy),
            ],
            check=True,
            capture_output=True,
            timeout=600,
        )
        pdf_path = Path(work) / "source.pdf"
        pdf = pypdfium2.PdfDocument(str(pdf_path))
        try:
            page_texts = [normalize(page.get_textpage().get_text_range()) for page in pdf]
        finally:
            pdf.close()
        visible = [s for s in extract["sheets"] if s["state"] == "visible"]
        sheet_texts = []
        for sheet in visible:
            texts = [c["text"] for c in sheet["cells"] if not c.get("header")]
            texts += [s["text"] for s in sheet["shapes"] + sheet["connectors"]]
            sheet_texts.append({normalize(t) for t in texts if len(normalize(t)) >= 2})
        assignment = assign_pages(page_texts, sheet_texts)
        for position, sheet in enumerate(visible):
            if has_figure(sheet):
                pages = [p for p, s in enumerate(assignment) if s == position]
                sheet["images"] = _save_pages(pdf_path, pages, figures_dir, sheet["index"])


def _render_excel(source: Path, extract: dict, figures_dir: Path) -> None:
    """Excel を操作して、シートごとに PDF を作る。原本は読み取り専用で開き、保存しない。"""
    import win32com.client

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        workbook = excel.Workbooks.Open(str(source.resolve()), ReadOnly=True, UpdateLinks=0)
        try:
            with tempfile.TemporaryDirectory() as work:
                for sheet in extract["sheets"]:
                    if sheet["state"] != "visible" or not has_figure(sheet):
                        continue
                    worksheet = workbook.Worksheets(sheet["name"])
                    # 図が複数のページに分かれないよう、1ページに収める
                    worksheet.PageSetup.Zoom = False
                    worksheet.PageSetup.FitToPagesWide = 1
                    worksheet.PageSetup.FitToPagesTall = 1
                    pdf_path = Path(work) / f"sheet-{sheet['index']:02d}.pdf"
                    worksheet.ExportAsFixedFormat(0, str(pdf_path))  # 0 = PDF
                    import pypdfium2

                    pdf = pypdfium2.PdfDocument(str(pdf_path))
                    count = len(pdf)
                    pdf.close()
                    sheet["images"] = _save_pages(pdf_path, list(range(count)), figures_dir, sheet["index"])
        finally:
            workbook.Close(SaveChanges=False)
    finally:
        excel.Quit()


def render(source: Path, extract: dict, figures_dir: Path, backend: str = "auto") -> str:
    """図形を含むシートを画像にし、中間データの各シートの images に記録する。"""
    if backend == "auto":
        backend = choose_backend()
    figures_dir.mkdir(parents=True, exist_ok=True)
    for old in figures_dir.glob("sheet-*.png"):
        old.unlink()  # 前回の描画の残りを消す
    if backend == "excel":
        _render_excel(Path(source), extract, figures_dir)
    elif backend == "libreoffice":
        _render_libreoffice(Path(source), extract, figures_dir)
    else:
        raise ValueError(f"描画の方法が不正: {backend}")
    return backend
