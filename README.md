# Northeast Deal Intel — MCP Server

Connect any MCP-compatible LLM (Claude, Cursor, Continue) to 14,000+ AI-scored commercial real estate deals and 100,000+ closed comps across the Northeast.

## What You Can Do

Ask your LLM natural language questions like:

- *"Find industrial deals in CT over 7% cap rate under $2M"*
- *"I have a $1.4M 1031 exchange closing in 45 days. What NNN retail fits?"*
- *"Compare the cap rate on this Hartford warehouse to recent comps"*
- *"Score this deal: 215 Main St, Windsor CT, $3.2M industrial, 7.8% cap"*
- *"Which CT deals have the highest sell probability right now?"*

## Tools Exposed

| Tool | Description | Tier Required |
|------|-------------|---------------|
| `search_deals` | Find active listings by state, type, score, price, cap rate | Any |
| `get_deal` | Full deal details + scoring breakdown + sell signal | Any |
| `search_comps` | 100K+ closed transactions for benchmarking | agent_starter |
| `score_deal` | Submit any deal for AI scoring | agent_pro |
| `get_market_benchmarks` | Cap rate + PSF benchmarks by state/type | Any |
| `find_1031_candidates` | Filtered search for exchange-ready deals | Any |
| `get_sell_signal` | Sell probability for a specific listing | agent_starter |
| `get_market_summary` | State-level market overview | Any |

## Setup

### 1. Get an API Key

Sign up at [northeastdealintel.com/agent-api.html](https://northeastdealintel.com/agent-api.html)

- **Agent Starter ($49/mo)** — `search_deals`, `get_deal`, `search_comps`, `get_sell_signal`, `get_market_summary`
- **Agent Pro ($149/mo)** — Everything above + `score_deal` (submit any deal for AI scoring)
- **Agent Enterprise ($499/mo)** — Full access + bulk exports + custom comp reports

### 2. Install dependencies

```bash
pip install mcp httpx
```

### 3. Configure Claude Desktop

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

Restart Claude Desktop. You'll see the NDI tools available in the tool picker.

### 4. Configure for other MCP clients

The server uses stdio transport (standard). Any MCP-compatible client works the same way — just point it at `ndi_mcp_server.py` with `NDI_API_KEY` in the environment.

**Cursor:** Add to `.cursor/mcp.json` in your project root.

**Continue:** Add to `~/.continue/config.json` under `mcpServers`.

## Example Conversations

**1031 Exchange**
> *"I sold a CT strip center for $1.8M and need a replacement property within 45 days. Find me NNN retail with cap rates above 7% priced between $1.5M and $2.2M."*

**Market Research**
> *"What's the average cap rate for industrial in Hartford vs. Fairfield County right now? Show me the top 5 deals in each submarket."*

**Deal Underwriting**
> *"Score this deal: 45 Industrial Dr, Wallingford CT. Asking $4.1M, 47,000 SF warehouse, single tenant NNN, 6.8% cap, 4 years remaining on lease."*

**Distress Hunting**
> *"Find me deals in CT with high sell probability — I'm looking for motivated sellers. Focus on industrial and multifamily."*

## API Base URL

`https://api.northeastdealintel.com`

Override with env var: `NDI_API_BASE=https://api.northeastdealintel.com`

## Questions

[hello@northeastdealintel.com](mailto:hello@northeastdealintel.com)
