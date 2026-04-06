"""Group declines into clusters the analysis works on."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from decimal import Decimal

from decline_assistant.models import Cluster, ClusterStats, ThreeDSStatus, Transaction


def cluster_key(tx: Transaction) -> tuple[str, str]:
    return (tx.response_code, tx.mcc)


def build_stats(transactions: list[Transaction]) -> ClusterStats:
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    for tx in transactions:
        totals[tx.currency] += tx.amount
    unauthenticated = sum(1 for tx in transactions if tx.three_ds_status is ThreeDSStatus.NONE)
    return ClusterStats(
        count=len(transactions),
        total_by_currency=dict(totals),
        schemes=dict(Counter(tx.scheme.value for tx in transactions)),
        three_ds=dict(Counter(tx.three_ds_status.value for tx in transactions)),
        unauthenticated_share=unauthenticated / len(transactions),
        retried_rows=sum(1 for tx in transactions if tx.retry_count > 0),
        max_retry_count=max(tx.retry_count for tx in transactions),
        first_seen=min(tx.timestamp for tx in transactions),
        last_seen=max(tx.timestamp for tx in transactions),
    )


def cluster_transactions(transactions: Iterable[Transaction]) -> list[Cluster]:
    """Cluster by (response code, MCC); largest clusters first, ties by code then MCC."""
    groups: defaultdict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for tx in transactions:
        groups[cluster_key(tx)].append(tx)
    clusters = [
        Cluster(
            id=f"{code}/{mcc}",
            response_code=code,
            mcc=mcc,
            transaction_ids=sorted(tx.id for tx in txs),
            stats=build_stats(txs),
        )
        for (code, mcc), txs in groups.items()
    ]
    clusters.sort(key=lambda c: (-c.size, c.response_code, c.mcc))
    return clusters
