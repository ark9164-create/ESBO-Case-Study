"""SQLite database schema and helper functions for attraction price storage."""

import sqlite3
import os
from datetime import datetime, date
from typing import Optional

from config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create the prices and price_changes tables if they don't exist."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venue TEXT NOT NULL,
            scrape_date TEXT NOT NULL,
            travel_date TEXT NOT NULL,
            tour_time TEXT NOT NULL,
            price_cents INTEGER,
            currency TEXT DEFAULT 'USD',
            product_type TEXT DEFAULT 'GA',
            raw_status TEXT,
            tour_group TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    # Add tour_group column if table already exists without it
    try:
        conn.execute("ALTER TABLE prices ADD COLUMN tour_group TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prices_venue_travel
        ON prices (venue, travel_date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prices_scrape
        ON prices (venue, scrape_date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_prices_venue_scrape_travel
        ON prices (venue, scrape_date DESC, travel_date)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venue TEXT NOT NULL,
            travel_date TEXT NOT NULL,
            tour_time TEXT NOT NULL,
            old_price_cents INTEGER,
            new_price_cents INTEGER,
            old_status TEXT,
            new_status TEXT,
            detected_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_changes_venue
        ON price_changes (venue, detected_at)
    """)
    conn.commit()
    conn.close()


def save_prices(venue: str, rows: list[dict]):
    """Save a batch of price rows for an attraction.

    Each row should have: travel_date, tour_time, price_cents, currency, status
    Detects price/status changes vs. the previous entry and logs them.
    """
    if not rows:
        return

    # Some scrapers can yield the same slot more than once within a run.
    # Keep the last-seen row per travel_date/tour_time so we don't log or save duplicates.
    deduped_rows: dict[tuple[str, str], dict] = {}
    for row in rows:
        deduped_rows[(row["travel_date"], row["tour_time"])] = row
    rows = list(deduped_rows.values())

    conn = _get_conn()
    scrape_date = date.today().isoformat()
    replace_existing_snapshot = conn.execute(
        "SELECT 1 FROM prices WHERE venue = ? AND scrape_date = ? LIMIT 1",
        (venue, scrape_date),
    ).fetchone() is not None

    # Compare against the previous completed scrape, not a partial rerun from today.
    prev_scrape_row = conn.execute(
        """SELECT scrape_date
           FROM prices
           WHERE venue = ? AND scrape_date < ?
           GROUP BY scrape_date
           ORDER BY scrape_date DESC
           LIMIT 1""",
        (venue, scrape_date),
    ).fetchone()
    if prev_scrape_row:
        prev_rows = conn.execute(
            """SELECT travel_date, tour_time, price_cents, raw_status
               FROM prices
               WHERE venue = ? AND scrape_date = ?""",
            (venue, prev_scrape_row["scrape_date"]),
        ).fetchall()
    else:
        prev_rows = []
    prev_lookup = {(r["travel_date"], r["tour_time"]): r for r in prev_rows}

    # Detect changes
    changes = []
    for r in rows:
        key = (r["travel_date"], r["tour_time"])
        prev = prev_lookup.get(key)
        if prev is not None:
            old_price = prev["price_cents"]
            new_price = r.get("price_cents")
            old_status = prev["raw_status"]
            new_status = r.get("status")
            if old_price != new_price or old_status != new_status:
                changes.append((
                    venue, r["travel_date"], r["tour_time"],
                    old_price, new_price, old_status, new_status,
                ))

    if replace_existing_snapshot:
        conn.execute(
            "DELETE FROM price_changes WHERE venue = ? AND date(detected_at) = ?",
            (venue, scrape_date),
        )

    # Insert price changes
    if changes:
        conn.executemany(
            """INSERT INTO price_changes (venue, travel_date, tour_time,
               old_price_cents, new_price_cents, old_status, new_status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            changes,
        )

    if replace_existing_snapshot:
        conn.execute(
            "DELETE FROM prices WHERE venue = ? AND scrape_date = ?",
            (venue, scrape_date),
        )

    # Insert new prices
    conn.executemany(
        """INSERT INTO prices (venue, scrape_date, travel_date, tour_time,
           price_cents, currency, product_type, raw_status, tour_group)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                venue,
                scrape_date,
                r["travel_date"],
                r["tour_time"],
                r.get("price_cents"),
                r.get("currency", "USD"),
                r.get("product_type", "GA"),
                r.get("status"),
                r.get("tour_group"),
            )
            for r in rows
        ],
    )
    conn.commit()
    conn.close()


def get_prices(
    venue: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict]:
    """Get prices filtered by attraction and/or travel date range."""
    conn = _get_conn()
    query = "SELECT * FROM prices WHERE 1=1"
    params: list = []
    if venue:
        query += " AND venue = ?"
        params.append(venue)
    if start_date:
        query += " AND travel_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND travel_date <= ?"
        params.append(end_date)
    query += " ORDER BY travel_date, tour_time"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_available_scrape_dates() -> list[str]:
    """Return all distinct scrape dates across all attractions, newest first."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT DISTINCT scrape_date FROM prices ORDER BY scrape_date DESC"
    ).fetchall()
    conn.close()
    return [r["scrape_date"] for r in rows]


def get_latest_snapshot(venue: str, scrape_date: str | None = None) -> list[dict]:
    """Get prices for an attraction for a given scrape_date (or the best/latest if not specified)."""
    conn = _get_conn()
    if scrape_date:
        resolved = scrape_date
    else:
        row = conn.execute(
            """SELECT scrape_date FROM prices WHERE venue = ?
               GROUP BY scrape_date ORDER BY MAX(travel_date) DESC, scrape_date DESC LIMIT 1""",
            (venue,),
        ).fetchone()
        if not row:
            conn.close()
            return []
        resolved = row["scrape_date"]
    rows = conn.execute(
        "SELECT * FROM prices WHERE venue = ? AND scrape_date = ? ORDER BY travel_date, tour_time",
        (venue, resolved),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_price_history(venue: str, travel_date: str, tour_time: str) -> list[dict]:
    """Get price changes over time for a specific attraction/date/tour time."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT scrape_date, price_cents, raw_status
           FROM prices
           WHERE venue = ? AND travel_date = ? AND tour_time = ?
           ORDER BY scrape_date""",
        (venue, travel_date, tour_time),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_price_changes(
    venue: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    detected_date: Optional[str] = None,
) -> list[dict]:
    """Get price change records with tour_group (joined from prices), optionally filtered."""
    conn = _get_conn()
    query = """
        SELECT pc.*,
               (SELECT p.tour_group FROM prices p
                WHERE p.venue=pc.venue AND p.travel_date=pc.travel_date AND p.tour_time=pc.tour_time
                AND p.tour_group IS NOT NULL LIMIT 1) as tour_group
        FROM price_changes pc
        WHERE 1=1
    """
    params: list = []
    if venue:
        query += " AND pc.venue = ?"
        params.append(venue)
    if start_date:
        query += " AND pc.travel_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND pc.travel_date <= ?"
        params.append(end_date)
    if detected_date:
        query += " AND DATE(pc.detected_at) = ?"
        params.append(detected_date)
    query += " ORDER BY pc.detected_at DESC, pc.travel_date, pc.tour_time"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scrape_dates_for_travel_date(travel_date: str) -> list[str]:
    """Return all distinct scrape dates that have any data for a given travel date."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT DISTINCT scrape_date FROM prices
           WHERE travel_date = ? AND price_cents IS NOT NULL
           ORDER BY scrape_date""",
        (travel_date,),
    ).fetchall()
    conn.close()
    return [r["scrape_date"] for r in rows]


def get_daily_price_history(travel_date: str) -> dict:
    """For a travel date, return cheapest price per attraction per scrape date.
    Returns {attraction: [{scrape_date, min_price_cents, changed}]}
    """
    conn = _get_conn()
    rows = conn.execute(
        """SELECT venue, scrape_date, MIN(price_cents) as min_price
           FROM prices
           WHERE travel_date = ? AND price_cents IS NOT NULL
           GROUP BY venue, scrape_date
           ORDER BY venue, scrape_date""",
        (travel_date,),
    ).fetchall()
    conn.close()

    from collections import defaultdict
    by_venue = defaultdict(list)
    for r in rows:
        by_venue[r["venue"]].append({"scrape_date": r["scrape_date"], "min_price_cents": r["min_price"]})

    # Mark changes vs previous scrape
    for entries in by_venue.values():
        for i, e in enumerate(entries):
            prev = entries[i - 1]["min_price_cents"] if i > 0 else None
            e["changed"] = prev is not None and e["min_price_cents"] != prev
            e["delta"] = (e["min_price_cents"] - prev) if (prev is not None and e["min_price_cents"] is not None) else None

    return dict(by_venue)


def get_daily_price_history_by_group(travel_date: str) -> dict:
    """For a travel date, return cheapest price per attraction per tour_group per scrape_date.
    Returns {attraction: {tour_group: [{scrape_date, min_price_cents, delta, changed}]}}
    For attractions without tour_group, uses 'GA' as the group key.
    """
    conn = _get_conn()
    rows = conn.execute(
        """SELECT venue, scrape_date, COALESCE(tour_group, 'GA') as grp, MIN(price_cents) as min_price
           FROM prices
           WHERE travel_date = ? AND price_cents IS NOT NULL
           GROUP BY venue, scrape_date, grp
           ORDER BY venue, grp, scrape_date""",
        (travel_date,),
    ).fetchall()
    conn.close()

    from collections import defaultdict
    # {attraction: {grp: [entries]}}
    result = defaultdict(lambda: defaultdict(list))
    for r in rows:
        result[r["venue"]][r["grp"]].append({
            "scrape_date": r["scrape_date"],
            "min_price_cents": r["min_price"],
        })

    # Mark changes vs previous scrape within each group
    for venue_data in result.values():
        for entries in venue_data.values():
            for i, e in enumerate(entries):
                prev = entries[i - 1]["min_price_cents"] if i > 0 else None
                e["changed"] = prev is not None and e["min_price_cents"] != prev
                e["delta"] = (e["min_price_cents"] - prev) if (prev is not None and e["min_price_cents"] is not None) else None

    # Convert defaultdicts to plain dicts
    return {v: dict(gd) for v, gd in result.items()}


def get_tour_times_for_date(venue: str, travel_date: str) -> list[str]:
    """Get distinct tour times available for an attraction on a given travel date."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT DISTINCT tour_time FROM prices
           WHERE venue = ? AND travel_date = ?
           ORDER BY tour_time""",
        (venue, travel_date),
    ).fetchall()
    conn.close()
    return [r["tour_time"] for r in rows]


def get_esb_group_price_history(travel_date: str) -> dict:
    """For ESB, return cheapest price per tour_group per scrape_date for a travel date.
    Returns {tour_group: [{scrape_date, min_price_cents}]}
    """
    conn = _get_conn()
    rows = conn.execute(
        """SELECT scrape_date, COALESCE(tour_group, 'GA') as grp, MIN(price_cents) as min_price
           FROM prices
           WHERE venue = 'esb' AND travel_date = ? AND price_cents IS NOT NULL
           GROUP BY scrape_date, grp
           ORDER BY grp, scrape_date""",
        (travel_date,),
    ).fetchall()
    conn.close()

    from collections import defaultdict
    result = defaultdict(list)
    for r in rows:
        result[r["grp"]].append({"scrape_date": r["scrape_date"], "min_price_cents": r["min_price"]})
    return dict(result)


def get_today_venue_counts() -> dict:
    """Return row count per attraction for today's scrape date."""
    today = date.today().isoformat()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT venue, COUNT(*) as cnt FROM prices WHERE scrape_date = ? GROUP BY venue",
        (today,),
    ).fetchall()
    conn.close()
    return {r["venue"]: r["cnt"] for r in rows}


def get_venue_scrape_summary(scrape_date: Optional[str] = None) -> dict:
    """Return per-venue summary stats for a given scrape date."""
    target_date = scrape_date or date.today().isoformat()
    conn = _get_conn()
    rows = conn.execute(
        """SELECT venue,
                  scrape_date,
                  COUNT(*) as row_count,
                  COUNT(DISTINCT travel_date) as travel_date_count,
                  MIN(travel_date) as travel_from,
                  MAX(travel_date) as travel_through
           FROM prices
           WHERE scrape_date = ?
           GROUP BY venue, scrape_date""",
        (target_date,),
    ).fetchall()
    conn.close()
    return {
        r["venue"]: {
            "scrape_date": r["scrape_date"],
            "row_count": r["row_count"],
            "travel_date_count": r["travel_date_count"],
            "travel_from": r["travel_from"],
            "travel_through": r["travel_through"],
        }
        for r in rows
    }


def get_previous_venue_scrape_summary(venue: str, before_date: Optional[str] = None) -> Optional[dict]:
    """Return the previous completed scrape summary for a venue before the given date."""
    cutoff = before_date or date.today().isoformat()
    conn = _get_conn()
    row = conn.execute(
        """SELECT venue,
                  scrape_date,
                  COUNT(*) as row_count,
                  COUNT(DISTINCT travel_date) as travel_date_count,
                  MIN(travel_date) as travel_from,
                  MAX(travel_date) as travel_through
           FROM prices
           WHERE venue = ? AND scrape_date < ?
           GROUP BY venue, scrape_date
           ORDER BY scrape_date DESC
           LIMIT 1""",
        (venue, cutoff),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "venue": row["venue"],
        "scrape_date": row["scrape_date"],
        "row_count": row["row_count"],
        "travel_date_count": row["travel_date_count"],
        "travel_from": row["travel_from"],
        "travel_through": row["travel_through"],
    }


def get_all_venues() -> list[str]:
    """Get list of all attractions that have data."""
    conn = _get_conn()
    rows = conn.execute("SELECT DISTINCT venue FROM prices ORDER BY venue").fetchall()
    conn.close()
    return [r["venue"] for r in rows]


def get_date_range() -> tuple[Optional[str], Optional[str]]:
    """Get min and max travel dates in the database."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT MIN(travel_date) as min_date, MAX(travel_date) as max_date FROM prices"
    ).fetchone()
    conn.close()
    if row:
        return row["min_date"], row["max_date"]
    return None, None


# Initialize on import
init_db()
