"""
Inventory analysis: stock value, margins, fast/slow movers, a simple
moving-average demand estimate, and restocking suggestions.
"""

import json
from pathlib import Path

from utils.helpers import safe_div
from services import ai_engine

DEMO_INVENTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_inventory.json"


def load_demo_inventory() -> list:
    try:
        with open(DEMO_INVENTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def moving_average(history: list, window: int = 3) -> float:
    """Average of the most recent `window` values in a monthly-units history list."""
    if not history:
        return 0.0
    recent = history[-window:] if len(history) >= window else history
    return round(sum(recent) / len(recent), 1)


def gross_margin_pct(purchase_price: float, selling_price: float) -> float:
    if selling_price <= 0:
        return 0.0
    return round(safe_div(selling_price - purchase_price, selling_price) * 100, 1)


def stock_value(quantity: float, purchase_price: float) -> float:
    return round(max(0.0, quantity) * max(0.0, purchase_price), 2)


def revenue_potential(quantity: float, selling_price: float) -> float:
    return round(max(0.0, quantity) * max(0.0, selling_price), 2)


def classify_movement(item_units_sold: float, all_units_sold: list) -> str:
    """Classify an item as Fast / Medium / Slow moving relative to the rest of the catalogue."""
    values = [v for v in all_units_sold if v is not None]
    if not values or len(values) < 2:
        return "Medium"
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    p33 = sorted_vals[max(0, int(n * 0.33) - 1)]
    p66 = sorted_vals[max(0, int(n * 0.66) - 1)]
    if item_units_sold >= p66 and item_units_sold > 0:
        return "Fast"
    if item_units_sold <= p33:
        return "Slow"
    return "Medium"


def analyze_inventory(items: list, forecast_context: dict | None = None) -> dict:
    """
    items: list of dicts with product_name, category, quantity, purchase_price,
           selling_price, monthly_units_sold, history (optional list).
    Returns enriched items plus summary lists (top movers, slow movers, high margin).
    """
    if not items:
        return {"items": [], "top_movers": [], "slow_movers": [], "high_margin": [], "restock_suggestions": []}

    all_units = [it.get("monthly_units_sold", 0) for it in items]
    enriched = []
    for it in items:
        units = it.get("monthly_units_sold", 0)
        margin = gross_margin_pct(it.get("purchase_price", 0), it.get("selling_price", 0))
        movement = classify_movement(units, all_units)
        history = it.get("history") or []
        enriched.append({
            **it,
            "stock_value": stock_value(it.get("quantity", 0), it.get("purchase_price", 0)),
            "revenue_potential": revenue_potential(it.get("quantity", 0), it.get("selling_price", 0)),
            "gross_margin_pct": margin,
            "movement": movement,
            "demand_estimate": moving_average(history) if history else units,
            "ml_forecast": ai_engine.forecast_demand(history, context=forecast_context) if history else {"forecast": float(units), "method": "current monthly units", "stability": "Low"},
        })

    top_movers = sorted(enriched, key=lambda x: x["monthly_units_sold"], reverse=True)[:5]
    slow_movers = sorted(enriched, key=lambda x: x["monthly_units_sold"])[:5]
    high_margin = sorted(enriched, key=lambda x: x["gross_margin_pct"], reverse=True)[:5]

    restock_suggestions = []
    for it in enriched:
        forecast = float(it.get("ml_forecast", {}).get("forecast", it.get("demand_estimate", 0)))
        if forecast > max(0, it.get("monthly_units_sold", 0)) * 1.10 and it["quantity"] <= max(1, forecast * 1.5):
            restock_suggestions.append(
                f"{it['product_name']} has an ML demand forecast of about {forecast:.0f} units next month "
                f"({it['ml_forecast'].get('stability', 'Low')} model stability). Review replenishment capacity."
            )
        elif it["movement"] == "Fast" and it["gross_margin_pct"] >= 15:
            restock_suggestions.append(
                f"{it['product_name']} is a fast-moving product with healthy margins "
                f"({it['gross_margin_pct']}%). Consider prioritising it during your next restock."
            )
        elif it["movement"] == "Slow" and it["quantity"] > 0:
            restock_suggestions.append(
                f"{it['product_name']} is moving slowly relative to your other products. "
                f"Consider pausing new purchases until existing stock clears."
            )

    return {
        "items": enriched,
        "top_movers": top_movers,
        "slow_movers": slow_movers,
        "high_margin": high_margin,
        "restock_suggestions": restock_suggestions[:6],
    }
