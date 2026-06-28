"""Pure analytics aggregation — no DB access, no network."""
from config import UNCERTAIN_REASONS


def compute_analytics(entries: list[dict]) -> dict:
    """Compute three metrics over audit log entries.

    Accepts the raw list returned by store.get_log(). Pure: no I/O inside.
    Every fraction guards against divide-by-zero; an empty list returns zeros.
    """
    classifications = [e for e in entries if e.get("entry_type") == "classification"]
    appeals = [e for e in entries if e.get("entry_type") == "appeal"]

    total = len(classifications)

    # --- Metric 1: verdict distribution ---
    counts = {"likely_ai": 0, "likely_human": 0, "uncertain": 0}
    for e in classifications:
        key = e.get("label_key", "")
        if key in counts:
            counts[key] += 1

    verdict_distribution = {
        label: {
            "count": counts[label],
            "fraction": counts[label] / total if total else 0.0,
        }
        for label in ("likely_ai", "likely_human", "uncertain")
    }

    # --- Metric 2: appeal rate ---
    appealed_ids = {e["content_id"] for e in appeals}
    appeal_rate = len(appealed_ids) / total if total else 0.0

    # --- Metric 3: uncertain breakdown by audit reason ---
    uncertain = [e for e in classifications if e.get("label_key") == "uncertain"]
    n_uncertain = len(uncertain)

    # Pre-seed all known reasons from the shared constant so absent reasons
    # report 0 rather than being dropped — pre-seed and emitter share the
    # same strings so they can't drift apart.
    reason_counts: dict[str, int] = {r: 0 for r in UNCERTAIN_REASONS}
    for e in uncertain:
        reason = e.get("audit_reason") or "none"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    uncertain_breakdown = {
        reason: {
            "count": count,
            "fraction": count / n_uncertain if n_uncertain else 0.0,
        }
        for reason, count in reason_counts.items()
    }

    return {
        "total_classifications": total,
        "verdict_distribution": verdict_distribution,
        "appeal_rate": appeal_rate,
        "appealed_count": len(appealed_ids),
        "uncertain_breakdown": uncertain_breakdown,
    }
