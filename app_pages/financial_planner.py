"""Financial Structuring Assistant page."""

import streamlit as st
import pandas as pd
import plotly.express as px

from services import financial_planner as fp
from utils import bootstrap
from utils.helpers import money
from utils.constants import EXPENSE_CATEGORIES


def render():
    context = bootstrap.require_context()
    ratios = context["ratios"]

    st.title("💰 Financial Structuring Assistant")
    st.caption("Estimate what the business needs money for, and how it fits current cash flow — "
               "before thinking about financing.")

    st.subheader("1. How much capital do you think you need?")
    need = st.number_input("Capital requirement (₹)", min_value=0.0, value=100000.0, step=5000.0)

    st.subheader("2. Why is the money needed?")
    st.caption("Allocate the amount across categories. The total must equal 100%.")
    default_pcts = {"Inventory": 50, "Supplier payments": 20, "Rent / operating expenses": 10,
                     "Equipment": 0, "Marketing": 0, "Emergency cash buffer": 20, "Other": 0}
    pcts = {}
    cols = st.columns(2)
    for i, cat in enumerate(EXPENSE_CATEGORIES):
        with cols[i % 2]:
            pcts[cat] = st.slider(cat, 0, 100, default_pcts.get(cat, 0), key=f"alloc_{cat}")

    total_pct = sum(pcts.values())
    if total_pct != 100:
        st.warning(f"Allocation currently totals {total_pct}%. Adjust the sliders to exactly 100%.")
    else:
        allocation = fp.allocate_capital(need, pcts)
        active = {k: v for k, v in allocation.items() if v > 0}
        df = pd.DataFrame({"Use": list(active.keys()), "Amount": list(active.values())})

        c1, c2 = st.columns([1.1, 1])
        with c1:
            st.markdown("**Suggested structure**")
            st.dataframe(df.style.format({"Amount": "₹{:,.0f}"}), hide_index=True, width='stretch')
            st.metric("Total proposed capital", money(need))
        with c2:
            fig = px.pie(df, names="Use", values="Amount", hole=.45,
                         color_discrete_sequence=px.colors.sequential.Greens_r)
            fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width='stretch')

        st.divider()
        st.subheader("3. Current business position")
        c1, c2, c3 = st.columns(3)
        c1.metric("Monthly operating surplus", money(ratios["operating_surplus"]))
        c2.metric("Existing EMI", money(ratios["loan_emi"]))
        c3.metric("Current EMI burden", f"{ratios['emi_burden_ratio']*100:.1f}%")

        st.subheader("4. How will this actually be funded?")
        st.caption(
            "Not all capital needs to come from a new loan. Split the requirement across sources — "
            "only the amount you put toward a new loan will generate an EMI below."
        )
        default_credit = min(need, ratios.get("receivables", 0.0))
        fc1, fc2 = st.columns(2)
        with fc1:
            own_savings = st.number_input("From own savings / reinvestment (₹)", min_value=0.0,
                                           value=0.0, step=5000.0, key="fund_savings")
            recovered_credit = st.number_input("From recovering outstanding customer credit (₹)",
                                                min_value=0.0, value=float(round(default_credit)),
                                                step=5000.0, key="fund_credit")
        with fc2:
            supplier_credit = st.number_input("From supplier / trade credit (₹)", min_value=0.0,
                                               value=0.0, step=5000.0, key="fund_supplier")
            new_loan = st.number_input("From a new loan (₹)", min_value=0.0,
                                        value=max(0.0, need - own_savings - recovered_credit - supplier_credit),
                                        step=5000.0, key="fund_loan")

        mix = fp.funding_mix_plan(need, own_savings, recovered_credit, supplier_credit, new_loan)
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Total funded", money(mix["total_funded"]))
        mc2.metric("Share from a new loan", f"{mix['loan_share_pct']}%")
        mc3.metric("Funded from non-debt sources", f"{mix['non_debt_share_pct']}%")

        if mix["shortfall"] > 0:
            st.warning(f"This mix covers {money(mix['total_funded'])} of the {money(mix['total_need'])} "
                       f"needed — a shortfall of {money(mix['shortfall'])}. Increase one of the sources above.")
        elif mix["surplus"] > 0:
            st.caption(f"This mix funds {money(mix['surplus'])} more than the stated requirement — "
                       "consider reducing one of the sources.")
        else:
            st.success("This funding mix fully covers the stated capital requirement.")

        st.subheader("5. Affordability signal (on the loan portion only)")
        if new_loan <= 0:
            st.info("No new loan in the current mix — there is no additional EMI to evaluate.")
            afford = None
        else:
            annual_rate = st.slider("Assumed annual interest rate for the new loan (%)", 8.0, 24.0, 14.0, 0.5)
            tenure_months = st.slider("Assumed repayment tenure (months)", 6, 60, 24)
            new_emi = fp.estimate_emi(new_loan, annual_rate, tenure_months)
            st.caption(f"Estimated EMI on the {money(new_loan)} loan portion at this rate/tenure: "
                       f"{money(new_emi)}/month (illustrative only).")

            afford = fp.affordability_indicator(ratios["loan_emi"], new_emi, ratios["revenue"])
            level_icon = {"Low": "🟢", "Moderate": "🟠", "High": "🔴", "Insufficient Data": "⚪"}
            st.metric("Financial pressure level", f"{level_icon.get(afford['level'], '')} {afford['level']}",
                      f"{afford['burden_pct']}% combined EMI burden")
            st.info(afford["message"])

            st.markdown("**Repayment tradeoff — same loan, different tenures**")
            st.caption("A shorter tenure means a higher EMI but far less total interest paid overall.")
            tradeoff_rows = fp.repayment_tradeoff_table(new_loan, annual_rate)
            tdf = pd.DataFrame(tradeoff_rows).rename(columns={
                "tenure_months": "Tenure (months)", "emi": "EMI/month",
                "total_interest": "Total interest", "total_repayment": "Total repayment",
            })
            selected_row = tdf["Tenure (months)"] == tenure_months

            def _highlight_selected(row):
                return ["background-color: #dcefe6" if selected_row.iloc[row.name] else "" for _ in row]

            st.dataframe(
                tdf.style.apply(_highlight_selected, axis=1).format({
                    "EMI/month": "₹{:,.0f}", "Total interest": "₹{:,.0f}", "Total repayment": "₹{:,.0f}",
                }),
                hide_index=True, width="stretch",
            )

            st.markdown("**Rate sensitivity — same loan and tenure, different offered rates**")
            st.caption("Quoted rates vary by lender; this shows how much that gap actually costs.")
            rate_rows = fp.rate_sensitivity(new_loan, tenure_months)
            rdf = pd.DataFrame(rate_rows).rename(columns={
                "annual_rate_pct": "Annual rate", "emi": "EMI/month", "total_interest": "Total interest",
            })
            rdf["Annual rate"] = rdf["Annual rate"].map(lambda r: f"{r:.1f}%")
            st.dataframe(
                rdf.style.format({"EMI/month": "₹{:,.0f}", "Total interest": "₹{:,.0f}"}),
                hide_index=True, width="stretch",
            )

        suggested_ceiling = fp.suggested_funding_ceiling(ratios["operating_surplus"])
        st.caption(
            f"Conservative prototype signal: based on the current monthly operating surplus, "
            f"a rough ceiling to consider for the loan portion is around {money(suggested_ceiling)} "
            "unless cash flow improves."
        )

    st.divider()
    st.subheader("6. Working capital gap")
    st.caption(
        "**Working Capital Need = Recommended Operating Buffer + Essential Inventory Requirement "
        "+ Receivable Pressure − Available Cash**"
    )
    buffer_months = st.slider("Recommended operating buffer (months of expenses)", 0.5, 3.0, 1.0, 0.5)
    gap = fp.working_capital_gap(ratios, operating_buffer_months=buffer_months)

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Operating buffer", money(gap["operating_buffer"]))
    g2.metric("Essential inventory", money(gap["essential_inventory"]))
    g3.metric("Receivable pressure", money(gap["receivable_pressure"]))
    g4.metric("Available cash", f"− {money(gap['available_cash'])}")

    if gap["has_gap"]:
        st.warning(f"Estimated working capital gap: **{money(gap['gap'])}**. "
                   "This is the amount the business may need to comfortably cover buffer, "
                   "inventory, and receivable pressure beyond current cash.")
    else:
        st.success(f"Current cash appears to comfortably cover the estimated working capital need "
                   f"(surplus of {money(abs(gap['gap']))}).")

    