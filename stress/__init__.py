"""The stress-testing engine. main.py uses these modules in this order:

portfolio.py   reads and checks the holdings in config.py
data.py        downloads daily prices from Yahoo Finance (and caches them)
scenarios.py   fits the factor model and runs the "what if" shocks
historical.py  replays past crises on today's portfolio
report.py      prints the results, draws charts, writes HTML and Excel
"""
