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
# Colors from Ain_Token_BI.pptx; chart green is brighter for contrast on dark surfaces.
BRAND, SURFACE, TEXT, MUTED = "#35A780", "#102E2E", "#F2F7F5", "#B2C9C0"
CSS = """
<style>
:root { --bg: #0B2121; --surface: #102E2E; --mint: #BDFADE;
        --ink: #F2F7F5; --muted: #B2C9C0; --border: #244543; }
.stApp, [data-testid="stHeader"] { background: var(--bg); color: var(--ink); }
.stMainBlockContainer { max-width: 1480px; padding-top: 3rem; padding-bottom: 2rem; }
h1 { color: var(--ink); letter-spacing: -.035em; font-weight: 650; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p,
[data-testid="stMetricLabel"] { color: var(--muted) !important; }
[data-testid="stMetric"] { background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 20px; min-height: 132px; }
[data-testid="stMetricValue"] { color: var(--mint); font-size: clamp(1.35rem, 2.2vw, 2rem); }
[data-testid="stLayoutWrapper"]:has(> [data-testid="stVerticalBlock"]) {
    border-color: var(--border) !important; border-radius: 16px; }
[data-testid="stExpander"] { background: var(--surface); border-color: var(--border); }
.eyebrow { color: var(--mint); font-size: .8rem; font-weight: 600;
    letter-spacing: .14em; margin-bottom: .6rem; }
@media (max-width: 640px) {
    .stMainBlockContainer { padding: 4.5rem 1rem 2rem; }
    h1 { font-size: 2rem !important; }
    [data-testid="stMetric"] { min-height: 112px; padding: 16px; }
}
</style>
"""

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


def style_chart(fig, height=320):
    """One chart style keeps typography, tooltips and axes consistent."""
    fig.update_layout(template="plotly_dark", height=height, showlegend=False,
                      paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
                      font=dict(family="Calibri, Segoe UI, sans-serif", color=TEXT, size=13),
                      margin=dict(l=16, r=24, t=24, b=16),
                      hoverlabel=dict(bgcolor="#244543", font_color=TEXT))
    fig.update_xaxes(gridcolor="#244543", zeroline=False, tickfont_color=MUTED)
    fig.update_yaxes(gridcolor="#244543", zeroline=False, tickfont_color=MUTED)
    return fig


def main() -> None:
    st.set_page_config(page_title="Ain Token: Sales Dashboard", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">AIN TOKEN / BUSINESS INTELLIGENCE</div>', unsafe_allow_html=True)
    df = load_data()

    st.title("Ain Token: Sales Dashboard")
    st.caption("AI inference API, revenue in DA, volume in millions of tokens. "
               "Source: SQLite ventes.db")

    # ---- KPI row -----------------------------------------------------------
    k = compute_kpis(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total revenue", f"{k['total_revenue']:,.0f} DA")
    c2.metric("Tokens sold", f"{k['total_tokens']:,.0f} M tokens")
    c3.metric("Average invoice value", f"{k['avg_invoice']:,.0f} DA",
              help="Total revenue divided by the number of invoices.")
    c3.caption(f"{k['total_revenue']:,.0f} DA ÷ {len(df):,} invoices")
    c4.metric("MoM revenue growth", "N/A" if k["mom"] is None else f"{k['mom']:+.1f}%",
              help="(Latest month revenue − previous month revenue) ÷ previous month revenue × 100.")
    monthly = df.groupby("month")["revenue"].sum().sort_index()
    if k["mom"] is not None:
        previous, latest = monthly.index[-2:]
        c4.caption(f"{pd.Timestamp(latest):%b %Y} vs {pd.Timestamp(previous):%b %Y}: "
                   f"{monthly.iloc[-1]:,.0f} vs {monthly.iloc[-2]:,.0f} DA")
    else:
        c4.caption("No comparable previous month revenue available.")

    if df.empty:
        st.info("No invoices available. Run create_db.py to populate the dashboard.")
        return
    st.caption(f"{df.sale_date.min():%b %Y} – {df.sale_date.max():%b %Y}  ·  "
               f"{len(df):,} invoices  ·  {df.customer.nunique()} clients  ·  "
               f"{df.model.nunique()} hosted models  ·  Fictional demonstration data")

    # Regional and model comparisons share one revenue color and explicit labels.
    left, right = st.columns(2)
    by_region = df.groupby("region", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
    by_model = df.groupby("model", as_index=False)["revenue"].sum().sort_values("revenue")
    with left, st.container(border=True):
        st.subheader("Revenue by region")
        leader = by_region.iloc[0]
        st.caption(f"{leader.region} leads with {leader.revenue / k['total_revenue']:.1%} of total revenue.")
        fig = px.bar(by_region, x="region", y="revenue", text_auto=".3s",
                     labels={"region": "Region", "revenue": "Revenue (DA)"}, color_discrete_sequence=[BRAND])
        fig.update_traces(width=.16, textposition="outside", cliponaxis=False,
                          hovertemplate="%{x}<br>%{y:,.0f} DA<extra></extra>")
        fig.update_layout(barcornerradius=4)
        st.plotly_chart(style_chart(fig), width="stretch", theme=None, config={"displayModeBar": False})

    with right, st.container(border=True):
        st.subheader("Top models")
        st.caption(f"{by_model.iloc[-1].model} is the highest-earning hosted model.")
        fig = px.bar(by_model, x="revenue", y="model", orientation="h", text_auto=".3s",
                     labels={"model": "", "revenue": "Revenue (DA)"}, color_discrete_sequence=[BRAND])
        fig.update_traces(width=.32, textposition="outside", cliponaxis=False,
                          hovertemplate="%{y}<br>%{x:,.0f} DA<extra></extra>")
        fig.update_xaxes(range=[0, by_model.revenue.max() * 1.25])
        fig.update_layout(barcornerradius=4)
        st.plotly_chart(style_chart(fig), width="stretch", theme=None, config={"displayModeBar": False})

    by_month = df.groupby("month", as_index=False)["revenue"].sum().sort_values("month")
    with st.container(border=True):
        st.subheader("Monthly revenue trend")
        peak = by_month.loc[by_month.revenue.idxmax()]
        st.caption(f"Peak month: {pd.Timestamp(peak.month):%B %Y} · {peak.revenue:,.0f} DA")
        fig = px.line(by_month, x="month", y="revenue", markers=True,
                      labels={"month": "Month", "revenue": "Revenue (DA)"}, color_discrete_sequence=[BRAND])
        fig.update_traces(line_width=2, marker=dict(size=9, line=dict(width=2, color=SURFACE)),
                          fill="tozeroy", fillcolor="rgba(53,167,128,.10)",
                          hovertemplate="%{x}<br>%{y:,.0f} DA<extra></extra>")
        fig.update_xaxes(type="category", tickmode="array", tickvals=by_month.month,
                         ticktext=pd.to_datetime(by_month.month).dt.strftime("%b %Y"),
                         showgrid=False, showspikes=True, spikemode="across", spikesnap="cursor")
        fig.update_yaxes(rangemode="tozero")
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(style_chart(fig, 300), width="stretch", theme=None, config={"displayModeBar": False})

    with st.expander("Show raw data"):
        st.dataframe(df, width="stretch", hide_index=True)
        st.download_button("Download invoices as CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           file_name="ain_token_invoices.csv", mime="text/csv")


if __name__ == "__main__":   # streamlit runs the script as __main__
    main()
