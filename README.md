# IndiaMART Leads Dashboard

A Streamlit-based web dashboard that fetches and visualises lead enquiries from the IndiaMART CRM API. Built to give a sales team an at-a-glance view of incoming leads, geographic distribution, and time-of-day patterns.

## Features

- **4 view modes** — Today / Single Date / Custom Range / Last 7 Days
- **KPI cards** — Total, New, Working, Pending, Daily Average
- **Cities Breakdown** — colorful horizontal bar chart (top 10 visible + scroll)
- **Time Distribution** — interactive donut chart (Morning / Afternoon / Evening / Night) with peak-hour highlight
  - Today / Single → actual counts
  - Range / Last 7 → average per day (smooths weekday/weekend mix)
- **CSV export** of filtered leads
- **Smart caching** — 5-minute in-memory cache per date range
- **Rate-limit aware** — respects IndiaMART's 1-call-per-5-min limit with live countdown banner
- **Light / Dark mode toggle** in sidebar
- **Auto-sync indicator** — last-sync timestamp, manual "Sync Now" button

## Tech Stack

- **Frontend & Backend**: Streamlit
- **Charts**: Plotly (interactive bar + donut)
- **HTTP client**: httpx
- **Data**: pandas
- **Config**: python-dotenv

## Setup

### Prerequisites

- Python 3.10+
- An IndiaMART CRM API key (`glusr_crm_key`)

### Install

```bash
git clone https://github.com/deodap8001/indiamart-leads-dashboard.git
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
streamlit run streamlit_app.py
```

The dashboard opens automatically at <http://localhost:8501>.

## Project Structure

```
.
├── streamlit_app.py         # Streamlit UI — KPIs, charts, table, export
├── indiamart_client.py      # API client with caching + rate-limit guard
├── requirements.txt
├── .env.example             # Template for environment variables
├── .streamlit/
│   └── secrets.toml.example # Template for Streamlit Cloud deployment
└── .gitignore
```

## API Notes

- IndiaMART API endpoint: `https://mapi.indiamart.com/wservce/crm/crmListing/v2/`
- **7-day maximum** window per request
- **1 call per 5 minutes** rate limit (enforced by client with a 5:15 cooldown)
- The app caches each unique date range separately for 5 minutes

## Deployment (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. Go to <https://share.streamlit.io>, sign in with GitHub, and select this repo.
3. Set the main file path to `streamlit_app.py`.
4. In the app's **Settings → Secrets**, add:
   ```toml
   INDIAMART_API_KEY = "your_glusr_crm_key_here"
   ```
5. Deploy — Streamlit Cloud will install from `requirements.txt` and launch the app.

## License

Internal project — not licensed for redistribution.
