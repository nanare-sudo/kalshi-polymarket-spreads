/**
 * Cross-venue prediction market scan from Node.js.
 *
 *   npm install apify-client
 *   export APIFY_TOKEN=...
 *
 * Actor: https://apify.com/nanare-sudo/prediction-spread-scanner
 */
import { ApifyClient } from 'apify-client';

const client = new ApifyClient({ token: process.env.APIFY_TOKEN });

const run = await client.actor('nanare-sudo/prediction-spread-scanner').call({
    mode: 'scan',
    maxMarketsPerVenue: 800,
    orderSizesUsd: [100, 1000],
    spreadSignalThreshold: 0.01,
});

const { items } = await client.dataset(run.defaultDatasetId).listItems();

const spreads = items.filter((r) => r.type === 'spread');
const summary = items.find((r) => r.type === 'scan-summary');

console.log(`verified matches: ${summary.verified_matches}, signals: ${summary.executable_spread_signals}`);

for (const s of spreads.sort((a, b) => (b.executable_spread_100 ?? -1) - (a.executable_spread_100 ?? -1)).slice(0, 5)) {
    console.log(
        `${s.kalshi.title} | conf ${s.match_confidence} | gross ${s.gross_spread_midpoint} | ` +
        `exec@$100 ${s.executable_spread_100} | depth_limited=${s.depth_limited}`,
    );
}
