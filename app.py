"""BRM Territory Hub -- a fully local territory management app for a
Big Rivers Marketing outside sales rep covering Nebraska and Iowa.

Everything runs on your machine. Data lives in data/territory.db (SQLite).
No account/sales data is ever sent anywhere. The only outbound network
calls this app makes are public news searches (see brm/news.py), and those
only ever send brand names / commodity search terms -- never your data.
"""
import os
from datetime import date, datetime, timedelta

from flask import Flask, g, render_template, request, redirect, url_for, flash, jsonify

from brm import db, importer, queries, news, intelligence

app = Flask(__name__)
app.secret_key = "brm-territory-hub-local-only"  # local single-user app; not security sensitive
# Pick up edited templates without a restart, so an update applies as soon as
# the files land.
app.config["TEMPLATES_AUTO_RELOAD"] = True

UPLOAD_DIR = db.DATA_DIR / "imports"


def get_db():
    if "db" not in g:
        g.db = db.get_connection()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.template_filter("money")
def money(v):
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        v = 0
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.0f}"


@app.template_filter("pct")
def pct(v):
    if v is None:
        return "--"
    return f"{v:+.1f}%"


@app.template_filter("dateshort")
def dateshort(v):
    if not v:
        return "--"
    try:
        d = datetime.strptime(v, "%Y-%m-%d").date()
        return d.strftime("%b %-d, %Y")
    except ValueError:
        return v


@app.context_processor
def inject_globals():
    return {"markets": importer.MARKETS, "today": date.today().isoformat()}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    conn = get_db()
    stats = queries.dashboard_stats(conn)
    due_this_week = queries.followups_due_this_week(conn)
    overdue_visits = queries.accounts_overdue_for_visit(conn, min_days=45, limit=12)
    movers = queries.top_movers(conn, limit=8)
    neglected = queries.neglected_revenue_accounts(conn, limit=8)
    top_targets = intelligence.prioritized_accounts(conn, limit=8)
    dormant = intelligence.dormant_branches(conn)[:5]
    news_items = news.list_news(conn, limit=8)
    news_last_refresh = news.last_refreshed(conn)
    return render_template(
        "dashboard.html",
        stats=stats,
        due_this_week=due_this_week,
        overdue_visits=overdue_visits,
        movers=movers,
        neglected=neglected,
        top_targets=top_targets,
        dormant=dormant,
        news_items=news_items,
        news_last_refresh=news_last_refresh,
    )


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@app.route("/accounts")
def accounts_list():
    conn = get_db()
    market = request.args.get("market") or None
    company_type = request.args.get("company_type") or None
    brand_id = request.args.get("brand_id", type=int)
    search = request.args.get("q") or None
    sort = request.args.get("sort", "name")
    accounts = queries.list_accounts(conn, market=market, company_type=company_type, brand_id=brand_id, search=search, sort=sort)
    company_types = [r["company_type"] for r in conn.execute("SELECT DISTINCT company_type FROM accounts WHERE company_type IS NOT NULL AND company_type != '' ORDER BY company_type")]
    brands = conn.execute("SELECT id, name FROM brands ORDER BY name").fetchall()
    return render_template(
        "accounts_list.html",
        accounts=accounts,
        company_types=company_types,
        brands=brands,
        filters={"market": market, "company_type": company_type, "brand_id": brand_id, "q": search or "", "sort": sort},
    )


@app.route("/accounts/new", methods=["POST"])
def account_new():
    conn = get_db()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Account name is required.", "error")
        return redirect(url_for("accounts_list"))
    account_id = importer.upsert_account(
        conn,
        name,
        company_type=request.form.get("company_type") or None,
        market=request.form.get("market") or importer.infer_market(name),
        city=request.form.get("city") or None,
        source="manual",
    )
    conn.commit()
    flash(f"Added account: {name}", "success")
    return redirect(url_for("account_detail", account_id=account_id))


@app.route("/accounts/<int:account_id>")
def account_detail(account_id):
    conn = get_db()
    account = queries.get_account(conn, account_id)
    if not account:
        flash("Account not found.", "error")
        return redirect(url_for("accounts_list"))
    contacts = queries.contacts_for_account(conn, account_id)
    calls = queries.call_history_for_account(conn, account_id)
    sales = queries.current_sales_for_account(conn, account_id)
    followups = queries.followups_for_account(conn, account_id)
    brands = conn.execute("SELECT id, name FROM brands ORDER BY name").fetchall()
    account_news = news.list_news(conn, account_id=account_id, limit=20)

    priority = intelligence.priority_for_account(conn, account)
    whitespace = intelligence.whitespace_for_account(conn, account_id)

    return render_template(
        "account_detail.html",
        account=account,
        contacts=contacts,
        calls=calls,
        sales=sales,
        followups=followups,
        brands=brands,
        account_news=account_news,
        priority=priority,
        whitespace=whitespace,
        tier_cadence=intelligence.TIER_CADENCE,
        all_groups=conn.execute("SELECT id, name FROM account_groups ORDER BY name").fetchall(),
    )


# ---------------------------------------------------------------------------
# Plan -- who to see next, and how to group the trip
# ---------------------------------------------------------------------------

@app.route("/plan")
def plan():
    conn = get_db()
    market = request.args.get("market") or None
    tier = request.args.get("tier") or None
    targets = intelligence.prioritized_accounts(conn, market=market, tier=tier, limit=30)
    clusters = intelligence.market_clusters(conn, per_market=6)
    return render_template(
        "plan.html",
        targets=targets,
        clusters=clusters,
        filters={"market": market, "tier": tier},
        tier_cadence=intelligence.TIER_CADENCE,
    )


# ---------------------------------------------------------------------------
# Buying groups
# ---------------------------------------------------------------------------

@app.route("/groups")
def groups_list():
    conn = get_db()
    groups = queries.list_groups(conn)
    suggestions = intelligence.suggested_groups(conn)
    return render_template("groups.html", groups=groups, suggestions=suggestions)


@app.route("/groups/new", methods=["POST"])
def group_new():
    conn = get_db()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Give the group a name.", "error")
        return redirect(url_for("groups_list"))
    existing = conn.execute("SELECT id FROM account_groups WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if existing:
        group_id = existing["id"]
    else:
        cur = conn.execute(
            "INSERT INTO account_groups (name, notes) VALUES (?, ?)",
            (name, request.form.get("notes", "").strip()),
        )
        group_id = cur.lastrowid

    # Optionally assign a whole detected chain at once.
    chain = request.form.get("chain", "").strip()
    assigned = 0
    if chain:
        for row in conn.execute("SELECT id, name FROM accounts").fetchall():
            if intelligence.chain_key(row["name"]) == chain:
                conn.execute("UPDATE accounts SET group_id = ? WHERE id = ?", (group_id, row["id"]))
                assigned += 1
    conn.commit()
    flash(f"Created '{name}'" + (f" with {assigned} account(s)." if assigned else "."), "success")
    return redirect(url_for("group_detail", group_id=group_id))


@app.route("/groups/<int:group_id>")
def group_detail(group_id):
    conn = get_db()
    group = queries.get_group(conn, group_id)
    if not group:
        flash("Group not found.", "error")
        return redirect(url_for("groups_list"))
    unassigned = conn.execute(
        "SELECT id, name FROM accounts WHERE group_id IS NULL OR group_id != ? ORDER BY name",
        (group_id,),
    ).fetchall()
    return render_template("group_detail.html", group=group, unassigned=unassigned)


@app.route("/groups/<int:group_id>/edit", methods=["POST"])
def group_edit(group_id):
    conn = get_db()
    name = request.form.get("name", "").strip()
    if name:
        conn.execute("UPDATE account_groups SET name = ?, notes = ? WHERE id = ?",
                     (name, request.form.get("notes", "").strip(), group_id))
        conn.commit()
        flash("Group updated.", "success")
    return redirect(url_for("group_detail", group_id=group_id))


@app.route("/groups/<int:group_id>/add", methods=["POST"])
def group_add_account(group_id):
    conn = get_db()
    account_id = request.form.get("account_id", type=int)
    if account_id:
        conn.execute("UPDATE accounts SET group_id = ? WHERE id = ?", (group_id, account_id))
        conn.commit()
        flash("Added to group.", "success")
    return redirect(url_for("group_detail", group_id=group_id))


@app.route("/accounts/<int:account_id>/group", methods=["POST"])
def account_set_group(account_id):
    conn = get_db()
    group_id = request.form.get("group_id", type=int)
    conn.execute("UPDATE accounts SET group_id = ? WHERE id = ?", (group_id or None, account_id))
    conn.commit()
    flash("Group updated." if group_id else "Removed from group.", "success")
    return redirect(request.referrer or url_for("account_detail", account_id=account_id))


@app.route("/opportunities")
def opportunities():
    conn = get_db()
    opps = intelligence.territory_opportunities(conn, limit=40)
    dormant = intelligence.dormant_branches(conn)
    return render_template("opportunities.html", opportunities=opps, dormant=dormant)


@app.route("/accounts/<int:account_id>/edit", methods=["POST"])
def account_edit(account_id):
    conn = get_db()
    fields = ["company_type", "class", "category", "street", "city", "state", "zip", "market",
              "tier", "cadence_days", "phone", "website", "status", "notes"]
    updates = {f: request.form.get(f, "").strip() for f in fields}
    updates["cadence_days"] = updates["cadence_days"] or None
    set_clause = ", ".join(f"{f} = ?" for f in fields)
    conn.execute(
        f"UPDATE accounts SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        list(updates.values()) + [account_id],
    )
    conn.commit()
    flash("Account updated.", "success")
    return redirect(url_for("account_detail", account_id=account_id))


@app.route("/accounts/<int:account_id>/contacts/new", methods=["POST"])
def contact_new(account_id):
    conn = get_db()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Contact name is required.", "error")
        return redirect(url_for("account_detail", account_id=account_id))
    conn.execute(
        "INSERT INTO contacts (account_id, name, role, phone, email, notes, source) VALUES (?, ?, ?, ?, ?, ?, 'manual')",
        (account_id, name, request.form.get("role", ""), request.form.get("phone", ""), request.form.get("email", ""), request.form.get("notes", "")),
    )
    conn.commit()
    flash(f"Added contact: {name}", "success")
    return redirect(url_for("account_detail", account_id=account_id))


@app.route("/contacts/<int:contact_id>/edit", methods=["POST"])
def contact_edit(contact_id):
    conn = get_db()
    row = conn.execute("SELECT account_id FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    if not row:
        flash("Contact not found.", "error")
        return redirect(url_for("accounts_list"))
    fields = ["name", "role", "phone", "email", "notes"]
    updates = [request.form.get(f, "").strip() for f in fields]
    set_clause = ", ".join(f"{f} = ?" for f in fields)
    conn.execute(f"UPDATE contacts SET {set_clause}, updated_at = datetime('now') WHERE id = ?", updates + [contact_id])
    conn.commit()
    flash("Contact updated.", "success")
    return redirect(url_for("account_detail", account_id=row["account_id"]))


# ---------------------------------------------------------------------------
# Call logging
# ---------------------------------------------------------------------------

@app.route("/calls/new", methods=["GET", "POST"])
def call_new():
    conn = get_db()
    if request.method == "POST":
        account_id = request.form.get("account_id", type=int)
        new_account_name = request.form.get("new_account_name", "").strip()
        if not account_id and new_account_name:
            account_id = importer.upsert_account(conn, new_account_name, market=importer.infer_market(new_account_name), source="manual")
        if not account_id:
            flash("Please choose or add an account.", "error")
            return redirect(url_for("call_new"))

        contact_id = request.form.get("contact_id", type=int)
        new_contact_name = request.form.get("new_contact_name", "").strip()
        if not contact_id and new_contact_name:
            contact_id = importer.get_or_create_contact(conn, account_id, new_contact_name, source="manual")

        brand_id = request.form.get("brand_id", type=int)
        new_brand_name = request.form.get("new_brand_name", "").strip()
        if not brand_id and new_brand_name:
            brand_id = importer.get_or_create_brand(conn, new_brand_name)

        call_date = request.form.get("call_date") or date.today().isoformat()
        followup_date = request.form.get("followup_date") or None

        cur = conn.execute(
            """INSERT INTO calls (account_id, contact_id, call_date, report_type, subject, brand_id, attendees, notes, followup_date, followup_notes, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')""",
            (
                account_id,
                contact_id,
                call_date,
                request.form.get("report_type", "").strip(),
                request.form.get("subject", "").strip(),
                brand_id,
                request.form.get("attendees", "").strip(),
                request.form.get("notes", "").strip(),
                followup_date,
                request.form.get("followup_notes", "").strip(),
            ),
        )
        call_id = cur.lastrowid

        if followup_date:
            conn.execute(
                """INSERT INTO followups (account_id, contact_id, call_id, description, due_date, source)
                   VALUES (?, ?, ?, ?, ?, 'auto')""",
                (
                    account_id,
                    contact_id,
                    call_id,
                    request.form.get("followup_notes", "").strip() or f"Follow up on {call_date}",
                    followup_date,
                ),
            )
        conn.commit()
        flash("Call logged.", "success")
        if request.form.get("log_another"):
            return redirect(url_for("call_new", account_id=account_id))
        return redirect(url_for("account_detail", account_id=account_id))

    preselect_account = request.args.get("account_id", type=int)
    accounts = conn.execute("SELECT id, name FROM accounts ORDER BY name").fetchall()
    brands = conn.execute("SELECT id, name FROM brands ORDER BY name").fetchall()
    contacts = []
    if preselect_account:
        contacts = queries.contacts_for_account(conn, preselect_account)
    return render_template(
        "call_new.html",
        accounts=accounts,
        brands=brands,
        contacts=contacts,
        preselect_account=preselect_account,
    )


@app.route("/api/accounts/<int:account_id>/contacts")
def api_account_contacts(account_id):
    conn = get_db()
    return jsonify(queries.contacts_for_account(conn, account_id))


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------

@app.route("/followups")
def followups_list():
    conn = get_db()
    status = request.args.get("status", "open")
    market = request.args.get("market") or None
    followups = queries.list_followups(conn, status=status, market=market)
    today = date.today().isoformat()
    for f in followups:
        f["overdue"] = bool(f["due_date"]) and f["due_date"] < today and f["status"] == "open"
    return render_template("followups.html", followups=followups, filters={"status": status, "market": market})


@app.route("/followups/new", methods=["POST"])
def followup_new():
    conn = get_db()
    account_id = request.form.get("account_id", type=int)
    if not account_id:
        flash("Choose an account for this follow-up.", "error")
        return redirect(request.referrer or url_for("followups_list"))
    conn.execute(
        "INSERT INTO followups (account_id, description, due_date, source) VALUES (?, ?, ?, 'manual')",
        (account_id, request.form.get("description", "").strip(), request.form.get("due_date") or None),
    )
    conn.commit()
    flash("Follow-up added.", "success")
    return redirect(request.referrer or url_for("followups_list"))


@app.route("/followups/<int:followup_id>/toggle", methods=["POST"])
def followup_toggle(followup_id):
    conn = get_db()
    row = conn.execute("SELECT status, account_id FROM followups WHERE id = ?", (followup_id,)).fetchone()
    if not row:
        return jsonify({"ok": False}), 404
    new_status = "done" if row["status"] == "open" else "open"
    completed_at = "datetime('now')" if new_status == "done" else "NULL"
    conn.execute(f"UPDATE followups SET status = ?, completed_at = {completed_at} WHERE id = ?", (new_status, followup_id))
    conn.commit()
    if request.is_json or request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True, "status": new_status})
    return redirect(request.referrer or url_for("followups_list"))


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------

@app.route("/brands")
def brands_list():
    conn = get_db()
    brands = queries.list_brands(conn)
    return render_template("brands_list.html", brands=brands)


@app.route("/brands/<int:brand_id>")
def brand_detail(brand_id):
    conn = get_db()
    brand = queries.get_brand(conn, brand_id)
    if not brand:
        flash("Brand not found.", "error")
        return redirect(url_for("brands_list"))
    brand_news = news.list_news(conn, brand_id=brand_id, limit=20)
    return render_template("brand_detail.html", brand=brand, brand_news=brand_news)


# ---------------------------------------------------------------------------
# News / market scanning
# ---------------------------------------------------------------------------

@app.route("/news")
def news_page():
    conn = get_db()
    category = request.args.get("category") or None
    items = news.list_news(conn, category=category, limit=200)
    brands = conn.execute("SELECT id, name FROM brands WHERE category IS NULL OR category != 'admin' ORDER BY name").fetchall()
    accounts = conn.execute("SELECT id, name FROM accounts ORDER BY name").fetchall()
    last_refresh = news.last_refreshed(conn)
    from brm import linecard
    return render_template("news.html", items=items, brands=brands, accounts=accounts,
                           category=category, last_refresh=last_refresh,
                           line_count=len(linecard.active_lines()))


@app.route("/news/refresh", methods=["POST"])
def news_refresh():
    conn = get_db()
    scope = request.form.get("scope", "all")
    if scope not in news.SCOPES:
        scope = "all"
    try:
        summary = news.refresh_news(conn, scope=scope)
        msg = f"Refreshed ({scope}): {summary['items_added']} new article(s) from {summary['queries_run']} searches."
        if summary["errors"]:
            msg += f" ({len(summary['errors'])} search(es) failed -- check your internet connection.)"
        flash(msg, "success" if summary["items_added"] or not summary["errors"] else "error")
    except Exception as e:
        flash(f"News refresh failed: {e}", "error")
    return redirect(url_for("news_page"))


@app.route("/news/manual", methods=["POST"])
def news_manual():
    conn = get_db()
    title = request.form.get("title", "").strip()
    if not title:
        flash("Title is required.", "error")
        return redirect(url_for("news_page"))
    news.add_manual_news(
        conn,
        title=title,
        url=request.form.get("url") or None,
        source=request.form.get("source") or "Manual entry",
        summary=request.form.get("summary") or None,
        category=request.form.get("category") or "manual",
        account_id=request.form.get("account_id", type=int) or None,
        brand_id=request.form.get("brand_id", type=int) or None,
    )
    flash("News item added.", "success")
    return redirect(url_for("news_page"))


@app.route("/news/<int:news_id>/link", methods=["POST"])
def news_link(news_id):
    conn = get_db()
    news.link_news(
        conn,
        news_id,
        account_id=request.form.get("account_id", type=int) or None,
        brand_id=request.form.get("brand_id", type=int) or None,
    )
    flash("Saved.", "success")
    return redirect(request.referrer or url_for("news_page"))


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@app.route("/import")
def import_page():
    conn = get_db()
    batches = conn.execute("SELECT * FROM import_batches ORDER BY id DESC LIMIT 25").fetchall()
    return render_template("import.html", batches=batches)


def _save_upload(file_storage, prefix):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in file_storage.filename if c.isalnum() or c in "._-")
    dest = UPLOAD_DIR / f"{prefix}_{ts}_{safe_name}"
    file_storage.save(dest)
    return dest


@app.route("/import/<kind>", methods=["POST"])
def import_run(kind):
    if kind not in ("companies", "journal", "sales"):
        flash("Unknown import type.", "error")
        return redirect(url_for("import_page"))
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Choose a file to import.", "error")
        return redirect(url_for("import_page"))

    conn = get_db()
    path = _save_upload(file, kind)
    try:
        if kind == "companies":
            summary = importer.import_companies(conn, path, filename=file.filename)
        elif kind == "journal":
            summary = importer.import_journal(conn, path, filename=file.filename)
        else:
            summary = importer.import_sales(conn, path, filename=file.filename)
    except Exception as e:
        flash(f"Import failed: {e}", "error")
        return redirect(url_for("import_page"))

    flash(_summary_message(kind, summary), "success")
    return redirect(url_for("import_page"))


def _summary_message(kind, summary):
    if kind == "companies":
        msg = f"Companies import: {summary['rows_seen']} row(s) seen, {summary['accounts_created']} account(s) created, {summary['accounts_updated']} updated."
        if summary.get("warning"):
            msg += " " + summary["warning"]
        return msg
    if kind == "journal":
        return (
            f"Journal import: {summary['calls_imported']} call(s) imported "
            f"({summary['calls_skipped_duplicate']} already had that call), "
            f"{summary['accounts_created']} new account(s), {summary['contacts_created']} new contact(s), "
            f"{summary['followups_created']} follow-up(s) created, {len(summary['brands_seen'])} brand(s) seen."
        )
    return (
        f"Sales import: {summary['accounts_seen']} account(s), {summary['brand_lines_imported']} brand line(s), "
        f"{len(summary['brands_seen'])} brand(s), total YTD {money(summary['total_current_ytd'])} "
        f"(prior {money(summary['total_prior_ytd'])})."
    )


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db.init_db()
    port = int(os.environ.get("PORT", 5000))
    # The reloader watches the program files and restarts automatically when
    # update.bat replaces them -- so an update needs nothing but a browser
    # refresh. The interactive debugger stays OFF: it would allow running
    # arbitrary code through the browser, and it isn't needed for this.
    app.run(
        host="127.0.0.1",
        port=port,
        debug=os.environ.get("BRM_DEBUG") == "1",
        use_reloader=True,
    )
