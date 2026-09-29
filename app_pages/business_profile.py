"""Business Profile page: create or edit the business profile + financial numbers."""

import streamlit as st

from database import db
from services import business_analysis as ba
from services import recommendation_engine as rec_engine
from utils.constants import BUSINESS_TYPES, LANGUAGES, STATES, SEASONS
from utils.helpers import safe_float


def _index_or(options, value, default=0):
    return options.index(value) if value in options else default


def render():
    st.title("👤 Business Profile")
    st.caption("Enter True Values As Whole Working Is Based On These Data")

    profile = st.session_state.get("profile") or {}
    has_existing = bool(profile.get("id"))

    latest_snapshot = {}
    if has_existing:
        snaps = db.get_latest_snapshots(profile["id"], limit=1)
        latest_snapshot = snaps[0] if snaps else {}

    with st.form("profile_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Owner name", profile.get("name", ""))
            business_type = st.selectbox(
                "Business type", BUSINESS_TYPES,
                index=_index_or(BUSINESS_TYPES, profile.get("business_type", ""), 0),
            )
            location = st.text_input("Location (village/town)", profile.get("location", ""))
            state = st.selectbox("State", STATES, index=_index_or(STATES, profile.get("state", ""), 0))
            district = st.text_input("District", profile.get("district", ""))
            language = st.selectbox(
                "Preferred language", LANGUAGES,
                index=_index_or(LANGUAGES, profile.get("language", "English"), 0),
            )
            employees = st.number_input("Employees", min_value=0, max_value=100,
                                         value=int(profile.get("employees", 0)))
            season = st.selectbox("Current season", SEASONS,
                                   index=_index_or(SEASONS, profile.get("season", "Regular"), 0))
            local_event = st.text_input("Optional local event/festival",
                                         profile.get("local_event", ""))
        with c2:
            revenue = st.number_input("Average monthly sales (₹)", min_value=0.0,
                                       value=safe_float(latest_snapshot.get("revenue"), 0.0), step=5000.0)
            expenses = st.number_input("Average monthly expenses (₹)", min_value=0.0,
                                        value=safe_float(latest_snapshot.get("expenses"), 0.0), step=5000.0)
            inventory_value = st.number_input("Current inventory value (₹)", min_value=0.0,
                                               value=safe_float(latest_snapshot.get("inventory_value"), 0.0),
                                               step=5000.0)
            receivables = st.number_input("Customer credit / outstanding (₹)", min_value=0.0,
                                           value=safe_float(latest_snapshot.get("receivables"), 0.0),
                                           step=5000.0)
            cash = st.number_input("Cash/bank balance available for business (₹)", min_value=0.0,
                                    value=safe_float(latest_snapshot.get("cash"), 0.0), step=5000.0)
            loan_outstanding = st.number_input("Existing business loan outstanding (₹)", min_value=0.0,
                                                value=safe_float(latest_snapshot.get("loan_outstanding"), 0.0),
                                                step=5000.0)
            loan_emi = st.number_input("Monthly loan EMI (₹)", min_value=0.0,
                                        value=safe_float(latest_snapshot.get("loan_emi"), 0.0), step=500.0)

        submitted = st.form_submit_button("Save & analyse", type="primary", width='stretch')

    if submitted:
        if not name.strip():
            st.error("Please enter the owner's name before saving.")
            return

        profile_data = {
            "name": name.strip(), "business_type": business_type, "location": location.strip(),
            "state": state, "district": district.strip(), "language": language,
            "employees": employees, "season": season, "local_event": local_event.strip(),
        }
        profile_id = db.upsert_profile(profile_data, profile_id=profile.get("id"))

        snapshot_data = {
            "revenue": revenue, "expenses": expenses, "inventory_value": inventory_value,
            "receivables": receivables, "cash": cash, "loan_outstanding": loan_outstanding,
            "loan_emi": loan_emi,
        }
        db.add_snapshot(profile_id, snapshot_data)

        # Refresh session state + regenerate the action plan from the new numbers.
        updated_profile = db.get_active_profile()
        st.session_state.profile = updated_profile
        ratios = ba.compute_ratios(snapshot_data)
        scores = ba.compute_health_score(ratios)
        ctx = rec_engine.build_context(updated_profile, ratios, scores)
        recs = rec_engine.generate_recommendations(ctx)
        plan = rec_engine.generate_action_plan(ctx, recs)
        db.replace_action_items(profile_id, plan)

        st.success("Profile saved. Your dashboard has been updated.")
        st.session_state.page = "dashboard"
        st.rerun()

    if has_existing:
        st.divider()
        st.caption(f"Last updated: {profile.get('updated_at', '—')}")