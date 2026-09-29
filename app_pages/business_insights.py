"""Business Analysis page: explainability + the scenario simulator."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from services import business_analysis as ba
from services import financial_planner as fp
from utils import bootstrap
from utils.helpers import money


SCORE_LABELS = {
    "sales_health": "Sales Health",
    "cash_flow": "Cash Flow",
    "inventory_health": "Inventory Health",
    "credit_health": "Credit Health",
    "debt_health": "Debt Health",
}

# (minimum score, rating word, css tier class) - checked top to bottom
RATING_TIERS = [
    (85, "Excellent", "excellent"),
    (70, "Good", "good"),
    (50, "Average", "average"),
    (30, "Poor", "poor"),
    (0, "Very Poor", "very-poor"),
]


def _rating_for(score: float):
    for minimum, word, css_class in RATING_TIERS:
        if score >= minimum:
            return word, css_class
    return "Very Poor", "very-poor"


def render():
    context = bootstrap.require_context()
    ratios = context["ratios"]
    scores = context["scores"]

    st.title("📊 Business Analysis")
    st.caption("Every score on this page is explainable — see exactly which numbers produced it.")

    st.subheader("Why did Vyapaar Sahayak score business this way?")
    for key, label in SCORE_LABELS.items():
        rating_word, tier_class = _rating_for(scores[key])
        st.markdown(
            f'<span class="rating-badge {tier_class}">{rating_word}</span>',
            unsafe_allow_html=True,
        )
        with st.expander(f"{label}: {scores[key]}/100"):
            for line in ba.explain_score(key, ratios):
                st.markdown(f"- {line}")

    st.divider()
    st.subheader("🔬 Business Scenario Simulator")
    st.caption(
        "See how a decision might change your Business Health Indicator"
    )

    c1, c2 = st.columns(2)
    with c1:
        sales_change = st.slider("What if monthly sales change by (%)?", -30, 30, 0, 5)
        reduce_credit = st.number_input("What if you collect this much outstanding credit (₹)?",
                                         min_value=0.0, max_value=float(ratios["receivables"]),
                                         value=0.0, step=1000.0)
    with c2:
        additional_loan = st.number_input("What if you take an additional loan of (₹)?",
                                           min_value=0.0, value=0.0, step=5000.0)
        additional_emi = 0.0
        if additional_loan > 0:
            annual_rate = st.slider("Assumed annual interest rate for that loan (%)", 8.0, 24.0, 14.0, 0.5)
            tenure = st.slider("Assumed tenure (months)", 6, 60, 24)
            additional_emi = fp.estimate_emi(additional_loan, annual_rate, tenure)
            st.caption(f"Estimated additional EMI: {money(additional_emi)}/month")

    scenario_result = ba.simulate_scenario(
        ratios, sales_change_pct=sales_change, additional_loan=additional_loan,
        additional_loan_emi=additional_emi, reduce_receivables_by=reduce_credit,
    )
    scenario_scores = scenario_result["scores"]

    st.markdown("### Before vs. after")
    b1, b2 = st.columns(2)
    with b1:
        st.metric("CURRENT — Health Score", f"{scores['overall']}/100", scores["label"])
    with b2:
        delta = scenario_scores["overall"] - scores["overall"]
        st.metric("AFTER — Health Score", f"{scenario_scores['overall']}/100",
                   f"{delta:+d} vs current", delta_color="normal")

    fig = go.Figure()
    categories = list(SCORE_LABELS.values())
    fig.add_trace(go.Scatterpolar(
        r=[scores[k] for k in SCORE_LABELS], theta=categories, fill='toself', name='Current',
        line_color="#7fb5a6",
    ))
    fig.add_trace(go.Scatterpolar(
        r=[scenario_scores[k] for k in SCORE_LABELS], theta=categories, fill='toself', name='After scenario',
        line_color="#2c5f8a",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True, height=420, margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(fig, width='stretch')

   