"""
Government scheme / opportunity directory. Loads a curated, structured
dataset and provides filtering. Never claims automatic eligibility.
"""

import json
from pathlib import Path

SCHEMES_PATH = Path(__file__).resolve().parent.parent / "data" / "schemes.json"


def load_schemes() -> list:
    try:
        with open(SCHEMES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def filter_schemes(schemes: list, category: str = "All", business_type: str = "All") -> list:
    out = []
    for s in schemes:
        if category != "All" and s.get("category") != category:
            continue
        targets = s.get("target_business_type", [])
        if business_type != "All" and targets and business_type not in targets:
            continue
        out.append(s)
    return out


def all_categories(schemes: list) -> list:
    return sorted({s.get("category", "Other") for s in schemes})
