"""Ain Token - Streamlit sales dashboard.

    streamlit run app.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).parent / "ventes.db"   # relative to this file, so cwd does not matter
BRAND = "#1f6feb"

SALES_QUERY = """
SELECT s.sale_id, s.sale_date, s.quantity,
       c.name AS customer, c.region, c.segment,
       p.name AS model, p.category, p.unit_price,
       s.quantity * p.unit_price AS revenue
FROM sales s
JOIN customers c ON c.customer_id = s.customer_id
JOIN products  p ON p.product_id  = s.product_id;
"""


def read_sales(db_path: Path | str = DB_PATH) -> pd.DataFrame:
    """One JOIN into a DataFrame, plus the derived date columns."""
    with sqlite3.connect(db_path) as con:
        df = pd.read_sql_query(SALES_QUERY, con)
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    df["month"] = df["sale_date"].dt.strftime("%Y-%m")
    return df


@st.cache_data
def load_data(db_path: Path | str = DB_PATH) -> pd.DataFrame:
    return read_sales(db_path)


def compute_kpis(df: pd.DataFrame) -> dict:
    """Headline numbers. mom is None when there is no previous month to compare against."""
    monthly = df.groupby("month")["revenue"].sum().sort_index()
    mom = None
    if len(monthly) >= 2 and monthly.iloc[-2]:
        mom = (monthly.iloc[-1] / monthly.iloc[-2] - 1) * 100
    return {
        "total_revenue": df["revenue"].sum(),
        "total_tokens": df["quantity"].sum(),
        "avg_invoice": df["revenue"].sum() / len(df) if len(df) else 0.0,
        "mom": mom,
    }


def main() -> None:
    st.set_page_config(page_title="Ain Token: Sales Dashboard", layout="wide")
    df = load_data()

    st.title("Ain Token: Sales Dashboard")
    st.caption("AI inference API, revenue in DA, volume in millions of tokens. "
               "Source: SQLite ventes.db")

    # ---- KPI row -----------------------------------------------------------
    k = compute_kpis(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total revenue", f"{k['total_revenue']:,.0f} DA")
    c2.metric("Tokens sold", f"{k['total_tokens']:,.0f} M tokens")
    c3.metric("Average invoice", f"{k['avg_invoice']:,.0f} DA")
    c4.metric("Latest MoM growth", "N/A" if k["mom"] is None else f"{k['mom']:+.1f}%")

    # ---- Charts 3 & 4, side by side ----------------------------------------
    left, right = st.columns(2)

    by_region = (df.groupby("region", as_index=False)["revenue"].sum()
                   .sort_values("revenue", ascending=False))
    fig_region = px.bar(by_region, x="region", y="revenue",
                        title="Revenue by region",
                        labels={"region": "Region", "revenue": "Revenue (DA)"},
                        color_discrete_sequence=[BRAND])
    fig_region.update_layout(showlegend=False)
    left.plotly_chart(fig_region, use_container_width=True)

    # horizontal bars draw the first row at the bottom -> ascending puts the best model on top
    by_model = (df.groupby("model", as_index=False)["revenue"].sum()
                  .sort_values("revenue"))
    fig_model = px.bar(by_model, x="revenue", y="model", orientation="h",
                       title="Revenue by model",
                       labels={"model": "Model", "revenue": "Revenue (DA)"},
                       color_discrete_sequence=[BRAND])
    fig_model.update_layout(showlegend=False)
    right.plotly_chart(fig_model, use_container_width=True)

    # ---- Chart 5, full width ------------------------------------------------
    by_month = (df.groupby("month", as_index=False)["revenue"].sum()
                  .sort_values("month"))
    fig_month = px.line(by_month, x="month", y="revenue", markers=True,
                        title="Monthly revenue trend",
                        labels={"month": "Month", "revenue": "Revenue (DA)"},
                        color_discrete_sequence=[BRAND])
    st.plotly_chart(fig_month, use_container_width=True)

    # ---- Raw data -----------------------------------------------------------
    with st.expander("Show raw data"):
        st.dataframe(df, use_container_width=True)


if __name__ == "__main__":   # streamlit runs the script as __main__
    main()
