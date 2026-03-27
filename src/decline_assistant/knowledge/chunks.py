"""Split knowledge markdown into heading-addressed chunks.

A chunk is the text under one heading (``#`` or ``##``) up to the next heading
of the same or higher level. Sub-headings (``###``) stay inside their parent so a
citation always points at a section a human can find in the file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(heading: str) -> str:
    return _SLUG_RE.sub("-", heading.lower()).strip("-")


@dataclass(frozen=True, slots=True)
class Chunk:
    source: str
    heading: str
    text: str
    level: int

    @property
    def chunk_id(self) -> str:
        return f"{self.source}#{slugify(self.heading)}"

    def excerpt(self, limit: int = 1200) -> str:
        """Body text trimmed to *limit* characters for prompt inclusion."""
        body = self.text.strip()
        return body if len(body) <= limit else body[: limit - 1].rstrip() + "…"


def chunk_markdown(markdown: str, source: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    heading: str | None = None
    level = 1
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if heading is not None and body:
            chunks.append(Chunk(source=source, heading=heading, text=body, level=level))
        buffer.clear()

    for line in markdown.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            heading = match.group(2)
        else:
            buffer.append(line)
    flush()
    return chunks


def load_knowledge(directory: str | Path) -> list[Chunk]:
    """Load every ``*.md`` file in *directory* (sorted, for deterministic ids)."""
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"knowledge directory not found: {root}")
    chunks: list[Chunk] = []
    for path in sorted(root.glob("*.md")):
        chunks.extend(chunk_markdown(path.read_text(encoding="utf-8"), source=path.name))
    return chunks
