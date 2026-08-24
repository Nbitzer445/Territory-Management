"""Market / manufacturer news scanning.

Live fetch uses Google News' public RSS search (no API key, no signup) so
this works out of the box. It is structured so a paid news API can be
dropped in later (see NEWS_API_KEY below) without changing the rest of the
app -- add a fetch function and register it in `refresh_news`.

IMPORTANT: this module only ever sends short public search phrases (brand
names, commodity terms) out over the network. It never reads or transmits
accounts, contacts, calls, or sales data.
"""
import html
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import requests

from .importer import _clean


def _strip_html(s):
    if not s:
        return s
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()

# Optional: set an API key via environment variable to plug in a paid news
# API later (e.g. NewsAPI.org). Not required -- Google News RSS works with
# no key at all.
NEWS_API_KEY = os.environ.get("BRM_NEWS_API_KEY", "")

COMMODITY_QUERIES = [
    ("copper prices", "commodity"),
    ("steel prices", "commodity"),
    ("PVC pipe resin prices", "commodity"),
]

MARKET_QUERIES = [
    ("plumbing wholesale distribution industry", "market"),
    ("HVAC distribution industry news", "market"),
    ("construction housing starts Nebraska Iowa", "demand"),
]


def _google_news_rss_url(query):
    q = quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _fetch_rss(query, max_items=6, timeout=8):
    """Fetch and parse a public RSS feed with the standard library XML parser
    (no feedparser dependency -- keeps setup to just `pip install -r
    requirements.txt` with nothing that needs a C/Rust build toolchain)."""
    url = _google_news_rss_url(query)
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "BRM-Territory-Hub/1.0"})
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    items = []
    for item in root.findall("./channel/item")[:max_items]:
        title = _clean(item.findtext("title"))
        link = item.findtext("link")
        source_el = item.find("source")
        source = _clean(source_el.text) if source_el is not None and source_el.text else "Google News"
        published = item.findtext("pubDate")
        summary = _strip_html(item.findtext("description"))
        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "published_at": published,
                "summary": summary,
            }
        )
    return items


def build_queries(conn, brand_ids=None):
    """Returns list of (query_string, category, query_tag)."""
    queries = []
    for q, cat in COMMODITY_QUERIES:
        queries.append((q, cat, q))
    for q, cat in MARKET_QUERIES:
        queries.append((q, cat, q))

    sql = "SELECT id, name FROM brands WHERE category IS NULL OR category != 'admin'"
    params = []
    if brand_ids:
        placeholders = ",".join("?" for _ in brand_ids)
        sql += f" AND id IN ({placeholders})"
        params = list(brand_ids)
    for row in conn.execute(sql, params).fetchall():
        queries.append((f'"{row["name"]}" plumbing OR manufacturer OR distributor', "manufacturer", row["name"]))
    return queries


def refresh_news(conn, brand_ids=None, max_items_per_query=5):
    """Fetch fresh items for each query and insert new ones (de-duped by URL)."""
    summary = {"queries_run": 0, "items_added": 0, "errors": []}
    queries = build_queries(conn, brand_ids=brand_ids)
    for query, category, tag in queries:
        summary["queries_run"] += 1
        try:
            items = _fetch_rss(query, max_items=max_items_per_query)
        except Exception as e:  # network issues shouldn't crash the app
            summary["errors"].append(f"{tag}: {e}")
            continue
        for item in items:
            if not item["url"]:
                continue
            exists = conn.execute("SELECT id FROM news_items WHERE url = ?", (item["url"],)).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT INTO news_items (title, url, source, published_at, summary, category, query_tag, manual)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (item["title"], item["url"], item["source"], item["published_at"], item["summary"], category, tag),
            )
            summary["items_added"] += 1
    conn.commit()
    return summary


def add_manual_news(conn, title, url=None, source=None, summary=None, category="manual", account_id=None, brand_id=None):
    cur = conn.execute(
        """INSERT INTO news_items (title, url, source, summary, category, manual, saved)
           VALUES (?, ?, ?, ?, ?, 1, 1)""",
        (title, url, source, summary, category),
    )
    news_id = cur.lastrowid
    if account_id or brand_id:
        conn.execute(
            "INSERT INTO news_links (news_id, account_id, brand_id) VALUES (?, ?, ?)",
            (news_id, account_id, brand_id),
        )
    conn.commit()
    return news_id


def link_news(conn, news_id, account_id=None, brand_id=None):
    conn.execute(
        "INSERT INTO news_links (news_id, account_id, brand_id) VALUES (?, ?, ?)",
        (news_id, account_id, brand_id),
    )
    conn.execute("UPDATE news_items SET saved = 1 WHERE id = ?", (news_id,))
    conn.commit()


def list_news(conn, category=None, brand_id=None, account_id=None, limit=100):
    where = []
    params = []
    joins = ""
    if brand_id or account_id:
        joins = "JOIN news_links nl ON nl.news_id = n.id"
        if brand_id:
            where.append("nl.brand_id = ?")
            params.append(brand_id)
        if account_id:
            where.append("nl.account_id = ?")
            params.append(account_id)
    if category:
        where.append("n.category = ?")
        params.append(category)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    rows = conn.execute(
        f"""SELECT DISTINCT n.* FROM news_items n {joins} {where_sql}
            ORDER BY n.fetched_at DESC, n.id DESC LIMIT ?""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def last_refreshed(conn):
    row = conn.execute("SELECT MAX(fetched_at) t FROM news_items WHERE manual = 0").fetchone()
    return row["t"] if row else None
