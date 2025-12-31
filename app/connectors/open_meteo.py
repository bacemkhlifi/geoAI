import httpx
from fastapi import HTTPException

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

async def fetch_daily_history(lat: float, lon: float, start_date: str, end_date: str) -> dict:
    """
    Fetch daily climate history from Open-Meteo Archive API.
    Dates format: YYYY-MM-DD
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum",
        "timezone": "auto"
    }

    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.get(ARCHIVE_URL, params=params)
        if r.status_code != 200:
            raise HTTPException(502, f"Open-Meteo archive error: {r.text}")
        return r.json()
