# Options Wheel Strategy Backtester

A backtesting application for the **Options Wheel Strategy** using Python and Streamlit.

## Quick Start

```bash
pip install streamlit yfinance pandas numpy scipy
streamlit run app.py
```

Or using a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Features

- **Phase A**: Cash-Secured Puts when no shares owned (sell put, collect premium, assign if ITM at expiry)
- **Phase B**: Covered Calls when shares owned (sell call, collect premium, called away if ITM at expiry)
- Weekly options (Friday expiry)
- Black-Scholes premium estimation (with yfinance option chain fallback when available)
- Interactive Streamlit UI with parameter inputs, actions table, summary metrics, and equity curve

## Project Structure

- `data.py` – Market data fetching (yfinance) and Black-Scholes premium estimation
- `strategy.py` – Wheel logic (put/call phases, assignment, called away)
- `app.py` – Streamlit UI

## Inputs

- **Stock Ticker** (e.g., AAPL, SPY)
- **Strike Percentage** (e.g., 0.95 = 95% of Monday open)
- **Backtest Start/End Date**
- **Starting Capital** (default 100,000)

## Outputs

- Summary: Starting/ending capital, total return %, puts/calls sold, assignments, call aways
- Equity curve chart
- Actions table with date, action, stock price, strike, premium, shares held, cash, portfolio value
