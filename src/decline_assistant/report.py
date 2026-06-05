"""Final report model and renderers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from decline_assistant.graph.verify import VerifyResult
from decline_assistant.knowledge import Retriever
from decline_assistant.models import Citation, Claim, Cluster, Severity

_SEVERITY_RANK = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}


class ClusterFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    cluster_id: str
    response_code: str
    mcc: str
    count: int
    explanation: str
    severity: Severity
    retryable: bool
    recommended_action: str
    claims: list[Claim]
    citations: list[Citation]
    dropped_claims: int = 0
    notes: list[str] = Field(default_factory=list)


class DeclineReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    model: str
    total_declines: int
    findings: list[ClusterFinding]
    warnings: list[str] = Field(default_factory=list)


def build_report(
    clusters: Sequence[Cluster],
    verified: Mapping[str, VerifyResult],
    retriever: Retriever,
    *,
    model: str,
    warnings: Sequence[str] = (),
    now: datetime | None = None,
) -> DeclineReport:
    findings: list[ClusterFinding] = []
    for cluster in clusters:
        result = verified.get(cluster.id)
        if result is None:
            continue
        a = result.analysis
        cited: dict[str, Citation] = {}
        for claim in a.claims:
            for cid in claim.citations:
                chunk = retriever.get(cid)
                if chunk is not None and cid not in cited:
                    cited[cid] = Citation(source=chunk.source, heading=chunk.heading, chunk_id=cid)
        findings.append(
            ClusterFinding(
                cluster_id=cluster.id,
                response_code=cluster.response_code,
                mcc=cluster.mcc,
                count=cluster.size,
                explanation=a.explanation,
                severity=a.severity,
                retryable=a.retryable,
                recommended_action=a.recommended_action,
                claims=a.claims,
                citations=list(cited.values()),
                dropped_claims=len(result.dropped),
                notes=result.notes,
            )
        )
    findings.sort(key=lambda f: (_SEVERITY_RANK[f.severity], -f.count, f.cluster_id))
    return DeclineReport(
        generated_at=now or datetime.now(UTC),
        model=model,
        total_declines=sum(c.size for c in clusters),
        findings=findings,
        warnings=list(warnings),
    )


def render_markdown(report: DeclineReport) -> str:
    out = [
        "# Decline report",
        "",
        f"{report.total_declines} declines in {len(report.findings)} clusters · "
        f"model `{report.model}` · {report.generated_at:%Y-%m-%d %H:%M} UTC",
        "",
        "| Cluster | Count | Severity | Retry? | Action |",
        "|---|---:|---|---|---|",
    ]
    for f in report.findings:
        action = f.recommended_action.replace("|", "/").replace("\n", " ")
        retry = "yes" if f.retryable else "no"
        out.append(f"| `{f.cluster_id}` | {f.count} | {f.severity} | {retry} | {action} |")

    for f in report.findings:
        out += ["", f"## {f.response_code} on MCC {f.mcc} ({f.count} declines)", ""]
        out += [f.explanation, "", f"**Do next:** {f.recommended_action}", ""]
        for claim in f.claims:
            refs = ", ".join(
                f"[{i}]" for i, c in enumerate(f.citations, 1) if c.chunk_id in claim.citations
            )
            out.append(f"- {claim.text} {refs}".rstrip())
        if f.citations:
            out += ["", "Sources:"]
            out += [f"{i}. {c.source} > {c.heading}" for i, c in enumerate(f.citations, 1)]
        if f.dropped_claims:
            out += ["", f"_{f.dropped_claims} unsupported claim(s) removed during verification._"]
        out += [f"> note: {n}" for n in f.notes]

    if report.warnings:
        out += ["", "## Warnings", ""]
        out += [f"- {w}" for w in report.warnings]
    return "\n".join(out) + "\n"


def render_json(report: DeclineReport) -> str:
    return report.model_dump_json(indent=2)
