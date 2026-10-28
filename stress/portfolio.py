"""Read the portfolio from config.py and check it before any work starts.

Catching a typo here (weights adding up to 0.9, a ticker listed twice) is much
kinder than a confusing error halfway through the calculations.
"""

import pandas as pd

CASH = "CASH"


class SettingsError(Exception):
    """A problem in config.py that the user must fix."""


def load_portfolio(holdings, portfolio_value):
    """Return a table with one row per holding: weight, class, name, value in $."""
    if not holdings:
        raise SettingsError("PORTFOLIO in config.py is empty.")

    table = pd.DataFrame(holdings)
    for column in ("ticker", "weight", "asset_class", "name"):
        if column not in table.columns:
            raise SettingsError("Every PORTFOLIO entry in config.py needs a '%s'." % column)

    table["ticker"] = table["ticker"].astype(str).str.strip().str.upper()
    duplicates = table["ticker"][table["ticker"].duplicated()].tolist()
    if duplicates:
        raise SettingsError("These tickers appear twice in PORTFOLIO: " + ", ".join(duplicates))

    if (table["weight"] < 0).any():
        # Short positions are possible in real life, but they make the
        # buy-and-hold replay logic misleading, so this teaching version stops.
        raise SettingsError("Weights must not be negative (short positions are not supported).")

    total = float(table["weight"].sum())
    if abs(total - 1.0) > 0.001:
        raise SettingsError(
            "The weights in PORTFOLIO add up to %.3f, but they must add up to 1.000.\n"
            "Adjust them in config.py and run again." % total
        )

    table = table.set_index("ticker")
    table["value"] = table["weight"] * portfolio_value
    return table


def market_tickers(portfolio):
    """Tickers that must be downloaded (everything except cash)."""
    return [t for t in portfolio.index if t != CASH]
