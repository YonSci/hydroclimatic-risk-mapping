"""Shared weighted-combination logic used by both hazard scoring
(hazard/hazard.py) and vulnerability scoring (vulnerability/vulnerability.py)
-- both combine several named component arrays via config-driven weights,
with the same "keys must match exactly" validation (quality-safeguards.md:
weights are the single source of truth for each indicator's contribution,
so a caller passing an unexpected or incomplete score set is a bug to catch
loudly, not silently ignore).
"""

from __future__ import annotations

from typing import Any


def weighted_sum(
    scores: dict[str, Any], weights: dict[str, float], group_name: str, error_cls: type[Exception]
) -> Any:
    missing = set(weights) - set(scores)
    extra = set(scores) - set(weights)
    if missing or extra:
        raise error_cls(
            f"scores for '{group_name}' don't match the configured {group_name} weight keys — "
            f"missing: {sorted(missing)}, unexpected: {sorted(extra)}"
        )
    terms = [weights[key] * scores[key] for key in weights]
    total = terms[0]
    for term in terms[1:]:
        total = total + term
    return total
