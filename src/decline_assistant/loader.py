"""Strict CSV loader for failed-transaction exports.

The loader is intentionally unforgiving: the header must match the documented
schema exactly (no extra columns, which is how free-text or full-PAN columns
sneak into prompts), every row must validate, and the PAN column is masked
before it is handed to anything else.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path

from pydantic import ValidationError

from decline_assistant.masking import mask_pan
from decline_assistant.models import Transaction

REQUIRED_COLUMNS: tuple[str, ...] = (
    "id",
    "timestamp",
    "masked_pan",
    "amount",
    "currency",
    "mcc",
    "response_code",
    "scheme",
    "three_ds_status",
    "retry_count",
)


class LoaderError(ValueError):
    """Raised when the CSV does not match the schema or a row is invalid."""


def validate_header(columns: Iterable[str]) -> None:
    seen = [c.strip() for c in columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in seen]
    unknown = [c for c in seen if c not in REQUIRED_COLUMNS]
    if missing:
        raise LoaderError(f"missing required columns: {', '.join(missing)}")
    if unknown:
        raise LoaderError(f"unknown columns are not allowed: {', '.join(unknown)}")
    if len(seen) != len(set(seen)):
        raise LoaderError("duplicate column names in header")


def parse_rows(rows: Iterable[Mapping[str, str]]) -> list[Transaction]:
    """Validate dict rows (already header-checked) into transactions."""
    transactions: list[Transaction] = []
    for line_no, raw in enumerate(rows, start=2):  # header is line 1
        cleaned = {k: (v or "").strip() for k, v in raw.items() if k is not None}
        cleaned["masked_pan"] = mask_pan(cleaned.get("masked_pan", ""))
        try:
            transactions.append(Transaction.model_validate(cleaned))
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
            )
            raise LoaderError(f"line {line_no}: {problems}") from None
    return transactions


def load_declines(path: str | Path) -> list[Transaction]:
    """Load and validate a declines CSV. Raises :class:`LoaderError` on any problem."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise LoaderError(f"file not found: {csv_path}")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise LoaderError("empty file: no header row")
        validate_header(reader.fieldnames)
        transactions = parse_rows(reader)
    if not transactions:
        raise LoaderError("no transaction rows found")
    return transactions
