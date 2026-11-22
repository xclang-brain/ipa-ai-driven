"""移行後の文書を、原本から取り出した中間データと照合する。"""

from __future__ import annotations

from pathlib import Path

from docmig.document import STATUSES, body_text, consume_all, normalize, parse
from docmig.xlsx_extract import has_figure, sha256_of


def required_strings(extract: dict) -> list[tuple[str, dict]]:
    """移行後の文書の本文に含まれていなければならない文字列と、その出どころ。"""
    items = []
    for sheet in extract["sheets"]:
        for cell in sheet["cells"]:
            if cell.get("header") == "繰り返し":
                continue  # 繰り返される見出し欄は、代表の1回分だけを求める
            items.append((normalize(cell["text"]), {"sheet": sheet["name"], "cell": cell["ref"]}))
        for shape in sheet["shapes"] + sheet["connectors"]:
            if shape["text"]:
                items.append((normalize(shape["text"]), {"sheet": sheet["name"], "shape": shape["id"]}))
    return items


def _figure_strings(sheet: dict) -> list[tuple[str, dict]]:
    return [
        (normalize(shape["text"]), {"sheet": sheet["name"], "shape": shape["id"]})
        for shape in sheet["shapes"] + sheet["connectors"]
        if shape["text"]
    ]


def verify(markdown: str, extract: dict, source: Path | None = None) -> dict:
    """文書を検査し、結果を返す。errors が空なら合格。"""
    errors: list[dict] = []
    document = parse(markdown)
    attributes = document.attributes

    # 原本の識別（FR-010）
    if attributes.get("source_sha256") != extract["source"]["sha256"]:
        errors.append({"kind": "原本の不一致", "detail": "文書の属性のハッシュ値が、中間データと一致しない"})
    source_checked = False
    if source is not None and Path(source).is_file():
        source_checked = True
        if sha256_of(source) != extract["source"]["sha256"]:
            errors.append({"kind": "原本の不一致", "detail": f"原本のファイル {source} の内容が、中間データと一致しない"})

    # 文字の照合（FR-011）
    missing = consume_all(body_text(document.body), required_strings(extract))
    for item in missing:
        errors.append({"kind": "文字の欠落", **item})

    # 図の検査（FR-012）
    figures = {figure.sheet: figure for figure in document.figures}
    todo = []
    for sheet in extract["sheets"]:
        if not has_figure(sheet):
            continue
        figure = figures.get(sheet["name"])
        if figure is None:
            errors.append({"kind": "図の枠がない", "sheet": sheet["name"]})
            continue
        if figure.is_todo:
            todo.append(figure.id)
            errors.append({"kind": "図が未記入", "sheet": sheet["name"], "figure": figure.id})
            continue
        for item in consume_all(body_text(figure.body), _figure_strings(sheet)):
            errors.append({"kind": "図の文字の欠落", "figure": figure.id, **item})

    # 確認の状態（FR-009）と要確認の印（FR-013）
    status = attributes.get("review_status")
    marks = document.review_marks
    if status not in STATUSES:
        errors.append({"kind": "状態が不正", "detail": f"review_status は {'、'.join(STATUSES)} のいずれかとする（現在の値: {status}）"})
    else:
        content_errors = [e for e in errors if e["kind"] != "状態の矛盾"]
        if status != STATUSES[0] and content_errors:
            errors.append({"kind": "状態の矛盾", "detail": f"検査に不合格の文書が「{status}」になっている"})
        if status == STATUSES[2] and marks:
            errors.append({"kind": "状態の矛盾", "detail": "要確認の印が残っている文書が「承認済み」になっている"})

    required = required_strings(extract)
    return {
        "passed": not errors,
        "review_status": status,
        "source_file_checked": source_checked,
        "counts": {
            "required_strings": len(required),
            "missing_strings": len(missing),
            "figures": sum(1 for s in extract["sheets"] if has_figure(s)),
            "figures_todo": len(todo),
            "review_marks": len(marks),
        },
        "review_marks": marks,
        "errors": errors,
    }


def format_report(report: dict) -> str:
    counts = report["counts"]
    lines = [
        f"判定: {'合格' if report['passed'] else '不合格'}",
        f"確認の状態: {report['review_status']}",
        f"原本の文字列: {counts['required_strings']} 件中、欠落 {counts['missing_strings']} 件",
        f"図: {counts['figures']} 件中、未記入 {counts['figures_todo']} 件",
        f"要確認の印: {counts['review_marks']} 件",
    ]
    if not report["source_file_checked"]:
        lines.append("原本のファイルが見つからないため、原本そのものとの照合は行っていない")
    for mark in report["review_marks"]:
        lines.append(f"  要確認: {mark}")
    for error in report["errors"]:
        where = "、".join(f"{k}={v}" for k, v in error.items() if k not in ("kind", "text", "detail"))
        detail = error.get("text") or error.get("detail") or ""
        lines.append(f"  {error['kind']}: {detail}" + (f"（{where}）" if where else ""))
    return "\n".join(lines)
