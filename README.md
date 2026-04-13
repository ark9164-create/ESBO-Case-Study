# ESBO Competitor Pricing Intelligence

A live competitor pricing tracker for NYC observation deck attractions, built as a 48-hour case study deliverable.

**Live Dashboard:** https://ak-esbo-case.vercel.app/guide

---

## What This Is

An automated system that collects, stores, and analyzes competitor pricing data for Empire State Building Observatory (ESBO) against Edge, Summit One Vanderbilt, and Top of the Rock.

**Built with AI.** Claude Code (Anthropic) was used to develop the scrapers, database schema, data pipeline, and dashboard in 48 hours.

---

## Components

### `/collector` - Data Collection Scripts
Python scripts using Playwright (browser automation) to collect pricing from each attraction's booking widget.

| File | Attraction | Method |
|---|---|---|
| `esb.py` | Empire State Building | DOM parsing |
| `edge.py` | Edge Hudson Yards | DOM parsing |
| `summit.py` | Summit One Vanderbilt | DOM parsing |
| `totr.py` | Top of the Rock | DOM parsing |
| `base.py` | Shared base class | Playwright browser management |
| `ventrata_base.py` | Shared widget parser | For Edge/TOR booking widgets |

### `/pipeline` - Data Pipeline
| File | Purpose |
|---|---|
| `config.py` | Attraction URLs, holidays, peak periods |
| `database.py` | SQLite schema and helpers |
| `build_json.py` | Builds static JSON from database |

### `/dashboard` - Static Site
- **index.html** - Executive dashboard with KPI cards
- **tracker.html** - Price tracker with tour time detail
- **trends.html** - Price history + day-of-week analysis
- **sunset.html** - Sunset pricing analysis
- **case-study.html** - Written case study (Sections 1-6)
- **methodology.html** - Data methodology documentation
- **compare.html** - Side-by-side attraction comparison
- **guide.html** - User guide
- **chatbot.html** - AI-powered Q&A

---

## Setup

### Requirements
- Python 3.10+
- Playwright with Chromium

### Install
```bash
pip install -r requirements.txt
playwright install chromium
```

### Run Scrapers
```bash
# From project root
python -m collector.esb      # ESB only
python -m collector.edge     # Edge only
python -m collector.summit   # Summit only
python -m collector.totr     # TOR only
```

### Build Dashboard Data
```bash
python pipeline/build_json.py
```

### Serve Dashboard
```bash
cd dashboard
python -m http.server 8000
# Open http://localhost:8000/auth.html
```

---

## Data Schema

One row per attraction, per tour time, per travel date, per scrape:

| Field | Type | Description |
|---|---|---|
| venue | string | esb, edge, summit, totr |
| scrape_date | date | When data was collected |
| travel_date | date | Ticket date |
| tour_time | string | e.g. "5:30 PM" |
| price_cents | int | Price in cents (null = sold out) |
| currency | string | USD |
| status | string | available, sold_out |
| tour_group | string | ESB only (Sunset, Twilight, etc.) |

---

## Data Coverage (as of April 2026)

| Attraction | Dates | Forward Window |
|---|---|---|
| ESB | 172 | ~6 months (through Sept 2026) |
| Edge | 267 | ~9 months (through Jan 2027) |
| Summit | 199 | ~7 months (through Oct 2026) |
| TOR | 264 | ~9 months (through Dec 2026) |

---

## Case Study Sections

The written case study (`dashboard/case-study.html`) covers:

1. **Data Collection** - How pricing data is collected
2. **Data Manipulation** - Schema, normalization, anomaly handling
3. **AI Utilization** - How Claude Code was used
4. **Analysis** - Pricing trends, competitive positioning, seasonality
5. **Revenue Recommendations** - 5 specific recommendations
6. **Additional Considerations** - Data gaps, model enhancements

---

## Limitations

- Site redesigns can break scrapers overnight
- No historical data before April 2026
- GA pricing only (premium tiers not scraped)
- Summit/TOR use dynamic JS requiring browser automation

---

## Production Path

Current: SQLite + static JSON + Vercel

Recommended: Azure PostgreSQL + Container Apps + Static Web Apps with Entra ID SSO. ~$58-99/month.

See Section 6 of the case study for full architecture.
