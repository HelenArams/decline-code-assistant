"""PAN masking.

Nothing that looks like a full card number may leave the loader. These helpers
are deliberately conservative: any run of 13-19 digits (optionally separated by
single spaces or dashes) is treated as a PAN and reduced to BIN + last four.
"""

from __future__ import annotations

import re

# 13-19 digits, allowing a single space or dash between groups (as in "4111 1111 1111 1111").
_PAN_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_KEEP_PREFIX = 6
_KEEP_SUFFIX = 4


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def mask_digits(digits: str) -> str:
    """Mask a digit-only PAN, keeping the BIN (first 6) and the last 4."""
    if len(digits) <= _KEEP_PREFIX + _KEEP_SUFFIX:
        return digits
    hidden = len(digits) - _KEEP_PREFIX - _KEEP_SUFFIX
    return f"{digits[:_KEEP_PREFIX]}{'*' * hidden}{digits[-_KEEP_SUFFIX:]}"


def contains_pan(text: str) -> bool:
    """Return True if *text* contains something that looks like a full PAN."""
    return _PAN_RE.search(text) is not None


def mask_pan(value: str) -> str:
    """Mask a single PAN-like value.

    Values that are already masked (``411111******1111``), tokens (``tok_8f3a``),
    or too short to be a PAN are returned unchanged.
    """
    value = value.strip()
    if not contains_pan(value):
        return value
    return mask_digits(_digits(value))


def redact(text: str) -> str:
    """Replace every PAN-like run inside free text with its masked form."""
    return _PAN_RE.sub(lambda m: mask_digits(_digits(m.group(0))), text)
