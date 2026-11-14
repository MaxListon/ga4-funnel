"""Streamlit dashboard over outputs/ (run `python -m ga4funnel.run` first).

    streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

OUT = Path(__file__).parent / "outputs"
ACCENT, MUTED, WARN = "#4b2e83", "#9aa1b2", "#b4541a"

st.set_page_config(page_title="GA4 Funnel", layout="wide")


@st.cache_data
def load():
    t = {n: pd.read_parquet(OUT / f"{n}.parquet") for n in ("funnel", "attribution", "items", "quality")}
    src = (OUT / "SOURCE").read_text().strip() if (OUT / "SOURCE").exists() else "unknown"
    return t, src


if not (OUT / "funnel.parquet").exists():
    st.error("No outputs yet. Run `python -m ga4funnel.run` first.")
    st.stop()

t, source = load()
f = t["funnel"]
q = t["quality"].set_index("check")["value"]

st.title("Google Merchandise Store: checkout funnel")
st.caption(f"GA4 sample · {q['Date range']} · source: {source}")
if source != "bigquery":
    st.warning("DEMO DATA: these numbers come from synthetic data and say nothing about the real store.")

overall = f[f.segment_type == "overall"].sort_values("step_order")
buy = overall[overall.step == "purchase"].iloc[0]
cols = st.columns(4)
cols[0].metric("Sessions", f"{int(overall.iloc[0].sessions_closed):,}")
cols[1].metric("Users", f"{int(q['Users']):,}")
cols[2].metric("Purchase sessions", f"{int(buy.sessions_open):,}")
cols[3].metric("Session conversion", f"{buy.open_rate:.2%}",
               help=f"95% CI {buy.open_rate_lo:.2%} to {buy.open_rate_hi:.2%}")

tab_funnel, tab_seg, tab_attr, tab_items, tab_dq = st.tabs(
    ["Funnel", "Compare segments", "Attribution", "Products", "Data quality"])

with tab_funnel:
    mode = st.radio("Funnel type", ["Closed (in order)", "Open (any order)"], horizontal=True)
    col = "sessions_closed" if mode.startswith("Closed") else "sessions_open"
    fig = go.Figure(go.Funnel(y=overall.step_label, x=overall[col], marker_color=ACCENT,
                              textinfo="value+percent initial+percent previous"))
    fig.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    show = overall[["step_label", "sessions_open", "sessions_closed", "step_rate", "step_rate_lo", "step_rate_hi", "lost_sessions"]]
    st.dataframe(show.style.format({"step_rate": "{:.1%}", "step_rate_lo": "{:.1%}", "step_rate_hi": "{:.1%}",
                                    "sessions_open": "{:,}", "sessions_closed": "{:,}", "lost_sessions": "{:,.0f}"}, na_rep="—"),
                 hide_index=True, use_container_width=True)

with tab_seg:
    seg_type = st.selectbox("Segment by", ["device_category", "channel", "week"],
                            format_func={"device_category": "Device", "channel": "Channel", "week": "Week"}.get)
    s = f[(f.segment_type == seg_type)]
    sizes = s[s.step == "session_start"].set_index("segment").sessions_closed
    min_n = st.slider("Hide segments with fewer sessions than", 0, 5000, 500, step=100)
    keep = sizes[sizes >= min_n].index
    s = s[s.segment.isin(keep) & (s.step != "session_start")]
    if seg_type == "week":
        conv = s[s.step == "purchase"].sort_values("segment")
        fig = go.Figure(go.Scatter(x=conv.segment, y=conv.open_rate, mode="lines+markers", line_color=ACCENT,
                                   error_y=dict(type="data", symmetric=False,
                                                array=conv.open_rate_hi - conv.open_rate,
                                                arrayminus=conv.open_rate - conv.open_rate_lo, color=MUTED)))
        fig.update_layout(yaxis_tickformat=".1%", yaxis_title="Session → purchase", height=420)
    else:
        fig = go.Figure()
        for seg in keep:
            g = s[s.segment == seg]
            fig.add_bar(name=f"{seg} (n={sizes[seg]:,})", x=g.step_label, y=g.step_rate,
                        error_y=dict(type="data", symmetric=False, array=g.step_rate_hi - g.step_rate,
                                     arrayminus=g.step_rate - g.step_rate_lo))
        fig.update_layout(barmode="group", yaxis_tickformat=".0%", yaxis_title="Step conversion (vs previous step)", height=460)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Error bars are 95% Wilson intervals. Wide bars mean the segment is too small to read much into.")

with tab_attr:
    a = t["attribution"].pivot_table(index="channel", columns="model", values="revenue_usd", aggfunc="sum").fillna(0)
    share = a.div(a.sum())
    labels = {"last_touch": "Last touch (purchasing session)", "first_touch_window": "First session in window",
              "first_user_ga4": "First user source (GA4)"}
    fig = go.Figure()
    for m, color in zip(["last_touch", "first_touch_window", "first_user_ga4"], [ACCENT, MUTED, WARN]):
        if m in share:
            fig.add_bar(name=labels[m], y=share.index, x=share[m], orientation="h", marker_color=color)
    fig.update_layout(barmode="group", xaxis_tickformat=".0%", xaxis_title="Share of revenue", height=480)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Same purchases and revenue under every model; only the credit moves.")

with tab_items:
    it = t["items"].dropna(subset=["views"])
    min_views = st.slider("Minimum product views", 0, 5000, 500, step=100)
    it = it[it.views >= min_views].sort_values("view_to_cart_rate", ascending=False)
    st.dataframe(it.style.format({"views": "{:,.0f}", "add_to_carts": "{:,.0f}", "units_purchased": "{:,.0f}",
                                  "item_revenue_usd": "${:,.0f}", "view_to_cart_rate": "{:.1%}",
                                  "units_per_cart_event": "{:.2f}"}, na_rep="—"),
                 hide_index=True, use_container_width=True)

with tab_dq:
    st.dataframe(t["quality"], hide_index=True, use_container_width=True)
