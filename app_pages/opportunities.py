"""Schemes & Opportunities page."""

import streamlit as st

from database import db
from services import scheme_service as scheme_svc
from services import local_context_service as local_svc
from services import live_opportunity_service as live_svc
from utils import bootstrap


def render():
    context = bootstrap.require_context()
    profile = context["profile"]
    snapshot = context.get("snapshot", {})
    inventory = db.list_inventory_items(profile["id"])

    st.title("🏛 Schemes & Opportunities")

    st.caption(
        "A curated prototype directory. Always verify eligibility and current terms "
        "on the official portal before applying — this page never declares automatic eligibility."
    )

    # ============================================================
    # HYPER-LOCAL BUSINESS INTELLIGENCE
    # ============================================================

    with st.expander(
        "📍 Hyper-local Business Intelligence",
        expanded=True
    ):

        st.caption(
            "We combine live weather, live nearby commercial/community activity, curated regional signals, "
            "your inventory and financial context — then use ML to estimate opportunity and demand. "
            "ML predicts; financial rules protect; the advisor explains."
        )

        # --------------------------------------------------------
        # Refresh button
        # --------------------------------------------------------

        if st.button(
            "🔄 Refresh local intelligence",
            width="stretch"
        ):
            st.cache_data.clear()
            st.rerun()

        # --------------------------------------------------------
        # Get hyper-local intelligence
        # --------------------------------------------------------

        intel = live_svc.get_hyperlocal_opportunities(
            location=profile.get(
                "location",
                ""
            ),

            state=profile.get(
                "state",
                "Punjab"
            ),

            district=profile.get(
                "district",
                ""
            ),

            business_type=profile.get(
                "business_type",
                ""
            ),

            season=profile.get(
                "season",
                "Regular"
            ),

            local_event=profile.get(
                "local_event",
                ""
            ),
            snapshot=snapshot,
            inventory=inventory,
        )

        # ========================================================
        # INTELLIGENCE MODE
        # ========================================================

        mode = intel.get(
            "mode",
            "CURATED FALLBACK"
        )

        if mode == "LIVE + CURATED":

            st.success(
                "🟢 Intelligence mode: LIVE + CURATED"
            )

            weather = intel.get(
                "weather"
            )

            if weather:

                c1, c2, c3, c4 = st.columns(4)

                c1.metric(
                    "Temperature",
                    f"{weather['temperature']} "
                    f"{weather['temperature_unit']}"
                )

                c2.metric(
                    "Rain chance",
                    f"{weather['rain_probability']}%"
                )

                c3.metric(
                    "3-day rain",
                    f"{weather['three_day_rain_mm']} mm"
                )

                c4.metric(
                    "Wind",
                    f"{weather['wind']} "
                    f"{weather['wind_unit']}"
                )

                st.info(
                    f"📍 **{weather['location_name']}, "
                    f"{weather['admin1']}** — "
                    f"{weather['weather']} • "
                    f"Live weather: Open-Meteo"
                )

        else:

            st.warning(
                "🟡 Intelligence mode: CURATED FALLBACK — "
                "live weather is unavailable, but local intelligence "
                "remains available."
            )

            if intel.get("live_error"):

                st.caption(
                    f"Live signal status: "
                    f"{intel['live_error']}"
                )

        # ========================================================
        # LIVE NEARBY CONTEXT
        # ========================================================

        nearby = intel.get("nearby_context", {})
        if nearby.get("available"):
            st.markdown("### 🗺️ Live 5 km local context")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Mapped places", nearby.get("count", 0))
            c2.metric("Relevant nearby", nearby.get("relevant_count", 0))
            c3.metric("Local activity density", f"{nearby.get('density_per_km2', 0):.1f}/km²")
            c4.metric("Nearby markets", nearby.get("market_count", 0))
            market_km = nearby.get("nearest_market_km")
            if market_km is not None:
                st.caption(f"Nearest mapped market: ~{market_km:.2f} km • Source: OpenStreetMap / Overpass • 5 km radius")
            else:
                st.caption("Source: OpenStreetMap / Overpass • 5 km radius. Mapped places are an activity proxy, not a direct demand measurement.")
        else:
            st.caption("Live nearby-place data is unavailable right now; weather and curated signals remain active.")

        # ========================================================
        # LOCAL SIGNALS
        # ========================================================

        st.markdown(
            "### 🔎 Local signals being analysed"
        )

        signals = intel.get(
            "signals",
            []
        )

        if signals:

            for signal in signals:

                signal_type = signal.get(
                    "type",
                    "Local signal"
                )

                signal_name = signal.get(
                    "signal",
                    "Local activity"
                )

                implication = signal.get(
                    "implication",
                    ""
                )

                st.markdown(
                    f"**{signal_type} — {signal_name}**"
                )

                if implication:

                    st.caption(
                        implication
                    )

        else:

            st.info(
                "No specific local signals were matched "
                "for the current profile."
            )

        # ========================================================
        # MODEL-DRIVEN OPPORTUNITY SCORE
        # ========================================================

        ml = intel.get("ml_opportunity", {})
        if ml:
            st.markdown("### 🧠 ML Opportunity Signal")
            c1, c2, c3 = st.columns(3)
            c1.metric("Opportunity probability", f"{ml.get('probability', 0):.1f}%")
            c2.metric("Model assessment", ml.get("label", "Unknown"))
            c3.metric("Model", "Random Forest")
            st.caption(
                "The model combines live weather, live nearby activity, regional signals, inventory and financial context. "
                "Prototype training uses transparent scenario data; production deployment should retrain it on anonymised real outcomes."
            )
            with st.expander("🔎 What influenced this AI score?", expanded=False):
                features = intel.get("model_features", {})
                st.write({k: round(v, 2) if isinstance(v, (int, float)) else v for k, v in features.items()})
                st.caption("These are model inputs, not proof of causation. Nearby OpenStreetMap activity is used as a local-context proxy.")

        # ========================================================
        # AI → INVENTORY ACTIONS
        # ========================================================

        inventory_actions = intel.get("inventory_actions", [])
        st.markdown("### 📦 AI → Inventory actions")
        if inventory_actions:
            st.caption("These actions connect the local/ML signal to products actually present in this shop.")
            for action in inventory_actions:
                st.markdown(f"**{action['product']}** — forecast {action['forecast']:.1f} units vs {action['current_stock']:.1f} in stock → potential gap **{action['gap']:.1f} units**")
                if action.get("estimated_cost", 0) > 0:
                    st.caption(f"Estimated purchase cost for the gap: ₹{action['estimated_cost']:,.0f}")
                with st.expander("Why did the model suggest this?", expanded=False):
                    for reason in action.get("reason", []):
                        st.write(f"• {reason}")
        else:
            st.success("No product currently needs an AI-driven restocking action based on the available signals. That is also a valid recommendation.")

        # ========================================================
        # AI BUSINESS ANALYSIS
        # ========================================================

        st.markdown(
            "### 🤖 AI Business Analysis"
        )

        analysis = intel.get(
            "analysis",
            {}
        )

        if analysis:

            # ----------------------------------------------------
            # Executive summary
            # ----------------------------------------------------

            summary = analysis.get(
                "summary",
                ""
            )

            if summary:

                st.info(
                    f"📊 **AI Summary**\n\n"
                    f"{summary}"
                )

            # ----------------------------------------------------
            # Detailed analysis
            # ----------------------------------------------------

            detailed_analysis = analysis.get(
                "analysis",
                []
            )

            if detailed_analysis:

                st.markdown(
                    "#### 🔎 Detailed Analysis"
                )

                for point in detailed_analysis:

                    st.markdown(
                        f"• {point}"
                    )

            # ----------------------------------------------------
            # Opportunities
            # ----------------------------------------------------

            opportunities = analysis.get(
                "opportunities",
                []
            )

            if opportunities:

                st.markdown(
                    "#### 📈 Potential Opportunities"
                )

                for opportunity in opportunities:

                    st.markdown(
                        f"• **{opportunity}**"
                    )

            # ----------------------------------------------------
            # Recommended actions
            # ----------------------------------------------------

            recommended_actions = analysis.get(
                "recommended_actions",
                []
            )

            if recommended_actions:

                st.markdown(
                    "#### 💡 What the Shopkeeper Should Do"
                )

                for index, action in enumerate(
                    recommended_actions,
                    start=1
                ):

                    st.markdown(
                        f"**{index}.** {action}"
                    )

            # ----------------------------------------------------
            # Timing
            # ----------------------------------------------------

            timing = analysis.get(
                "timing",
                []
            )

            if timing:

                st.markdown(
                    "#### 🗓️ Recommended Timing"
                )

                for item in timing:

                    st.markdown(
                        f"• {item}"
                    )

            # ----------------------------------------------------
            # Risks
            # ----------------------------------------------------

            risks = analysis.get(
                "risks",
                []
            )

            if risks:

                st.markdown(
                    "#### ⚠️ Risks & Things to Watch"
                )

                for risk in risks:

                    st.markdown(
                        f"• {risk}"

                    )

        else:

            # This happens if the live opportunity service
            # has not yet been updated to return "analysis".

            st.info(
                "Detailed business analysis is not available yet. "
                "The local signals above are still available."
            )

        # ========================================================
        # GENERAL SUGGESTIONS
        # ========================================================

        suggestions = intel.get(
            "suggestions",
            []
        )

        if suggestions:

            st.markdown(
                "#### 📌 Quick Actions"
            )

            for suggestion in suggestions:

                st.markdown(
                    f"• {suggestion}"
                )

        # ========================================================
        # SOURCE / DISCLAIMER
        # ========================================================

        st.caption(
            f"Updated: {intel.get('updated_at', '—')} • "
            f"Sources: {intel.get('source', '—')}. "
            "These are decision-support signals, not guaranteed sales forecasts."
        )

    # ============================================================
    # SCHEMES SECTION
    # ============================================================

    schemes = scheme_svc.load_schemes()

    categories = [
        "All"
    ] + scheme_svc.all_categories(
        schemes
    )

    c1, c2 = st.columns(2)

    with c1:

        category = st.selectbox(
            "Filter by category",
            categories
        )

    with c2:

        show_only_relevant = st.checkbox(
            f"Show only schemes relevant to "
            f"{profile.get('business_type', 'my business')}",
            value=True
        )

    business_filter = (
        profile.get(
            "business_type",
            "All"
        )
        if show_only_relevant
        else "All"
    )

    filtered = scheme_svc.filter_schemes(
        schemes,
        category=category,
        business_type=business_filter
    )

    bookmarks = set(
        db.list_bookmarks(
            profile["id"]
        )
    )

    if not filtered:

        st.info(
            "No schemes match the current filters."
        )

    # ============================================================
    # SCHEME CARDS
    # ============================================================

    for scheme in filtered:

        with st.container(
            border=True
        ):

            c1, c2 = st.columns(
                [3, 1]
            )

            with c1:

                st.markdown(
                    f"**{scheme['scheme_name']}**"
                )

                st.caption(
                    f"{scheme['category']} • "
                    f"{scheme.get('target_location', 'All India')}"
                )

                st.write(
                    scheme["description"]
                )

                st.markdown(
                    f"**Why this may be relevant:** "
                    f"{scheme['why_relevant']}"
                )

                st.caption(
                    "✅ Potentially relevant — verify eligibility. "
                    f"What to check: {scheme['eligibility_note']}"
                )

                st.caption(
                    "Last verified in this prototype dataset: "
                    f"{scheme.get('last_verified', '—')}"
                )

            with c2:

                st.link_button(
                    "Open official source",
                    scheme["official_url"],
                    width="stretch"
                )

                is_bookmarked = (
                    scheme["scheme_name"]
                    in bookmarks
                )

                label = (
                    "★ Saved"
                    if is_bookmarked
                    else "☆ Save"
                )

                if st.button(
                    label,
                    key=f"bm_{scheme['scheme_name']}",
                    width="stretch"
                ):

                    db.toggle_bookmark(
                        profile["id"],
                        scheme["scheme_name"]
                    )

                    st.rerun()