"""Replay past crises on today's portfolio.

For each regime we take every holding's actual price path between the start
and end dates and ask: "if exactly this happened again, starting with today's
weights, what would the portfolio be worth along the way?"

Assumptions (worth questioning in class):
  - Buy and hold: no rebalancing and no selling during the crisis.
  - Returns include dividends and coupons (adjusted prices).
  - If a holding did not exist yet, its path is estimated from the factor model
    and the factors' actual moves in that period. The report marks these.
"""

import pandas as pd

from .portfolio import CASH
from .scenarios import cumulative_moves, factor_levels


def replay_regimes(prices, portfolio, regimes, model, factors):
    weights = portfolio["weight"]
    value = float(portfolio["value"].sum())
    levels = factor_levels(prices, factors)
    last_date = prices.index[-1]

    rows, paths, asset_returns, warnings = [], {}, {}, []
    for regime in regimes:
        name = regime["name"]
        start, end = pd.Timestamp(regime["start"]), pd.Timestamp(regime["end"])
        window = prices.loc[start:end]
        if len(window) < 2:
            warnings.append("%s: no price data between %s and %s, so it was skipped."
                            % (name, regime["start"], regime["end"]))
            continue
        if end > last_date:
            warnings.append("%s: the end date is after the latest price (%s); the replay "
                            "stops there." % (name, last_date.strftime("%d %b %Y")))

        factor_path = cumulative_moves(levels.loc[window.index], factors)
        holding_paths, estimated = {}, []
        for ticker in portfolio.index:
            if ticker == CASH:
                holding_paths[ticker] = pd.Series(1.0, index=window.index)
                continue
            p = window[ticker]
            if pd.notna(p.iloc[0]) and pd.notna(p.iloc[-1]):
                holding_paths[ticker] = (p / p.iloc[0]).ffill()
            else:
                # The fund had no prices yet: estimate its path as
                # 1 + sum over factors of (beta x factor's move since the start).
                beta = model.betas.loc[ticker]
                implied = (factor_path[beta.index].fillna(0.0) * beta).sum(axis=1)
                holding_paths[ticker] = (1 + implied).clip(lower=0.0)
                estimated.append(ticker)

        holding_paths = pd.DataFrame(holding_paths)
        portfolio_path = holding_paths.mul(weights, axis=1).sum(axis=1)
        returns = holding_paths.iloc[-1] - 1
        drawdown = (portfolio_path / portfolio_path.cummax() - 1).min()
        context = factor_path.iloc[-1]

        paths[name] = portfolio_path
        asset_returns[name] = returns
        rows.append({
            "regime": name,
            "start": window.index[0],
            "end": window.index[-1],
            "trading_days": len(window) - 1,
            "portfolio_return": float(portfolio_path.iloc[-1] - 1),
            "pnl": float(portfolio_path.iloc[-1] - 1) * value,
            "max_drawdown": float(drawdown),
            "worst_day": float(portfolio_path.pct_change(fill_method=None).min()),
            "worst_holding": returns.drop(CASH, errors="ignore").idxmin(),
            "best_holding": returns.drop(CASH, errors="ignore").idxmax(),
            "spx_move": _display(context, factors, "SPX"),
            "ust10y_move_bp": _display(context, factors, "UST10Y"),
            "estimated": ", ".join(estimated),
            "about": regime.get("about", ""),
        })
        if estimated:
            warnings.append("%s: no prices yet for %s; estimated from the factor model."
                            % (name, ", ".join(estimated)))

    summary = pd.DataFrame(rows).set_index("regime") if rows else pd.DataFrame()
    contributions = (pd.DataFrame(asset_returns).mul(weights, axis=0)
                     .groupby(portfolio["asset_class"], sort=False).sum().T) if rows else pd.DataFrame()
    return {
        "summary": summary,
        "asset_returns": pd.DataFrame(asset_returns),
        "paths": paths,
        "contributions": contributions,
        "warnings": warnings,
    }


def _display(context, factors, key):
    """A factor's move in readable units, or None if that factor is not set up."""
    if key not in factors or pd.isna(context.get(key)):
        return None
    return float(context[key] * (100 if factors[key]["kind"] == "return" else 1))
