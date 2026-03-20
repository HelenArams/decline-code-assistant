from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from decline_assistant.loader import REQUIRED_COLUMNS, LoaderError, load_declines
from decline_assistant.models import Scheme, ThreeDSStatus, Transaction

HEADER = ",".join(REQUIRED_COLUMNS)


def _write(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "declines.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_loads_bundled_sample(sample_csv: Path) -> None:
    rows = load_declines(sample_csv)
    assert len(rows) == 24
    assert all(isinstance(r, Transaction) for r in rows)
    assert rows[0].scheme is Scheme.VISA
    assert rows[0].three_ds_status is ThreeDSStatus.AUTHENTICATED
    assert rows[0].amount == Decimal("49.90")


def test_full_pan_is_masked_immediately(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        HEADER,
        "t1,2026-03-01T10:00:00Z,4111111111111111,10.00,EUR,5734,51,visa,Y,0",
        "t2,2026-03-01T10:00:00Z,4111 1111 1111 1111,10.00,EUR,5734,51,visa,Y,0",
    )
    rows = load_declines(path)
    assert [r.masked_pan for r in rows] == ["411111******1111", "411111******1111"]


def test_unknown_column_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        HEADER + ",cardholder_name",
        "t1,2026-03-01T10:00:00Z,411111******1111,10.00,EUR,5734,51,visa,Y,0,Jane",
    )
    with pytest.raises(LoaderError, match=r"unknown columns.*cardholder_name"):
        load_declines(path)


def test_missing_column_is_rejected(tmp_path: Path) -> None:
    cols = [c for c in REQUIRED_COLUMNS if c != "mcc"]
    path = _write(tmp_path, ",".join(cols), "t1,2026-03-01T10:00:00Z,x,1,EUR,51,visa,Y,0")
    with pytest.raises(LoaderError, match="missing required columns: mcc"):
        load_declines(path)


def test_invalid_row_reports_line_and_field(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        HEADER,
        "t1,2026-03-01T10:00:00Z,411111******1111,10.00,EUR,5734,51,visa,Y,0",
        "t2,2026-03-01T10:00:00Z,411111******1111,-5,EUR,57,51,visa,Y,0",
    )
    with pytest.raises(LoaderError) as info:
        load_declines(path)
    message = str(info.value)
    assert message.startswith("line 3:")
    assert "amount" in message
    assert "mcc" in message


def test_normalises_scheme_code_and_three_ds(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        HEADER,
        "t1,2026-03-01T10:00:00Z,tok_1,10.00,eur,5734,1a,MC,,0",
    )
    (row,) = load_declines(path)
    assert row.scheme is Scheme.MASTERCARD
    assert row.currency == "EUR"
    assert row.response_code == "1A"
    assert row.three_ds_status is ThreeDSStatus.NONE


def test_empty_file_and_missing_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(LoaderError, match="empty file"):
        load_declines(empty)
    with pytest.raises(LoaderError, match="file not found"):
        load_declines(tmp_path / "nope.csv")


def test_header_only_file(tmp_path: Path) -> None:
    path = _write(tmp_path, HEADER)
    with pytest.raises(LoaderError, match="no transaction rows"):
        load_declines(path)
