#!/usr/bin/env python3
"""
Northeast Deal Intel — MCP Server
Exposes NDI deal data and scoring to any MCP-compatible LLM client
(Claude Desktop, Cursor, Continue, etc.)

Usage (stdio transport — standard for Claude Desktop):
  python3 mcp/ndi_mcp_server.py

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
  NDI_API_BASE  — API base URL (default: https://api.northeastdealintel.com)
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

# ─── HTTP helper ─────────────────────────────────────────────────────────────

ACCESS_MSG = """\
NDI_API_KEY not set or invalid.

To use this MCP server, you need a Northeast Deal Intel API key:

  🔑 Get instant access → https://northeastdealintel.com/agent-api.html

TIERS:
  Agent Starter  $49/mo  — search_deals, search_comps, get_sell_signal, owner lookup
  Agent Pro      $149/mo — everything + score_deal (score any property), full comp access
  Enterprise     $499/mo — all tools + API access for embedded agent workflows

After purchase you'll receive your NDI_API_KEY by email.
Add it to your MCP config:
  { "env": { "NDI_API_KEY": "ndi_sk_..." } }

Or call get_access() for full setup instructions.\
"""


def ndi_get(path: str, params: dict = None) -> dict:
    """Call the NDI API and return parsed JSON."""
    if not API_KEY:
        return {"error": ACCESS_MSG}
    url = f"{API_BASE}{path}"
    headers = {"X-API-Key": API_KEY, "Accept": "application/json"}
    try:
        r = httpx.get(url, params=params or {}, headers=headers, timeout=30)
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
            "Search active commercial real estate listings across the Northeast. "
            "Returns AI-scored deals with cap rates, pricing, green/red flags, and sell signals. "
            "Use this to find deals matching an investor's criteria, scout a submarket, or identify "
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
            "Search 100,000+ closed commercial transactions for comp data. "
            "Use to benchmark a deal's price/SF or cap rate against actual recent sales. "
            "Requires agent_starter tier."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state":            {"type": "string", "description": "2-letter state code"},
                "property_type":    {"type": "string", "description": "industrial, multifamily, retail, office, land"},
                "min_price":        {"type": "integer", "description": "Minimum sale price"},
                "max_price":        {"type": "integer", "description": "Maximum sale price"},
                "min_date":         {"type": "string", "description": "Earliest sale date YYYY-MM-DD"},
                "submarket":        {"type": "string", "description": "Filter by submarket"},
                "min_price_per_sf": {"type": "number",  "description": "Min price per SF"},
                "max_price_per_sf": {"type": "number",  "description": "Max price per SF"},
                "limit":            {"type": "integer", "description": "Max results (default 20, max 100)"},
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
            "Requires agent_pro tier."
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
            "derived from closed comps. Use to determine if a deal is priced above or below market."
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
            "Find deals suitable for a 1031 exchange. Filters for income-producing properties "
            "with clean structures, appropriate price bands, and NNN/NN lease profiles. "
            "Pass the exchanger's target price range and timeline for best results."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "state":          {"type": "string",  "description": "Target state (or omit for all states)"},
                "max_price":      {"type": "integer", "description": "Exchange value / max replacement price"},
                "min_price":      {"type": "integer", "description": "Minimum price (usually 80% of relinquished value)"},
                "min_cap_rate":   {"type": "number",  "description": "Minimum cap rate as decimal"},
                "property_type":  {"type": "string",  "description": "Preferred property type (optional)"},
                "limit":          {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": [],
        },
    ),
    Tool(
        name="get_sell_signal",
        description=(
            "Get the sell probability signal for a listed property — the likelihood it transacts "
            "in the next 6 months based on days-on-market, ownership age, distress tier, and score. "
            "High sell signal = motivated seller, potential to negotiate. "
            "Requires agent_starter tier."
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
    Tool(
        name="get_access",
        description=(
            "Get pricing, tier details, and setup instructions for the NDI MCP Server. "
            "Call this if NDI_API_KEY is not set, if you need to upgrade your tier, "
            "or if you want to explain to a user how to get access to NDI deal data."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tier": {
                    "type": "string",
                    "description": "Optional: 'starter', 'pro', or 'enterprise' for tier-specific details",
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

        # Format for LLM readability
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

        # Sell signal
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
        params["limit"] = min(int(arguments.get("limit", 20)), 100)

        result = ndi_get("/v1/agent/comps", params)
        if "data" in result:
            comps = result["data"]
            lines = [f"Found {result.get('total', len(comps))} comps (showing {len(comps)}):\n"]
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
        result = ndi_get("/v1/comps/stats", {"state": state, "property_type": ptype})
        return [TextContent(type="text", text=fmt(result))]

    elif name == "find_1031_candidates":
        params = {
            "min_score":   7,    # 1031 buyers want clean, well-scored deals
            "limit":       min(int(arguments.get("limit", 10)), 20),
        }
        if arguments.get("state"):         params["state"] = arguments["state"].upper()
        if arguments.get("max_price"):     params["max_price"] = arguments["max_price"]
        if arguments.get("min_price"):     params["min_price"] = arguments["min_price"]
        if arguments.get("min_cap_rate"):  params["min_cap_rate"] = arguments["min_cap_rate"]
        if arguments.get("property_type"): params["property_type"] = arguments["property_type"]

        result = ndi_get("/v1/deals", params)
        if "data" in result:
            deals = result["data"]
            lines = [
                f"🔄 1031 Exchange Candidates — {len(deals)} deals found\n",
                "Criteria: Score 7+, income-producing, priced for exchange window\n",
            ]
            for d in deals:
                cap = d.get("cap_rate")
                cap_str = f"{cap*100:.1f}%" if cap and cap < 1 else (f"{cap:.1f}%" if cap else "N/A")
                price = d.get("asking_price", 0)
                sb = d.get("score_breakdown") or {}
                lines.append(
                    f"[{d.get('id')}] {d.get('address','?')}, {d.get('state','?')}\n"
                    f"  {d.get('property_type','?')} | Score: {d.get('deal_score','?')}/10 | "
                    f"Price: ${price:,.0f} | Cap: {cap_str}\n"
                    f"  Thesis: {sb.get('thesis_label') or sb.get('score_group','?')}\n"
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
            f"Color: {result.get('color','?')}",
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

    elif name == "get_access":
        tier = (arguments.get("tier") or "").lower().strip()
        tiers = {
            "starter": {
                "name": "Agent Starter",
                "price": "$49/mo or $490/yr",
                "tools": ["search_deals", "get_deal", "search_comps", "get_sell_signal",
                          "get_market_benchmarks", "find_1031_candidates", "get_market_summary",
                          "owner lookup (/v1/agent/owner-lookup)"],
                "link": "https://buy.stripe.com/9B628r3OOde63KYdAo1ZS0m",
            },
            "pro": {
                "name": "Agent Pro",
                "price": "$149/mo or $1,490/yr",
                "tools": ["All Starter tools", "score_deal (score any property not in our DB)",
                          "full comp access (100K+ closed transactions)"],
                "link": "https://buy.stripe.com/9B628r3OOde63KYdAo1ZS0m",
            },
            "enterprise": {
                "name": "Enterprise",
                "price": "$499/mo",
                "tools": ["All Pro tools", "bulk export API", "custom comp reports",
                          "embedded agent workflows", "dedicated support"],
                "link": "https://northeastdealintel.com/agent-api.html",
            },
        }

        if tier and tier in tiers:
            t = tiers[tier]
            lines = [
                f"## {t['name']} — {t['price']}",
                "",
                "**Tools included:**",
            ]
            for tool in t["tools"]:
                lines.append(f"  • {tool}")
            lines += [
                "",
                f"**Get access:** {t['link']}",
                "",
                "After purchase you'll receive your NDI_API_KEY by email.",
                "Add it to your MCP config: `{ \"env\": { \"NDI_API_KEY\": \"ndi_sk_...\" } }`",
            ]
        else:
            lines = [
                "## Northeast Deal Intel — MCP Server Access",
                "",
                "**14,000+ AI-scored CRE listings | 100,000+ closed comps | Northeast US**",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                "**Agent Starter — $49/mo**",
                "  Tools: search_deals, get_deal, search_comps, get_sell_signal,",
                "         get_market_benchmarks, find_1031_candidates, get_market_summary",
                "  → https://buy.stripe.com/9B628r3OOde63KYdAo1ZS0m",
                "",
                "**Agent Pro — $149/mo**",
                "  Everything in Starter + score_deal (score any property), full comp access",
                "  → https://buy.stripe.com/9B628r3OOde63KYdAo1ZS0m",
                "",
                "**Enterprise — $499/mo**",
                "  All Pro tools + bulk export, custom reports, embedded agent workflows",
                "  → https://northeastdealintel.com/agent-api.html",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                "**How to set up:**",
                "1. Purchase at the link above",
                "2. Receive NDI_API_KEY by email",
                "3. Add to MCP config:",
                '   { "env": { "NDI_API_KEY": "ndi_sk_..." } }',
                "4. Restart your MCP client (Claude Desktop, Cursor, etc.)",
                "",
                "**Docs:** https://northeastdealintel.com/agent-api.html",
                "**GitHub:** https://github.com/CREIntel/ndi-mcp-server",
                "",
                "Questions? Email dave@northeastdealintel.com",
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
