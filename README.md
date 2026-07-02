# Northeast Deal Intel — MCP Server

Connect any MCP-compatible LLM (Claude, Cursor, Continue) to 9,400+ AI-scored commercial real estate deals and 118,000+ closed comps across the Northeast US.

## What You Can Do

Ask your LLM natural language questions like:

- *"Find industrial deals in CT over 7% cap rate under $2M"*
- *"I have a $1.4M 1031 exchange closing in 45 days. What NNN retail fits?"*
- *"Compare the cap rate on this Hartford warehouse to recent comps"*
- *"Score this deal: 215 Main St, Windsor CT, $3.2M industrial, 7.8% cap"*
- *"Score these 5 deals and rank them by investment quality"*
- *"What's the submarket profile for Hartford Metro industrial right now?"*
- *"Find Opportunity Zone deals in CT with 1031 crossover potential"*

## Tools Exposed

### Core Tools (API Key or x402)

| Tool | Description | x402 Price |
|------|-------------|------------|
| `search_deals` | Find active listings by state, type, score, price, cap rate | $0.02 |
| `get_deal` | Full deal details + scoring breakdown + sell signal | $0.02 |
| `search_comps` | 118K+ closed transactions for benchmarking | $0.03 |
| `score_deal` | Submit any deal for AI scoring | $0.10 |
| `get_market_benchmarks` | Cap rate + PSF benchmarks by state/type | $0.02 |
| `find_1031_candidates` | Ranked replacement properties for 1031 exchange | $0.05 |
| `get_sell_signal` | Sell probability for a specific listing | $0.05 |
| `get_market_summary` | State-level market overview | $0.02 |

### New x402 Pay-Per-Call Tools

| Tool | Description | x402 Price |
|------|-------------|------------|
| `get_comps` | Closed comp lookup — 118K+ records, up to 10/call | **$0.03** |
| `get_submarket_intel` | Submarket profile: cap rates, comp velocity, score dist | **$0.03** |
| `get_oz_deals` | Opportunity Zone deals + OZ+1031 crossover flags | **$0.02** |
| `find_1031_candidates` | Ranked 1031 replacement properties | **$0.05** |
| `batch_score_deals` | Score up to 10 deals in one call | **$0.05** |
| `get_access` | Pricing, tier info, x402 setup instructions | free |

## Access Options

### Option 1 — API Key Subscription (best for regular use)

| Tier | Price | Daily Limit |
|------|-------|-------------|
| Agent Starter | $49/mo | 500 req/day |
| Agent Pro | $149/mo | 5,000 req/day |
| Enterprise | $499/mo | 50,000 req/day |

→ **[Get an API key](https://northeastdealintel.com/agent-api.html)**

### Option 2 — x402 Pay-Per-Call (no subscription)

Pay in USDC on Base mainnet. No signup. No API key. Pay only for what you use.

- **Network:** Base mainnet (`eip155:8453`)
- **Pay to:** `0x24FAcafEB49b4e3FACF0B3e69604A2F4640c9bf2`
- **Discovery:** `https://api.northeastdealintel.com/.well-known/x402`

Pricing ranges from **$0.02 to $0.10 per call** depending on endpoint. Call `get_access(tier='x402')` from within your MCP client for setup details.

## Setup

### 1. Install dependencies

```bash
pip install mcp httpx
```

### 2. Configure Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "northeast-deal-intel": {
      "command": "python3",
      "args": ["/path/to/ndi_mcp_server.py"],
      "env": {
        "NDI_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

Restart Claude Desktop. You'll see NDI tools in the tool picker.

### 3. Other MCP clients

**Cursor:** Add to `.cursor/mcp.json` in your project root.

**Continue:** Add to `~/.continue/config.json` under `mcpServers`.

The server uses stdio transport — any MCP-compatible client works the same way.

## Example Conversations

**1031 Exchange**
> *"I sold a CT strip center for $1.8M and need a replacement property within 45 days. Find me NNN retail with cap rates above 7% priced between $1.5M and $2.2M."*

**Batch Portfolio Screen**
> *"Here are 8 deals I'm looking at this week. Score them all and tell me which 3 are worth pursuing."*

**Market Research**
> *"What's the average cap rate for industrial in Hartford Metro right now? How does it compare to the last 90 days of closed transactions?"*

**Opportunity Zone**
> *"Find me CT deals that qualify for both Opportunity Zone treatment and a 1031 exchange — what's the crossover inventory look like?"*

**Submarket Deep Dive**
> *"Give me the full picture on Fairfield County multifamily — active listings, comp velocity, score distribution."*

## API Reference

Base URL: `https://api.northeastdealintel.com`

x402 Discovery: `https://api.northeastdealintel.com/.well-known/x402`

OpenAPI Docs: `https://api.northeastdealintel.com/docs`

## Questions

[hello@northeastdealintel.com](mailto:hello@northeastdealintel.com) · [northeastdealintel.com](https://northeastdealintel.com)
