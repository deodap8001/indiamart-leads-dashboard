import csv
import io
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from indiamart_client import fetch_leads, parse_query_time

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="IndiaMART Lead Dashboard")


def classify_status(query_time_str: str, today: datetime) -> str:
    dt = parse_query_time(query_time_str)
    if dt is None:
        return "PENDING"
    age_days = (today.date() - dt.date()).days
    if age_days <= 0:
        return "NEW"
    if age_days == 1:
        return "WORKING"
    return "PENDING"


def parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None


def resolve_window(mode: str, date_str: str | None, start_str: str | None, end_str: str | None) -> tuple[datetime, datetime, str]:
    now = datetime.now()
    today = datetime(now.year, now.month, now.day)

    if mode == "single":
        d = parse_date(date_str) or today
        return d, d, d.strftime("%d-%b-%Y")

    if mode == "range":
        s = parse_date(start_str) or (today - timedelta(days=6))
        e = parse_date(end_str) or today
        if s > e:
            s, e = e, s
        return s, e, f"{s.strftime('%d-%b-%Y')} to {e.strftime('%d-%b-%Y')}"

    if mode == "last7":
        s = today - timedelta(days=6)
        e = today
        return s, e, "Last 7 Days"

    return today, today, "Today"


def filter_leads_to_window(leads: list[dict], start: datetime, end: datetime) -> list[dict]:
    out = []
    for lead in leads:
        dt = parse_query_time(lead.get("QUERY_TIME", ""))
        if dt is None:
            continue
        if start.date() <= dt.date() <= end.date():
            out.append(lead)
    return out


def build_today_kpis(leads: list[dict]) -> dict:
    today = datetime.now()
    counts = {"NEW": 0, "WORKING": 0, "PENDING": 0}
    days_seen = set()

    for lead in leads:
        status = classify_status(lead.get("QUERY_TIME", ""), today)
        lead["_status"] = status
        counts[status] += 1
        dt = parse_query_time(lead.get("QUERY_TIME", ""))
        if dt:
            days_seen.add(dt.date())

    leads.sort(key=lambda l: l.get("QUERY_TIME", ""), reverse=True)
    total = len(leads)
    unique_days = len(days_seen) or 1
    daily_avg = round(total / unique_days, 1)

    return {
        "mode": "today",
        "new_count": counts["NEW"],
        "working_count": counts["WORKING"],
        "pending_count": counts["PENDING"],
        "total": total,
        "daily_avg": daily_avg,
        "unique_days": unique_days,
    }


def build_range_kpis(leads: list[dict], start: datetime, end: datetime, mode: str) -> dict:
    today = datetime.now()
    new_count = 0
    working_count = 0
    pending_count = 0
    days_seen = set()

    for lead in leads:
        status = classify_status(lead.get("QUERY_TIME", ""), today)
        lead["_status"] = status
        if status == "NEW":
            new_count += 1
        elif status == "WORKING":
            working_count += 1
        elif status == "PENDING":
            pending_count += 1
        dt = parse_query_time(lead.get("QUERY_TIME", ""))
        if dt:
            days_seen.add(dt.date())

    leads.sort(key=lambda l: l.get("QUERY_TIME", ""), reverse=True)
    total = len(leads)
    span_days = (end.date() - start.date()).days + 1
    daily_avg = round(total / span_days, 1) if span_days > 0 else 0

    return {
        "mode": mode,
        "total": total,
        "new_count": new_count,
        "working_count": working_count,
        "pending_count": pending_count,
        "daily_avg": daily_avg,
        "unique_days": span_days,
        "span_days": span_days,
    }


def _hour_label(hour: int) -> str:
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"


def build_hour_breakdown(leads: list[dict], span_days: int = 1) -> dict | None:
    hour_counts: dict[int, int] = {}
    for lead in leads:
        dt = parse_query_time(lead.get("QUERY_TIME", ""))
        if dt is None:
            continue
        hour_counts[dt.hour] = hour_counts.get(dt.hour, 0) + 1

    if not hour_counts:
        return None

    period_specs = [
        {"label": "Morning (6 AM – 11 AM)", "hours": list(range(6, 12)), "color": "#ffc107"},
        {"label": "Afternoon (12 PM – 4 PM)", "hours": list(range(12, 17)), "color": "#fd7e14"},
        {"label": "Evening (5 PM – 8 PM)", "hours": list(range(17, 21)), "color": "#6f42c1"},
        {"label": "Night (9 PM – 5 AM)", "hours": list(range(21, 24)) + list(range(0, 6)), "color": "#495057"},
    ]

    is_averaged = span_days > 1
    divisor = span_days if is_averaged else 1

    def fmt(n: float) -> float | int:
        if not is_averaged:
            return n
        return round(n / divisor, 1)

    result_periods = []
    for p in period_specs:
        total = sum(hour_counts.get(h, 0) for h in p["hours"])
        if total > 0:
            result_periods.append({"label": p["label"], "count": fmt(total), "color": p["color"]})

    peak_hour, peak_total = max(hour_counts.items(), key=lambda x: x[1])
    total_value = sum(hour_counts.values())

    return {
        "periods": result_periods,
        "peak_hour": _hour_label(peak_hour),
        "peak_count": fmt(peak_total),
        "total": fmt(total_value),
        "is_averaged": is_averaged,
        "span_days": span_days,
    }


def build_city_breakdown(leads: list[dict], top_n: int | None = None) -> list[dict]:
    counter: Counter = Counter()
    for lead in leads:
        raw = lead.get("SENDER_CITY")
        if not raw:
            continue
        city = str(raw).strip()
        if not city or city.lower() in ("<nil>", "nil", "none", "null"):
            continue
        city = city.title()
        counter[city] += 1

    top = counter.most_common(top_n) if top_n else counter.most_common()
    return [{"city": c, "count": n} for c, n in top]


@app.get("/")
def dashboard(request: Request, mode: str = "today", date: str | None = None, start: str | None = None, end: str | None = None):
    if mode not in ("today", "single", "range", "last7"):
        mode = "today"

    start_dt, end_dt, label = resolve_window(mode, date, start, end)

    now = datetime.now()
    last7_start = datetime(now.year, now.month, now.day) - timedelta(days=6)
    today_end = datetime(now.year, now.month, now.day)
    within_last_7 = start_dt.date() >= last7_start.date() and end_dt.date() <= today_end.date()

    if within_last_7:
        result = fetch_leads(start_date=last7_start, end_date=today_end, force=False)
    else:
        result = fetch_leads(start_date=start_dt, end_date=end_dt, force=False)

    all_leads = result.get("leads", [])

    if mode == "today":
        leads = all_leads
        kpis = build_today_kpis(leads)
    else:
        leads = filter_leads_to_window(all_leads, start_dt, end_dt)
        kpis = build_range_kpis(leads, start_dt, end_dt, mode)

    if mode == "today":
        today_dt = datetime(now.year, now.month, now.day)
        chart_leads = filter_leads_to_window(all_leads, today_dt, today_dt)
        chart_span_days = 1
    else:
        chart_leads = leads
        chart_span_days = (end_dt.date() - start_dt.date()).days + 1

    city_breakdown = build_city_breakdown(chart_leads)
    hour_breakdown = build_hour_breakdown(chart_leads, span_days=chart_span_days)

    last_sync = None
    if result.get("from_cache") and result.get("cache_age_seconds") is not None:
        secs = result["cache_age_seconds"]
        last_sync = f"{secs // 60}m {secs % 60}s ago (cached)"
    elif result.get("ok"):
        last_sync = "Just now"

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "kpis": kpis,
            "ok": result.get("ok", False),
            "error": result.get("error") or result.get("sync_error"),
            "last_sync": last_sync,
            "leads": leads,
            "mode": mode,
            "window_label": label,
            "selected_date": start_dt.strftime("%Y-%m-%d") if mode == "single" else "",
            "selected_start": start_dt.strftime("%Y-%m-%d"),
            "selected_end": end_dt.strftime("%Y-%m-%d"),
            "today_iso": datetime.now().strftime("%Y-%m-%d"),
            "current_day": datetime.now().strftime("%a").upper(),
            "cooldown_remaining": result.get("cooldown_remaining", 0),
            "city_breakdown": city_breakdown,
            "hour_breakdown": hour_breakdown,
        },
    )


EXPORT_COLUMNS = [
    ("Status", "_status"),
    ("Query Time", "QUERY_TIME"),
    ("Name", "SENDER_NAME"),
    ("Mobile", "SENDER_MOBILE"),
    ("Email", "SENDER_EMAIL"),
    ("City", "SENDER_CITY"),
    ("State", "SENDER_STATE"),
    ("Company", "SENDER_COMPANY"),
    ("Subject", "SUBJECT"),
    ("Product", "QUERY_PRODUCT_NAME"),
    ("Message", "QUERY_MESSAGE"),
    ("Query ID", "UNIQUE_QUERY_ID"),
]


_BR_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)


def clean_cell(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s in ("<nil>", "nil", "None", "null"):
        return ""
    s = _BR_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


@app.get("/export")
def export_csv(mode: str = "today", date: str | None = None, start: str | None = None, end: str | None = None):
    if mode not in ("today", "single", "range", "last7"):
        mode = "today"

    start_dt, end_dt, label = resolve_window(mode, date, start, end)
    now = datetime.now()
    last7_start = datetime(now.year, now.month, now.day) - timedelta(days=6)
    today_end = datetime(now.year, now.month, now.day)
    within_last_7 = start_dt.date() >= last7_start.date() and end_dt.date() <= today_end.date()

    if within_last_7:
        result = fetch_leads(start_date=last7_start, end_date=today_end, force=False)
    else:
        result = fetch_leads(start_date=start_dt, end_date=end_dt, force=False)

    all_leads = result.get("leads", [])
    if mode == "today":
        leads = all_leads
        build_today_kpis(leads)
    else:
        leads = filter_leads_to_window(all_leads, start_dt, end_dt)
        build_range_kpis(leads, start_dt, end_dt, mode)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([h for h, _ in EXPORT_COLUMNS])
    for lead in leads:
        writer.writerow([clean_cell(lead.get(key)) for _, key in EXPORT_COLUMNS])

    buf.seek(0)
    filename_label = label.replace(" ", "_").replace("/", "-")
    filename = f"leads-{filename_label}.csv"

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/sync")
def sync(mode: str = "today", date: str | None = None, start: str | None = None, end: str | None = None):
    start_dt, end_dt, _ = resolve_window(mode, date, start, end)
    now = datetime.now()
    last7_start = datetime(now.year, now.month, now.day) - timedelta(days=6)
    today_end = datetime(now.year, now.month, now.day)
    within_last_7 = start_dt.date() >= last7_start.date() and end_dt.date() <= today_end.date()

    if within_last_7:
        fetch_leads(start_date=last7_start, end_date=today_end, force=True)
    else:
        fetch_leads(start_date=start_dt, end_date=end_dt, force=True)

    qs = f"?mode={mode}"
    if date:
        qs += f"&date={date}"
    if start:
        qs += f"&start={start}"
    if end:
        qs += f"&end={end}"
    return RedirectResponse(url=f"/{qs}", status_code=303)


if __name__ == "__main__":
    import webbrowser
    import uvicorn

    url = "http://127.0.0.1:8000"
    print(f"\nIndiaMART Lead Dashboard starting at {url}\n")
    webbrowser.open(url)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
