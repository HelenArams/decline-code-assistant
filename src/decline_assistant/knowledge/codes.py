"""Structured lookup of response codes parsed from the knowledge base.

The ISO 8583 file follows a fixed layout (``## 51 - Insufficient funds`` plus a
bullet list of ``**Field:** value`` lines). Parsing it here means the CLI, the
``lookup_code`` tool and the MCP server all answer from the same text that the
model cites, with no second copy of the table to drift.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from decline_assistant.knowledge.chunks import Chunk
from decline_assistant.models import Citation

_CODE_HEADING_RE = re.compile(r"^([0-9A-Z]{2}(?:\s*/\s*[0-9A-Z]{2})*)\s+-\s+(.+)$")
_FIELD_RE = re.compile(r"^-\s+\*\*(?P<key>[A-Za-z ]+):\*\*\s*(?P<value>.*)$")
_FIELDS = ("group", "kind", "retryable", "severity")


class CodeEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    aliases: tuple[str, ...]
    title: str
    group: str
    kind: str
    retryable: str
    severity: str
    summary: str
    citation: Citation

    @property
    def is_hard(self) -> bool:
        return self.kind.startswith("hard")

    @property
    def is_retryable(self) -> bool:
        return self.retryable.lower().startswith("yes")

    def describe(self) -> str:
        """Compact plain-text rendering used for tool results and the CLI."""
        return (
            f"{self.code} - {self.title}\n"
            f"Group: {self.group}\nKind: {self.kind}\nRetryable: {self.retryable}\n"
            f"Severity: {self.severity}\n\n{self.summary}\n\nSource: {self.citation}"
        )


def _parse_fields(body: str) -> tuple[dict[str, str], str]:
    fields: dict[str, str] = {}
    prose: list[str] = []
    current: str | None = None
    for line in body.splitlines():
        match = _FIELD_RE.match(line)
        if match:
            current = match.group("key").strip().lower()
            fields[current] = match.group("value").strip()
        elif current and line.startswith("  ") and line.strip():
            fields[current] = f"{fields[current]} {line.strip()}"
        else:
            current = None
            prose.append(line)
    return fields, "\n".join(prose).strip()


def parse_code_entry(chunk: Chunk) -> CodeEntry | None:
    match = _CODE_HEADING_RE.match(chunk.heading)
    if match is None:
        return None
    codes = tuple(c.strip() for c in match.group(1).split("/"))
    fields, summary = _parse_fields(chunk.text)
    if any(f not in fields for f in _FIELDS):
        return None
    return CodeEntry(
        code=codes[0],
        aliases=codes,
        title=match.group(2).strip(),
        group=fields["group"],
        kind=fields["kind"],
        retryable=fields["retryable"],
        severity=fields["severity"],
        summary=summary,
        citation=Citation(source=chunk.source, heading=chunk.heading, chunk_id=chunk.chunk_id),
    )


class CodeBook:
    def __init__(self, entries: Iterable[CodeEntry]) -> None:
        self._entries: dict[str, CodeEntry] = {}
        for entry in entries:
            for alias in entry.aliases:
                self._entries[alias] = entry

    @classmethod
    def from_chunks(cls, chunks: Iterable[Chunk]) -> CodeBook:
        return cls(e for c in chunks if (e := parse_code_entry(c)) is not None)

    def __len__(self) -> int:
        return len({id(e) for e in self._entries.values()})

    def __contains__(self, code: object) -> bool:
        return isinstance(code, str) and code.strip().upper() in self._entries

    def codes(self) -> list[str]:
        return sorted(self._entries)

    def lookup(self, code: str) -> CodeEntry | None:
        return self._entries.get(code.strip().upper())
