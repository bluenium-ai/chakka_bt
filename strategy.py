"""
Options Wheel strategy backtesting logic.
Implements Phase A (Cash-Secured Put) and Phase B (Covered Call).
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any

from data import (
    get_historical_prices,
    compute_historical_volatility,
    get_put_premium,
    get_call_premium,
    get_weekly_fridays,
)


CONTRACT_SIZE = 100  # 1 contract = 100 shares
RISK_FREE_RATE = 0.05
VOL_WINDOW = 20


def run_wheel_backtest(
    ticker: str,
    strike_percentage: float,
    start_date: datetime,
    end_date: datetime,
    starting_capital: float,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Run the Options Wheel backtest.
    Returns (actions_df, summary_dict).
    """
    # Fetch price data (extend slightly to ensure we have data for all weeks)
    buffer_start = start_date - timedelta(days=60)
    prices_df = get_historical_prices(ticker, buffer_start, end_date)

    # Get weekly Fridays (expiry days)
    fridays = get_weekly_fridays(start_date, end_date)
    if not fridays:
        return pd.DataFrame(), {"error": "No weekly expiry dates in range"}

    actions: List[Dict[str, Any]] = []
    cash = starting_capital
    shares_held = 0
    current_strike: float | None = None
    puts_sold = 0
    calls_sold = 0
    assignments = 0
    call_aways = 0

    for friday in fridays:
        # Monday of this week (entry day)
        monday = friday - timedelta(days=4)
        if monday < pd.Timestamp(buffer_start) or friday > pd.Timestamp(end_date):
            continue

        # Get Monday open and Friday close from price data
        monday_str = monday.strftime("%Y-%m-%d")
        friday_str = friday.strftime("%Y-%m-%d")

        monday_data = prices_df[prices_df.index.date == monday.date()]
        friday_data = prices_df[prices_df.index.date == friday.date()]

        if monday_data.empty or friday_data.empty:
            continue

        open_price = float(monday_data["Open"].iloc[0])
        close_price = float(friday_data["Close"].iloc[0])

        # Compute volatility for premium estimation (using history up to monday)
        hist_prices = prices_df.loc[:monday_str]["Close"]
        volatility = compute_historical_volatility(hist_prices, window=VOL_WINDOW)

        # Compute strike for this week
        strike = round(open_price * strike_percentage, 2)

        if shares_held == 0:
            # Phase A: Cash-Secured Put
            premium_per_share = get_put_premium(
                ticker, open_price, strike, friday, monday, volatility, RISK_FREE_RATE
            )
            premium_total = premium_per_share * CONTRACT_SIZE
            cash += premium_total
            puts_sold += 1
            current_strike = strike

            actions.append({
                "date": monday_str,
                "action": "Sell Put",
                "stock_price": open_price,
                "strike": strike,
                "premium": premium_total,
                "shares_held": shares_held,
                "cash_balance": cash,
                "portfolio_value": cash + shares_held * open_price,
            })

            # Friday expiry: check assignment
            if close_price < strike:
                # Assigned: buy 100 shares at strike
                cost = strike * CONTRACT_SIZE
                if cash >= cost:
                    cash -= cost
                    shares_held = CONTRACT_SIZE
                    assignments += 1
                    actions.append({
                        "date": friday_str,
                        "action": "Assigned",
                        "stock_price": close_price,
                        "strike": strike,
                        "premium": 0,
                        "shares_held": shares_held,
                        "cash_balance": cash,
                        "portfolio_value": cash + shares_held * close_price,
                    })
                else:
                    # Insufficient cash - log but cannot assign (edge case)
                    actions.append({
                        "date": friday_str,
                        "action": "Assigned (insufficient cash - skipped)",
                        "stock_price": close_price,
                        "strike": strike,
                        "premium": 0,
                        "shares_held": shares_held,
                        "cash_balance": cash,
                        "portfolio_value": cash + shares_held * close_price,
                    })
            else:
                # Put expires worthless
                pass  # Already logged Sell Put

        else:
            # Phase B: Covered Call
            premium_per_share = get_call_premium(
                ticker, open_price, strike, friday, monday, volatility, RISK_FREE_RATE
            )
            premium_total = premium_per_share * CONTRACT_SIZE
            cash += premium_total
            calls_sold += 1
            current_strike = strike

            actions.append({
                "date": monday_str,
                "action": "Sell Call",
                "stock_price": open_price,
                "strike": strike,
                "premium": premium_total,
                "shares_held": shares_held,
                "cash_balance": cash,
                "portfolio_value": cash + shares_held * open_price,
            })

            # Friday expiry: check called away
            if close_price > strike:
                # Shares called away
                proceeds = strike * CONTRACT_SIZE
                cash += proceeds
                shares_held = 0
                call_aways += 1
                current_strike = None
                actions.append({
                    "date": friday_str,
                    "action": "Called Away",
                    "stock_price": close_price,
                    "strike": strike,
                    "premium": 0,
                    "shares_held": shares_held,
                    "cash_balance": cash,
                    "portfolio_value": cash + shares_held * close_price,
                })

    # Final portfolio value (use last known prices)
    if not prices_df.empty:
        last_close = float(prices_df["Close"].iloc[-1])
        final_value = cash + shares_held * last_close
    else:
        final_value = cash + shares_held * 0

    summary = {
        "starting_capital": starting_capital,
        "ending_balance": final_value,
        "total_return_pct": ((final_value - starting_capital) / starting_capital) * 100,
        "puts_sold": puts_sold,
        "calls_sold": calls_sold,
        "assignments": assignments,
        "call_aways": call_aways,
        "shares_held_at_end": shares_held,
        "cash_at_end": cash,
    }

    # Build actions DataFrame
    actions_df = pd.DataFrame(actions) if actions else pd.DataFrame()

    return actions_df, summary


def build_equity_curve(actions_df: pd.DataFrame, starting_capital: float) -> pd.DataFrame:
    """
    Build equity curve DataFrame for charting.
    """
    if actions_df.empty:
        return pd.DataFrame({"date": [], "portfolio_value": []})

    df = actions_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    # Use portfolio_value from actions
    curve = df[["date", "portfolio_value"]].drop_duplicates(subset="date").sort_values("date")

    # Prepend starting point
    first_date = curve["date"].min()
    start_row = pd.DataFrame([{
        "date": first_date - timedelta(days=1),
        "portfolio_value": starting_capital
    }])
    curve = pd.concat([start_row, curve], ignore_index=True).sort_values("date")
    return curve
