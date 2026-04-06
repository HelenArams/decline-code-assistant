"""Domain models shared by the loader, graph, report and MCP layers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from decline_assistant.masking import contains_pan, mask_pan


class Scheme(StrEnum):
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    OTHER = "other"


class ThreeDSStatus(StrEnum):
    """EMV 3DS ``transStatus`` plus ``none`` for unauthenticated traffic."""

    AUTHENTICATED = "Y"
    ATTEMPTED = "A"
    NOT_AUTHENTICATED = "N"
    UNAVAILABLE = "U"
    REJECTED = "R"
    CHALLENGE = "C"
    DECOUPLED = "D"
    INFORMATIONAL = "I"
    NONE = "none"


ResponseCode = Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{2}$")]
Mcc = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


class Transaction(BaseModel):
    """One failed authorization as it appears in the input CSV."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str = Field(min_length=1)
    timestamp: datetime
    masked_pan: str = Field(min_length=4, description="Masked PAN or a payment token")
    amount: Decimal = Field(ge=0)
    currency: Currency
    mcc: Mcc
    response_code: ResponseCode
    scheme: Scheme
    three_ds_status: ThreeDSStatus = ThreeDSStatus.NONE
    retry_count: int = Field(ge=0, default=0)

    @field_validator("masked_pan", mode="before")
    @classmethod
    def _mask(cls, value: object) -> object:
        # Defence in depth: the loader masks before validation, but a Transaction
        # built directly in code must never hold a full PAN either.
        if isinstance(value, str) and contains_pan(value):
            return mask_pan(value)
        return value

    @field_validator("response_code", "currency", mode="before")
    @classmethod
    def _upper(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("scheme", mode="before")
    @classmethod
    def _scheme(cls, value: object) -> object:
        if isinstance(value, str):
            lowered = value.strip().lower()
            aliases = {"mc": "mastercard", "master": "mastercard", "americanexpress": "amex"}
            return aliases.get(lowered, lowered)
        return value

    @field_validator("three_ds_status", mode="before")
    @classmethod
    def _three_ds(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "" or stripped.lower() in {"none", "n/a", "-"}:
                return ThreeDSStatus.NONE
            return stripped.upper()
        return value

    @property
    def is_eea_scheme_soft_decline(self) -> bool:
        """True for the PSD2 soft-decline codes (Mastercard 65, Visa 1A)."""
        return (self.scheme is Scheme.MASTERCARD and self.response_code == "65") or (
            self.scheme is Scheme.VISA and self.response_code == "1A"
        )


class Citation(BaseModel):
    """Pointer to a knowledge-base chunk: file plus heading."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="Knowledge file name, e.g. retry_policies.md")
    heading: str = Field(description="Heading of the cited section")
    chunk_id: str = Field(description="Stable id: '<source>#<heading-slug>'")

    def __str__(self) -> str:
        return f"{self.source} > {self.heading}"


class ClusterStats(BaseModel):
    """Aggregates the model is allowed to see. No PANs, no tokens, no ids."""

    model_config = ConfigDict(frozen=True)

    count: int
    total_by_currency: dict[str, Decimal]
    schemes: dict[str, int]
    three_ds: dict[str, int]
    unauthenticated_share: float = Field(ge=0.0, le=1.0)
    retried_rows: int
    max_retry_count: int
    first_seen: datetime
    last_seen: datetime

    @property
    def span_seconds(self) -> float:
        return (self.last_seen - self.first_seen).total_seconds()


class Cluster(BaseModel):
    """Declines sharing a response code and merchant category."""

    model_config = ConfigDict(frozen=True)

    id: str
    response_code: ResponseCode
    mcc: Mcc
    transaction_ids: list[str]
    stats: ClusterStats

    @property
    def size(self) -> int:
        return self.stats.count

    def brief(self) -> str:
        """Deterministic plain-text summary used in prompts and tool results."""
        s = self.stats
        totals = ", ".join(f"{amt:.2f} {ccy}" for ccy, amt in sorted(s.total_by_currency.items()))
        schemes = ", ".join(f"{k}={v}" for k, v in sorted(s.schemes.items()))
        three_ds = ", ".join(f"{k}={v}" for k, v in sorted(s.three_ds.items()))
        return (
            f"cluster_id: {self.id}\n"
            f"response_code: {self.response_code}\n"
            f"mcc: {self.mcc}\n"
            f"declines: {s.count}\n"
            f"total_amount: {totals}\n"
            f"schemes: {schemes}\n"
            f"three_ds_status: {three_ds}\n"
            f"unauthenticated_share: {s.unauthenticated_share:.0%}\n"
            f"rows_with_retries: {s.retried_rows} (max retry_count {s.max_retry_count})\n"
            f"window: {s.first_seen.isoformat()} .. {s.last_seen.isoformat()} "
            f"({s.span_seconds:.0f}s)"
        )
