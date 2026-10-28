"""
Settings you may change. There are no secrets in this file, and this project
needs no API key.

The three things you will most likely want to edit:
  1. PORTFOLIO  - what you hold and how much of each
  2. REGIMES    - past crises to replay on today's portfolio
  3. SCENARIOS  - "what if" shocks, such as "S&P 500 falls 8%"
"""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"   # report, charts and Excel file go here
CACHE_DIR = OUTPUT_DIR / "cache"      # downloaded prices, so reruns are fast


# ============================================================ 1. PORTFOLIO
# Each holding is a Yahoo Finance ticker. We use exchange-traded funds (ETFs)
# because each one stands in for a whole asset class and has a long price
# history, so it can be tested against crises back to 2007.
#
# "weight" is the share of the portfolio (0.30 = 30%). Weights must add up to 1.
# "CASH" is special: it is not downloaded and always returns 0%.

PORTFOLIO_VALUE = 1_000_000   # in US dollars, used to show gains and losses in $

PORTFOLIO = [
    {"ticker": "SPY",  "weight": 0.30, "asset_class": "Equities",         "name": "US large-cap stocks (S&P 500)"},
    {"ticker": "EFA",  "weight": 0.10, "asset_class": "Equities",         "name": "Developed-market stocks outside the US"},
    {"ticker": "EEM",  "weight": 0.05, "asset_class": "Equities",         "name": "Emerging-market stocks"},
    {"ticker": "IEF",  "weight": 0.15, "asset_class": "Government bonds", "name": "US Treasuries, 7-10 years"},
    {"ticker": "TLT",  "weight": 0.10, "asset_class": "Government bonds", "name": "US Treasuries, 20+ years"},
    {"ticker": "LQD",  "weight": 0.10, "asset_class": "Corporate bonds",  "name": "US investment-grade corporate bonds"},
    {"ticker": "HYG",  "weight": 0.05, "asset_class": "Corporate bonds",  "name": "US high-yield corporate bonds"},
    {"ticker": "GLD",  "weight": 0.05, "asset_class": "Commodities",      "name": "Gold"},
    {"ticker": "DBC",  "weight": 0.05, "asset_class": "Commodities",      "name": "Broad commodities (energy, metals, farm goods)"},
    {"ticker": "VNQ",  "weight": 0.03, "asset_class": "Real estate",      "name": "US real estate investment trusts"},
    {"ticker": "CASH", "weight": 0.02, "asset_class": "Cash",             "name": "Cash"},
]


# ============================================================ 2. HISTORICAL REGIMES
# A regime replay asks: "if this exact period happened again, starting today,
# what would each holding do?" We take each ETF's actual return between the
# two dates and apply it to today's weights.
#
# Most windows run from the S&P 500's closing high to its closing low, so they
# show the equity sell-off at its worst. The taper tantrum is different: it is
# the 2013 bond sell-off, when yields jumped. Check the dates yourself and
# change them if you define a crisis differently.

REGIMES = [
    {"name": "Global Financial Crisis", "start": "2007-10-09", "end": "2009-03-09",
     "about": "Housing bust, Lehman Brothers collapse, global recession."},
    {"name": "Euro debt crisis and US downgrade", "start": "2011-04-29", "end": "2011-10-03",
     "about": "Greek debt fears spread; S&P downgraded US government debt."},
    {"name": "Taper tantrum", "start": "2013-05-02", "end": "2013-06-24",
     "about": "The Fed hinted it would slow bond buying; long yields jumped."},
    {"name": "Q4 2018 Fed tightening sell-off", "start": "2018-09-20", "end": "2018-12-24",
     "about": "Rate hikes plus balance-sheet shrinking; trade-war worries."},
    {"name": "Covid-19 crash", "start": "2020-02-19", "end": "2020-03-23",
     "about": "Pandemic lockdowns; the fastest bear market on record."},
    {"name": "2022 inflation and rate hikes", "start": "2022-01-03", "end": "2022-10-12",
     "about": "Fed raised rates fast; stocks and bonds fell together."},
    {"name": "Yen carry-trade unwind", "start": "2024-07-16", "end": "2024-08-05",
     "about": "Bank of Japan hike forced investors out of yen-funded trades."},
    {"name": "2025 US tariff shock", "start": "2025-02-19", "end": "2025-04-08",
     "about": "Trade-war fears, then sweeping US tariffs on 2 April; sharp global sell-off."},
]


# ============================================================ 3. HYPOTHETICAL SCENARIOS
# A scenario is a shock to one or more market "factors" (defined below).
# Units: stock, oil, dollar and gold shocks are in percent (-8 means -8%);
# the Treasury yield shock is in basis points (50 means +0.50%).
#
# The program reports every scenario two ways:
#   isolated   - only the factors you name move; all others stay flat.
#   correlated - factors you do not name move the way they have usually moved
#                alongside your shock (for example, stocks falling often
#                comes with yields falling and the dollar rising).

SCENARIOS = [
    {"name": "S&P 500 falls 8%",                     "shocks": {"SPX": -8}},
    {"name": "S&P 500 falls 20% (bear market)",      "shocks": {"SPX": -20}},
    {"name": "US 10Y yield rises 50 bp",             "shocks": {"UST10Y": 50}},
    {"name": "US 10Y yield rises 100 bp",            "shocks": {"UST10Y": 100}},
    {"name": "US 10Y yield falls 75 bp (rate cuts)", "shocks": {"UST10Y": -75}},
    {"name": "Oil jumps 30%",                        "shocks": {"OIL": 30}},
    {"name": "US dollar strengthens 5%",             "shocks": {"USD": 5}},
    {"name": "Stagflation: stocks -10%, yields +75 bp, oil +25%",
     "shocks": {"SPX": -10, "UST10Y": 75, "OIL": 25}},
    {"name": "Flight to safety: stocks -15%, yields -60 bp, gold +8%",
     "shocks": {"SPX": -15, "UST10Y": -60, "GOLD": 8}},
]

# Which of the two versions the summary ranking at the top of the report uses.
SUMMARY_SCENARIO_MODE = "correlated"   # or "isolated"


# ============================================================ FACTOR MODEL
# The model learns how sensitive each holding is to each factor (its "beta")
# from recent weekly data. "kind" tells the program how to measure a move:
#   return - percentage change in price
#   yield  - change in the yield, in basis points
# Yahoo shows ^TNX as the 10-year yield in percent (4.25 means 4.25%).

FACTORS = {
    "SPX":    {"ticker": "^GSPC",    "kind": "return", "label": "S&P 500"},
    "UST10Y": {"ticker": "^TNX",     "kind": "yield",  "label": "US 10-year Treasury yield"},
    "OIL":    {"ticker": "BZ=F",     "kind": "return", "label": "Brent crude oil"},
    "USD":    {"ticker": "DX-Y.NYB", "kind": "return", "label": "US dollar index"},
    "GOLD":   {"ticker": "GC=F",     "kind": "return", "label": "Gold"},
}

# Range of each slider in the report's "Try your own shock" section:
# (lowest, highest, step), in the same units as SCENARIOS (% or bp).
SLIDER_RANGES = {
    "SPX":    (-40, 20, 1),
    "UST10Y": (-200, 200, 5),
    "OIL":    (-50, 50, 1),
    "USD":    (-15, 15, 0.5),
    "GOLD":   (-25, 25, 1),
}

LOOKBACK_YEARS = 5      # how many recent years the betas and correlations use
RETURN_FREQUENCY = "W-FRI"  # weekly, Friday to Friday: less noise than daily
MIN_WEEKS = 52          # fewer weeks than this and the program warns you


# ============================================================ DATA AND OUTPUT
HISTORY_START = "2007-01-01"  # first date to download; must be before every regime
CACHE_MAX_AGE_HOURS = 24      # re-download prices once they are older than this
OPEN_REPORT_IN_BROWSER = True # open the HTML report automatically when done
