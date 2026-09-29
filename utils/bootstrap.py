"""
Shared bootstrap helpers used by app.py and every page.

Centralises: DB init, session-state defaults, global CSS, and a single
`get_context()` call that returns the current profile + snapshot +
computed ratios/scores so pages don't repeat this logic.
"""

import streamlit as st

from database import db
from services import business_analysis as ba
from services import recommendation_engine as rec_engine
from utils.constants import DEMO_PROFILE, DEMO_SNAPSHOT, DEMO_PREVIOUS_SNAPSHOT
from services import inventory_service as inv_service
from services import ai_engine

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&display=swap');

:root {
  --bg: #f4f0e6;
  --surface: #ffffff;
  --surface-2: #fbf9f3;
  --border: #dcd6c6;
  --ink: #000000;
  --ink-soft: rgba(0,0,0,0.72);
  --ink-faint: rgba(0,0,0,0.55);
  --ink-on-dark: #ffffff;

  /* palette lifted from the reference swatch: deep blue -> teal -> mint -> cream */
  --navy: #2c5f8a;
  --navy-2: #336a99;
  --teal: #5fa0b8;
  --teal-soft: #e4eeec;

  --amber: #8a6a3f;
  --rose: #b0533e;
  --rose-soft: #f6e6df;

  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 22px;

  --shadow-1: 0 1px 2px rgba(28,27,23,0.05), 0 1px 1px rgba(28,27,23,0.04);
  --shadow-2: 0 8px 20px rgba(28,27,23,0.08), 0 2px 6px rgba(28,27,23,0.05);
  --shadow-3: 0 16px 40px rgba(28,27,23,0.14), 0 4px 12px rgba(28,27,23,0.08);
}

.main { background: var(--bg); }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1100px; }

body, .stApp, p, div, span, label, li {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--ink);
}

h1, h2, h3 {
  font-family: 'Source Serif 4', Georgia, serif;
  font-weight: 600;
  letter-spacing: -0.015em;
  color: var(--ink);
}

.small { color: var(--ink-faint); font-size: 0.82rem; letter-spacing: 0.01em; }

/* ---------- SIDEBAR ---------- */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--navy) 0%, #1f4060 100%);
  border-right: 1px solid rgba(0,0,0,0.2);
}
section[data-testid="stSidebar"] * { color: var(--ink-on-dark) !important; }
section[data-testid="stSidebar"] .small,
section[data-testid="stSidebar"] p { color: rgba(255,255,255,0.75) !important; }

section[data-testid="stSidebar"] .stButton > button {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: var(--radius-sm);
  text-align: left;
  font-weight: 500;
  padding: 10px 14px;
  transition: all 0.15s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(255,255,255,0.09);
  border-color: rgba(255,255,255,0.18);
  transform: translateX(2px);
}
/* active/primary sidebar item */
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--teal) 0%, var(--navy-2) 100%);
  border: none;
  color: #ffffff !important;
  box-shadow: 0 4px 14px rgba(95,160,184,0.4);
}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] * { color: #ffffff !important; }

/* ---------- HERO ---------- */
.hero {
  position: relative;
  overflow: hidden;
  padding: 34px 38px;
  border-radius: var(--radius-lg);
  background:
    radial-gradient(circle at 90% -10%, rgba(44,95,138,0.14), transparent 55%),
    radial-gradient(circle at -5% 120%, rgba(95,160,184,0.18), transparent 50%),
    linear-gradient(180deg, var(--surface) 0%, var(--surface-2) 100%);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-2);
}
.hero::before {
  content: "";
  position: absolute; top: 0; left: 0;
  width: 5px; height: 100%;
  background: linear-gradient(180deg, var(--navy), var(--teal));
}
.hero h1 {
  font-size: 2.5rem;
  margin: 10px 0 6px 0;
}

/* ---------- BADGES ---------- */
.badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 13px;
  border-radius: 999px;
  background: var(--teal-soft);
  color: var(--ink);
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: 1px solid rgba(44,95,138,0.25);
}
.badge.warn { background: var(--teal-soft); color: var(--ink); border-color: rgba(95,160,184,0.35); }
.badge.risk { background: var(--rose-soft); color: var(--ink); border-color: rgba(176,58,46,0.3); }

/* ---------- METRIC CARDS ---------- */
.metric-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 20px 22px 18px 22px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-1);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  overflow: hidden;
}
.metric-card::after {
  content: "";
  position: absolute; inset: 0 0 auto 0; height: 3px;
  background: linear-gradient(90deg, var(--navy-2), var(--teal));
  opacity: 0.9;
}
.metric-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-3); }
.metric-card .label {
  font-size: 0.8rem; color: var(--ink-faint); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.04em;
}
.metric-card .value {
  font-family: 'Source Serif 4', serif;
  font-size: 1.9rem; font-weight: 700; color: var(--ink);
  line-height: 1.15; margin-top: 4px;
}
.metric-card.negative::after { background: linear-gradient(90deg, var(--rose), var(--amber)); }

.metric-delta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: var(--ink);
}
.metric-delta.positive { background: #dcefe6; border: 1px solid rgba(47,125,92,0.25); }
.metric-delta.negative { background: var(--rose-soft); border: 1px solid rgba(176,58,46,0.25); }
.metric-delta.neutral  { background: #ece9e0; border: 1px solid rgba(0,0,0,0.1); }

/* 5-tier rating badges (score explainability, etc.) - black text throughout,
   color carried entirely by the background/border so it stays consistent
   with the rest of the app's badge system. */
.rating-badge {
  display: inline-block;
  margin-bottom: 4px;
  padding: 3px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--ink);
}
.rating-badge.excellent { background: #cdebd9; border: 1px solid rgba(31,102,68,0.3); }
.rating-badge.good      { background: var(--teal-soft); border: 1px solid rgba(95,160,184,0.35); }
.rating-badge.average   { background: #f3e6c4; border: 1px solid rgba(163,103,43,0.3); }
.rating-badge.poor      { background: #f3d6b8; border: 1px solid rgba(176,110,43,0.35); }
.rating-badge.very-poor { background: var(--rose-soft); border: 1px solid rgba(176,58,46,0.35); }

/* ---------- HYPER-LOCAL INTELLIGENCE (Opportunities page) ---------- */
.hyperlocal-status {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 16px; border-radius: 999px;
  font-weight: 700; font-size: 13px; color: var(--ink);
  margin-bottom: 14px;
}
.hyperlocal-status .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.hyperlocal-status.live { background: #dcefe6; border: 1px solid rgba(31,102,68,0.3); }
.hyperlocal-status.live .dot { background: #1f6644; }
.hyperlocal-status.fallback { background: var(--teal-soft); border: 1px solid rgba(95,160,184,0.35); }
.hyperlocal-status.fallback .dot { background: var(--navy); }

.location-chip {
  background: var(--teal-soft);
  border: 1px solid rgba(95,160,184,0.3);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  margin-top: 12px;
  font-size: 0.92rem;
}

.signal-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 14px 16px 14px 20px;
  margin-bottom: 8px;
  box-shadow: var(--shadow-1);
}
.signal-card::before {
  content: ""; position: absolute; top: 0; left: 0; bottom: 0; width: 4px;
  background: var(--teal); border-radius: var(--radius-sm) 0 0 var(--radius-sm);
}

.ai-summary-card {
  position: relative;
  background: linear-gradient(135deg, #fff 0%, var(--teal-soft) 140%);
  border: 1px solid rgba(44,95,138,0.18);
  border-radius: var(--radius-md);
  padding: 20px 24px;
  margin-bottom: 14px;
  box-shadow: var(--shadow-2);
}
.ai-summary-card::before {
  content: ""; position: absolute; top: 0; left: 0; bottom: 0; width: 4px;
  background: var(--navy); border-radius: var(--radius-md) 0 0 var(--radius-md);
}

.analysis-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px 18px;
  margin-bottom: 10px;
  box-shadow: var(--shadow-1);
}

/* ---------- PRIORITY CARD ---------- */
.priority-card {
  position: relative;
  background: linear-gradient(135deg, #fff 0%, var(--rose-soft) 130%);
  border: 1px solid rgba(176,58,46,0.18);
  border-radius: var(--radius-md);
  padding: 22px 26px;
  margin-bottom: 10px;
  box-shadow: var(--shadow-2);
}
.priority-card::before {
  content: "";
  position: absolute; top: 0; left: 0; bottom: 0; width: 4px;
  background: var(--rose);
  border-radius: var(--radius-md) 0 0 var(--radius-md);
}

/* ---------- SCHEME / GENERIC CARDS ---------- */
.scheme-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px 22px;
  box-shadow: var(--shadow-1);
  transition: box-shadow 0.15s ease;
}
.scheme-card:hover { box-shadow: var(--shadow-2); }

/* ---------- PROGRESS / HEALTH BARS ---------- */
.stProgress > div > div {
  background: linear-gradient(90deg, var(--navy-2), var(--teal)) !important;
  border-radius: 999px !important;
}
.stProgress > div { background: var(--teal-soft) !important; border-radius: 999px !important; }

hr { border: 0; border-top: 1px solid var(--border); margin: 1.6rem 0; }

[data-testid="stChatMessage"] {
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-1);
}

/* ---------- SCORE PILL (e.g. "51/100") ---------- */
.score-pill {
  font-family: 'Source Serif 4', serif;
  font-size: 3rem;
  font-weight: 700;
  color: var(--ink);
  line-height: 1;
}
</style>
"""


def apply_global_style():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def init_session_state():
    if "profile" not in st.session_state:
        st.session_state.profile = db.get_active_profile()


def load_demo_business():
    """Seed the database with the full realistic demo dataset."""
    profile_data = dict(DEMO_PROFILE)
    profile_data["is_demo"] = 1
    profile_id = db.upsert_profile(profile_data)
    db.add_snapshot(profile_id, DEMO_PREVIOUS_SNAPSHOT)
    db.add_snapshot(profile_id, DEMO_SNAPSHOT)

    db.clear_inventory(profile_id)
    for d in inv_service.load_demo_inventory():
        db.add_inventory_item(profile_id, {
            "product_name": d["product_name"],
            "category": d["category"],
            "quantity": d["quantity"],
            "purchase_price": d["purchase_price"],
            "selling_price": d["selling_price"],
            "monthly_units_sold": inv_service.moving_average(d["monthly_history"]),
            "history": d["monthly_history"],
        })

    profile = db.get_active_profile()
    snapshot = db.get_latest_snapshots(profile_id, limit=1)[0]
    ratios = ba.compute_ratios(snapshot)
    scores = ba.compute_health_score(ratios)
    ai_risk = ai_engine.score_business_risk(ratios)
    ctx = rec_engine.build_context(profile, ratios, scores)
    recs = rec_engine.generate_recommendations(ctx)
    plan = rec_engine.generate_action_plan(ctx, recs)
    db.replace_action_items(profile_id, plan)

    st.session_state.profile = profile
    return profile


def reset_demo_data():
    db.reset_all_data()
    st.session_state.profile = None


def get_context():
    """
    Returns a dict with everything a page typically needs:
    profile, snapshot, previous_snapshot, ratios, scores, ctx (LLM-safe
    structured context), recommendations, changes (what changed vs previous).
    Returns None if no profile/snapshot exists yet.
    """
    profile = st.session_state.get("profile")
    if not profile:
        return None

    snapshots = db.get_latest_snapshots(profile["id"], limit=2)
    if not snapshots:
        return None

    snapshot = snapshots[0]
    previous_snapshot = snapshots[1] if len(snapshots) > 1 else None

    ratios = ba.compute_ratios(snapshot)
    scores = ba.compute_health_score(ratios)
    ai_risk = ai_engine.score_business_risk(ratios)
    ctx = rec_engine.build_context(profile, ratios, scores)
    recommendations = rec_engine.generate_recommendations(ctx)
    changes = ba.compare_snapshots(snapshot, previous_snapshot) if previous_snapshot else []

    return {
        "profile": profile,
        "snapshot": snapshot,
        "previous_snapshot": previous_snapshot,
        "ratios": ratios,
        "scores": scores,
        "ai_risk": ai_risk,
        "ctx": ctx,
        "recommendations": recommendations,
        "changes": changes,
    }


def require_context():
    """Use at the top of a page: shows a friendly message and stops if no profile exists."""
    context = get_context()
    if context is None:
        st.info(
            "No business profile found yet. Go to **👤 Business Profile** to create one, "
            "or reload the app and choose **Load demo business**."
        )
        st.stop()
    return context