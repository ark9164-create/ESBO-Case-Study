#!/usr/bin/env python3
"""
Build static site data files from SQLite.
Run from project root: venv_win/Scripts/python static-build/build.py
Outputs JSON files to static-build/data/
"""

import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = Path(os.getenv("PRICE_SHOP_DB_PATH", str(ROOT / "data" / "prices.db")))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)

VENUES = {
    "esb": {"name": "Empire State Building"},
    "edge": {"name": "Edge Hudson Yards"},
    "summit": {"name": "Summit One Vanderbilt"},
    "totr": {"name": "Top of the Rock"},
}
VENUE_KEYS = ["esb", "edge", "summit", "totr"]
VENUE_COLORS = {"esb": "#60a5fa", "edge": "#c084fc", "summit": "#34d399", "totr": "#fbbf24"}

ESB_TOUR_GROUP_ORDER = [
    "Early Access", "Opening", "Pre-Sunset", "Pre-Sunset 2",
    "Sunset", "Twilight", "Post-Sunset 2", "Post-Sunset", "Last Hour",
]
ESB_SUNSET_GROUPS = ["Sunset", "Twilight"]

HOLIDAYS = {
    "2026-01-01": "New Year's Day", "2026-01-19": "MLK Day",
    "2026-02-16": "Presidents' Day", "2026-04-05": "Easter",
    "2026-05-25": "Memorial Day", "2026-06-19": "Juneteenth",
    "2026-07-03": "July 4th (Observed)", "2026-07-04": "July 4th",
    "2026-09-07": "Labor Day", "2026-10-12": "Columbus Day",
    "2026-11-11": "Veterans Day", "2026-11-26": "Thanksgiving",
    "2026-11-27": "Black Friday", "2026-12-24": "Christmas Eve",
    "2026-12-25": "Christmas", "2026-12-31": "New Year's Eve",
    "2027-01-01": "New Year's Day", "2027-01-18": "MLK Day",
    "2027-02-15": "Presidents' Day", "2027-03-28": "Easter",
    "2027-05-31": "Memorial Day", "2027-06-19": "Juneteenth",
    "2027-07-04": "July 4th", "2027-07-05": "July 4th (Observed)",
    "2027-09-06": "Labor Day", "2027-11-25": "Thanksgiving",
    "2027-11-26": "Black Friday", "2027-12-24": "Christmas Eve",
    "2027-12-25": "Christmas", "2027-12-31": "New Year's Eve",
}

PEAK_PERIODS = [
    ["2026-03-28", "2026-04-05", "Spring Break"],
    ["2026-06-20", "2026-09-06", "Summer"],
    ["2026-12-19", "2027-01-04", "Holiday Season"],
    ["2027-03-27", "2027-04-04", "Spring Break"],
    ["2027-06-19", "2027-09-05", "Summer"],
]


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def build_prices_latest():
    """Get latest snapshot per attraction using same logic as get_latest_snapshot()."""
    conn = get_conn()
    result = {}
    for vk in VENUE_KEYS:
        row = conn.execute(
            """SELECT scrape_date FROM prices WHERE venue = ?
               GROUP BY scrape_date ORDER BY MAX(travel_date) DESC, scrape_date DESC LIMIT 1""",
            (vk,),
        ).fetchone()
        if not row:
            result[vk] = []
            continue
        scrape_date = row["scrape_date"]
        rows = conn.execute(
            """SELECT scrape_date, travel_date, tour_time, price_cents, raw_status, tour_group
               FROM prices WHERE venue = ? AND scrape_date = ? ORDER BY travel_date, tour_time""",
            (vk, scrape_date),
        ).fetchall()
        result[vk] = [dict(r) for r in rows]
    conn.close()
    return result


def build_prices_history():
    """Min price per attraction per travel_date per scrape_date (all scrapes)."""
    conn = get_conn()
    scrape_dates = [r["scrape_date"] for r in conn.execute(
        "SELECT DISTINCT scrape_date FROM prices ORDER BY scrape_date"
    ).fetchall()]

    rows = conn.execute(
        """SELECT venue, scrape_date, travel_date, MIN(price_cents) as min_price
           FROM prices WHERE price_cents IS NOT NULL
           GROUP BY venue, scrape_date, travel_date
           ORDER BY travel_date, venue, scrape_date"""
    ).fetchall()
    conn.close()

    by_travel = {}
    for r in rows:
        td = r["travel_date"]
        vk = r["venue"]
        if td not in by_travel:
            by_travel[td] = {}
        if vk not in by_travel[td]:
            by_travel[td][vk] = []
        by_travel[td][vk].append({
            "scrape_date": r["scrape_date"],
            "min_price_cents": r["min_price"],
        })

    return {"scrape_dates": scrape_dates, "by_travel_date": by_travel}


def build_price_changes():
    """All price change records with tour_group."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT pc.*,
               (SELECT p.tour_group FROM prices p
                WHERE p.venue=pc.venue AND p.travel_date=pc.travel_date AND p.tour_time=pc.tour_time
                AND p.tour_group IS NOT NULL LIMIT 1) as tour_group
        FROM price_changes pc
        ORDER BY pc.detected_at DESC, pc.travel_date, pc.tour_time"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_coverage(latest):
    """Coverage summary from latest snapshot data."""
    coverage = {}
    for vk in VENUE_KEYS:
        rows = latest.get(vk, [])
        scrape_dates = {r["scrape_date"] for r in rows if r.get("scrape_date")}
        travel_dates = sorted(r["travel_date"] for r in rows if r.get("travel_date"))
        coverage[vk] = {
            "scrape_date": max(scrape_dates) if scrape_dates else None,
            "travel_from": travel_dates[0] if travel_dates else None,
            "travel_through": travel_dates[-1] if travel_dates else None,
        }
    return coverage


def build_blackout_dates(latest):
    """Dates with no rows or only sold-out rows inside each venue's covered range."""
    blackout_by_venue = {}
    blackout_dates = {}

    for vk in VENUE_KEYS:
        rows = latest.get(vk, [])
        travel_dates = sorted({r["travel_date"] for r in rows if r.get("travel_date")})
        if not travel_dates:
            blackout_by_venue[vk] = []
            continue

        by_date = {}
        for row in rows:
            travel_date = row.get("travel_date")
            if not travel_date:
                continue
            by_date.setdefault(travel_date, []).append(row)

        sold_out_dates = {
            travel_date
            for travel_date, day_rows in by_date.items()
            if day_rows and all((r.get("raw_status") or "available") == "sold_out" for r in day_rows)
        }

        missing_dates = set()
        cur = date.fromisoformat(travel_dates[0])
        end = date.fromisoformat(travel_dates[-1])
        available_dates = set(travel_dates)
        while cur <= end:
            iso = cur.isoformat()
            if iso not in available_dates:
                missing_dates.add(iso)
            cur += timedelta(days=1)

        blackout_list = sorted(missing_dates | sold_out_dates)
        blackout_by_venue[vk] = blackout_list
        for travel_date in blackout_list:
            blackout_dates.setdefault(travel_date, []).append(vk)

    for travel_date in blackout_dates:
        blackout_dates[travel_date].sort()

    return blackout_by_venue, dict(sorted(blackout_dates.items()))


def build_run_inconsistencies():
    """Run-to-run regressions matching the validator warnings."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT venue,
                  scrape_date,
                  COUNT(*) as row_count,
                  COUNT(DISTINCT travel_date) as travel_date_count,
                  MIN(travel_date) as travel_from,
                  MAX(travel_date) as travel_through
           FROM prices
           GROUP BY venue, scrape_date
           ORDER BY venue, scrape_date"""
    ).fetchall()
    conn.close()

    by_venue = {}
    inconsistencies = []
    row_drop_threshold = 0.85

    for row in rows:
        current = dict(row)
        venue = current["venue"]
        previous = by_venue.get(venue)
        if previous:
            coverage_regressed = (
                current["travel_through"]
                and previous["travel_through"]
                and current["travel_through"] < previous["travel_through"]
            )
            row_drop = (
                previous["row_count"] > 0
                and current["row_count"] < int(previous["row_count"] * row_drop_threshold)
            )
            if coverage_regressed or row_drop:
                flags = []
                if coverage_regressed:
                    flags.append("coverage_regressed")
                if row_drop:
                    flags.append("row_drop")
                inconsistencies.append({
                    "venue": venue,
                    "scrape_date": current["scrape_date"],
                    "row_count": current["row_count"],
                    "travel_date_count": current["travel_date_count"],
                    "travel_from": current["travel_from"],
                    "travel_through": current["travel_through"],
                    "previous": previous,
                    "flags": flags,
                    "row_delta": current["row_count"] - previous["row_count"],
                    "travel_through_delta_days": (
                        (date.fromisoformat(current["travel_through"]) - date.fromisoformat(previous["travel_through"])).days
                        if current["travel_through"] and previous["travel_through"]
                        else None
                    ),
                    "message": (
                        f"{venue}: current {current['scrape_date']} covers "
                        f"{current['travel_from']} -> {current['travel_through']} "
                        f"across {current['travel_date_count']} dates / {current['row_count']} rows; "
                        f"previous {previous['scrape_date']} covered "
                        f"{previous['travel_from']} -> {previous['travel_through']} "
                        f"across {previous['travel_date_count']} dates / {previous['row_count']} rows"
                    ),
                })
        by_venue[venue] = current

    return {
        "row_drop_threshold": row_drop_threshold,
        "run_inconsistencies": inconsistencies,
    }


def build_prices_floor(latest):
    """Minimum available price per venue from the latest snapshot — tiny file for the dashboard GA row."""
    floor = {}
    for vk, rows in latest.items():
        avail = [r["price_cents"] for r in rows if r.get("raw_status") == "available" and r.get("price_cents")]
        floor[vk] = min(avail) if avail else None
    return floor


def build_price_changes_recent(changes, days=30):
    """Last N days of actual price changes (excludes status-only rows) — small file for the Market Pulse."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    recent = [
        c for c in changes
        if c.get("new_price_cents") and c.get("old_price_cents")
        and c["new_price_cents"] != c["old_price_cents"]
        and str(c.get("detected_at", ""))[:10] >= cutoff
    ]
    return recent


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), default=str)
    size_kb = os.path.getsize(path) / 1024
    print(f"  wrote {path.name} ({size_kb:.1f} KB)")


def write_split_latest(latest):
    """Write per-venue latest payloads for pages that prefer smaller parallel fetches."""
    for vk, rows in latest.items():
        write_json(OUT_DIR / f"prices_latest_{vk}.json", rows)


def main():
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}")
        return

    print("Building static site data...")

    latest = build_prices_latest()
    coverage = build_coverage(latest)
    blackout_by_venue, blackout_dates = build_blackout_dates(latest)

    meta = {
        "venues": VENUES,
        "venue_keys": VENUE_KEYS,
        "venue_colors": VENUE_COLORS,
        "holidays": HOLIDAYS,
        "peak_periods": PEAK_PERIODS,
        "esb_tour_group_order": ESB_TOUR_GROUP_ORDER,
        "esb_sunset_groups": ESB_SUNSET_GROUPS,
        "coverage": coverage,
        "blackout_by_venue": blackout_by_venue,
        "blackout_dates": blackout_dates,
        "built_at": datetime.now().isoformat(timespec="seconds"),
    }

    write_json(OUT_DIR / "meta.json", meta)
    write_json(OUT_DIR / "prices_latest.json", latest)
    write_split_latest(latest)

    history = build_prices_history()
    write_json(OUT_DIR / "prices_history.json", history)

    changes = build_price_changes()
    write_json(OUT_DIR / "price_changes.json", changes)

    floor = build_prices_floor(latest)
    write_json(OUT_DIR / "prices_floor.json", floor)

    recent_changes = build_price_changes_recent(changes)
    write_json(OUT_DIR / "price_changes_recent.json", recent_changes)

    anomalies = build_run_inconsistencies()
    write_json(OUT_DIR / "anomalies.json", anomalies)

    print(f"\nDone. Files in {OUT_DIR}")
    print(f"  Latest rows: { {vk: len(v) for vk, v in latest.items()} }")
    print(f"  History travel dates: {len(history['by_travel_date'])}")
    print(f"  Price changes: {len(changes)}")


if __name__ == "__main__":
    main()
