"""Read-side query helpers: dashboard stats, sales intelligence, account/brand
rollups. Kept as plain SQL over the sqlite3 connection -- no ORM.
"""
from datetime import date, datetime, timedelta


def _today_iso():
    return date.today().isoformat()


def days_since(iso_date):
    if not iso_date:
        return None
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (date.today() - d).days


# ---------------------------------------------------------------------------
# Accounts with computed fields
# ---------------------------------------------------------------------------

def list_accounts(conn, market=None, company_type=None, brand_id=None, search=None, sort="name"):
    where = []
    params = []
    joins = ""
    if brand_id:
        joins = "JOIN calls cbrand ON cbrand.account_id = a.id AND cbrand.brand_id = ?"
        params.append(brand_id)
    if market:
        where.append("a.market = ?")
        params.append(market)
    if company_type:
        where.append("a.company_type = ?")
        params.append(company_type)
    if search:
        where.append("a.name LIKE ?")
        params.append(f"%{search}%")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT DISTINCT a.*
        FROM accounts a
        {joins}
        {where_sql}
    """
    rows = conn.execute(sql, params).fetchall()
    accounts = [dict(r) for r in rows]

    for acct in accounts:
        acct.update(account_computed_fields(conn, acct["id"]))

    sort_key = {
        "name": lambda x: (x["name"] or "").lower(),
        "days_since_visit": lambda x: (x["days_since_visit"] if x["days_since_visit"] is not None else 999999),
        "ytd_sales": lambda x: -(x["ytd_sales"] or 0),
        "yoy_variance": lambda x: (x["yoy_variance"] or 0),
    }.get(sort, lambda x: (x["name"] or "").lower())
    accounts.sort(key=sort_key)
    return accounts


# ---------------------------------------------------------------------------
# Buying groups
# ---------------------------------------------------------------------------

def list_groups(conn):
    rows = conn.execute("SELECT * FROM account_groups ORDER BY name").fetchall()
    groups = []
    for r in rows:
        g = dict(r)
        g.update(group_rollup(conn, g["id"]))
        groups.append(g)
    groups.sort(key=lambda g: -(g["ytd_sales"] or 0))
    return groups


def group_members(conn, group_id):
    rows = conn.execute(
        "SELECT id FROM accounts WHERE group_id = ? ORDER BY name", (group_id,)
    ).fetchall()
    return [r["id"] for r in rows]


def group_rollup(conn, group_id):
    """Combined numbers for a buying group -- the figures that actually mean something."""
    member_ids = group_members(conn, group_id)
    if not member_ids:
        return {"member_count": 0, "ytd_sales": 0, "prior_ytd_sales": 0, "yoy_variance": 0,
                "total_visits": 0, "last_visit_date": None, "days_since_visit": None}
    placeholders = ",".join("?" for _ in member_ids)
    batch_id = latest_sales_batch_id(conn)
    ytd = prior = 0.0
    if batch_id:
        row = conn.execute(
            f"""SELECT SUM(current_ytd) cur, SUM(prior_ytd) pri FROM sales_snapshots
                WHERE import_batch_id = ? AND account_id IN ({placeholders})""",
            [batch_id] + member_ids,
        ).fetchone()
        ytd = row["cur"] or 0.0
        prior = row["pri"] or 0.0
    visits = conn.execute(
        f"SELECT COUNT(*) c FROM calls WHERE account_id IN ({placeholders})", member_ids
    ).fetchone()["c"]
    last = conn.execute(
        f"SELECT MAX(call_date) d FROM calls WHERE account_id IN ({placeholders})", member_ids
    ).fetchone()["d"]
    return {
        "member_count": len(member_ids),
        "ytd_sales": ytd,
        "prior_ytd_sales": prior,
        "yoy_variance": ytd - prior,
        "total_visits": visits,
        "last_visit_date": last,
        "days_since_visit": days_since(last),
    }


def group_sales_by_brand(conn, group_id):
    """Combined brand-level sales across every branch in the group."""
    member_ids = group_members(conn, group_id)
    batch_id = latest_sales_batch_id(conn)
    if not member_ids or not batch_id:
        return []
    placeholders = ",".join("?" for _ in member_ids)
    rows = conn.execute(
        f"""SELECT b.id AS brand_id, b.name AS brand_name,
                   SUM(s.current_ytd) AS current_ytd,
                   SUM(s.prior_ytd) AS prior_ytd,
                   COUNT(DISTINCT s.account_id) AS branches
            FROM sales_snapshots s JOIN brands b ON b.id = s.brand_id
            WHERE s.import_batch_id = ? AND s.account_id IN ({placeholders})
            GROUP BY b.id ORDER BY SUM(s.current_ytd) DESC""",
        [batch_id] + member_ids,
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["variance"] = (d["current_ytd"] or 0) - (d["prior_ytd"] or 0)
        out.append(d)
    return out


def get_group(conn, group_id):
    row = conn.execute("SELECT * FROM account_groups WHERE id = ?", (group_id,)).fetchone()
    if not row:
        return None
    g = dict(row)
    g.update(group_rollup(conn, group_id))
    g["accounts"] = [get_account(conn, aid) for aid in group_members(conn, group_id)]
    g["sales_by_brand"] = group_sales_by_brand(conn, group_id)
    return g


def group_map(conn):
    """{account_id: (group_id, group_name)} for every grouped account."""
    rows = conn.execute(
        """SELECT a.id, a.group_id, g.name FROM accounts a
           JOIN account_groups g ON g.id = a.group_id
           WHERE a.group_id IS NOT NULL"""
    ).fetchall()
    return {r["id"]: (r["group_id"], r["name"]) for r in rows}


def siblings_map(conn):
    """{account_id: [all account_ids sharing its group, including itself]}."""
    rows = conn.execute(
        "SELECT id, group_id FROM accounts WHERE group_id IS NOT NULL"
    ).fetchall()
    by_group = {}
    for r in rows:
        by_group.setdefault(r["group_id"], []).append(r["id"])
    return {r["id"]: by_group[r["group_id"]] for r in rows}


def account_computed_fields(conn, account_id):
    last_call = conn.execute(
        "SELECT call_date FROM calls WHERE account_id = ? ORDER BY call_date DESC LIMIT 1", (account_id,)
    ).fetchone()
    total_visits = conn.execute("SELECT COUNT(*) c FROM calls WHERE account_id = ?", (account_id,)).fetchone()["c"]
    sales = current_sales_for_account(conn, account_id)
    ytd = sum(s["current_ytd"] or 0 for s in sales)
    prior = sum(s["prior_ytd"] or 0 for s in sales)
    last_visit_date = last_call["call_date"] if last_call else None
    fields = {
        "last_visit_date": last_visit_date,
        "days_since_visit": days_since(last_visit_date),
        "total_visits": total_visits,
        "ytd_sales": ytd,
        "prior_ytd_sales": prior,
        "yoy_variance": ytd - prior,
        "group_id": None,
        "group_name": None,
        "group_ytd_sales": None,
        "group_yoy_variance": None,
    }

    # If this branch belongs to a buying group, the group's combined figures
    # are the meaningful ones -- a PO raised at one branch and transferred to
    # another lands all the revenue on a single account.
    row = conn.execute(
        """SELECT a.group_id, g.name FROM accounts a
           LEFT JOIN account_groups g ON g.id = a.group_id
           WHERE a.id = ?""",
        (account_id,),
    ).fetchone()
    if row and row["group_id"]:
        roll = group_rollup(conn, row["group_id"])
        fields["group_id"] = row["group_id"]
        fields["group_name"] = row["name"]
        fields["group_ytd_sales"] = roll["ytd_sales"]
        fields["group_yoy_variance"] = roll["yoy_variance"]
    return fields


def get_account(conn, account_id):
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if not row:
        return None
    acct = dict(row)
    acct.update(account_computed_fields(conn, account_id))
    return acct


def latest_sales_batch_id(conn):
    row = conn.execute(
        "SELECT id FROM import_batches WHERE batch_type = 'sales' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def current_sales_for_account(conn, account_id):
    batch_id = latest_sales_batch_id(conn)
    if not batch_id:
        return []
    rows = conn.execute(
        """SELECT s.*, b.name AS brand_name FROM sales_snapshots s
           JOIN brands b ON b.id = s.brand_id
           WHERE s.account_id = ? AND s.import_batch_id = ?
           ORDER BY s.current_ytd DESC""",
        (account_id, batch_id),
    ).fetchall()
    return [dict(r) for r in rows]


def sales_history_for_account(conn, account_id):
    rows = conn.execute(
        """SELECT s.*, b.name AS brand_name, ib.imported_at, ib.filename
           FROM sales_snapshots s
           JOIN brands b ON b.id = s.brand_id
           JOIN import_batches ib ON ib.id = s.import_batch_id
           WHERE s.account_id = ?
           ORDER BY ib.id DESC, s.current_ytd DESC""",
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def call_history_for_account(conn, account_id):
    rows = conn.execute(
        """SELECT c.*, b.name AS brand_name, ct.name AS contact_name
           FROM calls c
           LEFT JOIN brands b ON b.id = c.brand_id
           LEFT JOIN contacts ct ON ct.id = c.contact_id
           WHERE c.account_id = ?
           ORDER BY c.call_date DESC, c.id DESC""",
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def contacts_for_account(conn, account_id):
    rows = conn.execute(
        "SELECT * FROM contacts WHERE account_id = ? ORDER BY name", (account_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def followups_for_account(conn, account_id):
    rows = conn.execute(
        """SELECT f.*, ct.name AS contact_name FROM followups f
           LEFT JOIN contacts ct ON ct.id = f.contact_id
           WHERE f.account_id = ? ORDER BY f.status ASC, f.due_date ASC""",
        (account_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

def list_followups(conn, status="open", market=None, account_id=None):
    where = []
    params = []
    if status and status != "all":
        where.append("f.status = ?")
        params.append(status)
    if account_id:
        where.append("f.account_id = ?")
        params.append(account_id)
    if market:
        where.append("a.market = ?")
        params.append(market)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"""SELECT f.*, a.name AS account_name, a.market, ct.name AS contact_name
            FROM followups f
            JOIN accounts a ON a.id = f.account_id
            LEFT JOIN contacts ct ON ct.id = f.contact_id
            {where_sql}
            ORDER BY (f.due_date IS NULL), f.due_date ASC""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def followups_due_this_week(conn):
    end = (date.today() + timedelta(days=7)).isoformat()
    today = _today_iso()
    rows = conn.execute(
        """SELECT f.*, a.name AS account_name, a.market FROM followups f
           JOIN accounts a ON a.id = f.account_id
           WHERE f.status = 'open' AND f.due_date IS NOT NULL AND f.due_date <= ?
           ORDER BY f.due_date ASC""",
        (end,),
    ).fetchall()
    result = [dict(r) for r in rows]
    for r in result:
        r["overdue"] = r["due_date"] is not None and r["due_date"] < today
    return result


# ---------------------------------------------------------------------------
# Dashboard / sales intelligence
# ---------------------------------------------------------------------------

def accounts_overdue_for_visit(conn, min_days=45, limit=25):
    accounts = list_accounts(conn)
    with_sales = [a for a in accounts if (a["days_since_visit"] is None or a["days_since_visit"] >= min_days)]
    with_sales.sort(key=lambda a: (a["days_since_visit"] if a["days_since_visit"] is not None else 999999), reverse=True)
    return with_sales[:limit]


def top_movers(conn, limit=10):
    batch_id = latest_sales_batch_id(conn)
    if not batch_id:
        return {"growth": [], "decline": []}
    rows = conn.execute(
        """SELECT s.*, a.name AS account_name, a.id AS account_id, b.name AS brand_name
           FROM sales_snapshots s
           JOIN accounts a ON a.id = s.account_id
           JOIN brands b ON b.id = s.brand_id
           WHERE s.import_batch_id = ?""",
        (batch_id,),
    ).fetchall()
    rows = [dict(r) for r in rows]
    growth = sorted([r for r in rows if (r["variance"] or 0) > 0], key=lambda r: -(r["variance"] or 0))[:limit]
    decline = sorted([r for r in rows if (r["variance"] or 0) < 0], key=lambda r: (r["variance"] or 0))[:limit]
    return {"growth": growth, "decline": decline}


def neglected_revenue_accounts(conn, min_days=60, min_ytd=1000, limit=15):
    accounts = list_accounts(conn)
    flagged = [
        a for a in accounts
        if (a["days_since_visit"] is None or a["days_since_visit"] >= min_days) and (a["ytd_sales"] or 0) >= min_ytd
    ]
    flagged.sort(key=lambda a: -(a["ytd_sales"] or 0))
    return flagged[:limit]


def brand_share_trend(conn):
    batch_id = latest_sales_batch_id(conn)
    if not batch_id:
        return []
    rows = conn.execute(
        """SELECT b.id, b.name, SUM(s.current_ytd) cur, SUM(s.prior_ytd) prior
           FROM sales_snapshots s JOIN brands b ON b.id = s.brand_id
           WHERE s.import_batch_id = ? AND b.category != 'admin'
           GROUP BY b.id ORDER BY cur DESC""",
        (batch_id,),
    ).fetchall()
    result = []
    for r in rows:
        r = dict(r)
        r["variance"] = (r["cur"] or 0) - (r["prior"] or 0)
        r["pct_change"] = ((r["variance"] / r["prior"]) * 100) if r["prior"] else None
        result.append(r)
    return result


def dashboard_stats(conn):
    total_accounts = conn.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"]
    total_calls = conn.execute("SELECT COUNT(*) c FROM calls").fetchone()["c"]
    open_followups = conn.execute("SELECT COUNT(*) c FROM followups WHERE status='open'").fetchone()["c"]
    batch_id = latest_sales_batch_id(conn)
    total_ytd = total_prior = 0.0
    if batch_id:
        row = conn.execute(
            "SELECT SUM(current_ytd) cur, SUM(prior_ytd) prior FROM sales_snapshots WHERE import_batch_id = ?",
            (batch_id,),
        ).fetchone()
        total_ytd = row["cur"] or 0.0
        total_prior = row["prior"] or 0.0
    return {
        "total_accounts": total_accounts,
        "total_calls": total_calls,
        "open_followups": open_followups,
        "total_ytd": total_ytd,
        "total_prior_ytd": total_prior,
        "total_variance": total_ytd - total_prior,
    }


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------

def list_brands(conn):
    batch_id = latest_sales_batch_id(conn)
    rows = conn.execute("SELECT * FROM brands ORDER BY name").fetchall()
    brands = [dict(r) for r in rows]
    for b in brands:
        if batch_id:
            agg = conn.execute(
                "SELECT SUM(current_ytd) cur, SUM(prior_ytd) prior, COUNT(DISTINCT account_id) n "
                "FROM sales_snapshots WHERE brand_id = ? AND import_batch_id = ?",
                (b["id"], batch_id),
            ).fetchone()
            b["ytd_sales"] = agg["cur"] or 0
            b["prior_ytd_sales"] = agg["prior"] or 0
            b["variance"] = (agg["cur"] or 0) - (agg["prior"] or 0)
            b["account_count"] = agg["n"] or 0
        else:
            b["ytd_sales"] = b["prior_ytd_sales"] = b["variance"] = b["account_count"] = 0
        b["call_count"] = conn.execute(
            "SELECT COUNT(*) c FROM calls WHERE brand_id = ?", (b["id"],)
        ).fetchone()["c"]
    brands.sort(key=lambda b: -(b["ytd_sales"] or 0))
    return brands


def get_brand(conn, brand_id):
    row = conn.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
    if not row:
        return None
    brand = dict(row)
    batch_id = latest_sales_batch_id(conn)
    if batch_id:
        rows = conn.execute(
            """SELECT s.*, a.name AS account_name, a.id AS account_id, a.market
               FROM sales_snapshots s JOIN accounts a ON a.id = s.account_id
               WHERE s.brand_id = ? AND s.import_batch_id = ?
               ORDER BY s.current_ytd DESC""",
            (brand_id, batch_id),
        ).fetchall()
        brand["accounts"] = [dict(r) for r in rows]
        brand["ytd_sales"] = sum(r["current_ytd"] or 0 for r in brand["accounts"])
        brand["prior_ytd_sales"] = sum(r["prior_ytd"] or 0 for r in brand["accounts"])
        brand["variance"] = brand["ytd_sales"] - brand["prior_ytd_sales"]
    else:
        brand["accounts"] = []
        brand["ytd_sales"] = brand["prior_ytd_sales"] = brand["variance"] = 0
    return brand
