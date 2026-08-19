# Kalshi × Polymarket: matched markets and *executable* spreads

[![Data: 2026-08-19](https://img.shields.io/badge/data-2026--08--19-blue)](data/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python examples](https://img.shields.io/badge/examples-Python%20%7C%20JS%20%7C%20MCP-informational)](examples/)

Open data, code and methodology for **cross-venue prediction-market analysis**: how to find
*equivalent* contracts on Kalshi and Polymarket, and what the price difference between them is
actually worth once you walk the orderbook and pay the fees.

> **The headline finding from the first public scan: 47% of observed cross-venue spreads are
> NEGATIVE once you account for fees and orderbook depth.** A price difference is not an arbitrage.

---

## What's in here

| Path | Contents |
|---|---|
| [`data/sample_matches.csv`](data/sample_matches.csv) | 10 verified Kalshi × Polymarket pairs with match confidence |
| [`data/sample_spreads.json`](data/sample_spreads.json) | 5 pairs with gross vs. executable spreads at $100/$1,000, fees, depth flags |
| [`data/sample_weather_markets.csv`](data/sample_weather_markets.csv) | Kalshi NYC/Chicago temperature markets joined with live NWS station observations |
| [`notebooks/spread_analysis.ipynb`](notebooks/spread_analysis.ipynb) | Executed notebook: gross vs. executable spread, with chart |
| [`examples/`](examples/) | Python, JavaScript and MCP/AI-agent examples |
| [`docs/methodology.md`](docs/methodology.md) | Matching pipeline, fee model, limitations |

## The problem: string similarity is not market equivalence

Naive matching produces confident nonsense on prediction markets:

- *"Will Trump Jr. run for office?"* ≠ *"Will Trump win the election?"* — 80% token overlap, different contracts
- *"…be the Republican nominee?"* ≠ *"…win the presidency?"* — same person, different event
- *"Fed cuts by 25bp in September"* ≠ *"Fed cuts in September"* — different resolution thresholds

The pipeline used here runs three stages — **blocking** (category + close-date window),
**IDF-weighted token overlap** (rare tokens dominate), and **rule verification** (numeric
thresholds, dates, entities must be compatible; optional LLM check of resolution criteria).
Every pair carries a `match_confidence` and `resolution_diff_notes`.
[Details →](docs/methodology.md)

## The second problem: gross spread ≠ executable spread

Most "arbitrage scanners" compare two midpoints. That number is not obtainable. What actually
matters:

```
executable spread = fill price walking the real orderbook at your order size
                  − Kalshi fee (0.07 · p · (1−p) per contract, applied per level)
                  − the other leg's fill
```

First public scan (2026-08-19, 800 markets per venue):

| Metric | Value |
|---|---|
| Candidate pairs after blocking | 312 |
| Verified matches (median confidence 0.83) | 17 |
| Median **gross** spread (midpoint) | $0.0045 |
| Largest gross spread | $0.0385 |
| Median **executable** spread @ $100 | $0.0006 |
| **Pairs with negative executable spread @ $100** | **47%** |

## Quickstart

```bash
pip install apify-client pandas
export APIFY_TOKEN=...   # free account at console.apify.com
python examples/spread_scan.py
```

```python
run = client.actor("nanare-sudo/prediction-spread-scanner").call(run_input={
    "mode": "scan", "maxMarketsPerVenue": 800, "orderSizesUsd": [100, 1000],
})
spreads = pd.json_normalize([r for r in items if r["type"] == "spread"])
spreads[["kalshi.title", "gross_spread_midpoint", "executable_spread_100", "depth_limited"]]
```

More: [Python](examples/spread_scan.py) · [JavaScript](examples/spread_scan.js) ·
[Weather markets](examples/weather_markets.py) · [AI agents via MCP](examples/mcp_agent.md)

## Live / full data

The samples here are a snapshot. Current and complete normalized data comes from two pay-per-event
Actors (you pay per record produced, free discovery modes included):

- **[Prediction Spread Scanner](https://apify.com/nanare-sudo/prediction-spread-scanner?utm_source=github&utm_medium=organic&utm_campaign=pmdata_repo&utm_content=readme)** — matched markets, orderbook pairs, executable spreads
- **[Kalshi Weather Markets + Station Nowcast](https://apify.com/nanare-sudo/kalshi-weather-markets?utm_source=github&utm_medium=organic&utm_campaign=pmdata_repo&utm_content=readme)** — weather markets joined with NWS/METAR observations, settled results, candles

Both are callable from Python, JavaScript, plain HTTP, and from AI agents via
[Apify MCP](https://mcp.apify.com).

## Data sources

All official and public: [Kalshi trade API v2](https://docs.kalshi.com),
[Polymarket Gamma + CLOB](https://docs.polymarket.com),
[NWS api.weather.gov](https://api.weather.gov) and
[aviationweather.gov METAR](https://aviationweather.gov/data/api/) (US public domain).
No login scraping, no personal data.

## Disclaimer

Market **data for research**. Not trading advice, not a profit claim, not a recommendation to
trade on any venue. Observed spreads are historical observations, not obtainable fills.
Prediction-market access is restricted in many jurisdictions — check your own.

MIT licensed. Issues and PRs welcome — especially matching failure cases.
