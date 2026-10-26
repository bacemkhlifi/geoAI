import httpx
from fastapi import HTTPException
from time import monotonic
from copy import deepcopy
from app.features.climate import summarize_10y_daily

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
_cache: dict = {}

async def fetch_daily_history(lat: float, lon: float, start_date: str, end_date: str) -> dict:
    """
    Fetch daily climate history from Open-Meteo Archive API.
    Dates format: YYYY-MM-DD
    """
    key = (round(lat, 4), round(lon, 4), start_date, end_date)
    cached = _cache.get(key)
    if cached and monotonic() - cached[0] < 86400:
        return deepcopy(cached[1])
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum",
        "timezone": "auto",
        "models": "era5",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(ARCHIVE_URL, params=params)
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload.get("daily"), dict):
                raise ValueError("Missing climate series")
            summary = summarize_10y_daily(payload["daily"])
            if not summary.get("error") and summary.get("period_days", 0) >= 3650:
                if len(_cache) >= 128:
                    _cache.pop(next(iter(_cache)))
                _cache[key] = (monotonic(), deepcopy(payload))
            return payload
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(502, "Climate provider temporarily unavailable") from None
