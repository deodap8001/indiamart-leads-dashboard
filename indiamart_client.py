import os
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("INDIAMART_API_KEY", "").strip()
API_URL = "https://mapi.indiamart.com/wservce/crm/crmListing/v2/"

CACHE_TTL_SECONDS = 5 * 60
MAX_DAYS = 7
RATE_LIMIT_COOLDOWN_SECONDS = 5 * 60 + 15

_cache: dict[str, dict] = {}
_last_rate_limit_at: float = 0.0
_last_api_call_at: float = 0.0


def _format_date(d: datetime) -> str:
    return d.strftime("%d-%b-%Y")


def _cache_key(start: datetime, end: datetime) -> str:
    return f"{start.date().isoformat()}_{end.date().isoformat()}"


def _call_api(start: datetime, end: datetime) -> dict[str, Any]:
    global _last_rate_limit_at, _last_api_call_at

    if not API_KEY:
        return {"ok": False, "error": "INDIAMART_API_KEY missing in .env", "leads": []}

    params = {
        "glusr_crm_key": API_KEY,
        "start_time": _format_date(start),
        "end_time": _format_date(end),
    }

    _last_api_call_at = time.time()
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(API_URL, params=params)
            payload = r.json()
    except Exception as e:
        return {"ok": False, "error": f"Network error: {e}", "leads": []}

    code = payload.get("CODE")
    message = payload.get("MESSAGE", "")
    leads = payload.get("RESPONSE") or []

    if code == 200:
        return {"ok": True, "error": None, "leads": leads, "message": message}
    if code == 204:
        return {"ok": True, "error": None, "leads": [], "message": message}
    if code == 429:
        _last_rate_limit_at = time.time()
        return {"ok": False, "error": f"Rate limit: {message}", "leads": [], "rate_limited": True}
    return {"ok": False, "error": f"API {code}: {message}", "leads": []}


def cooldown_remaining() -> int:
    if _last_rate_limit_at == 0:
        return 0
    elapsed = time.time() - _last_rate_limit_at
    remaining = RATE_LIMIT_COOLDOWN_SECONDS - elapsed
    return max(0, int(remaining))


def fetch_leads(start_date: datetime | None = None, end_date: datetime | None = None, force: bool = False) -> dict[str, Any]:
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=MAX_DAYS)

    diff_days = (end_date.date() - start_date.date()).days
    if diff_days > MAX_DAYS:
        return {
            "ok": False,
            "error": f"Date range too large: max {MAX_DAYS} days allowed (you asked {diff_days} days).",
            "leads": [],
            "from_cache": False,
            "cache_age_seconds": 0,
        }
    if start_date > end_date:
        return {
            "ok": False,
            "error": "Start date must be before or equal to end date.",
            "leads": [],
            "from_cache": False,
            "cache_age_seconds": 0,
        }

    key = _cache_key(start_date, end_date)
    now = time.time()
    entry = _cache.get(key)

    if not force and entry is not None:
        age = now - entry["fetched_at"]
        if age < CACHE_TTL_SECONDS:
            return {
                **entry["data"],
                "from_cache": True,
                "cache_age_seconds": int(age),
                "cooldown_remaining": cooldown_remaining(),
            }

    cooldown = cooldown_remaining()
    if cooldown > 0:
        if entry is not None:
            return {
                **entry["data"],
                "from_cache": True,
                "cache_age_seconds": int(now - entry["fetched_at"]),
                "sync_error": f"Rate limit cooldown: {cooldown}s remaining. API call blocked to prevent extending the lock.",
                "cooldown_remaining": cooldown,
            }
        return {
            "ok": False,
            "error": f"Rate limit cooldown: wait {cooldown}s before next sync. API call blocked.",
            "leads": [],
            "from_cache": False,
            "cache_age_seconds": 0,
            "cooldown_remaining": cooldown,
        }

    result = _call_api(start_date, end_date)
    if result["ok"]:
        _cache[key] = {"data": result, "fetched_at": now}
        return {**result, "from_cache": False, "cache_age_seconds": 0, "cooldown_remaining": 0}

    if entry is not None:
        return {
            **entry["data"],
            "from_cache": True,
            "cache_age_seconds": int(now - entry["fetched_at"]),
            "sync_error": result["error"],
            "cooldown_remaining": cooldown_remaining(),
        }

    return {**result, "from_cache": False, "cache_age_seconds": 0, "cooldown_remaining": cooldown_remaining()}


def parse_query_time(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
