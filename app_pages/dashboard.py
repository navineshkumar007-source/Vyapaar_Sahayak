"""Dashboard page: executive snapshot of the business."""

import streamlit as st
import pandas as pd
import plotly.express as px

from utils import bootstrap
from utils.helpers import money, first_name
from utils.constants import HEALTH_LABEL_COLORS, DISCLAIMER


def render():
    context = bootstrap.require_context()
    profile = context["profile"]
    ratios = context["ratios"]
    scores = context["scores"]
    recommendations = context["recommendations"]
    changes = context["changes"]
    ai_risk = context.get("ai_risk", {})

    st.markdown(f"""
    <div class="hero">
      <span class="badge">AI BUSINESS SAHAYAK</span>
      <h1 style="margin-bottom:4px">Good Morning, {first_name(profile['name'])} </h1>
      <p class="small">{profile['business_type']} • {profile.get('location','')}</p>
      <p style="font-size:1.02rem">Here is how your business is doing today.</p>
    </div>
    """, unsafe_allow_html=True)

    st.write("")
    cols = st.columns(5)
    changes_by_key = {c["key"]: c for c in changes if c.get("key")}

    # Operating surplus has no direct field in compare_snapshots (it's derived:
    # revenue - expenses), so build its delta manually from the two snapshots.
    surplus_change = None
    previous_snapshot = context.get("previous_snapshot")
    if previous_snapshot:
        prev_surplus = float(previous_snapshot.get("revenue", 0)) - float(previous_snapshot.get("expenses", 0))
        cur_surplus = ratios["operating_surplus"]
        delta = cur_surplus - prev_surplus
        if prev_surplus != 0 and abs(delta) >= max(0.01 * abs(prev_surplus), 1):
            pct = (delta / prev_surplus) * 100
            surplus_change = {
                "direction": "up" if delta > 0 else "down",
                "pct_change": pct,
                "tone": "positive" if delta > 0 else "negative",
            }

    vals = [
        ("Monthly sales", money(ratios["revenue"]), changes_by_key.get("revenue")),
        ("Monthly expenses", money(ratios["expenses"]), changes_by_key.get("expenses")),
        ("Operating surplus", money(ratios["operating_surplus"]), surplus_change),
        ("Cash available", money(ratios["cash"]), changes_by_key.get("cash")),
        ("Outstanding credit", money(ratios["receivables"]), changes_by_key.get("receivables")),
    ]
    for col, (label, val, chg) in zip(cols, vals):
        with col:
            delta_html = ""
            if chg:
                arrow = "▲" if chg["direction"] == "up" else "▼"
                tone = chg["tone"]  # positive | negative | neutral
                delta_html = (
                    f'<div class="metric-delta {tone}">{arrow} {abs(chg["pct_change"]):.1f}%</div>'
                )
            st.markdown(
                f'<div class="metric-card"><div class="small">{label}</div>'
                f'<h3>{val}</h3>{delta_html}</div>',
                unsafe_allow_html=True,
            )

    st.write("")
    c1, c2 = st.columns([1, 1.5])

    with c1:
        st.subheader("Business Health Indicator")
        icon = HEALTH_LABEL_COLORS.get(scores["label"], "")
        st.metric("Overall score", f"{scores['overall']}/100", f"{icon} {scores['label']}")
        df = pd.DataFrame({
            "Area": ["Sales", "Cash flow", "Inventory", "Credit", "Debt"],
            "Score": [scores["sales_health"], scores["cash_flow"], scores["inventory_health"],
                      scores["credit_health"], scores["debt_health"]],
        })
        fig = px.bar(df, x="Score", y="Area", orientation="h", range_x=[0, 100], text="Score")
        fig.update_traces(marker_color="#2c5f8a")
        fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig, width='stretch')
        st.caption("The Business Health Indicator is the deterministic financial guardrail.")
        if ai_risk:
            st.metric("AI Risk Detector", f"{ai_risk['risk_score']}/100", ai_risk['label'])
           

    with c2:
        st.subheader(" Top Priority Today")
        top = context["recommendations"][0] if recommendations else None
        if top:
            with st.container(border=True):
                st.markdown(f"### {top['icon']} {top['title']}")
                st.write(top["reason"])
                st.markdown(f"**Suggested action:** {top['action']}")
                st.caption(f"Expected impact: {top['impact']}")

        st.subheader("What changed?")
        if changes:
            for c in changes[:4]:
                arrow = "🔺" if c["direction"] == "up" else "🔻"
                st.markdown(f"{arrow} {c['text']}")
        else:
            st.caption("No earlier snapshot yet — update your profile again later to see week-over-week changes.")

    st.write("")
    st.subheader("Money flow snapshot")
    flow = pd.DataFrame({
        "Category": ["Sales", "Expenses", "Outstanding credit", "Inventory", "Cash"],
        "Amount": [ratios["revenue"], ratios["expenses"], ratios["receivables"],
                   ratios["inventory_value"], ratios["cash"]],
    })
    fig = px.bar(flow, x="Category", y="Amount", text_auto=".2s", color="Category",
                 color_discrete_sequence=["#2c5f8a", "#5fa0b8", "#7fb5a6", "#b0533e", "#1f4060"])
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
    st.plotly_chart(fig, width='stretch')
