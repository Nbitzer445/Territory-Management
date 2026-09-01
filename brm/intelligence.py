"""Territory decision-making: who to see next, and what to sell them.

Everything here is deliberately explainable -- each account's priority score
comes back with the human-readable reasons that produced it, so the ranking
can be trusted (or argued with) rather than taken on faith.

Three ideas drive it:
  1. Priority   -- who's overdue, at risk, or owed something, weighted by how
                   much revenue is actually on the line.
  2. Whitespace -- lines a distributor doesn't buy that its own sister
                   branches (or same-type peers) do. This is the opportunity list.
  3. Clusters   -- those priorities grouped by market, so a day out is a route
                   rather than a scramble.
"""
import math
import re

from . import queries

# --- Visit cadence -----------------------------------------------------------
# Target days between visits by tier. A = your bread and butter, D = long tail.
TIER_CADENCE = {"A": 21, "B": 42, "C": 90, "D": 120}

# Auto-tier by YTD sales when no tier has been set by hand.
TIER_THRESHOLDS = [("A", 50000), ("B", 10000), ("C", 1000)]

DEFAULT_CADENCE = 60  # accounts with no sales history (contractors, prospects)

# --- Priority scoring weights ------------------------------------------------
W_OVERDUE_MAX = 75      # max points from being past cadence
W_REVENUE_MAX = 40      # max points from account size
W_DECLINE_MAX = 55      # max points from YoY erosion
W_FOLLOWUP_OVERDUE = 18  # per overdue follow-up
W_FOLLOWUP_OPEN = 8      # per open (not yet due) follow-up
W_FOLLOWUP_MAX = 36


def suggest_tier(ytd_sales):
    ytd = ytd_sales or 0
    for tier, threshold in TIER_THRESHOLDS:
        if ytd >= threshold:
            return tier
    return "D"


def effective_tier(account):
    """Hand-set tier wins; otherwise derive from sales."""
    return (account.get("tier") or "").strip().upper() or suggest_tier(account.get("ytd_sales"))


def target_cadence(account):
    """Explicit per-account override wins, then tier default."""
    override = account.get("cadence_days")
    if override:
        return int(override)
    tier = effective_tier(account)
    if not account.get("ytd_sales"):
        # No sales history -- treat as a relationship call, not a revenue call.
        return max(TIER_CADENCE.get(tier, DEFAULT_CADENCE), DEFAULT_CADENCE)
    return TIER_CADENCE.get(tier, DEFAULT_CADENCE)


def compute_priority(account, max_ytd=None, followup_counts=None):
    """Score one account. Returns {score, reasons, tier, cadence, ...}.

    `account` is a dict from queries.list_accounts (already carries
    days_since_visit, ytd_sales, yoy_variance, etc).
    """
    reasons = []
    score = 0.0

    tier = effective_tier(account)
    cadence = target_cadence(account)
    days = account.get("days_since_visit")
    ytd = account.get("ytd_sales") or 0
    variance = account.get("yoy_variance") or 0
    prior = account.get("prior_ytd_sales") or 0

    # 1. Cadence -------------------------------------------------------------
    if days is None:
        if ytd > 0:
            score += 60
            reasons.append("never visited but buying")
        else:
            score += 15
            reasons.append("never visited")
    else:
        ratio = days / cadence if cadence else 0
        if ratio >= 1:
            pts = min(ratio, 3.0) / 3.0 * W_OVERDUE_MAX
            score += pts
            over = days - cadence
            reasons.append(f"{days}d since visit -- {over}d past {tier}-tier target of {cadence}d")
        elif ratio >= 0.75:
            score += 8
            reasons.append(f"due soon ({days}d of {cadence}d target)")

    # 2. Revenue at stake ----------------------------------------------------
    # Log-scaled so a $500k account doesn't drown out everything else.
    if ytd > 0 and max_ytd:
        pts = (math.log10(ytd + 1) / math.log10(max_ytd + 1)) * W_REVENUE_MAX
        score += pts
        if ytd >= 50000:
            reasons.append(f"${ytd:,.0f} YTD at stake")

    # 3. YoY erosion ---------------------------------------------------------
    if variance < 0 and prior > 0:
        pct_drop = abs(variance) / prior
        pts = min(pct_drop, 1.0) * W_DECLINE_MAX
        # Weight the drop by how material it is in dollars.
        if abs(variance) < 1000:
            pts *= 0.3
        score += pts
        reasons.append(f"down ${abs(variance):,.0f} ({pct_drop * 100:.0f}%) vs last year")

    # 4. Owed follow-ups -----------------------------------------------------
    if followup_counts:
        overdue = followup_counts.get("overdue", 0)
        openish = followup_counts.get("open", 0)
        pts = min(overdue * W_FOLLOWUP_OVERDUE + openish * W_FOLLOWUP_OPEN, W_FOLLOWUP_MAX)
        if pts:
            score += pts
            if overdue:
                reasons.append(f"{overdue} overdue follow-up{'s' if overdue > 1 else ''}")
            elif openish:
                reasons.append(f"{openish} open follow-up{'s' if openish > 1 else ''}")

    return {
        "score": round(score, 1),
        "reasons": reasons,
        "tier": tier,
        "cadence": cadence,
        "auto_tier": not (account.get("tier") or "").strip(),
    }


def _followup_counts_by_account(conn):
    """{account_id: {'open': n, 'overdue': n}} for open follow-ups."""
    from datetime import date

    today = date.today().isoformat()
    counts = {}
    rows = conn.execute(
        "SELECT account_id, due_date FROM followups WHERE status = 'open'"
    ).fetchall()
    for r in rows:
        entry = counts.setdefault(r["account_id"], {"open": 0, "overdue": 0})
        if r["due_date"] and r["due_date"] < today:
            entry["overdue"] += 1
        else:
            entry["open"] += 1
    return counts


def prioritized_accounts(conn, market=None, tier=None, limit=None, include_zero_sales=True):
    """All accounts, scored and ranked highest-priority first."""
    accounts = queries.list_accounts(conn, market=market)
    if not accounts:
        return []
    max_ytd = max((a.get("ytd_sales") or 0) for a in accounts) or 1
    followups = _followup_counts_by_account(conn)

    scored = []
    for a in accounts:
        if not include_zero_sales and not (a.get("ytd_sales") or 0):
            continue
        p = compute_priority(a, max_ytd=max_ytd, followup_counts=followups.get(a["id"]))
        if tier and p["tier"] != tier:
            continue
        a = dict(a)
        a.update(p)
        scored.append(a)

    scored.sort(key=lambda a: -a["score"])
    return scored[:limit] if limit else scored


# ---------------------------------------------------------------------------
# Chain detection -- sister branches are the best possible comparison
# ---------------------------------------------------------------------------

_CITY_WORDS = {
    "omaha", "lincoln", "norfolk", "columbus", "fremont", "carroll", "spencer",
    "sioux", "city", "south", "council", "bluffs", "la", "vista", "le", "mars",
    "center", "storm", "lake", "red", "oak", "showroom", "nesc",
}


def chain_key(name):
    """Reduce an account name to the chain it belongs to.

    'Ferguson Enterprises Omaha on Grover St #226' -> 'ferguson enterprises'
    'Kelly Supply Norfolk'                          -> 'kelly supply'
    """
    if not name:
        return ""
    s = name.lower()
    s = re.split(r"\s+on\s+", s)[0]        # drop street qualifiers
    s = re.sub(r"#\s*\d+", " ", s)          # drop branch numbers
    s = re.sub(r"\(.*?\)", " ", s)          # drop parentheticals
    s = re.sub(r"[^a-z0-9\s]", " ", s)      # drop punctuation
    tokens = [t for t in s.split() if t]
    kept = []
    for t in tokens:
        if t in _CITY_WORDS and kept:
            break
        kept.append(t)
    if not kept:
        kept = tokens[:2]
    return " ".join(kept[:2]).strip()


# ---------------------------------------------------------------------------
# Whitespace -- what they're NOT buying that comparable accounts are
# ---------------------------------------------------------------------------

def _sales_matrix(conn):
    """{account_id: {brand_id: current_ytd}} for the latest sales snapshot."""
    batch_id = queries.latest_sales_batch_id(conn)
    if not batch_id:
        return {}, {}
    matrix = {}
    brand_names = {}
    rows = conn.execute(
        """SELECT s.account_id, s.brand_id, s.current_ytd, b.name AS brand_name, b.category
           FROM sales_snapshots s JOIN brands b ON b.id = s.brand_id
           WHERE s.import_batch_id = ?""",
        (batch_id,),
    ).fetchall()
    for r in rows:
        if r["category"] == "admin":
            continue
        matrix.setdefault(r["account_id"], {})[r["brand_id"]] = r["current_ytd"] or 0
        brand_names[r["brand_id"]] = r["brand_name"]
    return matrix, brand_names


def _median(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return 0
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


# A regional distribution center can book 100x what a branch does, which would
# otherwise turn one DC into a fantasy benchmark for every small branch.
OUTLIER_MULTIPLE = 5

# Floor on the per-opportunity credibility cap, so a nearly-dormant branch
# still surfaces opportunities instead of being capped down to nothing.
MIN_OPPORTUNITY_CAP = 5000

# A branch doing less than this share of its chain's median is "dormant".
DORMANT_SHARE = 0.10


def _robust_benchmark(values):
    """Median with extreme high outliers trimmed."""
    vals = sorted(v for v in values if v)
    if not vals:
        return 0
    if len(vals) >= 3:
        med = _median(vals)
        trimmed = [v for v in vals if v <= med * OUTLIER_MULTIPLE]
        if trimmed:
            vals = trimmed
    return _median(vals)


def _healthy_peer_level(values):
    """Median of the top half -- 'what a branch of this banner does when it's working'.

    A plain median lies on a bimodal chain (two strong branches, three asleep),
    and the plain maximum lies when one member is really a regional DC.
    """
    vals = sorted(v for v in values)
    if not vals:
        return 0
    upper = vals[len(vals) // 2:]
    return _median(upper)


def whitespace_for_account(conn, account_id, min_peer_buyers=2, limit=12):
    """Brands this account buys $0 of that comparable accounts do buy.

    Peers are, in order of confidence:
      1. sister branches of the same chain
      2. accounts of the same company type that carry sales
    """
    matrix, brand_names = _sales_matrix(conn)
    if not matrix:
        return []

    account = queries.get_account(conn, account_id)
    if not account:
        return []

    all_accounts = {a["id"]: a for a in queries.list_accounts(conn)}
    mine = matrix.get(account_id, {})
    my_total = sum(mine.values())

    my_chain = chain_key(account["name"])
    chain_peers = [
        aid for aid, a in all_accounts.items()
        if aid != account_id and chain_key(a["name"]) == my_chain and aid in matrix
    ]
    type_peers = [
        aid for aid, a in all_accounts.items()
        if aid != account_id and aid in matrix
        and (a.get("company_type") or "") == (account.get("company_type") or "")
    ]

    peers = chain_peers if len(chain_peers) >= min_peer_buyers else type_peers
    peer_kind = "sister branches" if peers is chain_peers and chain_peers else "similar accounts"
    if not peers:
        return []

    # Scale the peer benchmark to this account's actual size. No generous floor:
    # a branch a tenth the size of its peers gets a tenth of the benchmark.
    peer_totals = [sum(matrix.get(p, {}).values()) for p in peers]
    median_peer_total = _robust_benchmark(peer_totals)
    if median_peer_total and my_total:
        size_ratio = max(0.05, min(my_total / median_peer_total, 1.5))
    else:
        size_ratio = 0.1

    results = []
    candidate_brands = {b for p in peers for b in matrix.get(p, {})}
    for brand_id in candidate_brands:
        if mine.get(brand_id, 0) > 0:
            continue  # already buying it
        buyers = [matrix[p][brand_id] for p in peers if matrix.get(p, {}).get(brand_id, 0) > 0]
        if len(buyers) < min_peer_buyers:
            continue
        benchmark = _robust_benchmark(buyers)
        estimate = benchmark * size_ratio
        # Credibility cap: one new line realistically doesn't add more than
        # half of what an account already buys from you in a year -- but never
        # cap so hard that a nearly-dormant branch shows no opportunity at all.
        estimate = min(estimate, max(my_total * 0.5, MIN_OPPORTUNITY_CAP))
        if estimate < 100:
            continue
        results.append({
            "brand_id": brand_id,
            "brand_name": brand_names.get(brand_id, "?"),
            "peer_buyers": len(buyers),
            "peer_kind": peer_kind,
            "peer_median": benchmark,
            "estimate": estimate,
            "best_peer": max(buyers),
        })

    results.sort(key=lambda r: -r["estimate"])
    return results[:limit]


def territory_opportunities(conn, limit=40, min_estimate=500):
    """Whitespace across every account that has sales, ranked by size."""
    matrix, _ = _sales_matrix(conn)
    out = []
    for account_id in matrix:
        account = queries.get_account(conn, account_id)
        if not account:
            continue
        for w in whitespace_for_account(conn, account_id, limit=5):
            if w["estimate"] < min_estimate:
                continue
            row = dict(w)
            row["account_id"] = account_id
            row["account_name"] = account["name"]
            row["market"] = account.get("market")
            row["days_since_visit"] = account.get("days_since_visit")
            out.append(row)
    out.sort(key=lambda r: -r["estimate"])
    return out[:limit]


def dormant_branches(conn, min_chain_size=2, min_chain_median=2000):
    """Branches doing almost nothing while their sister branches do real volume.

    This is the highest-signal finding in a multi-branch territory: same banner,
    same buying group, wildly different results usually means a relationship
    gap rather than a market gap.
    """
    matrix, _ = _sales_matrix(conn)
    if not matrix:
        return []

    accounts = {a["id"]: a for a in queries.list_accounts(conn)}
    totals = {aid: sum(brands.values()) for aid, brands in matrix.items()}

    # Group accounts that carry sales into chains.
    chains = {}
    for aid in matrix:
        acct = accounts.get(aid)
        if not acct:
            continue
        chains.setdefault(chain_key(acct["name"]), []).append(aid)

    findings = []
    for chain, members in chains.items():
        if len(members) < min_chain_size + 1:
            continue
        member_totals = [totals.get(m, 0) for m in members]
        healthy = _healthy_peer_level(member_totals)
        if healthy < min_chain_median:
            continue
        best = max(member_totals)
        for aid in members:
            total = totals.get(aid, 0)
            if total >= healthy * DORMANT_SHARE:
                continue
            acct = accounts[aid]
            findings.append({
                "account_id": aid,
                "account_name": acct["name"],
                "market": acct.get("market"),
                "days_since_visit": acct.get("days_since_visit"),
                "ytd_sales": total,
                "chain": chain,
                "chain_median": healthy,
                "chain_best": best,
                "gap": healthy - total,
                "peer_count": len(members) - 1,
            })

    findings.sort(key=lambda f: -f["gap"])
    return findings


# ---------------------------------------------------------------------------
# Route clustering -- turn priorities into day trips
# ---------------------------------------------------------------------------

def market_clusters(conn, per_market=6, min_score=0):
    """Group top-priority accounts by market so a day out is a route."""
    scored = prioritized_accounts(conn)
    clusters = {}
    for a in scored:
        if a["score"] < min_score:
            continue
        market = a.get("market") or "Other"
        clusters.setdefault(market, []).append(a)

    out = []
    for market, accounts in clusters.items():
        top = accounts[:per_market]
        out.append({
            "market": market,
            "accounts": top,
            "total_score": round(sum(a["score"] for a in top), 1),
            "total_ytd": sum(a.get("ytd_sales") or 0 for a in top),
            "overdue_count": sum(
                1 for a in accounts
                if a.get("days_since_visit") is not None and a["days_since_visit"] > a["cadence"]
            ),
            "account_count": len(accounts),
        })
    out.sort(key=lambda c: -c["total_score"])
    return out
