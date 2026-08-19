"""Kalshi weather markets joined with live NWS/METAR station observations.

Each record carries the market (bid/ask/last, strike) plus the current temperature at the
settlement station and `distance_to_strike_f` = station °F minus strike.

Setup:
    pip install apify-client pandas
    export APIFY_TOKEN=...

Actor: https://apify.com/nanare-sudo/kalshi-weather-markets
"""
import os

import pandas as pd
from apify_client import ApifyClient

client = ApifyClient(os.environ["APIFY_TOKEN"])

run = client.actor("nanare-sudo/kalshi-weather-markets").call(
    run_input={
        "mode": "markets",
        "seriesTickers": [],        # empty = auto-discover all ~350 weather series
        "cityFilter": "NYC",        # or "Chicago", "rain", "London", ...
        "includeNowcast": True,
    },
)

df = pd.json_normalize(list(client.dataset(run["defaultDatasetId"]).iterate_items()))

cols = ["ticker", "title", "last_price", "yes_bid", "yes_ask",
        "nowcast.temp_f", "nowcast.temp_trend_3h_f", "distance_to_strike_f", "close_time"]
print(df[cols].sort_values("distance_to_strike_f").to_string(index=False))

# Example research question: how does market probability relate to distance-to-strike right now?
print(df[["last_price", "distance_to_strike_f"]].corr())

# Backtesting? mode="settled" returns resolved markets with results,
# mode="candlesticks" returns full price history per market.
