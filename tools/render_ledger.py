"""台帳から、人が読むための一覧とトレーサビリティ表を出力する。

使い方:
    pip install -e ".[dev]"
    python tools/render_ledger.py

入力（正本）:
    requirements/requirements.yaml         要求
    requirements/system-requirements.yaml  要件
    tests/test_*.py                        テスト（名前に要件IDを含む）
出力（直接は編集しない）:
    docs/requirements.md          要求一覧
    docs/system-requirements.md   要件一覧
    docs/traceability.md          要求、要件、テストの対応
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements" / "requirements.yaml"
SYSTEM = ROOT / "requirements" / "system-requirements.yaml"
TESTS = ROOT / "tests"
DOCS = ROOT / "docs"

GENERATED = "このファイルは `tools/render_ledger.py` が台帳から出力したものである。内容を変えるときは台帳を編集し、出力し直す。"
TEST_NAME = re.compile(r"^def (test_(n?fr)(\d{3})_\w+)", re.M)


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def tests_by_requirement() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(TESTS.glob("test_*.py")):
        for name, prefix, number in TEST_NAME.findall(path.read_text(encoding="utf-8")):
            found.setdefault(f"{prefix.upper()}-{number}", []).append(f"{path.name}::{name}")
    return found


def check(requirements: dict, system: dict, tests: dict) -> None:
    ids = [r["id"] for r in requirements["requirements"]]
    system_ids = [r["id"] for r in system["requirements"]]
    problems = []
    for name, values in (("要求", ids), ("要件", system_ids)):
        duplicated = sorted({i for i in values if values.count(i) > 1})
        if duplicated:
            problems.append(f"{name}のIDが重複している: {duplicated}")
    for req in requirements["requirements"]:
        unknown = [r for r in req.get("related", []) if r not in ids]
        if unknown:
            problems.append(f"{req['id']} の関連に、台帳にない要求がある: {unknown}")
    for req in system["requirements"]:
        unknown = [r for r in req["derived_from"] if r not in ids]
        if unknown:
            problems.append(f"{req['id']} の由来に、台帳にない要求がある: {unknown}")
        if "自動テスト" in req["verification"] and req["id"] not in tests:
            problems.append(f"{req['id']} は自動テストで確かめる要件だが、対応するテストがない")
    for item in system.get("not_covered", []):
        if item["id"] not in ids:
            problems.append(f"not_covered に、台帳にない要求がある: {item['id']}")
    orphan = sorted(set(tests) - set(system_ids))
    if orphan:
        problems.append(f"台帳にない要件IDを名前に含むテストがある: {orphan}")
    if problems:
        raise SystemExit("\n".join(problems))


def render_requirements(ledger: dict) -> str:
    lines = [
        "# 要求一覧",
        "",
        GENERATED,
        "",
        f"台帳: `requirements/requirements.yaml`　版 {ledger['version']}（{ledger['updated']} 更新）",
        "",
        "| ID | 要求 | 種別 | 優先度 | 状態 | 発生源 | 関連 |",
        "|---|---|---|---|---|---|---|",
    ]
    for req in ledger["requirements"]:
        lines.append(
            f"| {req['id']} | {req['statement']} | {req['type']} | {req['priority']} | {req['status']} | "
            f"{'、'.join(req['source'])} | {'、'.join(req.get('related', []))} |"
        )
    lines += ["", "## 変更履歴", ""]
    for req in ledger["requirements"]:
        lines += [f"### {req['id']} {req['title']}", ""]
        lines += [f"- {entry['date']}　{entry['change']}" for entry in req["history"]]
        lines.append("")
    return "\n".join(lines)


def render_system(ledger: dict) -> str:
    lines = [
        "# 要件一覧",
        "",
        GENERATED,
        "",
        f"台帳: `requirements/system-requirements.yaml`　版 {ledger['version']}（{ledger['updated']} 更新）",
        "",
        f"対象: {ledger['target']}",
        "",
    ]
    for req in ledger["requirements"]:
        lines += [
            f"## {req['id']} {req['title']}",
            "",
            req["statement"] + "。",
            "",
            f"- 由来: {'、'.join(req['derived_from'])}",
            f"- 確かめ方: {req['verification']}",
            f"- 状態: {req['status']}",
            "- 受入条件:",
        ]
        lines += [f"  - {item}" for item in req["acceptance"]]
        lines.append("")
    return "\n".join(lines)


def render_traceability(requirements: dict, system: dict, tests: dict) -> str:
    derived: dict[str, list[dict]] = {}
    for req in system["requirements"]:
        for source in req["derived_from"]:
            derived.setdefault(source, []).append(req)
    not_covered = {item["id"]: item["reason"] for item in system.get("not_covered", [])}

    lines = [
        "# トレーサビリティ表",
        "",
        GENERATED,
        "",
        "## 要求から要件へ",
        "",
        "| 要求 | 内容 | 優先度 | 要件 |",
        "|---|---|---|---|",
    ]
    for req in requirements["requirements"]:
        targets = "、".join(r["id"] for r in derived.get(req["id"], []))
        if not targets:
            targets = f"なし（{not_covered.get(req['id'], '理由の記録がない')}）"
        lines.append(f"| {req['id']} | {req['title']} | {req['priority']} | {targets} |")

    lines += [
        "",
        "## 要件からテストへ",
        "",
        "| 要件 | 内容 | 由来 | 確かめ方 | 状態 | 自動テスト |",
        "|---|---|---|---|---|---|",
    ]
    for req in system["requirements"]:
        names = "<br>".join(f"`{name}`" for name in tests.get(req["id"], [])) or "なし"
        lines.append(
            f"| {req['id']} | {req['title']} | {'、'.join(req['derived_from'])} | {req['verification']} | "
            f"{req['status']} | {names} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    requirements, system, tests = load(REQUIREMENTS), load(SYSTEM), tests_by_requirement()
    check(requirements, system, tests)
    outputs = {
        "requirements.md": render_requirements(requirements),
        "system-requirements.md": render_system(system),
        "traceability.md": render_traceability(requirements, system, tests),
    }
    for name, text in outputs.items():
        (DOCS / name).write_text(text, encoding="utf-8")
        print(f"docs/{name} を出力した")
    print(f"要求 {len(requirements['requirements'])} 件、要件 {len(system['requirements'])} 件、テスト {sum(map(len, tests.values()))} 件")


if __name__ == "__main__":
    main()
