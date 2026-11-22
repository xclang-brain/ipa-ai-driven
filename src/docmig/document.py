"""移行後の文書（Markdown）の書式と、その読み取り。

文書の書式は docs/05-specification.md に定めている。
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

import yaml

STATUSES = ("未確認", "AI確認済み", "承認済み")
TODO_MARK = "<!-- transcription:todo -->"

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_FIGURE = re.compile(
    r'<!-- figure:begin id="(?P<id>[^"]+)" sheet="(?P<sheet>[^"]*)" -->\n(?P<body>.*?)<!-- figure:end -->',
    re.S,
)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_REVIEW_MARK = re.compile(r"【要確認[:：]\s*([^】]*)】")
_MERMAID = re.compile(r"```mermaid\n(.*?)```", re.S)
_MERMAID_ENTITY = re.compile(r"#(\w+);")
_BREAK = re.compile(r"<br\s*/?>", re.I)
_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~])")
_SPACE = re.compile(r"\s+")
_TOP_HEADING = re.compile(r"^#{1,2} .*$", re.M)


def normalize(text: str) -> str:
    """照合のために文字列を整える。空白と改行を取り除く。"""
    return _SPACE.sub("", text)


def body_text(markdown: str) -> str:
    """Markdown から、照合の対象になる本文の文字だけを取り出して整える。

    コメント、画像の記法、要確認の印は本文に数えない。文書名とシート名の見出し
    （# と ##）は道具が付けたものなので、これも数えない。Mermaid の中の文字参照
    （#quot; など）と HTML の文字参照、Markdown のエスケープは元の文字に戻す。
    """
    text = _MERMAID.sub(lambda m: _MERMAID_ENTITY.sub(r"&\1;", m.group(0)), markdown)
    text = _COMMENT.sub("", text)
    text = _TOP_HEADING.sub("", text)
    text = _IMAGE.sub("", text)
    text = _REVIEW_MARK.sub("", text)
    text = _BREAK.sub("", text)
    text = _ESCAPE.sub(r"\1", text)
    text = html.unescape(text)
    return normalize(text)


@dataclass
class Figure:
    id: str
    sheet: str
    body: str

    @property
    def is_todo(self) -> bool:
        return TODO_MARK in self.body


@dataclass
class Document:
    attributes: dict
    body: str
    figures: list[Figure] = field(default_factory=list)

    @property
    def review_marks(self) -> list[str]:
        return [m.group(1).strip() for m in _REVIEW_MARK.finditer(_COMMENT.sub("", self.body))]


def parse(markdown: str) -> Document:
    match = _FRONT_MATTER.match(markdown)
    if not match:
        raise ValueError("文書の先頭に属性（--- で囲んだ部分）がない")
    attributes = yaml.safe_load(match.group(1)) or {}
    body = markdown[match.end():]
    figures = [Figure(m["id"], html.unescape(m["sheet"]), m["body"]) for m in _FIGURE.finditer(body)]
    return Document(attributes, body, figures)


def consume_all(haystack: str, needles: list[tuple[str, dict]]) -> list[dict]:
    """needles の文字列が、出現回数も含めて haystack にすべてあるかを調べる。

    長い文字列から順に探し、見つかった部分は使用済みにする。これにより、短い
    文字列が、それを含む長い文字列の一部として数えられることを防ぐ。
    見つからなかったものを返す。
    """
    used = bytearray(len(haystack))
    missing = []
    for text, origin in sorted(needles, key=lambda item: -len(item[0])):
        if not text:
            continue
        start = 0
        while True:
            found = haystack.find(text, start)
            if found < 0:
                missing.append({"text": text, **origin})
                break
            if not any(used[found:found + len(text)]):
                used[found:found + len(text)] = b"\x01" * len(text)
                break
            start = found + 1
    return missing
