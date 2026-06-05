from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from decline_assistant.config import Settings
from decline_assistant.graph import GraphDeps, build_graph
from decline_assistant.llm import FakeAnthropic, OfflineAnalyst
from decline_assistant.report import DeclineReport, render_json, render_markdown

CHUNK_51 = "iso8583_response_codes.md#51-insufficient-funds"


def test_end_to_end_with_scripted_fake(knowledge_dir: Path, tmp_path: Path) -> None:
    csv = tmp_path / "d.csv"
    csv.write_text(
        "id,timestamp,masked_pan,amount,currency,mcc,response_code,scheme,three_ds_status,retry_count\n"
        "a,2026-03-01T10:00:00Z,4111111111111111,10.00,EUR,5734,51,visa,Y,0\n"
        "b,2026-03-01T11:00:00Z,tok_2,20.00,EUR,5734,51,visa,Y,1\n",
        encoding="utf-8",
    )
    answer = {
        "cluster_id": "51/5734",
        "explanation": "Two cardholders were short of funds.",
        "severity": "low",
        "retryable": True,
        "recommended_action": "Retry in 24h, ideally near payday.",
        "claims": [
            {
                "text": "Insufficient funds is a soft decline",
                "kind": "root_cause",
                "citations": [CHUNK_51],
            },
            {"text": "Issuer is probably down", "kind": "root_cause", "citations": []},
        ],
    }
    fake = FakeAnthropic(
        [[FakeAnthropic.tool_use("lookup_code", {"code": "51"})], [FakeAnthropic.json(answer)]]
    )
    deps = GraphDeps.build(Settings(knowledge_dir=knowledge_dir), llm=fake)
    report: DeclineReport = build_graph(deps).invoke({"csv_path": str(csv)})["report"]

    (finding,) = report.findings
    assert finding.count == 2 and finding.retryable
    assert [c.text for c in finding.claims] == ["Insufficient funds is a soft decline"]
    assert finding.dropped_claims == 1
    assert finding.citations[0].heading == "51 - Insufficient funds"

    # nothing card-like reaches the model
    sent = json.dumps([str(m) for call in fake.calls for m in call.messages])
    assert "4111111111111111" not in sent and "411111" not in sent and "tok_2" not in sent
    # the cached prefix is identical for both calls
    assert fake.calls[0].system == fake.calls[1].system


def test_markdown_and_json_render(knowledge_dir: Path, sample_csv: Path) -> None:
    deps = GraphDeps.build(
        Settings(knowledge_dir=knowledge_dir, llm_backend="fake"), llm=OfflineAnalyst()
    )
    state = build_graph(deps).invoke({"csv_path": str(sample_csv)})
    report = state["report"].model_copy(update={"generated_at": datetime(2026, 3, 2, tzinfo=UTC)})

    md = render_markdown(report)
    assert md.startswith("# Decline report\n")
    assert "24 declines in 9 clusters" in md
    assert "## 51 on MCC 5734 (4 declines)" in md
    assert "retry_policies.md > " in md
    # high severity first
    assert md.index("`91/5734`") < md.index("`51/5734`")

    data = json.loads(render_json(report))
    assert data["total_declines"] == 24
    assert {f["cluster_id"] for f in data["findings"]} >= {"51/5734", "65/5734"}
    assert DeclineReport.model_validate(data) == report
