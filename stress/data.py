"""Download daily prices from Yahoo Finance and keep a copy in output/cache.

Why a cache? Downloading 15 price histories takes a while, and Yahoo limits how
often one internet connection may ask for data. So after the first successful
download the program reuses the saved file for a day.

Prices are "adjusted": dividends and bond coupons are added back in, so a
return measured from them is the total return an investor actually earned.
"""

import logging
import time
from datetime import datetime

import pandas as pd

CACHE_FILE_NAME = "prices.csv"
ATTEMPTS = 3


class DataError(Exception):
    """Prices could not be obtained. The message says what to do."""


def load_prices(tickers, start, cache_dir, max_age_hours, refresh=False):
    """Return a table of daily prices: one row per date, one column per ticker."""
    cache_file = cache_dir / CACHE_FILE_NAME
    cached = _read_cache(cache_file)

    if cached is not None and not refresh and _cache_is_usable(cached, cache_file, tickers,
                                                               start, max_age_hours):
        saved = datetime.fromtimestamp(cache_file.stat().st_mtime)
        print("Using prices saved on %s. (Type  python main.py --refresh  in the terminal"
              " to download fresh ones.)" % saved.strftime("%d %b %Y %H:%M"))
        return cached[tickers]

    print("Downloading daily prices for %d tickers from Yahoo Finance ..." % len(tickers))
    try:
        prices = _download(tickers, start)
    except DataError as error:
        # An old copy is better than nothing, as long as it has every ticker.
        if cached is not None and set(tickers) <= set(cached.columns):
            print("\nWARNING: the download failed, so the older saved prices are used instead.")
            print(str(error).splitlines()[0] + "\n")
            return cached[tickers]
        raise

    cache_dir.mkdir(parents=True, exist_ok=True)
    prices.to_csv(cache_file)
    print("Downloaded prices from %s to %s.\n"
          % (prices.index[0].strftime("%d %b %Y"), prices.index[-1].strftime("%d %b %Y")))
    return prices


# ---------------------------------------------------------------- helpers

def _download(tickers, start):
    # Imported here, not at the top, so the tests can run without yfinance
    # ever touching the internet.
    import yfinance as yf

    # yfinance prints its own alarming messages ("possibly delisted") for any
    # failure, even a dropped Wi-Fi connection. We explain problems ourselves.
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    series = {}
    missing = list(tickers)
    for attempt in range(1, ATTEMPTS + 1):
        try:
            raw = yf.download(missing, start=start, auto_adjust=True,
                              progress=False, threads=True)
        except Exception as error:  # noqa: BLE001 - any failure: retry, then explain
            print("  Download problem: %s" % error)
            raw = None

        if raw is not None and not raw.empty and "Close" in raw.columns.get_level_values(0):
            close = raw["Close"]
            if isinstance(close, pd.Series):  # older yfinance, single ticker
                close = close.to_frame(missing[0])
            for ticker in close.columns:
                values = close[ticker].dropna()
                if not values.empty:
                    series[ticker] = values

        missing = [t for t in tickers if t not in series]
        if not missing:
            break
        if attempt < ATTEMPTS:
            wait = 10 * attempt
            print("  No data yet for %s. Trying again in %d seconds ..."
                  % (", ".join(missing), wait))
            time.sleep(wait)

    if missing:
        raise DataError(
            "Yahoo Finance returned no prices for: " + ", ".join(missing) + "\n\n"
            "Possible reasons:\n"
            "  - No internet connection. Check it and run main.py again.\n"
            "  - A ticker is misspelt. Check it on https://finance.yahoo.com\n"
            "  - Yahoo is limiting requests ('Too Many Requests').\n"
            "    Wait 10-15 minutes and run again."
        )

    prices = pd.DataFrame(series)
    prices.index = _clean_dates(prices.index)
    prices = prices.sort_index()
    prices = prices[~prices.index.duplicated(keep="last")]
    # Markets close on different holidays (futures trade on some days the stock
    # market is shut). Carrying the last price forward for up to 5 days gives
    # every column a value on every date. ffill never fills the dates before a
    # ticker's first price, so a fund launched in 2010 stays empty before 2010.
    prices = prices.ffill(limit=5)
    return prices[tickers]


def _clean_dates(index):
    """Plain calendar dates without time zones, so all tickers line up."""
    index = pd.to_datetime(index)
    if index.tz is not None:
        index = index.tz_localize(None)
    return index.normalize()


def _read_cache(cache_file):
    if not cache_file.exists():
        return None
    try:
        cached = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        cached.index = _clean_dates(cached.index)
        return cached
    except (ValueError, OSError, pd.errors.ParserError):
        return None  # a damaged cache is simply downloaded again


def _cache_is_usable(cached, cache_file, tickers, start, max_age_hours):
    age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
    has_all = set(tickers) <= set(cached.columns)
    early_enough = cached.index.min() <= pd.Timestamp(start) + pd.Timedelta(days=10)
    return age_hours <= max_age_hours and has_all and early_enough
