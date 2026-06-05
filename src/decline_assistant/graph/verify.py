"""Second pass over the model's claims.

The model is told to cite, and usually does, but "usually" is not good enough
for something ops people act on. A claim survives only if:

* it cites at least one chunk id that exists in the knowledge base, and
* the claim text shares at least one meaningful term with a cited chunk
  (cheap guard against citing a random section just to have a citation).

The retryable flag is also checked against the code book, because a wrong
"retry this" on a hard decline costs real money in scheme fees.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from decline_assistant.knowledge import CodeBook, Retriever
from decline_assistant.knowledge.retriever import tokenize
from decline_assistant.models import Claim, Cluster, ClusterAnalysis

# words that show up in nearly every claim and prove nothing about support
_GENERIC = frozenset({"code", "decline", "declines", "declined", "transaction", "transactions"})


@dataclass(frozen=True, slots=True)
class DroppedClaim:
    claim: Claim
    reason: str


@dataclass(slots=True)
class VerifyResult:
    analysis: ClusterAnalysis
    dropped: list[DroppedClaim] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _supported(claim: Claim, retriever: Retriever) -> tuple[list[str], str | None]:
    valid = [cid for cid in claim.citations if retriever.get(cid) is not None]
    if not claim.citations:
        return [], "no citation"
    if not valid:
        return [], "cites unknown chunk(s): " + ", ".join(claim.citations)
    claim_terms = set(tokenize(claim.text)) - _GENERIC
    for cid in valid:
        chunk = retriever.get(cid)
        assert chunk is not None
        if claim_terms & set(tokenize(f"{chunk.heading} {chunk.text}")):
            return valid, None
    return [], "cited sections do not mention anything in the claim"


def verify_analysis(
    analysis: ClusterAnalysis, cluster: Cluster, retriever: Retriever, codebook: CodeBook
) -> VerifyResult:
    kept: list[Claim] = []
    dropped: list[DroppedClaim] = []
    for claim in analysis.claims:
        valid, reason = _supported(claim, retriever)
        if reason is None:
            kept.append(claim.model_copy(update={"citations": valid}))
        else:
            dropped.append(DroppedClaim(claim, reason))

    notes: list[str] = []
    update: dict[str, object] = {"claims": kept}
    entry = codebook.lookup(cluster.response_code)
    if entry is not None and analysis.retryable and entry.is_hard:
        update["retryable"] = False
        notes.append(
            f"model marked {entry.code} retryable but the knowledge base lists it as "
            f"'{entry.kind}'; overridden to not retryable"
        )
    if not kept:
        notes.append("no claim survived verification; treat the explanation as unverified")
    return VerifyResult(analysis.model_copy(update=update), dropped, notes)
