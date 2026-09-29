"""Inventory Insights page."""

from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px

from database import db
from services import inventory_service as inv_service
from utils import bootstrap
from utils.helpers import money


def render():
    context = bootstrap.require_context()
    profile = context["profile"]

    st.title("📦 Inventory Insights")
    st.caption("Track stock value, margins, and which products deserve your next restocking budget.")

    items = db.list_inventory_items(profile["id"])

    with st.expander("➕ Add a product"):
        with st.form("add_product_form"):
            c1, c2 = st.columns(2)
            with c1:
                product_name = st.text_input("Product name")
                category = st.text_input("Category", value="General")
                quantity = st.number_input("Quantity in stock", min_value=0.0, value=0.0, step=1.0)
            with c2:
                purchase_price = st.number_input("Purchase price (₹ per unit)", min_value=0.0, value=0.0, step=1.0)
                selling_price = st.number_input("Selling price (₹ per unit)", min_value=0.0, value=0.0, step=1.0)
                monthly_units_sold = st.number_input("Monthly units sold (approx.)", min_value=0.0, value=0.0, step=1.0)
            add_submitted = st.form_submit_button("Add product", type="primary")

        if add_submitted:
            if not product_name.strip():
                st.error("Please enter a product name.")
            else:
                db.add_inventory_item(profile["id"], {
                    "product_name": product_name.strip(), "category": category.strip() or "General",
                    "quantity": quantity, "purchase_price": purchase_price,
                    "selling_price": selling_price, "monthly_units_sold": monthly_units_sold,
                    "history": [],
                })
                st.success(f"Added {product_name}.")
                st.rerun()

    if not items:
        st.info("No products yet. Add your own above, or load the demo business from the home screen "
                 "to explore this page with a realistic sample catalogue.")
        return

    result = inv_service.analyze_inventory(items, forecast_context={"month": datetime.now().month})
    enriched = result["items"]

    total_stock_value = sum(i["stock_value"] for i in enriched)
    total_revenue_potential = sum(i["revenue_potential"] for i in enriched)
    avg_margin = round(sum(i["gross_margin_pct"] for i in enriched) / len(enriched), 1)

    c1, c2, c3 = st.columns(3)
    c1.metric("Estimated stock value", money(total_stock_value))
    c2.metric("Estimated revenue potential", money(total_revenue_potential))
    c3.metric("Average gross margin", f"{avg_margin}%")

    st.divider()
    tab1, tab2, tab3 = st.tabs(["📋 All products", "🚀 Top & slow movers", "💡 Suggestions"])

    with tab1:
        st.caption("Edit any cell below and click **Save changes** to update your catalogue.")

        editable_cols = ["product_name", "category", "quantity", "purchase_price",
                          "selling_price", "monthly_units_sold"]
        df = pd.DataFrame([{
            "id": i["id"],
            "Product": i["product_name"], "Category": i["category"], "Qty": i["quantity"],
            "Purchase ₹": i["purchase_price"], "Selling ₹": i["selling_price"],
            "Monthly units": i["monthly_units_sold"], "Demand est.": i["demand_estimate"],
            "Margin %": i["gross_margin_pct"], "Movement": i["movement"],
            "Stock value ₹": i["stock_value"],
        } for i in enriched])

        edited_df = st.data_editor(
            df,
            hide_index=True,
            width='stretch',
            key="inventory_editor",
            column_config={
                "id": None,  # hidden, used to map edits back to DB rows
                "Product": st.column_config.TextColumn("Product", required=True),
                "Category": st.column_config.TextColumn("Category"),
                "Qty": st.column_config.NumberColumn("Qty", min_value=0.0, step=1.0),
                "Purchase ₹": st.column_config.NumberColumn("Purchase ₹", min_value=0.0, step=1.0, format="₹%.2f"),
                "Selling ₹": st.column_config.NumberColumn("Selling ₹", min_value=0.0, step=1.0, format="₹%.2f"),
                "Monthly units": st.column_config.NumberColumn("Monthly units", min_value=0.0, step=1.0),
                "Demand est.": st.column_config.NumberColumn("Demand est.", disabled=True),
                "Margin %": st.column_config.NumberColumn("Margin %", disabled=True, format="%.1f%%"),
                "Movement": st.column_config.TextColumn("Movement", disabled=True),
                "Stock value ₹": st.column_config.NumberColumn("Stock value ₹", disabled=True, format="₹%.2f"),
            },
        )

        col_save, col_del1, col_del2 = st.columns([1, 2, 1])
        with col_save:
            if st.button("💾 Save changes", type="primary", key="save_inventory_edits"):
                original_by_id = {i["id"]: i for i in enriched}
                name_to_col = {
                    "Product": "product_name", "Category": "category", "Qty": "quantity",
                    "Purchase ₹": "purchase_price", "Selling ₹": "selling_price",
                    "Monthly units": "monthly_units_sold",
                }
                updated_count = 0
                for _, row in edited_df.iterrows():
                    item_id = row["id"]
                    original = original_by_id.get(item_id)
                    if original is None:
                        continue
                    changed_fields = {}
                    for display_col, db_col in name_to_col.items():
                        new_val = row[display_col]
                        old_val = original[db_col]
                        if db_col == "product_name" or db_col == "category":
                            if str(new_val).strip() != str(old_val):
                                changed_fields[db_col] = str(new_val).strip()
                        else:
                            try:
                                if float(new_val) != float(old_val):
                                    changed_fields[db_col] = float(new_val)
                            except (TypeError, ValueError):
                                pass
                    if changed_fields:
                        db.update_inventory_item(item_id, changed_fields)
                        updated_count += 1
                if updated_count:
                    st.success(f"Saved changes to {updated_count} product(s).")
                    st.rerun()
                else:
                    st.info("No changes to save.")
        with col_del2:
            st.download_button(
                "⬇️ Export CSV",
                data=df.drop(columns=["id"]).to_csv(index=False).encode("utf-8"),
                file_name="inventory.csv",
                mime="text/csv",
                key="export_inventory_csv",
            )

        low_stock = [i for i in enriched if i["quantity"] <= max(1.0, 0.2 * (i["monthly_units_sold"] or 1))]
        if low_stock:
            names = ", ".join(f"**{i['product_name']}**" for i in low_stock[:8])
            st.warning(f"⚠️ Low stock relative to monthly sales: {names}")

        delete_choice = st.selectbox(
            "Remove a product", ["—"] + [i["product_name"] for i in enriched], key="del_choice"
        )
        if delete_choice != "—" and st.button("Remove selected product", key="del_btn"):
            target = next(i for i in enriched if i["product_name"] == delete_choice)
            db.delete_inventory_item(target["id"])
            if "del_choice" in st.session_state:
                del st.session_state["del_choice"]
            st.rerun()

    with tab2:
        colA, colB = st.columns(2)
        with colA:
            st.markdown("**🚀 Top movers**")
            for i in result["top_movers"]:
                st.markdown(f"- **{i['product_name']}** — {i['monthly_units_sold']:.0f} units/month, "
                            f"{i['gross_margin_pct']}% margin")
        with colB:
            st.markdown("**🐢 Slow movers**")
            for i in result["slow_movers"]:
                st.markdown(f"- **{i['product_name']}** — {i['monthly_units_sold']:.0f} units/month, "
                            f"{i['gross_margin_pct']}% margin")

        fig = px.bar(
            pd.DataFrame([{"Product": i["product_name"], "Units/month": i["monthly_units_sold"],
                           "Movement": i["movement"]} for i in enriched]),
            x="Product", y="Units/month", color="Movement",
            color_discrete_map={"Fast": "#2c5f8a", "Medium": "#5fa0b8", "Slow": "#b0533e"},
        )
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, width='stretch')

    with tab3:
        if result["restock_suggestions"]:
            for s in result["restock_suggestions"]:
                st.markdown(f"💡 {s}")
        else:
            st.caption("Add more products or sales history to get restocking suggestions.")
        
        st.markdown("### Demand forecasts")
        for item in enriched:
            fc = item.get("ml_forecast", {})
            st.write(f"**{item['product_name']}** → {fc.get('forecast', 0):.1f} units next month · {fc.get('stability', 'Low')}")