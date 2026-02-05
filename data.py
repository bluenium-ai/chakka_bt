"""
Market data module for Options Wheel backtesting.
Fetches historical prices via yfinance and estimates option premiums via Black-Scholes
when option chains are unavailable.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, Tuple


def get_historical_prices(
    ticker: str,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    """
    Fetch daily OHLCV data for a ticker using yfinance.
    Returns DataFrame with columns: Open, High, Low, Close, Volume.
    """
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, end=end_date, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No price data found for {ticker} between {start_date} and {end_date}")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def compute_historical_volatility(
    prices: pd.Series,
    window: int = 20,
    annualization_factor: float = np.sqrt(252)
) -> float:
    """
    Compute annualized historical volatility from price series.
    Uses log returns and a rolling window.
    """
    if len(prices) < 2 or window < 2:
        return 0.20  # Default 20% annual vol if insufficient data
    log_returns = np.log(prices / prices.shift(1)).dropna()
    if len(log_returns) < window:
        vol = log_returns.std()
    else:
        vol = log_returns.tail(window).std()
    if vol == 0 or np.isnan(vol):
        return 0.20
    return float(vol * annualization_factor)


def black_scholes_put(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float
) -> float:
    """
    Black-Scholes formula for European put option price.
    S = spot, K = strike, T = time to expiry (years), r = risk-free rate, sigma = vol.
    """
    from scipy.stats import norm
    if T <= 0:
        return max(0, K - S)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return max(0.0, put_price)


def black_scholes_call(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float
) -> float:
    """
    Black-Scholes formula for European call option price.
    """
    from scipy.stats import norm
    if T <= 0:
        return max(0, S - K)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return max(0.0, call_price)


def estimate_put_premium(
    stock_price: float,
    strike: float,
    expiry_date: datetime,
    valuation_date: datetime,
    volatility: float,
    risk_free_rate: float = 0.05
) -> float:
    """
    Estimate put option premium via Black-Scholes.
    Returns premium per share; multiply by 100 for 1 contract.
    """
    T = (expiry_date - valuation_date).days / 365.0
    premium_per_share = black_scholes_put(
        S=stock_price, K=strike, T=T, r=risk_free_rate, sigma=volatility
    )
    return premium_per_share


def estimate_call_premium(
    stock_price: float,
    strike: float,
    expiry_date: datetime,
    valuation_date: datetime,
    volatility: float,
    risk_free_rate: float = 0.05
) -> float:
    """
    Estimate call option premium via Black-Scholes.
    Returns premium per share; multiply by 100 for 1 contract.
    """
    T = (expiry_date - valuation_date).days / 365.0
    premium_per_share = black_scholes_call(
        S=stock_price, K=strike, T=T, r=risk_free_rate, sigma=volatility
    )
    return premium_per_share


def get_option_premium_from_chain(
    ticker: str,
    strike: float,
    expiry_date: datetime,
    option_type: str  # "put" or "call"
) -> Optional[float]:
    """
    Try to fetch option premium from yfinance option chain.
    Returns premium per share (bid+ask)/2 * 100 for contract, or None if unavailable.
    """
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return None
        # Find closest expiry to our target
        target_str = expiry_date.strftime("%Y-%m-%d")
        if target_str not in expirations:
            return None
        chain = stock.option_chain(target_str)
        opt_df = chain.puts if option_type == "put" else chain.calls
        # Find nearest strike
        opt_df = opt_df.copy()
        opt_df["strike_diff"] = abs(opt_df["strike"] - strike)
        nearest = opt_df.loc[opt_df["strike_diff"].idxmin()]
        mid = (nearest["bid"] + nearest["ask"]) / 2
        if np.isnan(mid) or mid <= 0:
            return None
        return float(mid)  # per share
    except Exception:
        return None


def get_put_premium(
    ticker: str,
    stock_price: float,
    strike: float,
    expiry_date: datetime,
    valuation_date: datetime,
    volatility: float,
    risk_free_rate: float = 0.05
) -> float:
    """
    Get put premium: try yfinance chain first, fallback to Black-Scholes.
    Returns premium per share.
    """
    chain_premium = get_option_premium_from_chain(ticker, strike, expiry_date, "put")
    if chain_premium is not None:
        return chain_premium
    return estimate_put_premium(
        stock_price, strike, expiry_date, valuation_date, volatility, risk_free_rate
    )


def get_call_premium(
    ticker: str,
    stock_price: float,
    strike: float,
    expiry_date: datetime,
    valuation_date: datetime,
    volatility: float,
    risk_free_rate: float = 0.05
) -> float:
    """
    Get call premium: try yfinance chain first, fallback to Black-Scholes.
    Returns premium per share.
    """
    chain_premium = get_option_premium_from_chain(ticker, strike, expiry_date, "call")
    if chain_premium is not None:
        return chain_premium
    return estimate_call_premium(
        stock_price, strike, expiry_date, valuation_date, volatility, risk_free_rate
    )


def get_weekly_fridays(start_date: datetime, end_date: datetime) -> list:
    """
    Return list of Friday dates (as datetime) between start and end.
    """
    fridays = []
    d = start_date
    # Move to next Friday
    while d.weekday() != 4:
        d += timedelta(days=1)
    while d <= end_date:
        fridays.append(d)
        d += timedelta(days=7)
    return fridays
