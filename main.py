"""
Portfolio stress testing and scenario analysis - replays past crises (the
Global Financial Crisis, Covid-19, the 2022 rate hikes and more) and "what if"
shocks (such as "S&P 500 falls 8%" or "US 10-year yield rises 50 bp") on a
portfolio of stocks, bonds, commodities and real estate.

How to run: open this file in VS Code and click the Run button (the triangle,
top right). The first run sets everything up by itself. See README.md.

Optional, in the VS Code terminal:
    python main.py --refresh     download fresh prices instead of the saved copy
"""

# Step 1 - setup. Keep these two lines first, before any other import.
from bootstrap import ensure_ready
ensure_ready(keys=[])  # this project needs no API key

# Step 2 - the project. Everything below runs inside the project's .venv.
import sys  # noqa: E402
from datetime import datetime  # noqa: E402

import config  # noqa: E402  (imports must come after ensure_ready)
from stress import data, historical, portfolio, report, scenarios  # noqa: E402


def main():
    refresh = "--refresh" in sys.argv
    try:
        holdings = portfolio.load_portfolio(config.PORTFOLIO, config.PORTFOLIO_VALUE)
        factor_tickers = [spec["ticker"] for spec in config.FACTORS.values()]
        # dict.fromkeys removes duplicates but keeps the order
        tickers = list(dict.fromkeys(portfolio.market_tickers(holdings) + factor_tickers))
        prices = data.load_prices(tickers, config.HISTORY_START, config.CACHE_DIR,
                                  config.CACHE_MAX_AGE_HOURS, refresh=refresh)
        results = run_analysis(holdings, prices)
    except (portfolio.SettingsError, data.DataError) as error:
        print("\n" + "=" * 64 + "\n" + str(error) + "\n" + "=" * 64 + "\n")
        sys.exit(1)

    print("Report:       " + str(results["html"]))
    print("Excel file:   " + str(results["excel"]))
    print("Chart images: " + str(results["charts"]))
    if config.OPEN_REPORT_IN_BROWSER:
        report.open_in_browser(results["html"])


def run_analysis(holdings, prices):
    """All the calculations and outputs, given the holdings and a price table."""
    if config.SUMMARY_SCENARIO_MODE not in scenarios.MODES:
        raise portfolio.SettingsError("SUMMARY_SCENARIO_MODE in config.py must be "
                                      "'isolated' or 'correlated'.")

    # 1. Learn each holding's sensitivity to the market factors.
    model = scenarios.fit_factor_model(prices, holdings, config.FACTORS, config.LOOKBACK_YEARS,
                                       config.RETURN_FREQUENCY, config.MIN_WEEKS)

    # 2. Replay past crises on today's weights.
    hist = historical.replay_regimes(prices, holdings, config.REGIMES, model, config.FACTORS)

    # 3. Apply the hypothetical shocks.
    scen = scenarios.run_scenarios(holdings, model, config.SCENARIOS, config.FACTORS,
                                   config.SUMMARY_SCENARIO_MODE)

    # 4. Show and save the results.
    report.print_summary(holdings, hist, scen, model, config.SUMMARY_SCENARIO_MODE)
    meta = {"summary_mode": config.SUMMARY_SCENARIO_MODE, "last_price": prices.index[-1],
            "created": datetime.now(), "presets": config.SCENARIOS,
            "slider_ranges": config.SLIDER_RANGES}
    return report.write_outputs(config.OUTPUT_DIR, holdings, hist, scen, model,
                                config.FACTORS, meta)


if __name__ == "__main__":
    main()
