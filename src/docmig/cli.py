"""コマンドライン。

    docmig migrate 原本.xlsx --out migrated/文書ID
    docmig figure migrated/文書ID            図の一覧
    docmig figure migrated/文書ID fig-s4     図を書き起こすための図形と矢印の一覧
    docmig verify migrated/文書ID
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from docmig.draft import build_draft
from docmig.figure_data import describe_figure, list_figures
from docmig.render import render
from docmig.verify import format_report, verify
from docmig.xlsx_extract import extract_xlsx

DOCUMENT = "document.md"
EXTRACT = "extract.json"
REPORT = "verify-report.json"


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def migrate(args) -> int:
    source, out = Path(args.source), Path(args.out)
    if source.suffix.lower() != ".xlsx":
        print(f"対応していない形式: {source.suffix}（現在は .xlsx のみ）", file=sys.stderr)
        return 2
    document = out / DOCUMENT
    if document.exists() and not args.force:
        print(f"{document} が既にある。上書きすると書き起こしや修正が失われる。上書きするには --force を付ける", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    extract = extract_xlsx(source, media_dir=out / "media")
    if args.render != "none":
        backend = render(source, extract, out / "figures", args.render)
        print(f"描画: {backend}")
    _write_json(out / EXTRACT, extract)
    doc_id = args.id or out.name
    document.write_text(build_draft(extract, doc_id, source.stem, _relative(source)), encoding="utf-8")
    figures = sum(1 for s in extract["sheets"] if s["shapes"] or s["connectors"])
    print(f"下書きを作成: {document}（シート {len(extract['sheets'])}、図 {figures}）")
    return 0


def verify_command(args) -> int:
    out = Path(args.directory)
    markdown = (out / DOCUMENT).read_text(encoding="utf-8")
    extract = json.loads((out / EXTRACT).read_text(encoding="utf-8"))
    document_source = None
    for line in markdown.splitlines():
        if line.startswith("source_file:"):
            document_source = Path(line.split(":", 1)[1].strip())
            break
    report = verify(markdown, extract, document_source)
    _write_json(out / REPORT, report)
    print(format_report(report))
    return 0 if report["passed"] else 1


def figure_command(args) -> int:
    out = Path(args.directory)
    extract = json.loads((out / EXTRACT).read_text(encoding="utf-8"))
    if args.figure:
        try:
            print(describe_figure(extract, args.figure), end="")
        except KeyError:
            print(f"図 {args.figure} はない", file=sys.stderr)
            return 2
        return 0
    markdown = (out / DOCUMENT).read_text(encoding="utf-8")
    for item in list_figures(extract, markdown):
        state = "未記入" if item["todo"] else "記入済み"
        images = "、".join(item["images"]) or "画像なし"
        print(f"{item['id']}\t{state}\t図形 {item['shapes']}、線 {item['connectors']}\t{item['sheet']}\t{images}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docmig", description="既存ドキュメントを Markdown に移行する")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("migrate", help="原本から中間データ、図の画像、下書きを作る")
    p.add_argument("source", help="原本のファイル（.xlsx）")
    p.add_argument("--out", required=True, help="出力先のフォルダ")
    p.add_argument("--id", help="文書ID（省略時は出力先のフォルダ名）")
    p.add_argument("--render", choices=["auto", "excel", "libreoffice", "none"], default="auto", help="図を画像にする方法")
    p.add_argument("--force", action="store_true", help="既にある文書を上書きする")
    p.set_defaults(run=migrate)

    p = commands.add_parser("figure", help="図の一覧、または図を書き起こすための図形と矢印の一覧を出す")
    p.add_argument("directory", help="移行後の文書のフォルダ")
    p.add_argument("figure", nargs="?", help="図のID（省略すると図の一覧）")
    p.set_defaults(run=figure_command)

    p = commands.add_parser("verify", help="移行後の文書を原本と照合する")
    p.add_argument("directory", help="移行後の文書のフォルダ")
    p.set_defaults(run=verify_command)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
