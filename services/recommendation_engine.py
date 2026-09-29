"""
Rule-based recommendation engine.

Builds a structured, factual context from the business analysis, then
turns it into human-readable recommendations, a single "top priority",
and a Today / This Week / This Month action plan. This structured
context is also what gets handed to the LLM layer (see llm_service.py) —
the LLM is only allowed to explain these numbers, never invent new ones.
"""

from utils.helpers import money, pct


def build_context(profile: dict, ratios: dict, scores: dict) -> dict:
    """A compact, rounded, LLM-and-template-safe summary of the business."""
    return {
        "owner_name": profile.get("name", ""),
        "business_type": profile.get("business_type", ""),
        "location": profile.get("location", ""),
        "monthly_revenue": round(ratios["revenue"]),
        "monthly_expenses": round(ratios["expenses"]),
        "operating_surplus": round(ratios["operating_surplus"]),
        "operating_margin_pct": round(ratios["operating_margin"] * 100, 1),
        "receivables": round(ratios["receivables"]),
        "receivable_ratio_pct": round(ratios["receivables_ratio"] * 100, 1),
        "inventory_value": round(ratios["inventory_value"]),
        "inventory_ratio_pct": round(ratios["inventory_to_revenue_ratio"] * 100, 1),
        "cash_available": round(ratios["cash"]),
        "loan_outstanding": round(ratios["loan_outstanding"]),
        "loan_emi": round(ratios["loan_emi"]),
        "emi_ratio_pct": round(ratios["emi_burden_ratio"] * 100, 1),
        "business_health": scores["overall"],
        "business_health_label": scores["label"],
        "sub_scores": {
            "sales_health": scores["sales_health"],
            "cash_flow": scores["cash_flow"],
            "inventory_health": scores["inventory_health"],
            "credit_health": scores["credit_health"],
            "debt_health": scores["debt_health"],
        },
    }


def generate_recommendations(ctx: dict) -> list:
    """Return a prioritised list of recommendation dicts, each explainable."""
    recs = []

    if ctx["receivable_ratio_pct"] > 15:
        recs.append({
            "priority": "High", "icon": "🔴",
            "title": "Collect outstanding customer credit first",
            "reason": f"₹{ctx['receivables']:,} is tied up in customer credit "
                      f"({ctx['receivable_ratio_pct']}% of monthly sales).",
            "action": "Prioritise collecting 30-40% of outstanding dues before placing new large stock orders.",
            "impact": f"Recovering even ₹{round(ctx['receivables']*0.3):,} would directly increase available "
                      f"working cash by that amount.",
        })

    if ctx["inventory_ratio_pct"] > 35:
        recs.append({
            "priority": "Medium", "icon": "🟠",
            "title": "Slow down broad inventory purchases",
            "reason": f"Inventory value is {ctx['inventory_ratio_pct']}% of monthly sales, above the "
                      f"typical healthy range of 25-30% for fast-moving retail.",
            "action": "Prioritise restocking only fast-moving items and pause purchasing slow movers.",
            "impact": "Reduces cash locked in unsold stock and frees up working capital.",
        })

    if ctx["operating_margin_pct"] < 15:
        recs.append({
            "priority": "High", "icon": "🔴",
            "title": "Protect your cash buffer",
            "reason": f"Operating surplus is ₹{ctx['operating_surplus']:,}, "
                      f"only {ctx['operating_margin_pct']}% of monthly sales.",
            "action": "Delay non-essential spending and try to negotiate supplier payment timing.",
            "impact": "A thin surplus leaves little room for unexpected expenses.",
        })

    if ctx["emi_ratio_pct"] > 12:
        recs.append({
            "priority": "Medium", "icon": "🟠",
            "title": "Keep loan EMI comfortably affordable",
            "reason": f"Monthly EMI is {ctx['emi_ratio_pct']}% of monthly sales.",
            "action": "Avoid taking on additional fixed repayments until monthly cash flow improves.",
            "impact": "Keeps a larger share of monthly surplus free for operating needs.",
        })

    if ctx["sub_scores"]["cash_flow"] >= 70 and not recs:
        recs.append({
            "priority": "Low", "icon": "🟢",
            "title": "Use surplus strategically",
            "reason": "Current cash position looks reasonable relative to expenses and receivables.",
            "action": "Consider small, measurable investments (e.g. a fast-moving product line) instead of a large expansion.",
            "impact": "Growth funded from surplus avoids new fixed repayment obligations.",
        })

    recs.append({
        "priority": "Low", "icon": "🟢",
        "title": "Review your top sellers weekly",
        "reason": "Regularly checking which products move fastest keeps purchasing decisions grounded in real demand.",
        "action": "Track your 5-10 fastest-moving products and use that list to guide the next restock.",
        "impact": "Reduces the chance of overstocking slow movers or running out of fast movers.",
    })

    priority_rank = {"High": 0, "Medium": 1, "Low": 2}
    recs.sort(key=lambda r: priority_rank.get(r["priority"], 3))
    return recs[:6]


def top_priority_today(ctx: dict, recommendations: list) -> dict:
    """Pick the single most urgent item to headline the dashboard."""
    if not recommendations:
        return {
            "icon": "🟢", "title": "No urgent issues detected",
            "reason": "Current numbers look broadly balanced.",
            "action": "Keep monitoring sales, cash, and receivables weekly.",
            "impact": "Staying consistent is what keeps a healthy business healthy.",
        }
    top = recommendations[0]
    return {
        "icon": top["icon"], "title": top["title"],
        "reason": top["reason"], "action": top["action"], "impact": top["impact"],
    }


def generate_action_plan(ctx: dict, recommendations: list) -> list:
    """Turn recommendations into a Today / This Week / This Month plan."""
    plan = []
    timeframes = ["Today", "This Week", "This Month"]
    for i, rec in enumerate(recommendations):
        timeframe = timeframes[min(i, len(timeframes) - 1)] if rec["priority"] == "High" else (
            "This Week" if rec["priority"] == "Medium" else "This Month"
        )
        plan.append({
            "title": rec["title"],
            "reason": rec["reason"],
            "expected_impact": rec["impact"],
            "priority": rec["priority"],
            "timeframe": timeframe,
        })
    return plan


def _detect_topic(question: str) -> str:
    """Very small keyword router so Smart Demo Mode answers actually change per question."""
    q = (question or "").lower()

    topic_keywords = [
        ("health_score", ["health score", "credit score", "why is my score", "score low", "score mean"]),
        ("inventory", ["inventory", "stock", "restock", "overstock"]),
        ("cash_flow", ["cash flow", "cashflow", "liquidity", "run out of cash", "short on cash"]),
        ("working_capital", ["working capital", "how much money", "how much capital", "capital need",
                              "funds do i need", "money do i need"]),
        ("loan", ["loan", "afford", "emi", "borrow", "debt", "financing"]),
        ("sales_drop", ["sales have fallen", "sales falling", "sales dropped", "sales down",
                         "sales decline", "less sales", "sales are down"]),
        ("priority", ["this week", "today", "focus", "priority", "what should i do", "most important"]),
    ]
    for topic, keywords in topic_keywords:
        if any(kw in q for kw in keywords):
            return topic
    return "general"


def _revenue_change_note(changes: list) -> str:
    if not changes:
        return ""
    for c in changes:
        if c["label"] == "Monthly sales":
            return c["text"]
    return ""


def answer_format_template(ctx: dict, recommendations: list, question: str = "", changes: list = None) -> str:
    """
    Build the Smart Demo Mode structured answer (also used as an LLM fallback).

    The answer is shaped by a small keyword router (`_detect_topic`) so that different
    questions about the same business produce different, topic-relevant answers instead
    of always repeating the single top-priority recommendation.
    """
    changes = changes or []
    topic = _detect_topic(question)
    top = top_priority_today(ctx, recommendations)
    sub = ctx["sub_scores"]

    def rec_matching(*keywords):
        """Find a recommendation whose title/reason mentions any of these keywords."""
        for r in recommendations:
            text = (r["title"] + " " + r["reason"]).lower()
            if any(k in text for k in keywords):
                return r
        return None

    if topic == "health_score":
        short_answer = (
            f"Your Business Health Indicator is currently {ctx['business_health']}/100 "
            f"({ctx['business_health_label']}). It's built from five parts, not one single number."
        )
        findings = [
            f"Sales health: {sub['sales_health']}/100 — based on your operating margin "
            f"({ctx['operating_margin_pct']}% of sales left after expenses).",
            f"Cash flow: {sub['cash_flow']}/100 — driven by outstanding customer credit "
            f"({ctx['receivable_ratio_pct']}% of sales) and available cash.",
            f"Debt health: {sub['debt_health']}/100 — your loan EMI is {ctx['emi_ratio_pct']}% of monthly sales.",
        ]
        actions = [
            "Open the **📊 Business Analysis** page and expand each score to see exactly which numbers drove it.",
            f"Start with the lowest of the five: focus on {min(sub, key=sub.get).replace('_',' ')}.",
        ]
        why = "This indicator is a prototype score built from your own numbers — it is not a credit bureau score."
        impact = "Understanding which sub-score is weakest tells you exactly where to act first."

    elif topic == "inventory":
        rec = rec_matching("inventory", "stock", "restock")
        short_answer = (
            f"Your inventory is currently valued at ₹{ctx['inventory_value']:,}, about "
            f"{ctx['inventory_ratio_pct']}% of monthly sales."
        )
        findings = [
            f"Inventory-to-sales ratio: {ctx['inventory_ratio_pct']}% "
            f"(a healthy range is typically 25-30% for fast-moving retail).",
            f"Cash currently available: ₹{ctx['cash_available']:,}.",
        ]
        if rec:
            findings.append(rec["reason"])
            actions = [rec["action"], "Check the **📦 Inventory Insights** page for fast/slow movers and margins."]
            why = rec["reason"]
            impact = rec["impact"]
        else:
            actions = ["Check the **📦 Inventory Insights** page to see which products are fast vs. slow moving "
                       "before deciding what to restock."]
            why = "Inventory levels look broadly reasonable relative to sales right now."
            impact = "Buying based on actual movement data (not guesswork) avoids cash getting stuck in slow stock."

    elif topic == "cash_flow":
        short_answer = (
            f"Cash flow health is {sub['cash_flow']}/100. Available cash is ₹{ctx['cash_available']:,}, "
            f"and ₹{ctx['receivables']:,} is currently tied up in customer credit."
        )
        findings = [
            f"₹{ctx['receivables']:,} is with customers ({ctx['receivable_ratio_pct']}% of monthly sales).",
            f"Operating surplus: ₹{ctx['operating_surplus']:,} ({ctx['operating_margin_pct']}% of sales).",
        ]
        rec = rec_matching("credit", "cash", "surplus")
        actions = [rec["action"] if rec else "Prioritise collecting outstanding customer credit before "
                   "new large purchases.", "Delay non-essential spending until surplus improves."]
        why = "Cash flow is driven mainly by how much cash is tied up in receivables versus what's on hand."
        impact = f"Collecting even 30-40% of outstanding credit (≈ ₹{round(ctx['receivables']*0.35):,}) " \
                 f"would directly add to available working cash."

    elif topic == "working_capital":
        operating_buffer = ctx["monthly_expenses"] * 1.0
        essential_inventory = ctx["monthly_revenue"] * 0.20
        gap = operating_buffer + essential_inventory + ctx["receivables"] - ctx["cash_available"]
        short_answer = (
            f"A rough working-capital estimate: {'you may need around ₹' + format(round(gap), ',') if gap > 0 else 'your current cash appears to comfortably cover a basic working-capital buffer'}."
        )
        findings = [
            f"Recommended operating buffer (1 month of expenses): ₹{round(operating_buffer):,}.",
            f"Essential inventory requirement (≈20% of monthly sales): ₹{round(essential_inventory):,}.",
            f"Receivable pressure: ₹{ctx['receivables']:,}. Available cash: ₹{ctx['cash_available']:,}.",
        ]
        actions = ["Open **💰 Financial Planner** for the full working-capital-gap breakdown and to size a "
                   "capital request.", "Consider collecting receivables first — it reduces the gap without new debt."]
        why = "Working Capital Need = Operating Buffer + Essential Inventory + Receivable Pressure − Available Cash."
        impact = "This is a transparent estimate, not a loan offer — actual financing depends on lender terms."

    elif topic == "loan":
        short_answer = (
            f"Your current loan EMI is ₹{ctx['loan_emi']:,}, about {ctx['emi_ratio_pct']}% of monthly sales "
            f"(outstanding loan: ₹{ctx['loan_outstanding']:,})."
        )
        if ctx["emi_ratio_pct"] < 10:
            pressure = "this currently looks like Low financial pressure"
        elif ctx["emi_ratio_pct"] < 20:
            pressure = "this currently looks like Moderate financial pressure"
        else:
            pressure = "this currently looks like High financial pressure"
        findings = [
            f"EMI burden: {ctx['emi_ratio_pct']}% of monthly sales — {pressure}.",
            f"Operating surplus available for repayments: ₹{ctx['operating_surplus']:,}/month.",
        ]
        actions = ["Open **💰 Financial Planner** to estimate the EMI for a specific new loan amount and see "
                   "the affordability signal.", "Avoid stacking new fixed repayments if surplus is thin."]
        why = "Affordability here is estimated only from EMI as a share of monthly sales and surplus."
        impact = "Based on the information provided — this is not a loan offer, approval, or eligibility decision."

    elif topic == "sales_drop":
        change_note = _revenue_change_note(changes)
        short_answer = (
            f"Current monthly sales are ₹{ctx['monthly_revenue']:,}."
            + (f" {change_note}" if change_note else "")
        )
        findings = [f"Operating margin is currently {ctx['operating_margin_pct']}% of sales."]
        if change_note:
            findings.append(change_note)
        rec = rec_matching("cash", "surplus", "credit")
        actions = [
            "Review which products are still moving (see **📦 Inventory Insights**) before cutting stock broadly.",
            rec["action"] if rec else "Protect your cash buffer and delay non-essential spending until sales recover.",
        ]
        why = "A sales dip affects operating surplus first, which is why protecting cash is usually the first move."
        impact = "Acting on cash and slow-moving stock early reduces the risk of a thin surplus turning negative."

    elif topic == "priority":
        short_answer = f"Right now, the top priority is: {top['title']}."
        findings = [r["reason"] for r in recommendations[:3]]
        actions = [r["action"] for r in recommendations[:3]]
        why = top["reason"]
        impact = top["impact"]

    else:  # general fallback
        short_answer = (
            f"Based on the information provided, the business health estimate is "
            f"{ctx['business_health']}/100 ({ctx['business_health_label']}). "
            f"The top priority right now is *{top['title'].lower()}*."
        )
        findings = [r["reason"] for r in recommendations[:3]]
        actions = [r["action"] for r in recommendations[:3]]
        why = top["reason"]
        impact = top["impact"]

    lines = ["**SHORT ANSWER**", short_answer]
    lines.append("\n**WHAT I NOTICED**")
    for f in findings:
        lines.append(f"- {f}")
    lines.append("\n**WHAT YOU SHOULD DO**")
    for i, a in enumerate(actions, 1):
        lines.append(f"{i}. {a}")
    lines.append("\n**WHY**")
    lines.append(why)
    lines.append("\n**EXPECTED IMPACT**")
    lines.append(impact + " This is an estimate based on the information provided, not a guarantee.")

    return "\n".join(lines)
