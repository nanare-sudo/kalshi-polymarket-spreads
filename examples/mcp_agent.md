# Use the scanners from an AI agent (MCP)

Every Apify Actor is callable through the [Apify MCP server](https://mcp.apify.com) — no custom
integration code needed. Point Claude, Cursor, or any MCP-capable agent at Apify and it can
discover and run the actors with pay-per-event billing.

## Claude Desktop / Claude Code

```json
{
  "mcpServers": {
    "apify": {
      "url": "https://mcp.apify.com/sse",
      "headers": { "Authorization": "Bearer YOUR_APIFY_TOKEN" }
    }
  }
}
```

Then ask things like:

> "Find equivalent contracts on Kalshi and Polymarket and show me the pairs where the
> executable spread at $100 order size is positive after fees."

> "Get today's Kalshi NYC high-temperature markets together with the current Central Park
> observation and the distance to each strike."

The agent will discover `nanare-sudo/prediction-spread-scanner` and
`nanare-sudo/kalshi-weather-markets` via MCP search and call them with structured input —
the input schemas are designed to be agent-friendly (one `mode` switch, sensible defaults,
no API keys for the underlying market data).

## Why this works well for agents

- **Pay-per-event pricing**: the agent pays only for the records it actually receives.
- **Free probes**: `mode: "discover"` and `mode: "canary"` cost (nearly) nothing and let the
  agent check data availability before a full run.
- **Typed output**: stable JSON schemas per record type (`match`, `spread`, `market`,
  `scan-summary`) documented in each Actor README.
