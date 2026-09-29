"""
Financial structuring helpers: capital allocation, EMI estimation,
affordability signal, and working-capital gap calculation.

All figures here are transparent, formula-based estimates for a
prototype — never a loan approval, offer, or guarantee.
"""

from utils.helpers import safe_div, clamp


def allocate_capital(amount: float, percentages: dict) -> dict:
    """percentages: {category: pct_0_to_100}. Returns {category: amount}."""
    amount = max(0.0, float(amount))
    return {cat: round(amount * pct / 100) for cat, pct in percentages.items()}


def estimate_emi(principal: float, annual_rate_pct: float, months: int) -> float:
    """Simple reducing-balance EMI estimate. For illustration only."""
    principal = max(0.0, float(principal))
    months = max(1, int(months))
    if principal == 0:
        return 0.0
    monthly_rate = (annual_rate_pct / 100) / 12
    if monthly_rate == 0:
        return principal / months
    factor = (1 + monthly_rate) ** months
    emi = principal * monthly_rate * factor / (factor - 1)
    return round(emi, 2)


def affordability_indicator(existing_emi: float, new_emi: float, revenue: float) -> dict:
    """Classify the combined EMI burden as Low / Moderate / High financial pressure."""
    total_emi = max(0.0, existing_emi) + max(0.0, new_emi)
    burden_pct = safe_div(total_emi, revenue) * 100

    if revenue <= 0:
        return {"burden_pct": 0, "level": "Insufficient Data",
                "message": "Enter monthly sales to estimate financial pressure."}

    if burden_pct < 10:
        level = "Low"
        message = ("Based on the entered business numbers, this combined EMI level looks like it would "
                    "create Low financial pressure relative to current sales.")
    elif burden_pct < 20:
        level = "Moderate"
        message = ("Based on the entered business numbers, taking on this additional fixed repayment "
                    "may create Moderate financial pressure.")
    else:
        level = "High"
        message = ("Based on the entered business numbers, this combined EMI level may create High "
                    "financial pressure. Consider a smaller amount or improving cash flow first.")

    return {"burden_pct": round(burden_pct, 1), "level": level, "message": message}


def working_capital_gap(ratios: dict, operating_buffer_months: float = 1.0,
                         essential_inventory_pct: float = 0.20) -> dict:
    """
    Working Capital Need = Recommended Operating Buffer
                          + Essential Inventory Requirement
                          + Receivable Pressure
                          - Available Cash

    - Recommended Operating Buffer: `operating_buffer_months` x monthly expenses.
    - Essential Inventory Requirement: `essential_inventory_pct` x monthly revenue.
    - Receivable Pressure: current receivables (cash currently tied up with customers).
    - Available Cash: cash currently on hand.
    """
    operating_buffer = ratios["expenses"] * operating_buffer_months
    essential_inventory = ratios["revenue"] * essential_inventory_pct
    receivable_pressure = ratios["receivables"]
    available_cash = ratios["cash"]

    gap = operating_buffer + essential_inventory + receivable_pressure - available_cash

    return {
        "operating_buffer": round(operating_buffer),
        "essential_inventory": round(essential_inventory),
        "receivable_pressure": round(receivable_pressure),
        "available_cash": round(available_cash),
        "gap": round(gap),
        "has_gap": gap > 0,
    }


def suggested_funding_ceiling(operating_surplus: float, months_multiple: float = 6.0) -> float:
    """A conservative, transparent prototype signal — not a lending decision."""
    return max(0.0, operating_surplus) * months_multiple


def funding_mix_plan(total_need: float, own_savings: float = 0.0, recovered_credit: float = 0.0,
                      supplier_credit: float = 0.0, new_loan: float = 0.0) -> dict:
    """
    Structure a capital requirement across multiple funding sources instead of
    assuming the whole amount becomes a single loan. Only the "new_loan" portion
    of the mix ever generates an EMI obligation elsewhere in the planner.
    """
    sources = {
        "Own savings / investment": max(0.0, float(own_savings)),
        "Recovered customer credit": max(0.0, float(recovered_credit)),
        "Supplier / trade credit": max(0.0, float(supplier_credit)),
        "New loan": max(0.0, float(new_loan)),
    }
    total_need = max(0.0, float(total_need))
    funded = sum(sources.values())

    return {
        "sources": sources,
        "total_funded": round(funded),
        "total_need": round(total_need),
        "shortfall": round(max(0.0, total_need - funded)),
        "surplus": round(max(0.0, funded - total_need)),
        "fully_funded": funded >= total_need,
        "loan_share_pct": round(safe_div(sources["New loan"], funded) * 100, 1) if funded else 0.0,
        "non_debt_share_pct": round(100 - (safe_div(sources["New loan"], funded) * 100), 1) if funded else 0.0,
    }


def repayment_tradeoff_table(principal: float, annual_rate_pct: float,
                              tenure_options_months: list = None) -> list:
    """
    The actual repayment tradeoff for the borrowed portion: a shorter tenure
    means a higher EMI but far less total interest paid, and vice versa.
    Returns one row per tenure option so they can be compared side by side.
    """
    principal = max(0.0, float(principal))
    tenure_options_months = tenure_options_months or [12, 24, 36, 48, 60]
    rows = []
    for months in tenure_options_months:
        emi = estimate_emi(principal, annual_rate_pct, months)
        total_repayment = round(emi * months)
        total_interest = round(total_repayment - principal)
        rows.append({
            "tenure_months": months,
            "emi": emi,
            "total_interest": max(0, total_interest),
            "total_repayment": total_repayment,
        })
    return rows


def rate_sensitivity(principal: float, tenure_months: int, rate_options_pct: list = None) -> list:
    """How EMI and total interest shift if the actual interest rate offered
    differs from the assumed one — useful since quoted rates vary by lender."""
    rate_options_pct = rate_options_pct or [10.0, 12.0, 14.0, 16.0, 18.0]
    rows = []
    for rate in rate_options_pct:
        emi = estimate_emi(principal, rate, tenure_months)
        total_repayment = round(emi * tenure_months)
        rows.append({
            "annual_rate_pct": rate,
            "emi": emi,
            "total_interest": max(0, round(total_repayment - principal)),
        })
    return rows