"""Weekly Action Plan page."""

import streamlit as st

from database import db
from services import recommendation_engine as rec_engine
from utils import bootstrap
from utils.constants import PRIORITY_ICON, ACTION_STATUSES


def render():
    context = bootstrap.require_context()
    profile = context["profile"]
    ctx = context["ctx"]
    recommendations = context["recommendations"]

    st.title("📅 Your Weekly Action Plan")
    st.caption("Your personal, explainable to-do list — generated from your current business numbers.")

    if st.button("🔄 Regenerate plan from latest data", key="regen_plan"):
        plan = rec_engine.generate_action_plan(ctx, recommendations)
        db.replace_action_items(profile["id"], plan)
        st.success("Plan regenerated.")
        st.rerun()

    items = db.list_action_items(profile["id"])
    if not items:
        plan = rec_engine.generate_action_plan(ctx, recommendations)
        db.replace_action_items(profile["id"], plan)
        items = db.list_action_items(profile["id"])

    completed = sum(1 for i in items if i["status"] == "Completed")
    total = len(items)
    st.progress(completed / total if total else 0, text=f"{completed} / {total} actions completed")

    st.write("")
    for timeframe in ["Today", "This Week", "This Month"]:
        group = [i for i in items if i["timeframe"] == timeframe]
        if not group:
            continue
        st.subheader(timeframe.upper())
        for item in group:
            with st.container(border=True):
                icon = PRIORITY_ICON.get(item["priority"], "🟢")
                st.markdown(f"**{icon} {item['title']}**")
                st.caption(item.get("reason", ""))
                if item.get("expected_impact"):
                    st.caption(f"Expected impact: {item['expected_impact']}")
                new_status = st.selectbox(
                    "Status", ACTION_STATUSES,
                    index=ACTION_STATUSES.index(item["status"]) if item["status"] in ACTION_STATUSES else 0,
                    key=f"status_{item['id']}",
                )
                if new_status != item["status"]:
                    db.update_action_status(item["id"], new_status)
                    st.rerun()

    st.divider()
    st.subheader("Simple weekly routine")
    st.checkbox("Review sales of top 5 products", key="routine_1")
    st.checkbox("Follow up on outstanding customer credit", key="routine_2")
    st.checkbox("Check cash before placing the next inventory order", key="routine_3")
    st.checkbox("Record unusual expenses", key="routine_4")
    st.checkbox("Review opportunities/schemes once a month", key="routine_5")
    st.success("Small decisions, made consistently, are the point of Vyapaar Sahayak.")