"""Ask Vyapaar Sahayak: the AI advisor chat page."""

import os

import streamlit as st

from database import db
from services import llm_service
from services import ai_engine
from utils import bootstrap

SUGGESTED_QUESTIONS = [
    "Why is my business health score what it is?",
    "Should I buy more inventory right now?",
    "How can I improve my cash flow?",
    "How much working capital might I need?",
    "What should I focus on this week?",
    "Can I afford another loan?",
]


def render():
    context = bootstrap.require_context()
    profile = context["profile"]
    ctx = context["ctx"]
    recommendations = context["recommendations"]
    ctx = dict(ctx)
    ctx["ai_risk_model"] = context.get("ai_risk", {})
    inventory_items = db.list_inventory_items(profile["id"])
    ctx["ml_demand_forecasts"] = [
        {"product": i["product_name"], "forecast": ai_engine.forecast_demand(i.get("history") or []).get("forecast", 0)}
        for i in inventory_items
    ]

    st.title("Ask Vyapaar Sahayak 🤖")
    

    has_api_key = bool(
        os.getenv("OPENROUTER_API_KEY", "").strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    mode_hint = "LLM connected + local ML active" if has_api_key else "Local ML active • LLM optional"
    st.caption(f"Status: {mode_hint}")

    history = db.list_chat_history(profile["id"])
    for msg in history:
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.markdown(msg["message"])

    if not history:
        st.markdown("**Try one of these:**")
        cols = st.columns(2)
        for i, q in enumerate(SUGGESTED_QUESTIONS):
            with cols[i % 2]:
                if st.button(q, width='stretch', key=f"suggest_{i}"):
                    st.session_state["pending_question"] = q
                    st.rerun()

    pending = st.session_state.pop("pending_question", None)
    question = st.chat_input("Ask a business question…") or pending

    if question:
        db.add_chat_message(profile["id"], "user", question)
        with st.chat_message("user"):
            st.markdown(question)

        response = llm_service.get_ai_response(ctx, question, recommendations, context["changes"])
        with st.chat_message("assistant"):
            st.markdown(response["text"])
            if response["note"]:
                st.caption(response["note"])
        db.add_chat_message(profile["id"], "assistant", response["text"])

    if history:
        if st.button("Clear conversation", key="clear_chat"):
            db.clear_chat_history(profile["id"])
            st.rerun()

    