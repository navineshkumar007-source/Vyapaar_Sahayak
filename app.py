"""
Vyapaar Sahayak — entry point.

Handles: page config, DB init, global styling, first-run onboarding
(Load demo business / Create my own business), sidebar navigation, and
dispatch to the selected page module.

NOTE ON ROUTING: page navigation is keyed by plain, stable string IDs
(e.g. "dashboard"), never by the emoji-decorated display label. This is
deliberate — display labels can be edited, retyped, or mangled by an
editor's encoding at any time without breaking navigation.
"""

import importlib

import streamlit as st
from dotenv import load_dotenv

from database import db
from utils import bootstrap
from utils.constants import APP_NAME, DISCLAIMER

load_dotenv()

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Boot sequence -----------------------------------------------------
try:
    db.init_db()
except Exception as e:
    st.error("We couldn't set up the local database. Please check the app's file permissions and reload.")
    st.caption(f"Technical detail: {e}")
    st.stop()

bootstrap.init_session_state()
bootstrap.apply_global_style()

# IMPORTANT: Page modules live in app_pages/, not Streamlit's special pages/ directory. This prevents Streamlit from auto-registering them as a second multipage navigation system. The custom sidebar below is the single source of truth for navigation.
# --- Page registry: stable "key" for routing, "label" only for display ---
PAGES = [
    {"key": "dashboard", "label": "🏠 Dashboard", "module": "app_pages.dashboard"},
    {"key": "business_insights", "label": "📊 Business Analysis", "module": "app_pages.business_insights"},
    {"key": "ai_advisor", "label": "🤖 Ask Vyapaar Sahayak", "module": "app_pages.ai_advisor"},
    {"key": "financial_planner", "label": "💰 Financial Planner", "module": "app_pages.financial_planner"},
    {"key": "inventory_insights", "label": "📦 Inventory Insights", "module": "app_pages.inventory_insights"},
    {"key": "opportunities", "label": "🏛 Opportunities", "module": "app_pages.opportunities"},
    {"key": "weekly_action_plan", "label": "📅 Action Plan", "module": "app_pages.weekly_action_plan"},
    {"key": "business_profile", "label": "👤 Business Profile", "module": "app_pages.business_profile"},
]
PAGE_MODULES = {p["key"]: importlib.import_module(p["module"]) for p in PAGES}
DEFAULT_PAGE_KEY = "dashboard"

if "page" not in st.session_state or st.session_state.page not in PAGE_MODULES:
    st.session_state.page = DEFAULT_PAGE_KEY

profile = st.session_state.profile

# --- First-run onboarding ------------------------------------------------
if profile is None:
    st.markdown(f"""
    <div class="hero">
      <span class="badge">AI BUSINESS SAHAYAK</span>
      <h1> Meet Your Business Sahayak 🙏</h1>
      <p style="font-size:1.08rem">{APP_NAME} turns simple business numbers into clear, practical
      actions — without requiring an accountant.</p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    st.info(
        "Start by loading a realistic demo business to explore the full app instantly, "
        "or Create your own profile from scratch."
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button(" Load demo business (Rehan Ahmed's Tailor Shop)", width='stretch', type="primary"):
            bootstrap.load_demo_business()
            st.session_state.page = "dashboard"
            st.rerun()
    with c2:
        if st.button("Create my own business", width='stretch'):
            st.session_state.profile = {}  # sentinel: "creating, not yet saved"
            st.session_state.page = "business_profile"
            st.rerun()
    st.stop()

# --- Sidebar navigation ---------------------------------------------------
with st.sidebar:
    st.markdown(f"## 🌾 {APP_NAME}")
    st.caption("A Practical Business Sathi For Micro-Entrepreneurs")
    st.divider()

    for p in PAGES:
        is_active = st.session_state.page == p["key"]
        if st.button(p["label"], width='stretch',
                     type="primary" if is_active else "secondary", key=f"nav_{p['key']}"):
            st.session_state.page = p["key"]
            st.rerun()

    st.divider()
    if profile:
        st.caption(f"Active business: **{profile.get('name','—')}**")
    if st.button("♻️ Reset demo data", width='stretch', key="reset_demo"):
        st.session_state["confirm_reset"] = True
    if st.session_state.get("confirm_reset"):
        st.warning("This clears all saved data (profile, inventory, chat, action plan).")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("Yes, reset", width='stretch', key="confirm_reset_yes"):
                bootstrap.reset_demo_data()
                st.session_state["confirm_reset"] = False
                st.rerun()
        with cc2:
            if st.button("Cancel", width='stretch', key="confirm_reset_no"):
                st.session_state["confirm_reset"] = False
                st.rerun()

# --- Page dispatch ---------------------------------------------------------
active_key = st.session_state.page
if active_key not in PAGE_MODULES:
    active_key = DEFAULT_PAGE_KEY
    st.session_state.page = active_key

PAGE_MODULES[active_key].render()

st.markdown("---")
st.caption(f"{APP_NAME} • {DISCLAIMER}")