"""中間データから、移行後の文書の下書き（Markdown）を作る。"""

from __future__ import annotations

import html

import yaml

from docmig import __version__
from docmig.document import STATUSES, TODO_MARK
from docmig.xlsx_extract import has_figure


def _escape_cell(text: str) -> str:
    return html.escape(text, quote=False).replace("|", "\\|").replace("\n", "<br>")


def _escape_line(text: str) -> str:
    return html.escape(text, quote=False).replace("\n", "<br>")


def _table(block: dict, by_ref: dict) -> list[str]:
    columns = sorted({by_ref[ref]["col"] for row in block["rows"] for ref in row})
    position = {col: i for i, col in enumerate(columns)}

    def line(refs):
        values = [""] * len(columns)
        for ref in refs:
            values[position[by_ref[ref]["col"]]] = _escape_cell(by_ref[ref]["text"])
        return "| " + " | ".join(values) + " |"

    rows = list(block["rows"])
    if block["first_row_is_header"]:
        header, rows = line(rows[0]), rows[1:]
    else:
        header = "| " + " | ".join([""] * len(columns)) + " |"
    return [header, "| " + " | ".join(["---"] * len(columns)) + " |"] + [line(r) for r in rows]


def _block(block: dict, by_ref: dict, sheet_names: str) -> list[str]:
    lines = [f'<!-- src: sheet="{html.escape(sheet_names)}" range="{block["range"]}" -->']
    if block["kind"] == "table":
        lines += _table(block, by_ref)
    else:
        for refs in block["rows"]:
            lines.append("　".join(_escape_line(by_ref[ref]["text"]) for ref in refs))
            lines.append("")
        lines.pop()
    return lines + [""]


def build_draft(extract: dict, doc_id: str, title: str, source_file: str) -> str:
    attributes = {
        "doc_id": doc_id,
        "title": title,
        "source_file": source_file,
        "source_sha256": extract["source"]["sha256"],
        "review_status": STATUSES[0],
        "migrated_with": f"docmig {__version__}",
    }
    out = ["---", yaml.safe_dump(attributes, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    out += [f"# {title}", ""]

    # 複数のシートで繰り返される見出し欄は、ここに1回だけ出力する
    for sheet in extract["sheets"]:
        for block in sheet["blocks"]:
            if not block.get("is_common_header"):
                continue
            names = [sheet["name"]] + [
                other["name"]
                for other in extract["sheets"]
                if other["blocks"] and other["blocks"][0]["common_header_of"] == block["id"]
            ]
            out += ["## 文書の属性", ""]
            out += _block(block, {c["ref"]: c for c in sheet["cells"]}, "、".join(names))

    for sheet in extract["sheets"]:
        by_ref = {c["ref"]: c for c in sheet["cells"]}
        out += [f"## {_escape_line(sheet['name'])}", ""]
        if sheet["state"] != "visible":
            out += ["原本では非表示のシートである。", ""]
        for block in sheet["blocks"]:
            if block.get("is_common_header") or block["common_header_of"]:
                continue
            out += _block(block, by_ref, sheet["name"])
        for picture in sheet["pictures"]:
            out.append(f'<!-- src: sheet="{html.escape(sheet["name"])}" picture="{picture["id"]}" -->')
            target = picture["file"] or ""
            out += [f"![貼り付け画像 {picture['name']}]({target})", ""]
            out += ["【要確認: 貼り付け画像の内容は読み取っていない】", ""]
        for item in sheet["unsupported"]:
            out += [f"【要確認: {item['kind']}（{item['name']}）は取り出しの対象外】", ""]
        if has_figure(sheet):
            out.append(f'<!-- figure:begin id="fig-s{sheet["index"]}" sheet="{html.escape(sheet["name"])}" -->')
            for image in sheet["images"]:
                out.append(f"![原本の図]({image})")
            out += ["", TODO_MARK, "<!-- figure:end -->", ""]
    return "\n".join(out).rstrip() + "\n"
