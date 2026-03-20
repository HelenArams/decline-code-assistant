from __future__ import annotations

import pytest

from decline_assistant.masking import contains_pan, mask_pan, redact


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("4111111111111111", "411111******1111"),
        ("4111 1111 1111 1111", "411111******1111"),
        ("4111-1111-1111-1111", "411111******1111"),
        ("378282246310005", "378282*****0005"),  # 15-digit Amex
        ("6011000990139424123", "601100*********4123"),  # 19-digit
    ],
)
def test_mask_full_pan(raw: str, expected: str) -> None:
    assert mask_pan(raw) == expected
    assert not contains_pan(mask_pan(raw))


@pytest.mark.parametrize(
    "value",
    ["411111******1111", "tok_7f2c9a1e", "123456789012", "", "abc"],
)
def test_already_masked_or_token_is_untouched(value: str) -> None:
    assert mask_pan(value) == value


def test_redact_inside_free_text() -> None:
    text = "card 4111111111111111 declined, token tok_x unchanged, amount 1234567"
    out = redact(text)
    assert "4111111111111111" not in out
    assert "411111******1111" in out
    assert "tok_x" in out
    assert "1234567" in out


def test_contains_pan_ignores_long_numeric_ids() -> None:
    # 12 digits is below the PAN minimum; 20 digits is above the maximum.
    assert not contains_pan("123456789012")
    assert not contains_pan("12345678901234567890")
