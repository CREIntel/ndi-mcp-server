#!/usr/bin/env python3
"""
Northeast Deal Intel — MCP Server
Exposes NDI deal data, scoring, comps, and market intelligence to any MCP-compatible LLM client
(Claude Desktop, Cursor, Continue, etc.)

Usage (stdio transport — standard for Claude Desktop):
  python3 ndi_mcp_server.py

Config in Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "northeast-deal-intel": {
        "command": "python3",
        "args": ["/path/to/ndi_mcp_server.py"],
        "env": { "NDI_API_KEY": "your_api_key_here" }
      }
    }
  }

Required env vars:
  NDI_API_KEY   — your Northeast Deal Intel API key (agent_starter tier min)
                  OR omit to use x402 pay-per-call (USDC on Base mainnet)
  NDI_API_BASE  — API base URL (default: https://api.northeastdealintel.com)

Pay-per-call (x402):
  New endpoints support x402 micropayments — no API key required.
  Pay in USDC on Base mainnet. Set NDI_X402_PRIVATE_KEY to enable.
  See: https://northeastdealintel.com/agent-api.html
"""

import os, sys, json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ─── Config ──────────────────────────────────────────────────────────────────

API_KEY  = os.environ.get("NDI_API_KEY", "")
API_BASE = os.environ.get("NDI_API_BASE", "https://api.northeastdealintel.com").rstrip("/")

server = Server("northeast-deal-intel")

# ─── HTTP helpers ─────────────────────────────────────────────────────────────

ACCESS_MSG = """\
NDI_API_KEY not set or invalid.

To use this MCP server you have two options:

OPTION 1 — API Key subscription (best for regular use):
  Agent Starter  $49/mo  — full tool access, 500 req/day
  Agent Pro      $149/mo — everything + batch scoring + bulk comps
  → Get a key: https://northeastdealintel.com/agent-api.html

OPTION 2 — Pay-per-call via x402 (no subscription needed):
  Pay in USDC on Base mainnet. Set NDI_X402_PRIVATE_KEY env var.
  Pricing: search $0.02 · comps $0.03 · score $0.10 · 1031-match $0.05
  → Docs: https://northeastdealintel.com/agent-api.html#x402

After purchase you'll receive your NDI_API_KEY by email.
Add it to your MCP config: { "env": { "NDI_API_KEY": "ndi_sk_..." } }

Call get_access() for full setup instructions.\
"""


def ndi_get(path: str, params: dict = None) -> dict:
    """Call the NDI API and return parsed JSON."""
    if not API_KEY:
        return {"error": ACCESS_MSG}
    url = f"{API_BASE}{path}"
    headers = {"X-API-Key": API_KEY, "Accept": "application/json"}
    try:
        r = httpx.get(url, params=params or {}, headers=headers, timeout=30)
        if r.status_code == 402:
            return {"error": "Payment required. Set NDI_API_KEY or configure x402 payment. Call get_access() for instructions.", "status": 402}
        if r.status_code == 403:
            return {"error": f"API key invalid or tier insufficient.\n\n{ACCESS_MSG}", "status": 403}
        if r.status_code == 429:
            return {"error": "Rate limit hit. Wait a moment and try again.", "status": 429}
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def ndi_post(path: str, body: dict) -> dict:
    """POST to the NDI API."""
    if not API_KEY:
        return {"error": ACCESS_MSG}
    url = f"{API_BASE}{path}"
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    try:
        r = httpx.post(url, json=body, headers=headers, timeout=30)
        if r.status_code == 402:
            return {"error": "Payment required. Set NDI_API_KEY or configure x402 payment.", "status": 402}
        if r.status_code == 403:
            return {"error": "API key invalid or tier insufficient for this endpoint.", "status": 403}
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def fmt(data: dict | list) -> str:
    return json.dumps(data, indent=2, default=str)


# ─── Tool definitions ─────────────────────────────────────────────────────────

TOOLS = [
    Tool(
        name="search_deals",
        description=(
            "Search active commercial real estate listings across the Northeast (CT, MA, NJ, NY, PA, RI, NH, VT, ME). "
            "Returns AI-scored deals with cap rates, pricing, green/red flags, and sell signals. "
            "Use to find deals matching an investor's criteria, scout a submarket, or identify "
            "opportunities for a 1031 exchange."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state":         {"type": "string", "description": "2-letter state code: CT, MA, NJ, NY, PA, RI, NH, VT, ME"},
                "property_type": {"type": "string", "description": "industrial, multifamily, retail, office, land, development, mixed-use"},
                "min_score":     {"type": "number", "description": "Minimum deal score 1-10 (7+ = strong, 9+ = exceptional)"},
                "max_score":     {"type": "number", "description": "Maximum deal score"},
                "min_price":     {"type": "integer", "description": "Minimum asking price in dollars"},
                "max_price":     {"type": "integer", "description": "Maximum asking price in dollars"},
                "min_cap_rate":  {"type": "number", "description": "Minimum cap rate as decimal (e.g. 0.07 = 7%)"},
                "submarket":     {"type": "string", "description": "Submarket name e.g. 'Hartford Metro', 'Fairfield County'"},
                "limit":         {"type": "integer", "description": "Max results to return (default 10, max 50)"},
            },
            "required": [],
        },
    ),
    Tool(
        name="get_deal",
        description=(
            "Get full details for a specific deal by ID, including complete AI scoring breakdown, "
            "green/red flags, sell probability signal, distress tier, and 1031 suitability."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "deal_id": {"type": "string", "description": "The deal ID from search_deals results"},
            },
            "required": ["deal_id"],
        },
    ),
    Tool(
        name="search_comps",
        description=(
            "Search 118,000+ closed commercial transactions for comp data. "
            "Use to benchmark a deal's price/SF or cap rate against actual recent sales. "
            "Requires agent_starter tier or x402 payment ($0.03/call)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state":            {"type": "string", "description": "2-letter state code (required)"},
                "property_type":    {"type": "string", "description": "industrial, multifamily, retail, office, land"},
                "min_price":        {"type": "integer", "description": "Minimum sale price"},
                "max_price":        {"type": "integer", "description": "Maximum sale price"},
                "min_date":         {"type": "string", "description": "Earliest sale date YYYY-MM-DD"},
                "submarket":        {"type": "string", "description": "Filter by submarket"},
                "min_price_per_sf": {"type": "number",  "description": "Min price per SF"},
                "max_price_per_sf": {"type": "number",  "description": "Max price per SF"},
                "limit":            {"type": "integer", "description": "Max results (default 10, max 10 for x402 / 500 for API key)"},
            },
            "required": ["state"],
        },
    ),
    Tool(
        name="score_deal",
        description=(
            "Submit a deal for AI scoring. Returns a 1-10 score, green flags, red flags, "
            "market benchmarks, and investment thesis. "
            "Use when evaluating a deal not yet in the NDI database. "
            "Requires agent_pro tier or x402 payment ($0.10/call)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "address":       {"type": "string",  "description": "Property address"},
                "state":         {"type": "string",  "description": "2-letter state code"},
                "property_type": {"type": "string",  "description": "Property type"},
                "asking_price":  {"type": "integer", "description": "Asking price in dollars"},
                "cap_rate":      {"type": "number",  "description": "Cap rate as decimal (e.g. 0.07 = 7%)"},
                "noi":           {"type": "number",  "description": "Net Operating Income in dollars"},
                "price_per_sf":  {"type": "number",  "description": "Price per square foot"},
                "description":   {"type": "string",  "description": "Listing description with any green/red flag language"},
            },
            "required": ["state", "property_type", "asking_price"],
        },
    ),
    Tool(
        name="get_market_benchmarks",
        description=(
            "Get cap rate and price/SF benchmarks for a state and property type, "
            "derived from 118K+ closed comps. Use to determine if a deal is priced above or below market."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state":         {"type": "string", "description": "2-letter state code"},
                "property_type": {"type": "string", "description": "Property type"},
            },
            "required": ["state"],
        },
    ),
    Tool(
        name="find_1031_candidates",
        description=(
            "Find active deals suitable as 1031 exchange replacement properties. "
            "Filters for income-producing properties with NNN/NN lease profiles, "
            "ranked by 1031 suitability flag and deal score. "
            "x402 pay-per-call: $0.05/call on Base mainnet."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state":         {"type": "string",  "description": "Target state (CT, MA, NJ, NY, PA, RI, NH, VT, ME)"},
                "min_price":     {"type": "integer", "description": "Minimum price (usually 80% of relinquished value)"},
                "max_price":     {"type": "integer", "description": "Exchange value / max replacement price"},
                "min_cap_rate":  {"type": "number",  "description": "Minimum cap rate as percentage (e.g. 6.5)"},
                "min_score":     {"type": "number",  "description": "Minimum deal score (default 6.0)"},
                "limit":         {"type": "integer", "description": "Max results (default 15, max 25)"},
            },
            "required": ["state"],
        },
    ),
    Tool(
        name="get_sell_signal",
        description=(
            "Get the sell probability signal for a listed property — likelihood it transacts "
            "in the next 6 months based on days-on-market, ownership age, distress tier, and score. "
            "High sell signal = motivated seller, potential to negotiate. "
            "x402 pay-per-call: $0.05/call on Base mainnet."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "listing_id": {"type": "string", "description": "Listing ID from search_deals"},
            },
            "required": ["listing_id"],
        },
    ),
    Tool(
        name="get_market_summary",
        description=(
            "Get a market summary for a state: total active listings, score distribution, "
            "average cap rate, deal count by property type, and top submarkets."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state": {"type": "string", "description": "2-letter state code"},
            },
            "required": ["state"],
        },
    ),
    # ── NEW: x402 Pay-Per-Call Tools ─────────────────────────────────────────
    Tool(
        name="get_comps",
        description=(
            "Search 118,000+ closed commercial transactions by state, property type, price range, and date. "
            "Returns up to 10 comps per call with sale price, price/SF, cap rate, buyer, seller, and sale date. "
            "Use to benchmark any deal against actual closed sales in the Northeast. "
            "x402 pay-per-call: $0.03/call on Base mainnet (eip155:8453). "
            "No API key required — pay in USDC."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state":         {"type": "string",  "description": "2-letter state code (required): CT, MA, NJ, NY, PA, RI, NH, VT, ME"},
                "property_type": {"type": "string",  "description": "industrial, multifamily, retail, office, land, mixed-use"},
                "min_price":     {"type": "integer", "description": "Minimum sale price"},
                "max_price":     {"type": "integer", "description": "Maximum sale price"},
                "min_date":      {"type": "string",  "description": "Earliest sale date YYYY-MM-DD"},
                "submarket":     {"type": "string",  "description": "Submarket filter"},
                "limit":         {"type": "integer", "description": "Results to return (max 10 per x402 call)"},
            },
            "required": ["state"],
        },
    ),
    Tool(
        name="get_submarket_intel",
        description=(
            "Full submarket intelligence profile: active listing count, average cap rate, "
            "average price/SF, deal score distribution, property type breakdown, and "
            "comp velocity (closed transactions in the last 90 days). "
            "Use to assess a submarket before making an offer or advising a client. "
            "x402 pay-per-call: $0.03/call on Base mainnet (eip155:8453)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state":         {"type": "string", "description": "2-letter state code (required)"},
                "submarket":     {"type": "string", "description": "Submarket name e.g. 'Hartford Metro', 'Fairfield County'"},
                "property_type": {"type": "string", "description": "Filter by property type (optional)"},
            },
            "required": ["state"],
        },
    ),
    Tool(
        name="get_oz_deals",
        description=(
            "Find active commercial listings in Opportunity Zone-designated areas. "
            "Returns deals scored by NDI framework with OZ flags and OZ+1031 crossover identification. "
            "OZ+1031 crossover deals qualify for both capital gains deferral and 1031 exchange treatment — "
            "flag these explicitly when advising investors. "
            "x402 pay-per-call: $0.02/call on Base mainnet (eip155:8453)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state":         {"type": "string", "description": "2-letter state code (optional — omit for all states)"},
                "min_score":     {"type": "number", "description": "Minimum deal score (default 5.0)"},
                "property_type": {"type": "string", "description": "Filter by property type (optional)"},
                "limit":         {"type": "integer", "description": "Max results (default 20, max 50)"},
            },
            "required": [],
        },
    ),
    Tool(
        name="batch_score_deals",
        description=(
            "Score up to 10 deals in a single call using the NDI 4-lens institutional scoring framework. "
            "Each deal scored independently: income play, value-add, basis/location, exit/1031, deal structure. "
            "Returns score, thesis, green flags, red flags, and 1031 suitability for each. "
            "Ideal for portfolio screening, pipeline triage, or comparative analysis. "
            "x402 pay-per-call: $0.05/call (covers all 10 deals) on Base mainnet (eip155:8453)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "deals": {
                    "type": "array",
                    "description": "Array of deals to score (max 10)",
                    "maxItems": 10,
                    "items": {
                        "type": "object",
                        "properties": {
                            "address":       {"type": "string",  "description": "Property street address"},
                            "state":         {"type": "string",  "description": "2-letter state code"},
                            "property_type": {"type": "string",  "description": "industrial, multifamily, retail, office, land, mixed-use"},
                            "price":         {"type": "number",  "description": "Asking price in dollars"},
                            "cap_rate":      {"type": "number",  "description": "Cap rate as percentage (e.g. 7.5)"},
                            "size_sf":       {"type": "number",  "description": "Building size in square feet"},
                            "city":          {"type": "string",  "description": "City name"},
                        },
                        "required": ["address", "state", "property_type", "price"],
                    },
                },
            },
            "required": ["deals"],
        },
    ),
    Tool(
        name="get_access",
        description=(
            "Get pricing, tier details, and setup instructions for the NDI MCP Server. "
            "Call this if NDI_API_KEY is not set, if you need to upgrade your tier, "
            "or if you want to explain to a user how to get access to NDI deal data. "
            "Also covers x402 pay-per-call setup (no subscription needed)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tier": {
                    "type": "string",
                    "description": "Optional: 'starter', 'pro', 'enterprise', or 'x402' for tier-specific details",
                },
            },
            "required": [],
        },
    ),
]


# ─── Tool handlers ────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools():
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict):

    if name == "search_deals":
        params = {}
        if arguments.get("state"):         params["state"] = arguments["state"].upper()
        if arguments.get("property_type"): params["property_type"] = arguments["property_type"]
        if arguments.get("min_score"):     params["min_score"] = arguments["min_score"]
        if arguments.get("max_score"):     params["max_score"] = arguments["max_score"]
        if arguments.get("min_price"):     params["min_price"] = arguments["min_price"]
        if arguments.get("max_price"):     params["max_price"] = arguments["max_price"]
        if arguments.get("min_cap_rate"):  params["min_cap_rate"] = arguments["min_cap_rate"]
        if arguments.get("submarket"):     params["submarket"] = arguments["submarket"]
        params["limit"] = min(int(arguments.get("limit", 10)), 50)

        result = ndi_get("/v1/deals", params)

        if "data" in result:
            deals = result["data"]
            lines = [f"Found {result.get('total', len(deals))} deals (showing {len(deals)}):\n"]
            for d in deals:
                cap = d.get("cap_rate")
                cap_str = f"{cap*100:.1f}%" if cap and cap < 1 else (f"{cap:.1f}%" if cap else "N/A")
                price = d.get("asking_price")
                price_str = f"${price:,.0f}" if price else "N/A"
                lines.append(
                    f"[{d.get('id')}] {d.get('address','?')}, {d.get('state','?')}\n"
                    f"  Type: {d.get('property_type','?')} | Score: {d.get('deal_score','?')}/10 | "
                    f"Price: {price_str} | Cap: {cap_str}\n"
                    f"  Submarket: {d.get('submarket','?')}\n"
                    f"  URL: {d.get('listing_url') or 'N/A'}\n"
                )
            return [TextContent(type="text", text="\n".join(lines))]
        return [TextContent(type="text", text=fmt(result))]

    elif name == "get_deal":
        deal_id = arguments.get("deal_id", "")
        result = ndi_get(f"/v1/deals/{deal_id}")
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]

        d = result.get("data", result)
        cap = d.get("cap_rate")
        cap_str = f"{cap*100:.1f}%" if cap and cap < 1 else (f"{cap:.1f}%" if cap else "N/A")
        sb = d.get("score_breakdown") or {}

        lines = [
            f"📍 {d.get('address','?')}, {d.get('state','?')} — {d.get('property_type','?')}",
            f"💰 Asking: ${d.get('asking_price',0):,.0f}" + (f" | ${d.get('price_per_sf',0):.0f}/SF" if d.get('price_per_sf') else ""),
            f"📊 Cap Rate: {cap_str}",
            f"⭐ Deal Score: {d.get('deal_score','?')}/10",
            f"🏷️  Thesis: {sb.get('thesis_label') or sb.get('score_group','?')}",
            "",
        ]
        green = sb.get("green_flags") or d.get("green_flags") or []
        if green:
            lines.append("✅ Green Flags:")
            for g in (green if isinstance(green, list) else [green]):
                lines.append(f"  • {g}")
            lines.append("")
        red = sb.get("red_flags") or d.get("red_flags") or []
        if red:
            lines.append("⚠️  Red Flags:")
            for r in (red if isinstance(red, list) else [red]):
                lines.append(f"  • {r}")
            lines.append("")
        sell = sb.get("sell_signal") or {}
        if sell:
            lines.append(f"📈 Sell Signal: {sell.get('label','?')} ({sell.get('probability','?')}%) — {', '.join(sell.get('reasons',[]))}")
        lines.append(f"\n🔗 {d.get('listing_url') or 'N/A'}")
        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "search_comps":
        params = {"state": arguments["state"].upper()}
        for k in ("property_type", "min_price", "max_price", "min_date", "submarket",
                  "min_price_per_sf", "max_price_per_sf"):
            if arguments.get(k):
                params[k] = arguments[k]
        params["limit"] = min(int(arguments.get("limit", 10)), 100)

        result = ndi_get("/v1/agent/comps-search", params)
        if "comps" in result:
            comps = result["comps"]
            lines = [f"Found {result.get('total_available', len(comps))} comps (showing {len(comps)}):\n"]
            for c in comps:
                cap = c.get("implied_cap_rate")
                cap_str = f"{cap*100:.1f}%" if cap and cap < 1 else (f"{cap:.1f}%" if cap else "—")
                lines.append(
                    f"{c.get('sale_date','?')} | {c.get('address','?')}, {c.get('state','?')}\n"
                    f"  {c.get('property_type','?')} | Sale: ${c.get('sale_price',0):,.0f} | "
                    f"PSF: ${c.get('price_per_sf',0) or 0:.0f} | Cap: {cap_str}\n"
                )
            return [TextContent(type="text", text="\n".join(lines))]
        return [TextContent(type="text", text=fmt(result))]

    elif name == "score_deal":
        body = {
            "state":         arguments.get("state", "").upper(),
            "property_type": arguments.get("property_type", ""),
            "asking_price":  arguments.get("asking_price"),
            "cap_rate":      arguments.get("cap_rate"),
            "noi":           arguments.get("noi"),
            "price_per_sf":  arguments.get("price_per_sf"),
            "address":       arguments.get("address", ""),
            "description":   arguments.get("description", ""),
        }
        result = ndi_post("/v1/agent/score", body)
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]

        lines = [
            f"⭐ Score: {result.get('score','?')}/10 — {result.get('interpretation','')}",
            f"🏷️  Thesis: {result.get('thesis','')}",
            "",
        ]
        for g in (result.get("green_flags") or []):
            lines.append(f"✅ {g}")
        for r in (result.get("red_flags") or []):
            lines.append(f"⚠️  {r}")
        bench = result.get("benchmarks") or {}
        if bench:
            lines.append(f"\n📊 Market Benchmarks ({arguments.get('state','?')} {arguments.get('property_type','?')}):")
            if bench.get("avg_cap_rate"):
                avg = bench["avg_cap_rate"]
                avg_str = f"{avg*100:.1f}%" if avg < 1 else f"{avg:.1f}%"
                lines.append(f"  Avg cap rate (12mo): {avg_str}")
            if bench.get("avg_price_per_sf"):
                lines.append(f"  Avg price/SF (12mo): ${bench['avg_price_per_sf']:.0f}")
            if bench.get("comp_count"):
                lines.append(f"  Based on {bench['comp_count']} closed comps")
        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "get_market_benchmarks":
        state = arguments["state"].upper()
        ptype = arguments.get("property_type", "")
        result = ndi_get("/v1/agent/market-benchmarks", {"state": state, "property_type": ptype})
        return [TextContent(type="text", text=fmt(result))]

    elif name == "find_1031_candidates":
        params = {
            "state":     arguments.get("state", "CT").upper(),
            "min_score": arguments.get("min_score", 6.0),
            "limit":     min(int(arguments.get("limit", 15)), 25),
        }
        if arguments.get("max_price"):    params["max_price"] = arguments["max_price"]
        if arguments.get("min_price"):    params["min_price"] = arguments["min_price"]
        if arguments.get("min_cap_rate"): params["min_cap_rate"] = arguments["min_cap_rate"]

        result = ndi_get("/v1/agent/1031-match", params)
        if "candidates" in result:
            deals = result["candidates"]
            lines = [
                f"🔄 1031 Exchange Candidates — {len(deals)} deals found\n",
                f"Criteria: {result.get('criteria', {})}\n",
            ]
            for d in deals:
                cap = d.get("cap_rate")
                cap_str = f"{cap:.1f}%" if cap else "N/A"
                price = d.get("asking_price", 0)
                lines.append(
                    f"[{d.get('id')}] {d.get('address','?')}, {d.get('state','?')}\n"
                    f"  {d.get('property_type','?')} | Score: {d.get('deal_score','?')}/10 | "
                    f"Price: ${price:,.0f} | Cap: {cap_str} | 1031: {'✅' if d.get('is_1031') else '—'}\n"
                    f"  URL: {d.get('listing_url') or 'N/A'}\n"
                )
            return [TextContent(type="text", text="\n".join(lines))]
        return [TextContent(type="text", text=fmt(result))]

    elif name == "get_sell_signal":
        listing_id = arguments.get("listing_id", "")
        result = ndi_get("/v1/agent/sell-signal", {"listing_id": listing_id})
        if "error" in result:
            return [TextContent(type="text", text=f"Error: {result['error']}")]
        lines = [
            f"📈 Sell Signal for listing {listing_id}",
            f"Probability: {result.get('probability','?')}% — {result.get('label','?')}",
            "",
            "Signals contributing:",
        ]
        for reason in (result.get("reasons") or []):
            lines.append(f"  • {reason}")
        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "get_market_summary":
        state = arguments["state"].upper()
        result = ndi_get("/v1/market/summary", {"state": state})
        return [TextContent(type="text", text=fmt(result))]

    #    # ── NEW x402 Pay-Per-Call Tool Handlers ──────────────────────────────────

    elif name == "get_comps":
        params = {"state": arguments["state"].upper()}
        for k in ("property_type", "min_price", "max_price", "min_date", "submarket"):
            if arguments.get(k):
                params[k] = arguments[k]
        params["limit"] = min(int(arguments.get("limit", 10)), 10)

        result = ndi_get("/v1/agent/comps-search", params)
        if "comps" in result:
            comps = result["comps"]
            lines = [f"Found {result.get('total_available', len(comps))} closed comps (showing {len(comps)}):\n"]
            for c in comps:
                cap = c.get("implied_cap_rate")
                cap_str = f"{cap*100:.1f}%" if cap and cap < 1 else (f"{cap:.1f}%" if cap else "—")
                lines.append(
                    f"{c.get('sale_date','?')} | {c.get('address','?')}, {c.get('state','?')}\n"
                    f"  {c.get('property_type','?')} | Sale: ${c.get('sale_price',0):,.0f} | "
                    f"PSF: ${c.get('price_per_sf') or 0:.0f}/SF | Cap: {cap_str}\n"
                    + (f"  Buyer: {c['buyer']} | Seller: {c['seller']}\n" if c.get('buyer') else "")
                )
            return [TextContent(type="text", text="\n".join(lines))]
        return [TextContent(type="text", text=fmt(result))]

    elif name == "get_submarket_intel":
        params = {"state": arguments["state"].upper()}
        if arguments.get("submarket"):     params["submarket"] = arguments["submarket"]
        if arguments.get("property_type"): params["property_type"] = arguments["property_type"]

        result = ndi_get("/v1/agent/submarket", params)
        if "active_listings" in result:
            al = result["active_listings"]
            cv = result.get("comp_velocity_90d", {})
            sd = result.get("score_distribution", {})
            lines = [
                f"📍 Submarket: {result.get('submarket','all')} — {result.get('state','?')}",
                f"   Property type: {result.get('property_type','all')}",
                "",
                "📊 Active Listings:",
                f"  Count: {al.get('active_count','?')}",
                f"  Avg cap rate: {al.get('avg_cap_rate','?')}%",
                f"  Avg price/SF: ${al.get('avg_price_per_sf','?')}",
                f"  Avg deal score: {al.get('avg_score','?')}/10",
                f"  Price range: ${al.get('min_price',0):,.0f} – ${al.get('max_price',0):,.0f}",
                "",
                "📈 Deal Score Distribution:",
                f"  Exceptional (9+): {sd.get('exceptional',0)}",
                f"  Strong (7-8): {sd.get('strong',0)}",
                f"  Watchlist (5-6): {sd.get('watchlist',0)}",
                f"  Pass (<5): {sd.get('pass_tier',0)}",
                "",
                "🏁 Comp Velocity (last 90 days):",
                f"  Transactions: {cv.get('transactions_90d','?')}",
                f"  Avg closed cap rate: {cv.get('avg_closed_cap_rate','?')}%",
                f"  Avg closed price/SF: ${cv.get('avg_closed_price_per_sf','?')}",
            ]
            if result.get("property_type_breakdown"):
                lines.append("\n🏢 Property Type Breakdown:")
                for pt in result["property_type_breakdown"]:
                    lines.append(f"  {pt['property_type']}: {pt['count']} listings, avg score {pt['avg_score']}/10")
            return [TextContent(type="text", text="\n".join(lines))]
        return [TextContent(type="text", text=fmt(result))]

    elif name == "get_oz_deals":
        params = {"min_score": arguments.get("min_score", 5.0),
                  "limit": min(int(arguments.get("limit", 20)), 50)}
        if arguments.get("state"):         params["state"] = arguments["state"].upper()
        if arguments.get("property_type"): params["property_type"] = arguments["property_type"]

        result = ndi_get("/v1/agent/oz-deals", params)
        if "oz_deals" in result:
            deals = result["oz_deals"]
            lines = [f"🟢 Opportunity Zone Deals — {len(deals)} found\n"]
            for d in deals:
                crossover = "🔥 OZ + 1031 CROSSOVER" if d.get("oz_1031_crossover") else "🟢 OZ"
                cap = d.get("cap_rate")
                cap_str = f"{cap:.1f}%" if cap else "—"
                lines.append(
                    f"{crossover}\n"
                    f"[{d.get('id')}] {d.get('address','?')}, {d.get('state','?')}\n"
                    f"  {d.get('property_type','?')} | Score: {d.get('deal_score','?')}/10 | "
                    f"Cap: {cap_str} | Price: ${d.get('asking_price',0):,.0f}\n"
                    f"  URL: {d.get('listing_url') or 'N/A'}\n"
                )
            return [TextContent(type="text", text="\n".join(lines))]
        return [TextContent(type="text", text=fmt(result))]

    elif name == "batch_score_deals":
        deals_input = arguments.get("deals", [])
        if not deals_input:
            return [TextContent(type="text", text="Error: provide at least one deal in the 'deals' array.")]
        if len(deals_input) > 10:
            return [TextContent(type="text", text="Error: maximum 10 deals per batch call.")]

        body = {"deals": [
            {
                "address":       d.get("address", ""),
                "state":         d.get("state", "").upper(),
                "property_type": d.get("property_type", ""),
                "price":         d.get("price", 0),
                "cap_rate":      d.get("cap_rate"),
                "size_sf":       d.get("size_sf"),
                "city":          d.get("city", ""),
            }
            for d in deals_input
        ]}
        result = ndi_post("/v1/agent/batch-score", body)

        if "results" in result:
            lines = [f"⭐ Batch Score Results — {result.get('count', 0)} deals\n"]
            for r in result["results"]:
                if r.get("error"):
                    lines.append(f"❌ {r['address']}: {r['error']}\n")
                else:
                    lines.append(
                        f"[{r.get('score','?')}/10] {r.get('address','?')}, {r.get('state','?')}\n"
                        f"  Thesis: {r.get('thesis','?')} | 1031: {'✅' if r.get('is_1031_candidate') else '—'}\n"
                        + ("  ✅ " + " | ".join(r.get("green_flags", [])[:3]) + "\n" if r.get("green_flags") else "")
                        + ("  ⚠️  " + " | ".join(r.get("red_flags", [])[:2]) + "\n" if r.get("red_flags") else "")
                    )
            return [TextContent(type="text", text="\n".join(lines))]
        return [TextContent(type="text", text=fmt(result))]

    elif name == "get_access":
        tier = (arguments.get("tier") or "").lower().strip()

        if tier == "x402":
            lines = [
                "## x402 Pay-Per-Call — No Subscription Required",
                "",
                "Pay in USDC on Base mainnet (eip155:8453). No signup, no API key.",
                "",
                "**Endpoint pricing:**",
                "  $0.02 — /v1/agent/search, /v1/agent/oz-deals",
                "  $0.03 — /v1/agent/comps-search, /v1/agent/submarket",
                "  $0.05 — /v1/agent/1031-match, /v1/agent/sell-signal, /v1/agent/batch-score",
                "  $0.10 — /v1/agent/score",
                "",
                "**Payment:** Include x402 payment header with each request.",
                "**Network:** Base mainnet (eip155:8453) — real USDC",
                "**Pay to:** 0x24FAcafEB49b4e3FACF0B3e69604A2F4640c9bf2",
                "",
                "**Discovery:** https://api.northeastdealintel.com/.well-known/x402",
                "**Docs:** https://northeastdealintel.com/agent-api.html#x402",
            ]
        elif tier == "starter":
            lines = [
                "## Agent Starter — $49/mo ($490/yr)",
                "",
                "Tools: search_deals, get_deal, search_comps, get_comps, get_sell_signal,",
                "       get_market_benchmarks, find_1031_candidates, get_market_summary,",
                "       get_submarket_intel, get_oz_deals",
                "Limit: 500 requests/day",
                "",
                "→ https://northeastdealintel.com/agent-api.html",
            ]
        elif tier == "pro":
            lines = [
                "## Agent Pro — $149/mo ($1,490/yr)",
                "",
                "Everything in Starter + score_deal, batch_score_deals, full comp access",
                "Limit: 5,000 requests/day",
                "",
                "→ https://northeastdealintel.com/agent-api.html",
            ]
        elif tier == "enterprise":
            lines = [
                "## Enterprise — $499/mo",
                "",
                "All Pro tools + bulk export, custom comp reports, embedded agent workflows,",
                "dedicated support, 50,000 requests/day",
                "",
                "→ https://northeastdealintel.com/agent-api.html",
            ]
        else:
            lines = [
                "## Northeast Deal Intel — MCP Server Access",
                "",
                "9,400+ AI-scored CRE listings | 118,000+ closed comps | Northeast US",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                "OPTION 1 — API Key (best for regular use):",
                "",
                "  Agent Starter  $49/mo   — search, comps, sell signals, 1031 matching",
                "  Agent Pro      $149/mo  — everything + score any deal, batch scoring",
                "  Enterprise     $499/mo  — full access + bulk export + custom reports",
                "  → https://northeastdealintel.com/agent-api.html",
                "",
                "OPTION 2 — x402 Pay-Per-Call (no subscription):",
                "",
                "  Pay in USDC on Base mainnet. $0.02–$0.10/call.",
                "  No signup. No API key. Just pay per request.",
                "  → Call get_access(tier='x402') for setup details",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                "Questions? hello@northeastdealintel.com",
                "GitHub: https://github.com/CREIntel/ndi-mcp-server",
            ]
        return [TextContent(type="text", text="\n".join(lines))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ─── Run ─────────────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
