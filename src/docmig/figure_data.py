"""図を書き起こすときに使う、図形と矢印の一覧を作る。

中間データ（extract.json）は大きいため、1つの図に必要な分だけを読みやすい形で出す。
"""

from __future__ import annotations

from docmig.document import parse
from docmig.geometry import EMU_PER_PT
from docmig.xlsx_extract import has_figure


def figure_id(sheet: dict) -> str:
    return f"fig-s{sheet['index']}"


def list_figures(extract: dict, markdown: str) -> list[dict]:
    state = {figure.id: figure.is_todo for figure in parse(markdown).figures}
    return [
        {
            "id": figure_id(sheet),
            "sheet": sheet["name"],
            "images": sheet["images"],
            "shapes": len(sheet["shapes"]),
            "connectors": len(sheet["connectors"]),
            "todo": state.get(figure_id(sheet), True),
        }
        for sheet in extract["sheets"]
        if has_figure(sheet)
    ]


def _one_line(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def _points(values) -> str:
    return ", ".join(str(round(v / EMU_PER_PT)) for v in values)


def describe_figure(extract: dict, wanted: str) -> str:
    """図の図形と矢印を Markdown の表にして返す。位置の単位は pt、原点はシートの左上。"""
    sheet = next((s for s in extract["sheets"] if has_figure(s) and figure_id(s) == wanted), None)
    if sheet is None:
        raise KeyError(wanted)
    names = {s["id"]: (s["text"] or s["kind"]) for s in sheet["shapes"]}

    def end(connector, which):
        recorded = connector[f"attached_{which}"]
        near = connector[f"near_{which}"]
        if recorded:
            return f"s{recorded}（ファイルに接続の記録あり）"
        if near:
            return f"s{near['shape']}（{near['distance_pt']} pt）"
        return "なし"

    lines = [
        f"# {wanted}　シート「{sheet['name']}」",
        "",
        f"画像: {'、'.join(sheet['images']) or 'なし'}",
        "",
        "## 図形",
        "",
        "位置は「左, 上, 幅, 高さ」。文字枠の列が「はい」の図形は、線や図形に添えられたラベルであることが多い。",
        "",
        "| 節点の名前 | 種類 | 文字 | 文字枠 | グループ | 位置 |",
        "|---|---|---|---|---|---|",
    ]
    for shape in sheet["shapes"]:
        lines.append(
            f"| s{shape['id']} | {shape['kind']} | {_one_line(shape['text'])} | "
            f"{'はい' if shape['textbox'] else ''} | {shape['group'] or ''} | {_points(shape['bbox'])} |"
        )
    lines += [
        "",
        "## 線と矢印",
        "",
        "始点側と終点側の列は、端点に最も近い図形（候補）と、端点からその図形の辺までの距離。",
        "候補は位置から機械的に求めたもので、正しいとは限らない。画像で確かめること。",
        "",
        "| 線 | 種類 | 始点側 | 終点側 | 矢じり | 始点 | 終点 |",
        "|---|---|---|---|---|---|---|",
    ]
    for connector in sheet["connectors"]:
        heads = {
            (False, False): "なし",
            (False, True): "終点",
            (True, False): "始点",
            (True, True): "両方",
        }[(connector["arrow_start"], connector["arrow_end"])]
        lines.append(
            f"| c{connector['id']} | {connector['kind']} | {end(connector, 'start')} | {end(connector, 'end')} | "
            f"{heads} | {_points(connector['start'])} | {_points(connector['end'])} |"
        )
    lines += ["", "## 節点の名前と文字の対応", ""]
    lines += [f"- s{shape_id}: {_one_line(text)}" for shape_id, text in names.items()]
    return "\n".join(lines) + "\n"
