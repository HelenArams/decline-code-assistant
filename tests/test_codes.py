from __future__ import annotations

from pathlib import Path

import pytest

from decline_assistant.knowledge import Chunk, load_knowledge
from decline_assistant.knowledge.codes import CodeBook, parse_code_entry


@pytest.fixture(scope="module")
def codebook(knowledge_dir: Path) -> CodeBook:
    return CodeBook.from_chunks(load_knowledge(knowledge_dir))


def test_every_expected_code_is_present(codebook: CodeBook) -> None:
    expected = {"00", "05", "14", "51", "54", "55", "57", "59", "61", "62", "65", "75", "91", "96"}
    assert expected <= set(codebook.codes())


def test_lookup_is_case_and_whitespace_tolerant(codebook: CodeBook) -> None:
    entry = codebook.lookup(" 1a ")
    assert entry is not None
    assert entry.code == "1A"
    assert "1A" in codebook
    assert "ZZ" not in codebook
    assert codebook.lookup("ZZ") is None


def test_fields_are_parsed_including_wrapped_lines(codebook: CodeBook) -> None:
    entry = codebook.lookup("51")
    assert entry is not None
    assert entry.title == "Insufficient funds"
    assert entry.group == "issuer / account balance"
    assert entry.kind == "soft"
    assert entry.retryable.startswith("yes")
    assert "30 days" in entry.retryable, "continuation line must be joined into the field"
    assert entry.severity == "low"
    assert entry.summary.startswith("The most common decline")
    assert entry.is_retryable and not entry.is_hard
    assert entry.citation.source == "iso8583_response_codes.md"
    assert entry.citation.heading == "51 - Insufficient funds"


def test_hard_decline_flags(codebook: CodeBook) -> None:
    stolen = codebook.lookup("43")
    assert stolen is not None
    assert stolen.is_hard and not stolen.is_retryable


def test_slash_aliases_share_one_entry(codebook: CodeBook) -> None:
    r0, r1 = codebook.lookup("R0"), codebook.lookup("R1")
    assert r0 is not None and r0 is r1
    assert r0.aliases == ("R0", "R1")


def test_describe_mentions_source(codebook: CodeBook) -> None:
    entry = codebook.lookup("91")
    assert entry is not None
    text = entry.describe()
    assert text.startswith("91 - Issuer or switch inoperative")
    assert "Source: iso8583_response_codes.md" in text


def test_non_code_chunks_are_ignored() -> None:
    chunk = Chunk(source="x.md", heading="Issuer declines", text="- **Group:** a", level=2)
    assert parse_code_entry(chunk) is None
    incomplete = Chunk(source="x.md", heading="77 - Thing", text="- **Group:** a", level=2)
    assert parse_code_entry(incomplete) is None
