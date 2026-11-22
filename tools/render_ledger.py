"""要求管理台帳（requirements/requirements.yaml）から、人が読むための一覧を出力する。

使い方:
    pip install -r requirements-dev.txt
    python tools/render_ledger.py

台帳が正本であり、出力された docs/requirements.md は直接編集しない。
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "requirements" / "requirements.yaml"
OUTPUT = ROOT / "docs" / "requirements.md"


def render(ledger: dict) -> str:
    lines = [
        "# 要求一覧",
        "",
        "このファイルは `requirements/requirements.yaml` から `tools/render_ledger.py` で出力したものである。"
        "内容を変えるときは台帳を編集し、出力し直す。",
        "",
        f"台帳の版: {ledger['version']}（{ledger['updated']} 更新）",
        "",
        "| ID | 要求 | 種別 | 優先度 | 状態 | 発生源 | 関連 |",
        "|---|---|---|---|---|---|---|",
    ]
    for req in ledger["requirements"]:
        lines.append(
            "| {id} | {statement} | {type} | {priority} | {status} | {source} | {related} |".format(
                id=req["id"],
                statement=req["statement"],
                type=req["type"],
                priority=req["priority"],
                status=req["status"],
                source="、".join(req["source"]),
                related="、".join(req.get("related", [])),
            )
        )
    lines += ["", "## 変更履歴", ""]
    for req in ledger["requirements"]:
        lines.append(f"### {req['id']} {req['title']}")
        lines.append("")
        for entry in req["history"]:
            lines.append(f"- {entry['date']}　{entry['change']}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ledger = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    ids = [req["id"] for req in ledger["requirements"]]
    duplicated = {i for i in ids if ids.count(i) > 1}
    if duplicated:
        raise SystemExit(f"要求IDが重複している: {sorted(duplicated)}")
    unknown = {
        rel for req in ledger["requirements"] for rel in req.get("related", []) if rel not in ids
    }
    if unknown:
        raise SystemExit(f"関連に、台帳にない要求IDがある: {sorted(unknown)}")
    OUTPUT.write_text(render(ledger), encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)} を出力した（{len(ids)} 件）")


if __name__ == "__main__":
    main()
