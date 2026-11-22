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


def _line_ends(sheet: dict) -> list[tuple[str, str, bool]]:
    """原本の線ごとの (始点の図形, 終点の図形, 向きがあるか)。

    端点の図形は、ファイルに接続の記録があればその図形、なければ位置から求めた候補とする。
    """
    lines = []
    for line in sheet["connectors"]:
        start = line.get("attached_start") or (line.get("near_start") or {}).get("shape")
        end = line.get("attached_end") or (line.get("near_end") or {}).get("shape")
        start, end = f"s{start}", f"s{end}"
        if line["arrow_end"] and not line["arrow_start"]:
            lines.append((start, end, True))
        elif line["arrow_start"] and not line["arrow_end"]:
            lines.append((end, start, True))
        else:
            lines.append((start, end, False))
    return lines


def unmatched_arrows(arrows: list[tuple[str, str, bool]], sheet: dict) -> list[tuple[str, str, bool]]:
    """Mermaid の矢印のうち、原本のどの線にも対応しないもの（FR-017）。

    原本の線1本は、矢印1本にだけ対応させる。向きのある線には、同じ向きの矢印だけが対応する。
    向きのない線（矢じりが両端にある、またはない）には、どちら向きの矢印も対応する。
    """
    lines = _line_ends(sheet)
    unmatched = []
    for arrow in arrows:
        start, end, directed = arrow
        for index, (line_start, line_end, line_directed) in enumerate(lines):
            same = (start, end) == (line_start, line_end)
            opposite = (start, end) == (line_end, line_start)
            if (line_directed and directed and same) or (not line_directed and (same or opposite)):
                del lines[index]
                break
        else:
            unmatched.append(arrow)
    return unmatched


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

    figures = {figure.sheet: figure for figure in document.figures}

    # 文字の照合（FR-011）
    # 同じ文字列が複数の図にある場合は、書き起こしが済んだ図の図形から先に数える。
    # 欠落が、未記入の図の図形として報告されるようにするためである。
    pending = {
        sheet["name"]
        for sheet in extract["sheets"]
        if has_figure(sheet) and (sheet["name"] not in figures or figures[sheet["name"]].is_todo)
    }
    required = sorted(required_strings(extract), key=lambda item: "shape" in item[1] and item[1]["sheet"] in pending)
    missing = consume_all(body_text(document.body), required)
    for item in missing:
        errors.append({"kind": "文字の欠落", **item})

    # 図の検査（FR-012）
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
        # 原本にない矢印（FR-017）
        for start, end, directed in unmatched_arrows(figure.arrows, sheet):
            detail = f"{start} から {end} への矢印" if directed else f"{start} と {end} を結ぶ線"
            errors.append({"kind": "原本にない矢印", "detail": detail, "figure": figure.id, "sheet": sheet["name"]})

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
