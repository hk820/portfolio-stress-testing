"""Hypothetical scenarios, such as "the S&P 500 falls 8%".

We cannot look up what happens after a shock that has not happened, so we use
a factor model:

  1. Measure a few market "factors" every week: the S&P 500, the 10-year US
     Treasury yield, oil, the US dollar and gold.
  2. For each holding, run a regression of its weekly return on the weekly
     factor moves. The slopes ("betas") say how much the holding tends to move
     when each factor moves. For example, a beta of -0.16 per 100 bp on a
     long-bond fund means it tends to lose about 16% if yields rise 1%.
  3. For a scenario, multiply the betas by the factor shocks and add up.

Two versions of every scenario are reported:
  isolated    only the factors named in the scenario move.
  correlated  the unnamed factors move by their "expected" amount given the
              named shocks, using the factors' recent covariance. This is the
              standard conditional-expectation formula:
                  other moves = Cov(other, named) x Cov(named)^-1 x named shocks
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .portfolio import CASH, SettingsError

MODES = ("isolated", "correlated")


@dataclass
class FactorModel:
    betas: pd.DataFrame          # rows: tickers, columns: factor keys (model units)
    stats: pd.DataFrame          # rows: tickers; r2, weeks
    covariance: pd.DataFrame     # factor covariance (model units)
    window: tuple                # (first date, last date) used for fitting
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------- factor data

def factor_levels(prices, factors):
    """Daily level of each factor. Yields are in percent (4.25 means 4.25%)."""
    levels = {}
    for key, spec in factors.items():
        values = prices[spec["ticker"]].astype(float)
        if spec["kind"] == "yield" and values.dropna().median() > 20:
            # Some data sources quote ^TNX as 10x the yield (42.5 = 4.25%).
            values = values / 10
        levels[key] = values
    return pd.DataFrame(levels)


def period_moves(levels, factors):
    """Move from one row to the next: decimal returns, or yield changes in bp."""
    moves = {}
    for key, spec in factors.items():
        if spec["kind"] == "yield":
            moves[key] = levels[key].diff() * 100          # percent points -> bp
        else:
            moves[key] = levels[key].pct_change(fill_method=None)
    return pd.DataFrame(moves)


def cumulative_moves(levels, factors):
    """Move from the first available value to each later row (same units)."""
    moves = {}
    for key, spec in factors.items():
        column = levels[key]
        first = column.first_valid_index()
        if first is None:
            moves[key] = pd.Series(np.nan, index=levels.index)
            continue
        base = column.loc[first]
        if spec["kind"] == "yield":
            moves[key] = (column - base) * 100
        else:
            moves[key] = column / base - 1
    return pd.DataFrame(moves)


def to_display_units(moves, factors):
    """Model units -> the units people read: % for returns, bp for yields."""
    out = moves.copy()
    for key, spec in factors.items():
        if key in out and spec["kind"] == "return":
            out[key] = out[key] * 100
    return out


# ---------------------------------------------------------------- fitting

def fit_factor_model(prices, portfolio, factors, lookback_years, frequency, min_weeks):
    """Estimate each holding's betas from the last `lookback_years` of data."""
    weekly = prices.resample(frequency).last()
    end = weekly.index[-1]
    start = end - pd.DateOffset(years=lookback_years)
    weekly = weekly.loc[weekly.index >= start - pd.Timedelta(days=7)]

    factor_moves = period_moves(factor_levels(weekly, factors), factors).iloc[1:]
    tickers = [t for t in portfolio.index if t != CASH]
    asset_returns = weekly[tickers].pct_change(fill_method=None).iloc[1:]

    betas, stats, warnings = {}, {}, []
    n_factors = len(factors)
    for ticker in tickers:
        data = pd.concat([asset_returns[ticker], factor_moves], axis=1).dropna()
        weeks = len(data)
        if weeks < n_factors + 10:
            raise SettingsError(
                "%s has only %d weeks of prices in the last %d years, too few to estimate\n"
                "its betas. Pick a fund with a longer history, or remove it from PORTFOLIO."
                % (ticker, weeks, lookback_years))
        if weeks < min_weeks:
            warnings.append("%s: betas are based on only %d weeks of data; treat its "
                            "scenario results with caution." % (ticker, weeks))

        y = data[ticker].to_numpy()
        x = np.column_stack([np.ones(weeks), data[list(factors)].to_numpy()])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)   # ordinary least squares
        residuals = y - x @ coef
        r2 = 1 - residuals.var() / y.var() if y.var() > 0 else float("nan")

        betas[ticker] = pd.Series(coef[1:], index=list(factors))  # drop the intercept
        stats[ticker] = {"r2": r2, "weeks": weeks}

    covariance = factor_moves.dropna().cov()
    return FactorModel(
        betas=pd.DataFrame(betas).T,
        stats=pd.DataFrame(stats).T,
        covariance=covariance,
        window=(factor_moves.index[0], factor_moves.index[-1]),
        warnings=warnings,
    )


# ---------------------------------------------------------------- scenarios

def shocks_in_model_units(shocks, factors):
    """Config units (% and bp) -> model units (decimals and bp)."""
    unknown = [k for k in shocks if k not in factors]
    if unknown:
        raise SettingsError("Unknown factor(s) in SCENARIOS: %s. Use one of: %s"
                            % (", ".join(unknown), ", ".join(factors)))
    return pd.Series({k: (v if factors[k]["kind"] == "yield" else v / 100)
                      for k, v in shocks.items()}, dtype=float)


def implied_factor_moves(shock, covariance, mode):
    """Full set of factor moves for a scenario, in model units."""
    moves = pd.Series(0.0, index=covariance.index)
    moves[shock.index] = shock.to_numpy()
    others = [k for k in covariance.index if k not in shock.index]
    if mode == "correlated" and others:
        named = list(shock.index)
        cov_named = covariance.loc[named, named].to_numpy()
        cov_other_named = covariance.loc[others, named].to_numpy()
        # pinv instead of inv: still works if two named factors are redundant
        moves[others] = cov_other_named @ np.linalg.pinv(cov_named) @ shock.to_numpy()
    return moves


def run_scenarios(portfolio, model, scenarios, factors, summary_mode):
    """Apply every scenario to every holding, both isolated and correlated."""
    weights = portfolio["weight"]
    value = float(portfolio["value"].sum())
    names = [s["name"] for s in scenarios]
    asset_returns = {m: pd.DataFrame(index=portfolio.index, columns=names, dtype=float)
                     for m in MODES}
    implied = pd.DataFrame(index=names, columns=list(factors), dtype=float)
    rows, warnings = [], []

    for scenario in scenarios:
        name = scenario["name"]
        shock = shocks_in_model_units(scenario["shocks"], factors)
        row = {"scenario": name, "shocks": _describe_shocks(scenario["shocks"], factors)}
        for mode in MODES:
            moves = implied_factor_moves(shock, model.covariance, mode)
            returns = model.betas[list(factors)] @ moves[list(factors)]
            if (returns < -1).any():
                # A straight-line model can "predict" losses above 100% for huge
                # shocks. A fund you own outright cannot lose more than 100%.
                warnings.append("%s (%s): some holdings capped at -100%%; the shock is far "
                                "outside the data the model learned from." % (name, mode))
                returns = returns.clip(lower=-1)
            returns = returns.reindex(portfolio.index).fillna(0.0)  # cash earns 0
            asset_returns[mode][name] = returns
            row[mode + "_return"] = float((weights * returns).sum())
            row[mode + "_pnl"] = row[mode + "_return"] * value
            if mode == "correlated":
                implied.loc[name] = moves
        rows.append(row)

    summary = pd.DataFrame(rows).set_index("scenario")
    contributions = (asset_returns[summary_mode].mul(weights, axis=0)
                     .groupby(portfolio["asset_class"], sort=False).sum().T)
    return {
        "summary": summary,
        "asset_returns": asset_returns,
        "implied_moves": to_display_units(implied, factors),
        "contributions": contributions,
        "warnings": warnings,
    }


def _describe_shocks(shocks, factors):
    parts = []
    for key, value in shocks.items():
        unit = " bp" if factors[key]["kind"] == "yield" else "%"
        parts.append("%s %+g%s" % (factors[key]["label"], value, unit))
    return "; ".join(parts)
