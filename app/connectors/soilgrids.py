import httpx
from fastapi import HTTPException

BASE = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# Keep it small for MVP
PROPS = ["phh2o", "soc", "clay", "sand", "silt", "cec"]

async def fetch_soilgrids(lat: float, lon: float) -> dict:
    params = {
        "lat": lat,
        "lon": lon,
        "property": ",".join(PROPS),
        "depth": "0-5cm"  # MVP: topsoil layer
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(BASE, params=params)
        if r.status_code != 200:
            raise HTTPException(502, f"SoilGrids error: {r.text}")
        return r.json()

def extract_topsoil_estimates(payload: dict) -> dict:
    """
    Extract a simple estimated soil profile from SoilGrids response.
    Response is nested; we keep it minimal.
    """
    out = {"source": "estimated", "depth": "0-5cm"}
    props = payload.get("properties", {}).get("layers", [])
    # In practice: parse each layer, pull mean value.
    # We'll keep placeholder parsing here because SoilGrids JSON is nested.
    # You can paste one real response and I’ll tailor exact extraction.
    return out
