import csv
import io
import os
import re
from collections import Counter
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# Pull secret from Streamlit Cloud secrets if running there, so indiamart_client
# (which reads os.getenv) keeps working without changes.
try:
    if "INDIAMART_API_KEY" in st.secrets:
        os.environ["INDIAMART_API_KEY"] = st.secrets["INDIAMART_API_KEY"]
except Exception:
    pass

from indiamart_client import fetch_leads, parse_query_time

st.set_page_config(
    page_title="IndiaMART Leads Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------
# Theme state (read at top, toggle rendered later in sidebar)
# -----------------------------
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
IS_DARK = bool(st.session_state.dark_mode)


# -----------------------------
# Custom CSS — uses CSS variables so dark/light only differs in the :root block
# -----------------------------
if IS_DARK:
    theme_vars = """
    :root {
        --bg-app-1: #0f172a;
        --bg-app-2: #1e293b;
        --bg-card: #1e293b;
        --bg-sidebar: #0f172a;
        --text-primary: #f1f5f9;
        --text-muted: #94a3b8;
        --text-faint: #64748b;
        --border: #334155;
        --shadow-card: 0 2px 8px rgba(0,0,0,0.35), 0 1px 2px rgba(0,0,0,0.45);
        --shadow-card-hover: 0 10px 25px rgba(0,0,0,0.45), 0 4px 10px rgba(0,0,0,0.4);
        --grid-line: #334155;
        --zero-line: #475569;
        --pill-ok-bg: #064e3b;     --pill-ok-fg: #6ee7b7;
        --pill-warn-bg: #78350f;   --pill-warn-fg: #fcd34d;
        --pill-error-bg: #7f1d1d;  --pill-error-fg: #fca5a5;
        --pill-muted-bg: #334155;  --pill-muted-fg: #cbd5e1;
        --badge-new-bg: #064e3b;     --badge-new-fg: #6ee7b7;
        --badge-working-bg: #1e3a8a; --badge-working-fg: #93c5fd;
        --badge-pending-bg: #78350f; --badge-pending-fg: #fcd34d;
    }
    """
else:
    theme_vars = """
    :root {
        --bg-app-1: #f8fafc;
        --bg-app-2: #f1f5f9;
        --bg-card: #ffffff;
        --bg-sidebar: #ffffff;
        --text-primary: #0f172a;
        --text-muted: #64748b;
        --text-faint: #94a3b8;
        --border: #e2e8f0;
        --shadow-card: 0 2px 8px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
        --shadow-card-hover: 0 10px 25px rgba(0,0,0,0.08), 0 4px 10px rgba(0,0,0,0.05);
        --grid-line: #f1f5f9;
        --zero-line: #e2e8f0;
        --pill-ok-bg: #d1fae5;    --pill-ok-fg: #065f46;
        --pill-warn-bg: #fef3c7;  --pill-warn-fg: #92400e;
        --pill-error-bg: #fee2e2; --pill-error-fg: #991b1b;
        --pill-muted-bg: #e2e8f0; --pill-muted-fg: #475569;
        --badge-new-bg: #d1fae5;    --badge-new-fg: #065f46;
        --badge-working-bg: #dbeafe; --badge-working-fg: #1e40af;
        --badge-pending-bg: #fef3c7; --badge-pending-fg: #92400e;
    }
    """

st.markdown(
    f"""
<style>
    {theme_vars}

    /* Hide Streamlit default chrome but keep sidebar toggle visible */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header[data-testid="stHeader"] {{
        background: transparent;
        height: 0;
    }}
    button[data-testid="stBaseButton-headerNoPadding"],
    button[data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {{
        visibility: visible !important;
        z-index: 999 !important;
    }}

    .stApp {{
        background: linear-gradient(180deg, var(--bg-app-1) 0%, var(--bg-app-2) 100%);
    }}

    .block-container {{
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }}

    /* Hero — stays purple gradient in both themes */
    .hero {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        color: white;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.25);
        margin-bottom: 1.5rem;
    }}
    .hero h1 {{
        font-size: 1.85rem; font-weight: 700; margin: 0;
        color: white; letter-spacing: -0.5px;
    }}
    .hero p {{
        font-size: 0.95rem; margin: 0.35rem 0 0 0;
        color: rgba(255,255,255,0.85); font-weight: 400;
    }}
    .hero-row {{
        display: flex; justify-content: space-between;
        align-items: center; flex-wrap: wrap; gap: 1rem;
    }}
    .hero-meta {{
        background: rgba(255,255,255,0.15);
        padding: 0.5rem 1rem; border-radius: 10px;
        backdrop-filter: blur(8px); font-size: 0.85rem; color: white;
    }}

    /* KPI cards */
    .kpi-grid {{
        display: grid; grid-template-columns: repeat(5, 1fr);
        gap: 1rem; margin-bottom: 1.5rem;
    }}
    @media (max-width: 1100px) {{
        .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
    .kpi-card {{
        background: var(--bg-card);
        border-radius: 14px; padding: 1.25rem;
        box-shadow: var(--shadow-card);
        border-top: 4px solid transparent;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        position: relative; overflow: hidden;
    }}
    .kpi-card:hover {{
        transform: translateY(-3px);
        box-shadow: var(--shadow-card-hover);
    }}
    .kpi-card.total   {{ border-top-color: #6366f1; }}
    .kpi-card.new     {{ border-top-color: #10b981; }}
    .kpi-card.working {{ border-top-color: #3b82f6; }}
    .kpi-card.pending {{ border-top-color: #f59e0b; }}
    .kpi-card.avg     {{ border-top-color: #06b6d4; }}

    .kpi-icon {{ font-size: 1.5rem; margin-bottom: 0.4rem; display: block; }}
    .kpi-label {{
        font-size: 0.78rem; text-transform: uppercase;
        color: var(--text-muted); font-weight: 600;
        letter-spacing: 0.6px; margin-bottom: 0.35rem;
    }}
    .kpi-value {{
        font-size: 2rem; font-weight: 700;
        color: var(--text-primary); line-height: 1;
    }}
    .kpi-sub {{
        font-size: 0.75rem; color: var(--text-faint); margin-top: 0.4rem;
    }}

    /* Section panels */
    .panel {{
        background: var(--bg-card);
        border-radius: 14px; padding: 1.25rem 1.5rem;
        box-shadow: var(--shadow-card); margin-bottom: 1.25rem;
    }}
    .panel-title {{
        font-size: 1.05rem; font-weight: 700;
        color: var(--text-primary); margin: 0 0 0.85rem 0;
        display: flex; align-items: center; gap: 0.5rem;
    }}

    /* Status pill */
    .status-pill {{
        display: inline-flex; align-items: center; gap: 0.4rem;
        padding: 0.3rem 0.75rem; border-radius: 999px;
        font-size: 0.8rem; font-weight: 600;
    }}
    .status-pill.ok    {{ background: var(--pill-ok-bg);    color: var(--pill-ok-fg); }}
    .status-pill.warn  {{ background: var(--pill-warn-bg);  color: var(--pill-warn-fg); }}
    .status-pill.error {{ background: var(--pill-error-bg); color: var(--pill-error-fg); }}
    .status-pill.muted {{ background: var(--pill-muted-bg); color: var(--pill-muted-fg); }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background: var(--bg-sidebar);
        border-right: 1px solid var(--border);
    }}
    section[data-testid="stSidebar"] > div {{ padding-top: 1.5rem; }}
    .sidebar-title {{
        font-size: 0.85rem; font-weight: 700; text-transform: uppercase;
        color: var(--text-muted); letter-spacing: 0.8px; margin: 0 0 0.5rem 0;
    }}

    /* Buttons */
    .stButton > button {{
        border-radius: 10px; font-weight: 600;
        border: none; transition: all 0.18s ease;
    }}
    .stDownloadButton > button {{
        border-radius: 10px; font-weight: 600;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white; border: none;
    }}
    .stDownloadButton > button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }}

    /* DataFrame container */
    .stDataFrame {{ border-radius: 12px; overflow: hidden; }}
    .js-plotly-plot {{ border-radius: 10px; }}

    /* Force colors on custom elements (beats Streamlit's default markdown color) */
    .kpi-value {{ color: var(--text-primary) !important; }}
    .kpi-label {{ color: var(--text-muted) !important; }}
    .kpi-sub   {{ color: var(--text-faint) !important; }}
    .panel-title {{ color: var(--text-primary) !important; }}

    /* Streamlit native widget text — make readable in both themes */
    .stApp {{ color: var(--text-primary); }}
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] li,
    .stApp [data-testid="stMarkdownContainer"] h1,
    .stApp [data-testid="stMarkdownContainer"] h2,
    .stApp [data-testid="stMarkdownContainer"] h3,
    .stApp [data-testid="stMarkdownContainer"] h4,
    .stApp [data-testid="stMarkdownContainer"] h5,
    .stApp [data-testid="stMarkdownContainer"] h6,
    .stApp [data-testid="stMarkdownContainer"] strong {{
        color: var(--text-primary);
    }}
    .stApp [data-testid="stCaptionContainer"],
    .stApp .stCaption {{
        color: var(--text-muted) !important;
    }}

    /* Sidebar — all text light in dark mode */
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h4,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h5,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] [data-testid="stRadio"] label,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] *,
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {{
        color: var(--text-primary) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
        color: var(--text-muted) !important;
    }}

    /* Inputs — date picker, etc. */
    .stDateInput label, .stDateInput div[data-baseweb="input"] input {{
        color: var(--text-primary) !important;
    }}
    .stDateInput div[data-baseweb="input"],
    .stDateInput div[data-baseweb="select"] {{
        background: var(--bg-card) !important;
    }}

    /* Dividers / hr */
    hr {{ border-color: var(--border) !important; }}
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------
# Helpers
# -----------------------------
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


def filter_leads_to_window(leads: list[dict], start: datetime, end: datetime) -> list[dict]:
    out = []
    for lead in leads:
        dt = parse_query_time(lead.get("QUERY_TIME", ""))
        if dt is None:
            continue
        if start.date() <= dt.date() <= end.date():
            out.append(lead)
    return out


def attach_status(leads: list[dict]) -> None:
    now = datetime.now()
    for lead in leads:
        lead["_status"] = classify_status(lead.get("QUERY_TIME", ""), now)


def build_kpis(leads: list[dict], span_days: int) -> dict:
    counts = {"NEW": 0, "WORKING": 0, "PENDING": 0}
    for lead in leads:
        counts[lead["_status"]] = counts.get(lead["_status"], 0) + 1
    total = len(leads)
    daily_avg = round(total / span_days, 1) if span_days > 0 else 0
    return {
        "new_count": counts["NEW"],
        "working_count": counts["WORKING"],
        "pending_count": counts["PENDING"],
        "total": total,
        "daily_avg": daily_avg,
    }


def _hour_label(hour: int) -> str:
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"


def _period_for_hour(hour: int) -> tuple[str, str]:
    """Return (period_label, color) for an hour 0-23."""
    if 6 <= hour <= 11:
        return "Morning", "#fbbf24"
    if 12 <= hour <= 16:
        return "Afternoon", "#f97316"
    if 17 <= hour <= 20:
        return "Evening", "#8b5cf6"
    return "Night", "#64748b"


def build_hour_breakdown(leads: list[dict], span_days: int) -> dict | None:
    # Initialize all 24 hours with 0 counts
    hour_counts: dict[int, int] = {h: 0 for h in range(24)}
    has_any = False
    for lead in leads:
        dt = parse_query_time(lead.get("QUERY_TIME", ""))
        if dt is None:
            continue
        hour_counts[dt.hour] += 1
        has_any = True

    if not has_any:
        return None

    is_averaged = span_days > 1
    divisor = span_days if is_averaged else 1

    def fmt(n: float) -> float | int:
        if not is_averaged:
            return n
        return round(n / divisor, 1)

    hours_detailed = []
    for h in range(24):
        period_label, color = _period_for_hour(h)
        hours_detailed.append({
            "hour": h,
            "label": _hour_label(h),
            "count": fmt(hour_counts[h]),
            "raw_count": hour_counts[h],
            "period": period_label,
            "color": color,
        })

    peak_hour, peak_total = max(hour_counts.items(), key=lambda x: x[1])
    peak_period, _ = _period_for_hour(peak_hour)

    # Period totals (for summary line)
    period_totals: dict[str, int] = {}
    for h, c in hour_counts.items():
        p, _ = _period_for_hour(h)
        period_totals[p] = period_totals.get(p, 0) + c

    return {
        "hours": hours_detailed,
        "peak_hour": _hour_label(peak_hour),
        "peak_count": fmt(peak_total),
        "peak_period": peak_period,
        "period_totals": {k: fmt(v) for k, v in period_totals.items()},
        "is_averaged": is_averaged,
        "span_days": span_days,
    }


def build_city_breakdown(leads: list[dict]) -> list[dict]:
    counter: Counter = Counter()
    for lead in leads:
        raw = lead.get("SENDER_CITY")
        if not raw:
            continue
        city = str(raw).strip()
        if not city or city.lower() in ("<nil>", "nil", "none", "null"):
            continue
        counter[city.title()] += 1
    return [{"city": c, "count": n} for c, n in counter.most_common()]


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


def leads_to_csv_bytes(leads: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([h for h, _ in EXPORT_COLUMNS])
    for lead in leads:
        writer.writerow([clean_cell(lead.get(key)) for _, key in EXPORT_COLUMNS])
    return buf.getvalue().encode("utf-8")


def leads_to_dataframe(leads: list[dict]) -> pd.DataFrame:
    rows = []
    for lead in leads:
        row = {h: clean_cell(lead.get(key)) for h, key in EXPORT_COLUMNS}
        rows.append(row)
    return pd.DataFrame(rows)


# Cycling 20-color palette
CITY_COLORS = [
    "#6366f1", "#ef4444", "#10b981", "#f97316", "#8b5cf6",
    "#14b8a6", "#ec4899", "#f59e0b", "#06b6d4", "#a855f7",
    "#f43f5e", "#22c55e", "#0ea5e9", "#fb7185", "#84cc16",
    "#3b82f6", "#eab308", "#d946ef", "#0d9488", "#dc2626",
]


def render_city_chart(city_breakdown: list[dict], scrollable: bool = False) -> None:
    if not city_breakdown:
        st.info("No city data for this period.")
        return
    cities = [c["city"] for c in city_breakdown]
    counts = [c["count"] for c in city_breakdown]
    colors = [CITY_COLORS[i % len(CITY_COLORS)] for i in range(len(cities))]

    text_color = "#f1f5f9" if IS_DARK else "#0f172a"
    tick_color = "#cbd5e1" if IS_DARK else "#334155"
    grid_color = "#334155" if IS_DARK else "#f1f5f9"
    zero_color = "#475569" if IS_DARK else "#e2e8f0"

    fig = go.Figure(
        go.Bar(
            x=counts[::-1],
            y=cities[::-1],
            orientation="h",
            marker=dict(color=colors[::-1], line=dict(width=0)),
            text=counts[::-1],
            textposition="outside",
            textfont=dict(size=12, color=text_color, weight=600),
            hovertemplate="<b>%{y}</b><br>Leads: %{x}<extra></extra>",
        )
    )

    bar_height = 36
    if scrollable:
        chart_height = max(360, bar_height * len(cities) + 40)
    else:
        chart_height = max(320, min(bar_height * len(cities), 1200))

    fig.update_layout(
        height=chart_height,
        margin=dict(l=10, r=30, t=10, b=10),
        xaxis=dict(
            title=None, showgrid=True,
            gridcolor=grid_color, zerolinecolor=zero_color,
            tickfont=dict(color=tick_color),
            side="top" if scrollable else "bottom",
        ),
        yaxis=dict(title=None, tickfont=dict(size=12, color=tick_color)),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, -apple-system, sans-serif"),
    )

    if scrollable:
        # Window shows ~top-10 bars; user scrolls down to see the rest
        with st.container(height=bar_height * 10 + 60, border=False):
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    else:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_hour_chart(hour_breakdown: dict | None) -> None:
    if not hour_breakdown or not hour_breakdown.get("period_totals"):
        st.info("No time-of-day data for this period.")
        return

    period_label_full = {
        "Morning":   "Morning (6 AM – 11 AM)",
        "Afternoon": "Afternoon (12 PM – 4 PM)",
        "Evening":   "Evening (5 PM – 8 PM)",
        "Night":     "Night (9 PM – 5 AM)",
    }
    period_color = {"Morning": "#fbbf24", "Afternoon": "#f97316", "Evening": "#8b5cf6", "Night": "#64748b"}

    totals = hour_breakdown["period_totals"]
    ordered = [p for p in ("Morning", "Afternoon", "Evening", "Night") if totals.get(p, 0) > 0]
    labels = [period_label_full[p] for p in ordered]
    values = [totals[p] for p in ordered]
    colors = [period_color[p] for p in ordered]

    legend_color = "#cbd5e1" if IS_DARK else "#334155"
    annot_color = "#f1f5f9" if IS_DARK else "#0f172a"
    annot_sub = "#94a3b8" if IS_DARK else "#64748b"
    pie_border = "#1e293b" if IS_DARK else "white"

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            marker=dict(colors=colors, line=dict(color=pie_border, width=3)),
            textinfo="value",
            textfont=dict(size=14, color="white", weight=700),
            hovertemplate="<b>%{label}</b><br>%{value} leads<br>%{percent}<extra></extra>",
        )
    )
    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=11, color=legend_color)),
        font=dict(family="Inter, system-ui, -apple-system, sans-serif"),
        paper_bgcolor="rgba(0,0,0,0)",
        annotations=[
            dict(
                text=f"<b>{hour_breakdown['peak_hour']}</b><br><span style='font-size:11px;color:{annot_sub}'>Peak hour</span>",
                x=0.5, y=0.5,
                font=dict(size=16, color=annot_color),
                showarrow=False,
            )
        ],
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    suffix = " (avg/day)" if hour_breakdown["is_averaged"] else ""
    st.markdown(
        f"<div style='text-align:center;color:{annot_sub};font-size:0.85rem;margin-top:-0.5rem;'>"
        f"Peak: <b style='color:{annot_color}'>{hour_breakdown['peak_hour']}</b> · "
        f"{hour_breakdown['peak_count']} leads{suffix}</div>",
        unsafe_allow_html=True,
    )


def kpi_card(klass: str, icon: str, label: str, value, sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="kpi-card {klass}">'
        f'<span class="kpi-icon">{icon}</span>'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


# -----------------------------
# Sidebar — filters
# -----------------------------
today = datetime.now()
today_date = today.date()
last7_start = today_date - timedelta(days=6)

with st.sidebar:
    st.markdown('<div class="sidebar-title">🚀 Dashboard</div>', unsafe_allow_html=True)
    theme_cols = st.columns([3, 2])
    with theme_cols[0]:
        st.caption("**Theme**")
    with theme_cols[1]:
        st.toggle("🌙", key="dark_mode", help="Toggle dark / light mode", label_visibility="visible")
    st.divider()
    st.markdown("##### Filters")

    mode_label = st.radio(
        "View mode",
        ["Today", "Single Date", "Custom Range", "Last 7 Days"],
        index=0,
    )

    mode_map = {"Today": "today", "Single Date": "single", "Custom Range": "range", "Last 7 Days": "last7"}
    mode = mode_map[mode_label]

    if mode == "single":
        picked = st.date_input("Date", value=today_date, max_value=today_date)
        if picked == today_date:
            mode = "today"
            start_dt = datetime(last7_start.year, last7_start.month, last7_start.day)
            end_dt = datetime(today.year, today.month, today.day)
            window_label = "Today + Open"
        else:
            start_dt = datetime(picked.year, picked.month, picked.day)
            end_dt = start_dt
            window_label = start_dt.strftime("%d-%b-%Y")
    elif mode == "range":
        default_start = today_date - timedelta(days=6)
        picked = st.date_input(
            "Range",
            value=(default_start, today_date),
            max_value=today_date,
        )
        if isinstance(picked, tuple) and len(picked) == 2:
            s, e = picked
        else:
            s = e = picked if not isinstance(picked, tuple) else picked[0]
        if s > e:
            s, e = e, s
        if (e - s).days > 6:
            st.warning("⚠️ Max 7 days. Trimming.")
            e = s + timedelta(days=6)
        start_dt = datetime(s.year, s.month, s.day)
        end_dt = datetime(e.year, e.month, e.day)
        window_label = f"{start_dt.strftime('%d-%b-%Y')} → {end_dt.strftime('%d-%b-%Y')}"
    elif mode == "last7":
        start_dt = datetime(last7_start.year, last7_start.month, last7_start.day)
        end_dt = datetime(today.year, today.month, today.day)
        window_label = "Last 7 Days"
    else:
        start_dt = datetime(last7_start.year, last7_start.month, last7_start.day)
        end_dt = datetime(today.year, today.month, today.day)
        window_label = "Today + Open"

    st.divider()
    sync_clicked = st.button("🔄 Sync Now", width="stretch", type="primary")

    st.divider()
    st.caption("ℹ️ API allows 1 call per 5 minutes. Data is cached between syncs.")


# -----------------------------
# Fetch leads
# -----------------------------
today_end = datetime(today.year, today.month, today.day)
last7_start_dt = today_end - timedelta(days=6)
within_last_7 = start_dt.date() >= last7_start_dt.date() and end_dt.date() <= today_end.date()

if within_last_7:
    result = fetch_leads(start_date=last7_start_dt, end_date=today_end, force=sync_clicked)
else:
    result = fetch_leads(start_date=start_dt, end_date=end_dt, force=sync_clicked)

all_leads = result.get("leads", [])

if mode == "today":
    leads = all_leads
    span_days = 7
else:
    leads = filter_leads_to_window(all_leads, start_dt, end_dt)
    span_days = (end_dt.date() - start_dt.date()).days + 1

attach_status(leads)
kpis = build_kpis(leads, span_days=span_days)

# Build sync status pill — cooldown gets its own live-countdown banner below the hero
cd = result.get("cooldown_remaining", 0)
err = result.get("error") if cd == 0 else None  # suppress cooldown's static error text in pill
sync_err = result.get("sync_error") if cd == 0 else None

if err or sync_err:
    pill_html = f'<span class="status-pill error">⚠️ {err or sync_err}</span>'
elif cd > 0 and result.get("from_cache"):
    age = result.get("cache_age_seconds", 0)
    pill_html = f'<span class="status-pill muted">🗂️ Cached · {age // 60}m {age % 60}s ago</span>'
elif cd > 0:
    pill_html = '<span class="status-pill warn">⏳ Waiting for cooldown...</span>'
elif result.get("from_cache") and result.get("cache_age_seconds") is not None:
    age = result["cache_age_seconds"]
    pill_html = f'<span class="status-pill muted">🗂️ Cached · {age // 60}m {age % 60}s ago</span>'
elif result.get("ok"):
    pill_html = '<span class="status-pill ok">✓ Live · Just now</span>'
else:
    pill_html = '<span class="status-pill muted">— No data</span>'


# -----------------------------
# Hero header
# -----------------------------
st.markdown(
    f"""
<div class="hero">
    <div class="hero-row">
        <div>
            <h1>🚀 IndiaMART Leads Dashboard</h1>
            <p>Real-time enquiry tracking · {today.strftime('%A, %d %B %Y')}</p>
        </div>
        <div style="display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap;">
            <div class="hero-meta">📅 {window_label}</div>
            {pill_html}
        </div>
    </div>
</div>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Live cooldown banner (countdown via embedded JS)
# -----------------------------
if cd > 0:
    if IS_DARK:
        banner_bg = "linear-gradient(135deg,#78350f 0%,#92400e 100%)"
        banner_color = "#fde68a"
        time_bg = "#1e293b"
        time_color = "#fde68a"
        time_border = "#a16207"
        done_bg = "#064e3b"
        done_color = "#6ee7b7"
        done_border = "#10b981"
        sub_color = "#fbbf24"
    else:
        banner_bg = "linear-gradient(135deg,#fef3c7 0%,#fde68a 100%)"
        banner_color = "#92400e"
        time_bg = "white"
        time_color = "#92400e"
        time_border = "#fcd34d"
        done_bg = "#d1fae5"
        done_color = "#065f46"
        done_border = "#6ee7b7"
        sub_color = "#a16207"

    countdown_html = (
        "<style>"
        "body{margin:0;padding:0;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;}"
        f".cd-banner{{display:flex;align-items:center;gap:0.7rem;padding:0.7rem 1.1rem;"
        f"background:{banner_bg};"
        f"color:{banner_color};border-radius:12px;font-size:0.9rem;font-weight:600;"
        "box-shadow:0 2px 8px rgba(245,158,11,0.18);}"
        ".cd-icon{font-size:1.2rem;}"
        f".cd-time{{font-family:'SF Mono',Consolas,monospace;font-size:1.05rem;font-weight:700;"
        f"padding:0.25rem 0.7rem;background:{time_bg};border-radius:8px;color:{time_color};"
        f"min-width:78px;text-align:center;box-shadow:inset 0 0 0 1px {time_border};}}"
        f".cd-time.done{{background:{done_bg};color:{done_color};box-shadow:inset 0 0 0 1px {done_border};}}"
        "</style>"
        '<div class="cd-banner">'
        '<span class="cd-icon">⏳</span>'
        '<span>Rate-limit cooldown — next API sync allowed in</span>'
        f'<span class="cd-time" id="cd-time">{cd // 60}:{cd % 60:02d}</span>'
        f'<span style="color:{sub_color};font-weight:500;font-size:0.82rem;">'
        '(IndiaMART allows 1 call per 5 min)</span>'
        '</div>'
        "<script>"
        "(function(){"
        f"var endTime=Date.now()+{cd}*1000;"
        "var el=document.getElementById('cd-time');"
        "function pad(n){return n<10?'0'+n:n;}"
        "function tick(){"
        "var rem=Math.max(0,Math.floor((endTime-Date.now())/1000));"
        "if(rem<=0){el.textContent='READY';el.classList.add('done');return;}"
        "var m=Math.floor(rem/60),s=rem%60;"
        "el.textContent=m+':'+pad(s);"
        "setTimeout(tick,1000);"
        "}"
        "tick();"
        "})();"
        "</script>"
    )
    components.html(countdown_html, height=60)


# -----------------------------
# KPI cards
# -----------------------------
avg_label = "Daily Avg" if span_days > 1 else "Today"
avg_value = kpis["daily_avg"] if span_days > 1 else kpis["total"]
avg_sub = f"over {span_days} days" if span_days > 1 else "leads today"

kpi_html = (
    '<div class="kpi-grid">'
    + kpi_card("total",   "📥", "Total Leads",  kpis["total"],         f"in {window_label}")
    + kpi_card("new",     "🆕", "New",          kpis["new_count"],     "received today")
    + kpi_card("working", "🔄", "Working",      kpis["working_count"], "1 day old")
    + kpi_card("pending", "⏰", "Pending",      kpis["pending_count"], "2+ days old")
    + kpi_card("avg",     "📊", avg_label,      avg_value,             avg_sub)
    + '</div>'
)
st.markdown(kpi_html, unsafe_allow_html=True)


# -----------------------------
# Charts row
# -----------------------------
chart_leads = leads
chart_span = span_days

city_breakdown = build_city_breakdown(chart_leads)
hour_breakdown = build_hour_breakdown(chart_leads, span_days=chart_span)

chart_cols = st.columns([3, 2], gap="medium")
with chart_cols[0]:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    city_count_label = f"{len(city_breakdown)} cities"
    scroll_city = len(city_breakdown) > 10
    if scroll_city:
        city_count_label += " · top 10 visible · scroll for more"
    st.markdown(f'<div class="panel-title">🌆 Cities Breakdown <span style="color:#94a3b8;font-weight:400;font-size:0.85rem;">· {city_count_label}</span></div>', unsafe_allow_html=True)
    render_city_chart(city_breakdown, scrollable=scroll_city)
    st.markdown('</div>', unsafe_allow_html=True)

with chart_cols[1]:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    title_suffix = " (avg/day)" if hour_breakdown and hour_breakdown["is_averaged"] else ""
    st.markdown(f'<div class="panel-title">⏱️ Time Distribution{title_suffix}</div>', unsafe_allow_html=True)
    render_hour_chart(hour_breakdown)
    st.markdown('</div>', unsafe_allow_html=True)


# -----------------------------
# Leads table
# -----------------------------
st.markdown('<div class="panel">', unsafe_allow_html=True)
table_header_cols = st.columns([3, 1])
with table_header_cols[0]:
    st.markdown(f'<div class="panel-title">📋 Leads <span style="color:#94a3b8;font-weight:400;font-size:0.85rem;">· {len(leads)} results</span></div>', unsafe_allow_html=True)
with table_header_cols[1]:
    filename_label = window_label.replace(" ", "_").replace("→", "-").replace("/", "-")
    st.download_button(
        "⬇️ Export CSV",
        data=leads_to_csv_bytes(leads),
        file_name=f"leads-{filename_label}.csv",
        mime="text/csv",
        width="stretch",
        disabled=len(leads) == 0,
    )

if leads:
    leads.sort(key=lambda l: l.get("QUERY_TIME", ""), reverse=True)
    df = leads_to_dataframe(leads)

    # Style status column with badge-like colors via pandas Styler
    if IS_DARK:
        badge_styles = {
            "NEW":     "background-color:#064e3b; color:#6ee7b7;",
            "WORKING": "background-color:#1e3a8a; color:#93c5fd;",
            "PENDING": "background-color:#78350f; color:#fcd34d;",
        }
    else:
        badge_styles = {
            "NEW":     "background-color:#d1fae5; color:#065f46;",
            "WORKING": "background-color:#dbeafe; color:#1e40af;",
            "PENDING": "background-color:#fef3c7; color:#92400e;",
        }

    def style_status(val: str):
        base = badge_styles.get(val, "")
        return f"{base} font-weight:700; border-radius:6px;" if base else ""

    styled = df.style.map(style_status, subset=["Status"])

    st.dataframe(
        styled,
        width="stretch",
        hide_index=True,
        height=520,
        column_config={
            "Status":     st.column_config.TextColumn(width="small"),
            "Query Time": st.column_config.TextColumn(width="medium"),
            "Name":       st.column_config.TextColumn(width="medium"),
            "Mobile":     st.column_config.TextColumn(width="small"),
            "Email":      st.column_config.TextColumn(width="medium"),
            "City":       st.column_config.TextColumn(width="small"),
            "State":      st.column_config.TextColumn(width="small"),
            "Company":    st.column_config.TextColumn(width="medium"),
            "Subject":    st.column_config.TextColumn(width="medium"),
            "Product":    st.column_config.TextColumn(width="medium"),
            "Message":    st.column_config.TextColumn(width="large"),
            "Query ID":   st.column_config.TextColumn(width="small"),
        },
    )
else:
    st.info("📭 No leads in this window. Try a different date range or click 🔄 Sync Now.")

st.markdown('</div>', unsafe_allow_html=True)
