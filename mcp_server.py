"""BRM Territory Hub -- MCP bridge for Claude Desktop.

Lets you talk to Claude about your own territory: "who should I see in Norfolk
this week?", "what have I talked about at Kelly Supply?", "where's my
whitespace at Winsupply?"

PRIVACY: this server runs on your machine and talks to Claude Desktop over a
local pipe (stdin/stdout). It is not a website and it is not reachable from the
internet. Claude only ever receives the specific answer to a question you ask
-- never the whole database.

Deliberately written against the standard library only. Adding a package here
would mean another thing that can fail to install; a plain JSON-RPC loop
cannot.

Run by Claude Desktop automatically. To test it by hand:
    echo {"jsonrpc":"2.0","id":1,"method":"tools/list"} | python mcp_server.py
"""
import json
import sys
import traceback
from datetime import date, datetime

from brm import db, queries, intelligence, news, linecard, importer

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "brm-territory-hub", "version": "1.1.0"}


def log(msg):
    """Diagnostics must go to stderr -- stdout is the protocol channel."""
    print(f"[brm-mcp] {msg}", file=sys.stderr, flush=True)


def money(v):
    v = float(v or 0)
    return f"{'-' if v < 0 else ''}${abs(v):,.0f}"


def _conn():
    return db.get_connection()


# ---------------------------------------------------------------------------
# Tool implementations -- each returns a readable text block
# ---------------------------------------------------------------------------

def tool_territory_summary(args):
    conn = _conn()
    s = queries.dashboard_stats(conn)
    dormant = intelligence.dormant_branches(conn)
    top = intelligence.prioritized_accounts(conn, limit=5)
    lines = [
        "TERRITORY SUMMARY (Nebraska & Iowa)",
        f"Accounts: {s['total_accounts']} | Calls logged: {s['total_calls']} | Open follow-ups: {s['open_followups']}",
        f"YTD sales: {money(s['total_ytd'])} vs prior-year {money(s['total_prior_ytd'])} "
        f"({money(s['total_variance'])} YoY)",
        "",
        "Top priorities right now:",
    ]
    for a in top:
        lines.append(f"  [{a['score']:.0f}] {a['name']} ({a.get('market') or 'Other'}) -- {'; '.join(a['reasons'])}")
    if dormant:
        lines.append("")
        lines.append("Dormant branches (sister branches doing far more):")
        for d in dormant[:5]:
            seen = "never visited" if d["days_since_visit"] is None else f"{d['days_since_visit']}d since visit"
            lines.append(
                f"  {d['account_name']}: {money(d['ytd_sales'])} vs {money(d['chain_median'])} "
                f"at a healthy sibling ({seen})"
            )
    return "\n".join(lines)


def tool_who_to_visit(args):
    conn = _conn()
    market = args.get("market")
    tier = args.get("tier")
    limit = int(args.get("limit", 10))
    accounts = intelligence.prioritized_accounts(conn, market=market, tier=tier, limit=limit)
    if not accounts:
        return "No accounts matched. Try without a market filter, or check the market spelling."

    header = "WHO TO VISIT NEXT"
    if market:
        header += f" -- {market}"
    if tier:
        header += f" (tier {tier})"
    lines = [header, ""]
    for a in accounts:
        seen = "never visited" if a["last_visit_date"] is None else f"last visit {a['last_visit_date']}"
        lines.append(f"[{a['score']:.0f}] {a['name']}")
        lines.append(
            f"    {a.get('company_type') or 'type unknown'} | {a.get('market') or 'Other'} | tier {a['tier']} "
            f"(target every {a['cadence']}d) | {seen}"
        )
        lines.append(f"    YTD {money(a['ytd_sales'])} ({money(a['yoy_variance'])} YoY)")
        for r in a["reasons"]:
            lines.append(f"    - {r}")
        lines.append("")
    return "\n".join(lines)


def _find_account(conn, name_or_id):
    """Fuzzy account lookup so 'kelly norfolk' finds 'Kelly Supply Norfolk'."""
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
        row = conn.execute("SELECT id FROM accounts WHERE id = ?", (int(name_or_id),)).fetchone()
        return row["id"] if row else None
    needle = (name_or_id or "").strip().lower()
    if not needle:
        return None
    exact = conn.execute("SELECT id FROM accounts WHERE name = ? COLLATE NOCASE", (needle,)).fetchone()
    if exact:
        return exact["id"]
    like = conn.execute(
        "SELECT id FROM accounts WHERE name LIKE ? ORDER BY LENGTH(name) LIMIT 1", (f"%{needle}%",)
    ).fetchone()
    if like:
        return like["id"]
    # Fall back to all-words-present matching ("kelly norfolk").
    words = needle.split()
    rows = conn.execute("SELECT id, name FROM accounts").fetchall()
    for r in rows:
        low = r["name"].lower()
        if all(w in low for w in words):
            return r["id"]
    return None


def tool_get_account(args):
    conn = _conn()
    account_id = _find_account(conn, args.get("account"))
    if not account_id:
        return f"No account found matching '{args.get('account')}'."

    a = queries.get_account(conn, account_id)
    p = intelligence.priority_for_account(conn, a)

    lines = [
        f"ACCOUNT: {a['name']}",
        f"{a.get('company_type') or 'type unknown'} | {a.get('market') or 'Other'} | "
        f"tier {p['tier']} (target every {p['cadence']}d)",
        f"Priority score {p['score']:.0f}" + (f" -- {'; '.join(p['reasons'])}" if p["reasons"] else " -- on cadence"),
        f"Last visit: {a['last_visit_date'] or 'never'} | "
        f"{a['days_since_visit'] if a['days_since_visit'] is not None else '?'} days ago | "
        f"{a['total_visits']} visits total",
        f"YTD {money(a['ytd_sales'])} vs prior {money(a['prior_ytd_sales'])} ({money(a['yoy_variance'])} YoY)",
    ]
    if a.get("notes"):
        lines.append(f"Notes: {a['notes']}")

    contacts = queries.contacts_for_account(conn, account_id)
    if contacts:
        lines.append("")
        lines.append("CONTACTS:")
        for c in contacts:
            bits = [c["name"]]
            if c.get("role"):
                bits.append(c["role"])
            if c.get("phone"):
                bits.append(c["phone"])
            if c.get("email"):
                bits.append(c["email"])
            lines.append("  " + " | ".join(bits))

    sales = queries.current_sales_for_account(conn, account_id)
    if sales:
        lines.append("")
        lines.append("SALES BY BRAND (current vs prior YTD):")
        for s in sales:
            lines.append(
                f"  {s['brand_name']}: {money(s['current_ytd'])} vs {money(s['prior_ytd'])} "
                f"({money(s['variance'])})"
            )

    ws = intelligence.whitespace_for_account(conn, account_id)
    if ws:
        lines.append("")
        lines.append("OPPORTUNITIES (not buying; comparable accounts do):")
        for w in ws[:8]:
            lines.append(
                f"  {w['brand_name']}: est. {money(w['estimate'])} "
                f"({w['peer_buyers']} {w['peer_kind']} buy it, median {money(w['peer_median'])})"
            )

    fus = [f for f in queries.followups_for_account(conn, account_id) if f["status"] == "open"]
    if fus:
        lines.append("")
        lines.append("OPEN FOLLOW-UPS:")
        for f in fus:
            lines.append(f"  {f['description']} (due {f['due_date'] or 'no date'})")

    calls = queries.call_history_for_account(conn, account_id)
    if calls:
        lines.append("")
        limit = int(args.get("visit_limit", 8))
        lines.append(f"RECENT VISITS (showing {min(limit, len(calls))} of {len(calls)}):")
        for c in calls[:limit]:
            who = f" with {c['contact_name']}" if c.get("contact_name") else ""
            brand = f" [{c['brand_name']}]" if c.get("brand_name") else ""
            lines.append(f"  {c['call_date']}{brand}{who}: {c['notes'] or c.get('subject') or ''}")
    return "\n".join(lines)


def tool_search_calls(args):
    conn = _conn()
    q = (args.get("query") or "").strip()
    if not q:
        return "Provide a search term."
    limit = int(args.get("limit", 20))
    like = f"%{q}%"
    rows = conn.execute(
        """SELECT c.call_date, c.notes, c.subject, a.name AS account_name, a.id AS account_id,
                  b.name AS brand_name, ct.name AS contact_name
           FROM calls c
           JOIN accounts a ON a.id = c.account_id
           LEFT JOIN brands b ON b.id = c.brand_id
           LEFT JOIN contacts ct ON ct.id = c.contact_id
           WHERE c.notes LIKE ? OR c.subject LIKE ? OR a.name LIKE ? OR b.name LIKE ?
                 OR c.attendees LIKE ?
           ORDER BY c.call_date DESC LIMIT ?""",
        (like, like, like, like, like, limit),
    ).fetchall()
    if not rows:
        return f"No calls mention '{q}'."
    lines = [f"CALLS MENTIONING '{q}' ({len(rows)} shown, newest first):", ""]
    for r in rows:
        brand = f" [{r['brand_name']}]" if r["brand_name"] else ""
        who = f" with {r['contact_name']}" if r["contact_name"] else ""
        lines.append(f"{r['call_date']} -- {r['account_name']}{brand}{who}")
        if r["notes"]:
            lines.append(f"    {r['notes']}")
    return "\n".join(lines)


def tool_find_opportunities(args):
    conn = _conn()
    market = args.get("market")
    limit = int(args.get("limit", 20))
    lines = []

    dormant = intelligence.dormant_branches(conn)
    if market:
        dormant = [d for d in dormant if (d.get("market") or "") == market]
    if dormant:
        lines.append("DORMANT BRANCHES (same banner, sister branch doing far more):")
        for d in dormant:
            seen = "never visited" if d["days_since_visit"] is None else f"{d['days_since_visit']}d since visit"
            lines.append(
                f"  {d['account_name']} ({d.get('market') or 'Other'}): {money(d['ytd_sales'])} "
                f"vs {money(d['chain_median'])} at a healthy sibling, best {money(d['chain_best'])} -- {seen}"
            )
        lines.append("")

    opps = intelligence.territory_opportunities(conn, limit=limit * 2)
    if market:
        opps = [o for o in opps if (o.get("market") or "") == market]
    opps = opps[:limit]
    if opps:
        lines.append("WHITESPACE (lines not being bought that comparable accounts buy):")
        for o in opps:
            seen = "never visited" if o["days_since_visit"] is None else f"{o['days_since_visit']}d since visit"
            lines.append(
                f"  {money(o['estimate'])} -- {o['brand_name']} at {o['account_name']} "
                f"({o['peer_buyers']} {o['peer_kind']} buy it; {seen})"
            )
    if not lines:
        return "No opportunities found for that filter."
    return "\n".join(lines)


def tool_brand_performance(args):
    conn = _conn()
    name = (args.get("brand") or "").strip()
    if not name:
        brands = queries.list_brands(conn)
        lines = ["ALL BRANDS (territory YTD, YoY):", ""]
        for b in brands:
            if b.get("category") == "admin":
                continue
            lines.append(
                f"  {b['name']}: {money(b['ytd_sales'])} ({money(b['variance'])} YoY), "
                f"{b['account_count']} accounts, {b['call_count']} calls logged"
            )
        return "\n".join(lines)

    row = conn.execute("SELECT id FROM brands WHERE name LIKE ? ORDER BY LENGTH(name) LIMIT 1", (f"%{name}%",)).fetchone()
    if not row:
        return f"No brand found matching '{name}'."
    brand = queries.get_brand(conn, row["id"])
    entry = linecard.find_entry(brand["name"])
    lines = [
        f"BRAND: {brand['name']}",
        f"Territory YTD {money(brand['ytd_sales'])} vs prior {money(brand['prior_ytd_sales'])} "
        f"({money(brand['variance'])} YoY) across {len(brand['accounts'])} accounts",
    ]
    if entry:
        parent = f" (parent: {entry['parent']})" if entry.get("parent") else ""
        lines.append(f"Line card: {entry['product']}{parent} -- territory {entry['territory']}")
    lines.append("")
    lines.append("ACCOUNTS BUYING IT:")
    for a in brand["accounts"]:
        lines.append(
            f"  {a['account_name']} ({a.get('market') or 'Other'}): {money(a['current_ytd'])} "
            f"vs {money(a['prior_ytd'])} ({money(a['variance'])})"
        )
    return "\n".join(lines)


def tool_open_followups(args):
    conn = _conn()
    market = args.get("market")
    fus = queries.list_followups(conn, status="open", market=market)
    if not fus:
        return "No open follow-ups."
    today = date.today().isoformat()
    lines = [f"OPEN FOLLOW-UPS ({len(fus)}):", ""]
    for f in fus:
        overdue = " [OVERDUE]" if f["due_date"] and f["due_date"] < today else ""
        lines.append(
            f"  {f['due_date'] or 'no date'}{overdue} -- {f['account_name']} "
            f"({f.get('market') or 'Other'}): {f['description']}"
        )
    return "\n".join(lines)


def tool_recent_news(args):
    conn = _conn()
    category = args.get("category")
    limit = int(args.get("limit", 15))
    items = news.list_news(conn, category=category, limit=limit)
    if not items:
        return "No news saved yet. Refresh the News page in the app to pull some in."
    lines = [f"RECENT NEWS{' -- ' + category if category else ''}:", ""]
    for n in items:
        lines.append(f"  [{n['category']}] {n['title']}")
        if n.get("source"):
            lines.append(f"      {n['source']} {n.get('url') or ''}")
    return "\n".join(lines)


def tool_log_call(args):
    conn = _conn()
    account_id = _find_account(conn, args.get("account"))
    if not account_id:
        return f"No account found matching '{args.get('account')}'. Nothing was logged."

    call_date = args.get("date") or date.today().isoformat()
    brand_id = None
    if args.get("brand"):
        row = conn.execute(
            "SELECT id FROM brands WHERE name LIKE ? ORDER BY LENGTH(name) LIMIT 1", (f"%{args['brand']}%",)
        ).fetchone()
        if row:
            brand_id = row["id"]
        else:
            brand_id = importer.get_or_create_brand(conn, args["brand"])

    contact_id = None
    if args.get("contact"):
        contact_id = importer.get_or_create_contact(conn, account_id, args["contact"], source="manual")

    cur = conn.execute(
        """INSERT INTO calls (account_id, contact_id, call_date, report_type, subject, brand_id,
                              attendees, notes, followup_date, followup_notes, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')""",
        (
            account_id, contact_id, call_date,
            args.get("report_type") or "Call Report",
            args.get("subject") or "",
            brand_id,
            args.get("contact") or "",
            args.get("notes") or "",
            args.get("followup_date"),
            args.get("followup_notes") or "",
        ),
    )
    call_id = cur.lastrowid

    created_fu = ""
    if args.get("followup_date"):
        conn.execute(
            """INSERT INTO followups (account_id, contact_id, call_id, description, due_date, source)
               VALUES (?, ?, ?, ?, ?, 'auto')""",
            (account_id, contact_id, call_id,
             args.get("followup_notes") or f"Follow up on {call_date}", args["followup_date"]),
        )
        created_fu = f" Follow-up created for {args['followup_date']}."
    conn.commit()

    acct = conn.execute("SELECT name FROM accounts WHERE id = ?", (account_id,)).fetchone()["name"]
    return f"Logged a {call_date} call at {acct}.{created_fu}"


def tool_add_followup(args):
    conn = _conn()
    account_id = _find_account(conn, args.get("account"))
    if not account_id:
        return f"No account found matching '{args.get('account')}'. Nothing was added."
    conn.execute(
        "INSERT INTO followups (account_id, description, due_date, source) VALUES (?, ?, ?, 'manual')",
        (account_id, args.get("description") or "Follow up", args.get("due_date")),
    )
    conn.commit()
    acct = conn.execute("SELECT name FROM accounts WHERE id = ?", (account_id,)).fetchone()["name"]
    return f"Added follow-up at {acct}: {args.get('description')} (due {args.get('due_date') or 'no date'})."


def tool_list_markets(args):
    conn = _conn()
    rows = conn.execute(
        "SELECT COALESCE(market,'Other') m, COUNT(*) c FROM accounts GROUP BY m ORDER BY c DESC"
    ).fetchall()
    return "MARKETS:\n" + "\n".join(f"  {r['m']}: {r['c']} accounts" for r in rows)


def tool_line_card(args):
    lines = ["BIG RIVERS LINE CARD -- Nebraska & Iowa", ""]
    for e in linecard.active_lines():
        parent = f" ({e['parent']})" if e.get("parent") else " (BRM Sales stock)"
        lines.append(f"  {e['brand']}{parent}: {e['product']} -- {e['territory']}")
    excluded = [e["brand"] for e in linecard.LINE_CARD if not linecard.in_my_territory(e)]
    if excluded:
        lines.append("")
        lines.append(f"On the card but NOT your territory: {', '.join(excluded)}")
    return "\n".join(lines)


TOOLS = [
    {
        "name": "territory_summary",
        "description": "High-level state of the Nebraska/Iowa territory: account and call counts, YTD vs prior-year sales, top visit priorities, and dormant branches. Good opening question.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_territory_summary,
    },
    {
        "name": "who_to_visit",
        "description": "Ranked list of accounts to visit next, with the reasons behind each score (overdue vs target cadence, revenue at stake, YoY decline, owed follow-ups). Filter by market to plan a day trip.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "description": "Lincoln, Omaha, Norfolk, Columbus, Fremont, Sioux City, NW Iowa, or Other"},
                "tier": {"type": "string", "description": "A, B, C or D"},
                "limit": {"type": "integer", "description": "How many to return (default 10)"},
            },
        },
        "handler": tool_who_to_visit,
    },
    {
        "name": "get_account",
        "description": "Full profile for one account: contacts, sales by brand with YoY, whitespace opportunities, open follow-ups, and recent visit notes. Accepts a partial name like 'kelly norfolk'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account name or partial name"},
                "visit_limit": {"type": "integer", "description": "How many recent visits to include (default 8)"},
            },
            "required": ["account"],
        },
        "handler": tool_get_account,
    },
    {
        "name": "search_calls",
        "description": "Search every logged visit by note text, account, brand, or attendee. Use to recall what was discussed, e.g. 'Pro-Flex demo' or 'backflow'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
            "required": ["query"],
        },
        "handler": tool_search_calls,
    },
    {
        "name": "find_opportunities",
        "description": "Where the growth is: dormant branches (same banner, sister branch doing far more) and whitespace (lines an account buys none of that comparable accounts buy).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "description": "Optional market filter"},
                "limit": {"type": "integer", "description": "Max whitespace rows (default 20)"},
            },
        },
        "handler": tool_find_opportunities,
    },
    {
        "name": "brand_performance",
        "description": "How one line is doing across the territory (accounts buying it, YTD, YoY), or omit the brand to list every line. Includes line card details.",
        "inputSchema": {
            "type": "object",
            "properties": {"brand": {"type": "string", "description": "Brand name or partial name; omit for all brands"}},
        },
        "handler": tool_brand_performance,
    },
    {
        "name": "open_followups",
        "description": "Everything currently owed, by due date, with overdue items flagged.",
        "inputSchema": {
            "type": "object",
            "properties": {"market": {"type": "string", "description": "Optional market filter"}},
        },
        "handler": tool_open_followups,
    },
    {
        "name": "recent_news",
        "description": "Saved market and manufacturer news. Categories: regional (Nebraska/Iowa business insight), manufacturer, commodity, demand, market, manual.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional category filter"},
                "limit": {"type": "integer", "description": "Max items (default 15)"},
            },
        },
        "handler": tool_recent_news,
    },
    {
        "name": "line_card",
        "description": "The Big Rivers line card for Nebraska/Iowa: every brand represented, its corporate parent, product description and territory.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_line_card,
    },
    {
        "name": "list_markets",
        "description": "Markets in the territory and how many accounts are in each.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": tool_list_markets,
    },
    {
        "name": "log_call",
        "description": "Log a visit into the territory database. Adds a new record; never overwrites anything. Use after a stop to capture what happened.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account name or partial name"},
                "notes": {"type": "string", "description": "What happened on the call"},
                "date": {"type": "string", "description": "YYYY-MM-DD; defaults to today"},
                "brand": {"type": "string", "description": "Brand/manufacturer discussed"},
                "contact": {"type": "string", "description": "Who you met with"},
                "subject": {"type": "string", "description": "Short subject line"},
                "report_type": {"type": "string", "description": "e.g. Contractor Call Report, Distributor Call Report, Phone Conversation"},
                "followup_date": {"type": "string", "description": "YYYY-MM-DD if a follow-up is owed"},
                "followup_notes": {"type": "string", "description": "What the follow-up is"},
            },
            "required": ["account", "notes"],
        },
        "handler": tool_log_call,
    },
    {
        "name": "add_followup",
        "description": "Add a follow-up task against an account. Additive only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "Account name or partial name"},
                "description": {"type": "string", "description": "What needs to happen"},
                "due_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["account", "description"],
        },
        "handler": tool_add_followup,
    },
]

HANDLERS = {t["name"]: t["handler"] for t in TOOLS}
TOOL_SPECS = [{k: v for k, v in t.items() if k != "handler"} for t in TOOLS]


# ---------------------------------------------------------------------------
# JSON-RPC plumbing
# ---------------------------------------------------------------------------

def handle_request(req):
    """Returns a result dict, or None for notifications (which get no reply)."""
    method = req.get("method")

    if method == "initialize":
        client_version = (req.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION
        return {
            "protocolVersion": client_version,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }

    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None

    if method == "ping":
        return {}

    if method == "tools/list":
        return {"tools": TOOL_SPECS}

    if method in ("resources/list", "prompts/list"):
        # Not offered, but answer politely rather than erroring.
        return {"resources": []} if method == "resources/list" else {"prompts": []}

    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if not handler:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
        try:
            text = handler(args)
        except Exception as e:
            log(f"tool {name} failed: {e}\n{traceback.format_exc()}")
            return {"content": [{"type": "text", "text": f"That query failed: {e}"}], "isError": True}
        return {"content": [{"type": "text", "text": text}], "isError": False}

    raise ValueError(f"Method not found: {method}")


def main():
    try:
        db.init_db()  # ensure schema/migrations before serving
    except Exception as e:
        log(f"database init failed: {e}")

    log(f"ready -- database at {db.DB_PATH}")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            log(f"bad JSON: {e}")
            continue

        req_id = req.get("id")
        try:
            result = handle_request(req)
        except ValueError as e:
            if req_id is not None:
                send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": str(e)}})
            continue
        except Exception as e:
            log(f"handler error: {e}\n{traceback.format_exc()}")
            if req_id is not None:
                send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}})
            continue

        # Notifications have no id and expect no response.
        if req_id is None:
            continue
        send({"jsonrpc": "2.0", "id": req_id, "result": result if result is not None else {}})


def send(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
