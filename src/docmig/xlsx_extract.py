"""Excel ファイルから、セル、図形、矢印、貼り付け画像を取り出して中間データにする。

セルは openpyxl で読む。図形は openpyxl では読めないため、ファイルの中の XML を直接読む。
"""

from __future__ import annotations

import datetime
import hashlib
import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.utils.datetime import from_excel

from docmig import __version__
from docmig.geometry import connector_endpoints, nearest_shape

NS = {
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
XDR = "{%s}" % NS["xdr"]
A = "{%s}" % NS["a"]
R = "{%s}" % NS["r"]

LINE_KINDS = ("line", "straightConnector", "bentConnector", "curvedConnector")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- ファイルの中の部品をたどる ------------------------------------------------


def _relationships(archive: zipfile.ZipFile, part: str) -> dict[str, dict]:
    """part から張られている関係（rId -> 参照先）を返す。"""
    rels_path = posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")
    if rels_path not in archive.namelist():
        return {}
    result = {}
    for rel in ET.fromstring(archive.read(rels_path)):
        target = rel.get("Target")
        if rel.get("TargetMode") != "External":
            if target.startswith("/"):
                target = target.lstrip("/")
            else:
                target = posixpath.normpath(posixpath.join(posixpath.dirname(part), target))
        result[rel.get("Id")] = {"target": target, "type": rel.get("Type", "")}
    return result


def _sheet_parts(archive: zipfile.ZipFile) -> list[dict]:
    """シートの名前、表示状態、XML の場所を、ブックの順に返す。"""
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = _relationships(archive, "xl/workbook.xml")
    sheets = []
    for sheet in workbook.find("main:sheets", NS):
        sheets.append(
            {
                "name": sheet.get("name"),
                "state": sheet.get("state", "visible"),
                "part": rels[sheet.get(R + "id")]["target"],
            }
        )
    return sheets


def _drawing_part(archive: zipfile.ZipFile, sheet_part: str) -> str | None:
    for rel in _relationships(archive, sheet_part).values():
        if rel["type"].endswith("/drawing"):
            return rel["target"]
    return None


# --- セル ----------------------------------------------------------------------


# 日本語環境の Excel が持つ日付の表示形式（組み込みの番号）。openpyxl は日付と
# 判定しないため、ここで補う。32 と 33 は時刻。
_JA_DATE_FORMATS = set(range(27, 32)) | set(range(34, 37)) | set(range(50, 59))
_JA_TIME_FORMATS = {32, 33}


def _cell_text(cell, epoch) -> str:
    value = cell.value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        format_id = cell._style.numFmtId
        if format_id in _JA_DATE_FORMATS or format_id in _JA_TIME_FORMATS:
            value = from_excel(value, epoch)
            if format_id in _JA_TIME_FORMATS and isinstance(value, datetime.datetime):
                value = value.time()
    if isinstance(value, datetime.datetime):
        if value.time() == datetime.time(0, 0):
            return value.date().isoformat()
        return value.isoformat(sep=" ")
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _is_filled(cell) -> bool:
    fill = cell.fill
    return bool(fill is not None and fill.fill_type == "solid")


def _extract_cells(worksheet, epoch) -> list[dict]:
    merged = {}
    for merged_range in worksheet.merged_cells.ranges:
        merged[(merged_range.min_row, merged_range.min_col)] = merged_range
    cells = []
    for row in worksheet.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            text = _cell_text(cell, epoch)
            if not text.strip():
                continue
            merged_range = merged.get((cell.row, cell.column))
            cells.append(
                {
                    "ref": cell.coordinate,
                    "row": cell.row,
                    "col": cell.column,
                    "end_col": merged_range.max_col if merged_range else cell.column,
                    "text": text,
                    "merge": merged_range.coord if merged_range else None,
                    "filled": _is_filled(cell),
                }
            )
    return cells


def _build_blocks(sheet_index: int, cells: list[dict]) -> list[dict]:
    """セルを、空行で区切られたまとまり（ブロック）に分ける。"""
    rows: dict[int, list[dict]] = {}
    for cell in cells:
        rows.setdefault(cell["row"], []).append(cell)
    blocks, current, previous_row = [], [], None
    for row_number in sorted(rows):
        if previous_row is not None and row_number - previous_row > 1 and current:
            blocks.append(current)
            current = []
        current.append(sorted(rows[row_number], key=lambda c: c["col"]))
        previous_row = row_number
    if current:
        blocks.append(current)

    result = []
    for number, block_rows in enumerate(blocks, start=1):
        flat = [cell for row in block_rows for cell in row]
        min_col = min(c["col"] for c in flat)
        max_col = max(c["end_col"] for c in flat)
        first, last = block_rows[0][0]["row"], block_rows[-1][0]["row"]
        is_table = len(block_rows) >= 2 and any(len(row) >= 2 for row in block_rows)
        header = (
            is_table
            and all(c["filled"] for c in block_rows[0])
            and not all(c["filled"] for row in block_rows[1:] for c in row)
        )
        result.append(
            {
                "id": f"s{sheet_index}-b{number}",
                "kind": "table" if is_table else "text",
                "range": f"{get_column_letter(min_col)}{first}:{get_column_letter(max_col)}{last}",
                "first_row_is_header": bool(header),
                "rows": [[c["ref"] for c in row] for row in block_rows],
                "common_header_of": None,
                "is_common_header": False,
            }
        )
    return result


def _mark_common_headers(sheets: list[dict]) -> None:
    """複数のシートの先頭で同じ内容が繰り返されるブロックに、印を付ける。

    最初に現れたシートのブロックを代表とし、ほかのシートのブロックには代表の
    ブロックIDを記録する。セルには header として "代表" か "繰り返し" を記録する。
    下書きには代表だけを出力する。
    """
    seen: dict[tuple, dict] = {}
    for sheet in sheets:
        if not sheet["blocks"]:
            continue
        block = sheet["blocks"][0]
        by_ref = {c["ref"]: c for c in sheet["cells"]}
        cells = [by_ref[ref] for row in block["rows"] for ref in row]
        signature = tuple((c["row"], c["col"], c["text"]) for c in cells)
        first = seen.get(signature)
        if first is None:
            seen[signature] = {"block": block, "cells": cells}
            continue
        block["common_header_of"] = first["block"]["id"]
        for cell in cells:
            cell["header"] = "繰り返し"
        first["block"]["is_common_header"] = True
        for cell in first["cells"]:
            cell["header"] = "代表"


# --- 図形 ----------------------------------------------------------------------


def _text_of(element) -> str:
    body = element.find("xdr:txBody", NS)
    if body is None:
        return ""
    paragraphs = []
    for paragraph in body.findall("a:p", NS):
        parts = []
        for node in paragraph:
            if node.tag in (A + "r", A + "fld"):
                parts.append(node.findtext("a:t", default="", namespaces=NS))
            elif node.tag == A + "br":
                parts.append("\n")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs).strip()


def _xfrm(properties):
    """位置と大きさ、反転、回転を読む。記録がなければ None。"""
    xfrm = properties.find("a:xfrm", NS) if properties is not None else None
    if xfrm is None or xfrm.find("a:off", NS) is None or xfrm.find("a:ext", NS) is None:
        return None
    off, ext = xfrm.find("a:off", NS), xfrm.find("a:ext", NS)
    result = {
        "bbox": [int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy"))],
        "flip_h": xfrm.get("flipH") in ("1", "true"),
        "flip_v": xfrm.get("flipV") in ("1", "true"),
        "rot": int(xfrm.get("rot", "0")),
    }
    ch_off, ch_ext = xfrm.find("a:chOff", NS), xfrm.find("a:chExt", NS)
    if ch_off is not None and ch_ext is not None:
        result["child"] = [
            int(ch_off.get("x")),
            int(ch_off.get("y")),
            int(ch_ext.get("cx")),
            int(ch_ext.get("cy")),
        ]
    return result


def _to_sheet(bbox, groups):
    """グループの中の座標を、シート上の座標に直す。groups は内側から外側の順。"""
    x, y, w, h = bbox
    for group in groups:
        gx, gy, gw, gh = group["bbox"]
        cx, cy, cw, ch = group.get("child", [gx, gy, gw, gh])
        scale_x = gw / cw if cw else 1.0
        scale_y = gh / ch if ch else 1.0
        x, y = gx + (x - cx) * scale_x, gy + (y - cy) * scale_y
        w, h = w * scale_x, h * scale_y
    return [round(x), round(y), round(w), round(h)]


def _anchor_range(anchor) -> str | None:
    def cell_of(marker):
        col = int(marker.findtext("xdr:col", namespaces=NS))
        row = int(marker.findtext("xdr:row", namespaces=NS))
        return f"{get_column_letter(col + 1)}{row + 1}"

    start, end = anchor.find("xdr:from", NS), anchor.find("xdr:to", NS)
    if start is None:
        return None
    if end is None:
        return cell_of(start)
    return f"{cell_of(start)}:{cell_of(end)}"


def _dash(properties) -> str | None:
    """線種（破線など）。実線や記録がない場合は None。"""
    dash = properties.find("a:ln/a:prstDash", NS) if properties is not None else None
    value = dash.get("val") if dash is not None else None
    return None if value in (None, "solid") else value


def _line_ends(properties):
    line = properties.find("a:ln", NS) if properties is not None else None
    if line is None:
        return False, False

    def has_arrow(tag):
        end = line.find(tag, NS)
        return end is not None and end.get("type", "none") != "none"

    return has_arrow("a:headEnd"), has_arrow("a:tailEnd")


class _DrawingReader:
    """1つのシートの描画データ（図形、矢印、貼り付け画像）を読む。"""

    def __init__(self, archive, part, media_dir: Path | None):
        self.archive = archive
        self.part = part
        self.rels = _relationships(archive, part)
        self.media_dir = media_dir
        self.shapes: list[dict] = []
        self.connectors: list[dict] = []
        self.pictures: list[dict] = []
        self.groups: list[dict] = []
        self.unsupported: list[dict] = []

    def read(self):
        root = ET.fromstring(self.archive.read(self.part))
        for anchor in root:
            anchor_range = _anchor_range(anchor)
            for element in anchor:
                self._read_element(element, anchor_range, groups=[], group_id=None)
        self._add_hints()
        return self

    def _read_element(self, element, anchor_range, groups, group_id):
        tag = element.tag
        if tag == XDR + "grpSp":
            xfrm = _xfrm(element.find("xdr:grpSpPr", NS))
            name = element.find("xdr:nvGrpSpPr/xdr:cNvPr", NS)
            inner = [xfrm] + groups if xfrm else groups
            if xfrm:
                self.groups.append(
                    {"id": name.get("id"), "name": name.get("name"), "bbox": _to_sheet(xfrm["bbox"], groups)}
                )
            for child in element:
                self._read_element(child, anchor_range, inner, name.get("id"))
        elif tag in (XDR + "sp", XDR + "cxnSp"):
            self._read_shape(element, anchor_range, groups, group_id)
        elif tag == XDR + "pic":
            self._read_picture(element, anchor_range, groups, group_id)
        elif tag in (XDR + "graphicFrame", XDR + "contentPart"):
            name = element.find(".//xdr:cNvPr", NS)
            self.unsupported.append(
                {
                    "id": name.get("id") if name is not None else None,
                    "name": name.get("name") if name is not None else None,
                    "kind": tag.split("}")[1],
                    "anchor": anchor_range,
                }
            )

    def _read_shape(self, element, anchor_range, groups, group_id):
        is_connector = element.tag == XDR + "cxnSp"
        non_visual = element.find("xdr:nvCxnSpPr" if is_connector else "xdr:nvSpPr", NS)
        name = non_visual.find("xdr:cNvPr", NS)
        properties = element.find("xdr:spPr", NS)
        geometry = properties.find("a:prstGeom", NS) if properties is not None else None
        kind = geometry.get("prst") if geometry is not None else "custom"
        xfrm = _xfrm(properties)
        if xfrm is None:
            return
        bbox = _to_sheet(xfrm["bbox"], groups)
        base = {
            "id": name.get("id"),
            "name": name.get("name"),
            "kind": kind,
            "anchor": anchor_range,
            "group": group_id,
            "dash": _dash(properties),
        }
        if is_connector or kind.startswith(LINE_KINDS):
            start, end = connector_endpoints(bbox, xfrm["flip_h"], xfrm["flip_v"], xfrm["rot"])
            arrow_start, arrow_end = _line_ends(properties)
            attached = non_visual.find("xdr:cNvCxnSpPr", NS) if is_connector else None
            start_link = attached.find("a:stCxn", NS) if attached is not None else None
            end_link = attached.find("a:endCxn", NS) if attached is not None else None
            base.update(
                {
                    "start": [round(start[0]), round(start[1])],
                    "end": [round(end[0]), round(end[1])],
                    "arrow_start": arrow_start,
                    "arrow_end": arrow_end,
                    "attached_start": start_link.get("id") if start_link is not None else None,
                    "attached_end": end_link.get("id") if end_link is not None else None,
                    "text": _text_of(element),
                }
            )
            self.connectors.append(base)
        else:
            text_box = non_visual.find("xdr:cNvSpPr", NS)
            base.update(
                {
                    "text": _text_of(element),
                    "textbox": text_box is not None and text_box.get("txBox") in ("1", "true"),
                    "bbox": bbox,
                }
            )
            self.shapes.append(base)

    def _read_picture(self, element, anchor_range, groups, group_id):
        name = element.find("xdr:nvPicPr/xdr:cNvPr", NS)
        xfrm = _xfrm(element.find("xdr:spPr", NS))
        blip = element.find("xdr:blipFill/a:blip", NS)
        target = self.rels.get(blip.get(R + "embed"), {}).get("target") if blip is not None else None
        saved = None
        if target and target in self.archive.namelist() and self.media_dir is not None:
            self.media_dir.mkdir(parents=True, exist_ok=True)
            destination = self.media_dir / posixpath.basename(target)
            destination.write_bytes(self.archive.read(target))
            saved = f"{self.media_dir.name}/{destination.name}"
        self.pictures.append(
            {
                "id": name.get("id"),
                "name": name.get("name"),
                "anchor": anchor_range,
                "group": group_id,
                "bbox": _to_sheet(xfrm["bbox"], groups) if xfrm else None,
                "file": saved,
            }
        )

    def _add_hints(self):
        """矢印の各端点に、最も近い図形を候補として記録する。"""
        for connector in self.connectors:
            connector["near_start"] = nearest_shape(connector["start"], self.shapes)
            connector["near_end"] = nearest_shape(connector["end"], self.shapes)


# --- 全体 ----------------------------------------------------------------------


def extract_xlsx(source: Path, media_dir: Path | None = None) -> dict:
    """Excel ファイルを読み、中間データを返す。

    media_dir を指定すると、貼り付け画像をそのフォルダに保存する。
    """
    source = Path(source)
    workbook = openpyxl.load_workbook(source, data_only=True)
    sheets = []
    with zipfile.ZipFile(source) as archive:
        for index, info in enumerate(_sheet_parts(archive), start=1):
            cells = _extract_cells(workbook[info["name"]], workbook.epoch)
            sheet = {
                "index": index,
                "name": info["name"],
                "state": info["state"],
                "cells": cells,
                "blocks": _build_blocks(index, cells),
                "shapes": [],
                "connectors": [],
                "pictures": [],
                "groups": [],
                "unsupported": [],
                "images": [],
            }
            drawing = _drawing_part(archive, info["part"])
            if drawing:
                reader = _DrawingReader(archive, drawing, media_dir).read()
                sheet.update(
                    shapes=reader.shapes,
                    connectors=reader.connectors,
                    pictures=reader.pictures,
                    groups=reader.groups,
                    unsupported=reader.unsupported,
                )
            sheets.append(sheet)
    _mark_common_headers(sheets)
    return {
        "tool": {"name": "docmig", "version": __version__},
        "source": {"file": source.name, "sha256": sha256_of(source), "kind": "xlsx"},
        "sheets": sheets,
    }


def has_figure(sheet: dict) -> bool:
    """シートに、書き起こしの対象になる図（図形や矢印）があるか。"""
    return bool(sheet["shapes"] or sheet["connectors"])
