# Methodology

How the numbers in this repository are produced. Everything here is reproducible with the
[Prediction Spread Scanner](https://apify.com/nanare-sudo/prediction-spread-scanner?utm_source=github&utm_medium=organic&utm_campaign=pmdata_repo&utm_content=methodology) —
the code paths described below are what the Actor actually executes.

## 1. Market universes

- **Kalshi**: `GET /trade-api/v2/events` (nested markets) from the official public API. The parser accepts both the
  legacy integer-cent fields and the August-2026 `*_dollars` / `*_fp` string fields.
- **Polymarket**: Gamma API `/events` (metadata, prices, CLOB token ids) + CLOB `/book` for depth.
- Filters before matching: open markets only, optional 24h-volume and liquidity floors. Default universe: 800 markets per venue.

## 2. Three-stage matching

Naive string similarity produces confident nonsense on prediction markets ("Trump" ≠ "Trump Jr.",
"nominee" ≠ "wins election"). The scanner therefore runs three stages:

1. **Blocking** — coarse category mapping (politics, economics, crypto, sports, weather, …) plus a close-date window (±1 day by default). This cuts ~640k possible pairs to a few hundred candidates.
2. **IDF-weighted token overlap** — token scores are weighted by inverse document frequency computed over the *loaded universe*, so rare tokens ("DeSantis", "CPI") count far more than "will" or "2028". Numbers and dates must be compatible.
3. **Rule verification** — numeric thresholds, dates and entities extracted from both titles are compared; conflicts (different strike, different office, different deadline) veto the match. Optionally an LLM (bring your own key) verifies resolution-criteria equivalence. Output carries `match_confidence` (0–1) and `resolution_diff_notes` — matches below the confidence threshold are dropped, near-misses can be exported for inspection.

Verified pairs are cached in a persistent store, so repeat runs are faster and cheaper.

## 3. Executable spread ≠ price difference

For every verified pair the scanner pulls **both full orderbooks** and simulates the two possible
directions (buy YES on venue A / sell YES on venue B, and the reverse) at target order sizes
($100 and $1,000 by default):

- fills are simulated by **walking the book level by level** (no midpoint fantasy),
- **Kalshi fees** are applied per level: `fee = 0.07 · p · (1 − p)` per contract,
- Polymarket CLOB fees are currently 0 (kept as an explicit constant in the code),
- if the book is too thin for the target size, the result is flagged `depth_limited`.

The output distinguishes `gross_spread_midpoint` (what naive comparisons report) from
`executable_spread_100` / `executable_spread_1000` (what would actually remain per share).

## 4. What we observed (first public scan, 2026-08-19)

| Metric | Value |
|---|---|
| Markets loaded | 1,600 (800 per venue) |
| Candidate pairs after blocking | 312 |
| Verified matches (confidence ≥ threshold, median 0.83) | 17 |
| Median gross spread (midpoint) | $0.0045 |
| Largest gross spread | $0.0385 |
| Median executable spread @ $100 | $0.0006 |
| **Share of pairs with NEGATIVE executable spread @ $100** | **47%** |

Read that last line again before calling anything "arbitrage": almost half of the observed
cross-venue price differences disappear or go negative once you account for fees and book depth.

## 5. Known limitations

- Matching is conservative by design; equivalent pairs with very different wording can be missed.
- Resolution rules can differ in ways titles do not reveal — `resolution_diff_notes` flags what the rule check saw, it is not legal advice on contract equivalence.
- Books move; a spread observed at scan time is not a fill you can still get.
- This is **market data for research**, not trading advice, and nothing here is a profit claim.
