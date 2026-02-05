"""
Options Wheel Strategy Backtester - Streamlit App
Single runnable app with input screen, actions table, summary, and equity curve.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from strategy import run_wheel_backtest, build_equity_curve


st.set_page_config(page_title="Options Wheel Backtester", page_icon="📈", layout="wide")

st.title("📈 Options Wheel Strategy Backtester")
st.markdown(
    "Backtest the classic wheel: **Cash-Secured Puts** (when no shares) → **Covered Calls** (when assigned)."
)

# --- UI Screen #1: Inputs ---
st.header("Parameters")
col1, col2, col3 = st.columns(3)

with col1:
    ticker = st.text_input("Stock Ticker", value="AAPL", placeholder="e.g. AAPL, SPY")
    strike_pct = st.number_input(
        "Strike Percentage",
        min_value=0.70,
        max_value=1.00,
        value=0.95,
        step=0.01,
        format="%.2f",
        help="0.95 = 95% of Monday open price",
    )

with col2:
    start_date = st.date_input(
        "Backtest Start Date",
        value=datetime.now() - timedelta(days=365),
        max_value=datetime.now(),
    )
    end_date = st.date_input(
        "Backtest End Date",
        value=datetime.now(),
        max_value=datetime.now(),
    )

with col3:
    starting_capital = st.number_input(
        "Starting Capital ($)",
        min_value=1000,
        value=100000,
        step=5000,
        format="%d",
    )

st.markdown("---")
run_clicked = st.button("🚀 Run Backtest", type="primary")

if run_clicked:
    if not ticker or not ticker.strip():
        st.error("Please enter a stock ticker.")
    elif start_date >= end_date:
        st.error("End date must be after start date.")
    else:
        with st.spinner("Running backtest... (fetching data & computing premiums)"):
            try:
                actions_df, summary = run_wheel_backtest(
                    ticker=ticker.strip().upper(),
                    strike_percentage=strike_pct,
                    start_date=datetime.combine(start_date, datetime.min.time()),
                    end_date=datetime.combine(end_date, datetime.min.time()),
                    starting_capital=starting_capital,
                )

                if "error" in summary:
                    st.error(summary["error"])
                elif actions_df.empty:
                    st.warning("No trading actions in this date range. Try a longer period.")
                else:
                    st.success("Backtest complete.")

                    # --- Summary Section ---
                    st.header("📊 Summary")
                    s = summary
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Starting Capital", f"${s['starting_capital']:,.2f}")
                    m2.metric("Ending Balance", f"${s['ending_balance']:,.2f}")
                    ret = s["total_return_pct"]
                    m3.metric("Total Return %", f"{ret:.2f}%")
                    m4.metric(
                        "Puts / Calls Sold",
                        f"{s['puts_sold']} / {s['calls_sold']}",
                    )
                    m5, m6, m7, m8 = st.columns(4)
                    m5.metric("Assignments", s["assignments"])
                    m6.metric("Call Aways", s["call_aways"])
                    m7.metric("Shares at End", s["shares_held_at_end"])
                    m8.metric("Cash at End", f"${s['cash_at_end']:,.2f}")

                    # --- Equity Curve ---
                    st.header("📈 Equity Curve")
                    curve_df = build_equity_curve(actions_df, s["starting_capital"])
                    if not curve_df.empty:
                        curve_df = curve_df.set_index("date")
                        st.line_chart(curve_df["portfolio_value"])

                    # --- Actions Table (UI Screen #2) ---
                    st.header("📋 Actions Table")
                    display_df = actions_df.copy()
                    display_df["Date"] = display_df["date"]
                    display_df["Action"] = display_df["action"]
                    display_df["Stock Price"] = display_df["stock_price"].map("${:,.2f}".format)
                    display_df["Strike"] = display_df["strike"].map("${:,.2f}".format)
                    display_df["Premium"] = display_df["premium"].map("${:,.2f}".format)
                    display_df["Shares Held"] = display_df["shares_held"]
                    display_df["Cash Balance"] = display_df["cash_balance"].map("${:,.2f}".format)
                    display_df["Portfolio Value"] = display_df["portfolio_value"].map("${:,.2f}".format)

                    st.dataframe(
                        display_df[
                            [
                                "Date",
                                "Action",
                                "Stock Price",
                                "Strike",
                                "Premium",
                                "Shares Held",
                                "Cash Balance",
                                "Portfolio Value",
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

            except Exception as e:
                st.error(f"Error: {e}")
                import traceback
                st.code(traceback.format_exc())
