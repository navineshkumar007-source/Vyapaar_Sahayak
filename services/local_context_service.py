"""
Hyper-local intelligence layer.

For this prototype, insights come from a small curated JSON dataset
matched by state / season / business type, with "Any" as a wildcard.
This is explicitly a PROTOTYPE LOCAL INSIGHT, not live market data —
every insight returned should be labelled as such in the UI. The
function signature is deliberately generic so a real market-data API
could be swapped in later without changing calling code.
"""

import json
from pathlib import Path

LOCAL_CONTEXT_PATH = Path(__file__).resolve().parent.parent / "data" / "local_context.json"


def load_local_context() -> list:
    try:
        with open(LOCAL_CONTEXT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def get_insights(state: str = "Any", season: str = "Any", business_type: str = "Any") -> list:
    """Return matching curated insights. 'Any' in the dataset acts as a wildcard."""
    rules = load_local_context()
    matches = []
    for rule in rules:
        state_ok = rule.get("state", "Any") in ("Any", state)
        season_ok = rule.get("season", "Any") in ("Any", season)
        biz_ok = rule.get("business_type", "Any") in ("Any", business_type)
        if state_ok and season_ok and biz_ok:
            matches.append(rule)
    # Prefer more specific matches (fewer "Any" wildcards) first.
    def specificity(rule):
        return sum(1 for f in (rule.get("state"), rule.get("season"), rule.get("business_type")) if f != "Any")
    matches.sort(key=specificity, reverse=True)
    return matches[:5]
