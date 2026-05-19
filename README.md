# IndiaMART Leads Dashboard

A FastAPI-based web dashboard that fetches and visualises lead enquiries from the IndiaMART CRM API. Built to give a sales team an at-a-glance view of incoming leads, geographic distribution, and time-of-day patterns.

## Features

- **4 view modes** — Today / Single Date / Custom Range / Last 7 Days
- **KPI cards** — New, Working, Pending, Daily Average
- **Cities Breakdown** — horizontal bar chart of all cities (scrollable)
- **Time Distribution / Typical Day Pattern** — doughnut chart with peak-hour detection
  - Today / Single → actual counts
  - Range / Last 7 → average per day (smooths weekday/weekend mix)
- **CSV export** of filtered leads
- **Smart caching** — 5-minute in-memory cache per date range
- **Rate-limit aware** — respects IndiaMART's 1-call-per-5-min limit with a client-side cooldown
- **Auto-sync indicator** — last-sync timestamp, manual "Sync Now" button

## Tech Stack

- **Backend**: FastAPI + Jinja2
- **Frontend**: Bootstrap 5, Bootstrap Icons, Chart.js 4
- **HTTP client**: httpx
- **Config**: python-dotenv

## Setup

### Prerequisites

- Python 3.10+
- An IndiaMART CRM API key (`glusr_crm_key`)

### Install

```bash
git clone https://github.com/rd-deodap/indiamart-leads-dashboard.git
cd indiamart-leads-dashboard
pip install -r requirements.txt
```

### Configure

Copy `.env.example` to `.env` and fill in your IndiaMART API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
INDIAMART_API_KEY=your_glusr_crm_key_here
```

### Run

```bash
python main.py
```

The dashboard opens automatically at <http://127.0.0.1:8000>.

## Project Structure

```
.
├── main.py                  # FastAPI app, routes, KPI/chart logic
├── indiamart_client.py      # API client with caching + rate-limit guard
├── templates/
│   └── dashboard.html       # Single-page Bootstrap UI
├── requirements.txt
├── .env.example             # Template for environment variables
└── .gitignore
```

## API Notes

- IndiaMART API endpoint: `https://mapi.indiamart.com/wservce/crm/crmListing/v2/`
- **7-day maximum** window per request
- **1 call per 5 minutes** rate limit (enforced by client)
- The app caches each unique date range separately for 5 minutes

## Routes

| Route     | Method | Purpose                              |
|-----------|--------|--------------------------------------|
| `/`       | GET    | Dashboard view                       |
| `/sync`   | GET    | Force-refresh from API (bypass cache)|
| `/export` | GET    | Download leads as CSV                |

Query parameters: `mode`, `date`, `start`, `end`

## License

Internal project — not licensed for redistribution.
