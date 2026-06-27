"""Golden-case runner: `python -m decline_assistant.evals evals/cases.yaml`.

Runs against the offline analyst by default, so it is deterministic and free.
With ANTHROPIC_API_KEY set and --live, the same checks run against Claude.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from decline_assistant.config import Settings
from decline_assistant.loader import parse_rows, validate_header
from decline_assistant.models import Severity
from decline_assistant.report import ClusterFinding, DeclineReport
from decline_assistant.service import analyze

_ORDER = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]


@dataclass
class CaseResult:
    name: str
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def check_finding(finding: ClusterFinding, expect: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    cid = finding.cluster_id
    if "retryable" in expect and finding.retryable != expect["retryable"]:
        errs.append(f"{cid}: retryable={finding.retryable}, expected {expect['retryable']}")
    rank = _ORDER.index(finding.severity)
    if "severity_at_least" in expect and rank < _ORDER.index(Severity(expect["severity_at_least"])):
        errs.append(f"{cid}: severity {finding.severity} below {expect['severity_at_least']}")
    if "severity_at_most" in expect and rank > _ORDER.index(Severity(expect["severity_at_most"])):
        errs.append(f"{cid}: severity {finding.severity} above {expect['severity_at_most']}")
    cited = {c.chunk_id for c in finding.citations}
    errs += [f"{cid}: missing citation {c}" for c in expect.get("must_cite", []) if c not in cited]
    action = finding.recommended_action.lower()
    errs += [
        f"{cid}: action does not mention '{w}'"
        for w in expect.get("action_mentions", [])
        if w.lower() not in action
    ]
    return errs


def check_report(report: DeclineReport, expected: dict[str, dict[str, Any]]) -> list[str]:
    by_id = {f.cluster_id: f for f in report.findings}
    errs: list[str] = []
    for cluster_id, expect in expected.items():
        finding = by_id.get(cluster_id)
        if finding is None:
            errs.append(f"{cluster_id}: no finding in report")
            continue
        errs += check_finding(finding, expect)
    return errs


def run_case(case: dict[str, Any], settings: Settings) -> CaseResult:
    result = CaseResult(case["name"])
    reader = csv.DictReader(io.StringIO(case["csv"]))
    validate_header(reader.fieldnames or [])
    report = analyze(transactions=parse_rows(reader), settings=settings)
    result.failures = check_report(report, case["expect"])
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--live", action="store_true", help="call Claude (needs a key)")
    args = parser.parse_args(argv)

    settings = Settings()
    if args.live and not settings.can_use_anthropic:
        print("--live needs ANTHROPIC_API_KEY", file=sys.stderr)
        return 2
    backend = "anthropic" if args.live else "fake"
    settings = settings.model_copy(update={"llm_backend": backend})

    cases = yaml.safe_load(args.cases.read_text(encoding="utf-8"))["cases"]
    results = [run_case(c, settings) for c in cases]
    for r in results:
        print(f"{'PASS' if r.passed else 'FAIL'}  {r.name}")
        for failure in r.failures:
            print(f"      - {failure}")
    passed = sum(r.passed for r in results)
    print(f"\n{passed}/{len(results)} cases passed ({backend})")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
