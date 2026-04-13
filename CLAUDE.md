# ESBO Competitor Pricing Intelligence - AI Context

## Project Overview

A 48-hour case study deliverable for Empire State Building Observatory (ESBO). The system collects, analyzes, and visualizes competitor pricing data from NYC observation deck attractions.

**Competitors:** Edge Hudson Yards, Summit One Vanderbilt, Top of the Rock

**Deliverables:**
1. Live pricing dashboard (static site on Vercel)
2. Python scrapers for automated data collection
3. Written case study answering 6 sections from the assignment PDF

---

## Architecture

```
ESBO-Case-Study/
├── collector/          # Playwright scrapers (one per attraction)
├── pipeline/           # Config, DB schema, JSON builder
└── dashboard/          # Static HTML site + JSON data
    └── api/            # Vercel serverless function (chat proxy)
```

**Data flow:** Scrapers → SQLite → build_json.py → JSON files → Static dashboard

---

## Key Files

### Scrapers (`/collector`)
- `base.py` - Playwright browser management, rate limiting
- `ventrata_base.py` - Shared checkout widget parser (Edge, TOR, ESB)
- `esb.py`, `edge.py`, `summit.py`, `totr.py` - Per-attraction scrapers

### Pipeline (`/pipeline`)
- `config.py` - Attraction URLs, holidays, tour group definitions
- `database.py` - SQLite schema (prices table)
- `build_json.py` - Builds static JSON from database

### Dashboard (`/dashboard`)
- `index.html` - Executive overview with KPIs
- `tracker.html` - Price tracker with tour time detail
- `sunset.html` - Sunset pricing analysis
- `trends.html` - Historical trends and day-of-week patterns
- `case-study.html` - Written case study (Sections 1-6)
- `methodology.html` - Data collection methodology
- `api/chat.js` - Serverless proxy for OpenRouter (chatbot)

---

## Data Schema

One row per attraction, per tour time, per travel date:

| Field | Type | Description |
|---|---|---|
| venue | string | esb, edge, summit, totr |
| scrape_date | date | When collected |
| travel_date | date | Ticket date |
| tour_time | string | e.g. "5:30 PM" |
| price_cents | int | Price in cents (null = sold out) |
| tour_group | string | ESB only (Sunset, Twilight, etc.) |

---

## Pricing Classification

- **Dynamic:** Price moves with demand/capacity (ESB, Edge)
- **Variable:** Fixed tiers set in advance, not demand-responsive (Summit, TOR)

ESB uses tour groups (Opening, Sunset, Twilight, etc.) that shift seasonally with sunset times.

---

## Key Metrics

- **Sunset premium:** Peak evening price minus noon baseline
- **Fee normalization:** ESB $5/order, Edge $2/ticket, Summit $3/order, TOR embedded
- **All-in price:** Base + fees for single ticket comparison

---

## Deployment

- **Dashboard:** Vercel (static site)
- **API Key:** Stored in Vercel env var `OPENROUTER_API_KEY`

---

## Commands

```bash
# Run scrapers
python -m collector.esb
python -m collector.edge

# Build JSON from database
python pipeline/build_json.py

# Local dev
cd dashboard && python -m http.server 8000

# Deploy
cd dashboard && vercel --prod
```

---

## Constraints

- All data from publicly available booking widgets
- No internal pricing data or systems referenced
- Recommendations are directional (public data only)
- GA pricing only (premium tiers not scraped)
