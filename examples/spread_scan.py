"""Cross-venue prediction market scan: Kalshi × Polymarket matched markets + executable spreads.

Runs the Prediction Spread Scanner on Apify and loads the results into pandas.

Setup:
    pip install apify-client pandas
    export APIFY_TOKEN=...   # free account: https://console.apify.com/settings/integrations

Pricing is pay-per-event (you only pay for verified matches / orderbook pairs / signals the
run actually produces): https://apify.com/nanare-sudo/prediction-spread-scanner
"""
import os

import pandas as pd
from apify_client import ApifyClient

client = ApifyClient(os.environ["APIFY_TOKEN"])

run = client.actor("nanare-sudo/prediction-spread-scanner").call(
    run_input={
        "mode": "scan",              # load both venues, match, pull books, compute spreads
        "maxMarketsPerVenue": 800,
        "orderSizesUsd": [100, 1000],
        "spreadSignalThreshold": 0.01,
        "includeCandidates": False,   # set True to inspect near-miss pairs
    },
)

items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

matches = pd.json_normalize([r for r in items if r["type"] == "match"])
spreads = pd.json_normalize([r for r in items if r["type"] == "spread"])
summary = next(r for r in items if r["type"] == "scan-summary")

print(f"markets loaded: {summary['kalshi_markets_loaded'] + summary['polymarket_markets_loaded']}")
print(f"verified matches: {summary['verified_matches']} | signals: {summary['executable_spread_signals']}")

# The honest columns: gross vs. executable
cols = [
    "kalshi.title", "match_confidence",
    "gross_spread_midpoint", "executable_spread_100", "executable_spread_1000",
    "depth_limited", "direction",
]
print(spreads[cols].sort_values("executable_spread_100", ascending=False).head(10).to_string(index=False))

# How much of the "arbitrage" survives fees + book depth?
negative_share = (spreads["executable_spread_100"] < 0).mean()
print(f"\nshare of pairs with NEGATIVE executable spread @$100: {negative_share:.0%}")
