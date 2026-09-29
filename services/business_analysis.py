"""
Core, explainable business-health calculations.

This module is the single source of truth for every number shown in the
app. It never talks to Streamlit, a database, or an LLM — it only takes
plain dicts of numbers and returns plain dicts of results, so it can be
unit tested on its own.
"""

from utils.helpers import safe_div, clamp


def compute_ratios(snapshot: dict) -> dict:
    """Turn a raw financial snapshot into named, explainable ratios."""
    revenue = max(float(snapshot.get("revenue", 0)), 0)
    expenses = max(float(snapshot.get("expenses", 0)), 0)
    cash = max(float(snapshot.get("cash", 0)), 0)
    receivables = max(float(snapshot.get("receivables", 0)), 0)
    inventory_value = max(float(snapshot.get("inventory_value", 0)), 0)
    loan_outstanding = max(float(snapshot.get("loan_outstanding", 0)), 0)
    loan_emi = max(float(snapshot.get("loan_emi", 0)), 0)

    operating_surplus = revenue - expenses
    operating_margin = safe_div(operating_surplus, revenue)
    cash_position_ratio = safe_div(cash, expenses)          # months of expenses covered by cash
    receivables_ratio = safe_div(receivables, revenue)      # credit tied up vs monthly sales
    inventory_to_revenue_ratio = safe_div(inventory_value, revenue)
    debt_burden_ratio = safe_div(loan_outstanding, revenue) # outstanding debt vs one month sales
    emi_burden_ratio = safe_div(loan_emi, revenue)
    working_capital_estimate = (cash + receivables) - (expenses * 0.5)

    return {
        "revenue": revenue,
        "expenses": expenses,
        "cash": cash,
        "receivables": receivables,
        "inventory_value": inventory_value,
        "loan_outstanding": loan_outstanding,
        "loan_emi": loan_emi,
        "operating_surplus": operating_surplus,
        "operating_margin": operating_margin,
        "cash_position_ratio": cash_position_ratio,
        "receivables_ratio": receivables_ratio,
        "inventory_to_revenue_ratio": inventory_to_revenue_ratio,
        "debt_burden_ratio": debt_burden_ratio,
        "emi_burden_ratio": emi_burden_ratio,
        "working_capital_estimate": working_capital_estimate,
    }


def compute_health_score(ratios: dict) -> dict:
    """Five explainable sub-scores (0-100) rolled up into one overall score."""

    sales_health = clamp(50 + ratios["operating_margin"] * 180)

    cash_flow = clamp(
        75
        - ratios["receivables_ratio"] * 110
        + ratios["cash_position_ratio"] * 12
    )

    inventory_health = clamp(
        82 - max(0.0, ratios["inventory_to_revenue_ratio"] - 0.25) * 80
    )

    credit_health = clamp(90 - max(0.0, ratios["receivables_ratio"] - 0.10) * 140)

    debt_health = clamp(90 - ratios["emi_burden_ratio"] * 180 - ratios["debt_burden_ratio"] * 25)

    overall = round(
        0.25 * sales_health
        + 0.25 * cash_flow
        + 0.20 * inventory_health
        + 0.15 * credit_health
        + 0.15 * debt_health
    )

    insufficient_data = ratios.get("revenue", 0) <= 0

    if insufficient_data:
        label = "Insufficient Data"
    elif overall >= 70:
        label = "Healthy"
    elif overall >= 55:
        label = "Needs Attention"
    else:
        label = "At Risk"

    return {
        "overall": overall,
        "label": label,
        "insufficient_data": insufficient_data,
        "sales_health": round(sales_health),
        "cash_flow": round(cash_flow),
        "inventory_health": round(inventory_health),
        "credit_health": round(credit_health),
        "debt_health": round(debt_health),
    }


def analyze(snapshot: dict) -> dict:
    """Convenience wrapper: ratios + scores in one call."""
    ratios = compute_ratios(snapshot)
    scores = compute_health_score(ratios)
    return {"ratios": ratios, "scores": scores}


def explain_score(component: str, ratios: dict) -> list:
    """Return a short list of plain-language bullet explanations for one sub-score."""
    r = ratios
    explanations = {
        "sales_health": [
            f"Monthly sales are currently {r['revenue']:,.0f} against expenses of {r['expenses']:,.0f}.",
            f"That leaves an operating surplus of {r['operating_surplus']:,.0f}, "
            f"or about {r['operating_margin']*100:.1f}% of sales.",
        ],
        "cash_flow": [
            f"₹{r['receivables']:,.0f} is currently tied up in customer credit "
            f"({r['receivables_ratio']*100:.1f}% of monthly sales).",
            f"Available cash covers roughly {r['cash_position_ratio']:.1f} month(s) of expenses.",
        ],
        "inventory_health": [
            f"Inventory on hand is valued at ₹{r['inventory_value']:,.0f}, "
            f"about {r['inventory_to_revenue_ratio']*100:.1f}% of monthly sales.",
            "A healthy range is typically under 25-30% of monthly sales for a fast-moving retail shop.",
        ],
        "credit_health": [
            f"Customer credit (receivables) is {r['receivables_ratio']*100:.1f}% of monthly sales.",
            "Keeping this under roughly 10% generally keeps working capital healthier.",
        ],
        "debt_health": [
            f"Monthly loan EMI is ₹{r['loan_emi']:,.0f}, about {r['emi_burden_ratio']*100:.1f}% of monthly sales.",
            f"Total outstanding loan is ₹{r['loan_outstanding']:,.0f}.",
        ],
    }
    return explanations.get(component, ["No explanation available for this component."])


def compare_snapshots(current: dict, previous: dict) -> list:
    """Build a 'what changed' list comparing two snapshots. Returns list of dicts."""
    if not previous:
        return []

    fields = [
        ("revenue", "Monthly sales", True),
        ("expenses", "Monthly expenses", False),
        ("receivables", "Outstanding customer credit", False),
        ("cash", "Cash available", True),
        ("inventory_value", "Inventory value", None),
        ("loan_outstanding", "Outstanding loan", False),
    ]
    changes = []
    for key, label, higher_is_better in fields:
        cur_val = float(current.get(key, 0))
        prev_val = float(previous.get(key, 0))
        if prev_val == 0 and cur_val == 0:
            continue
        delta = cur_val - prev_val
        if abs(delta) < max(0.01 * prev_val, 1):
            continue
        pct_change = safe_div(delta, prev_val) * 100
        direction = "up" if delta > 0 else "down"
        if higher_is_better is None:
            tone = "neutral"
        elif (higher_is_better and delta > 0) or (not higher_is_better and delta < 0):
            tone = "positive"
        else:
            tone = "negative"
        changes.append({
            "key": key,
            "label": label,
            "direction": direction,
            "delta": delta,
            "pct_change": pct_change,
            "tone": tone,
            "text": f"{label} {'increased' if delta > 0 else 'decreased'} by ₹{abs(delta):,.0f} "
                    f"({abs(pct_change):.1f}%) since the last update.",
        })
    return changes


def simulate_scenario(base_snapshot: dict, sales_change_pct: float = 0.0,
                       additional_loan: float = 0.0, additional_loan_emi: float = 0.0,
                       reduce_receivables_by: float = 0.0) -> dict:
    """Apply a hypothetical change to a snapshot and return the resulting analysis.

    Purely a transparent recalculation using the same formulas as `analyze()` —
    no prediction model, no guaranteed outcomes.
    """
    scenario = dict(base_snapshot)
    base_cash = float(base_snapshot.get("cash", 0))
    base_receivables = float(base_snapshot.get("receivables", 0))
    receivables_collected = max(0.0, min(reduce_receivables_by, base_receivables))

    scenario["revenue"] = max(0.0, float(base_snapshot.get("revenue", 0)) * (1 + sales_change_pct / 100))
    scenario["loan_outstanding"] = max(0.0, float(base_snapshot.get("loan_outstanding", 0)) + additional_loan)
    scenario["loan_emi"] = max(0.0, float(base_snapshot.get("loan_emi", 0)) + additional_loan_emi)
    scenario["receivables"] = max(0.0, base_receivables - receivables_collected)
    # Cash goes up by any new loan disbursed AND any receivables actually collected.
    scenario["cash"] = max(0.0, base_cash + additional_loan + receivables_collected)
    return analyze(scenario)