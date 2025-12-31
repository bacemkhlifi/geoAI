# app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone, date
from typing import Literal

from app.connectors.open_meteo import fetch_daily_history
from app.features.climate import summarize_10y_daily, drought_risk_from_rainfall, aridity_class
from app.recommendations.tunisia import build_recommendations_tn

app = FastAPI(title="Tunisia GeoAI MVP", version="0.5.0")


# ----------------------------
# Request Models
# ----------------------------
class Site(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    name: str | None = None
    radius_m: int = Field(100, ge=10, le=5000)


class Constraints(BaseModel):
    country: str = "TN"
    irrigation_available: bool | None = None

    # NEW: irrigation realism
    water_ec_dS_m: float | None = Field(default=None, ge=0, le=50)
    water_source_reliability: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    # Later (optional): water_volume_m3_per_year: float | None


class SoilTest(BaseModel):
    ph: float | None = Field(default=None, ge=0, le=14)
    ec_dS_m: float | None = Field(default=None, ge=0, le=50)  # soil EC


class AnalyzeRequest(BaseModel):
    site: Site
    constraints: Constraints = Constraints()
    soil_test: SoilTest | None = None


# ----------------------------
# Helpers / Validation
# ----------------------------
def validate_point_in_tunisia(lat: float, lon: float) -> None:
    # Simple Tunisia bounding box (MVP). Avoids totally wrong coords.
    if not (30.0 <= lat <= 37.6 and 7.5 <= lon <= 11.9):
        raise HTTPException(
            400,
            f"Coordinates ({lat}, {lon}) are outside Tunisia bounds. "
            "Please provide a Tunisia point or change constraints.country."
        )

def _date_10y_window_end_today() -> tuple[str, str]:
    end_d = date.today()
    try:
        start_d = date(end_d.year - 10, end_d.month, end_d.day)
    except ValueError:
        start_d = date(end_d.year - 10, end_d.month, 28)
    return start_d.isoformat(), end_d.isoformat()

def salinity_risk_from_soil_ec(ec: float | None) -> str:
    if ec is None:
        return "UNKNOWN"
    if ec < 2.0:
        return "LOW"
    if ec < 4.0:
        return "MODERATE"
    return "HIGH"

def water_salinity_risk(ec: float | None) -> str:
    if ec is None:
        return "UNKNOWN"
    if ec < 2.0:
        return "LOW"
    if ec < 4.0:
        return "MODERATE"
    return "HIGH"

def build_risks(indicators: dict, constraints: dict, soil: dict | None) -> list[dict]:
    risks = []

    # Drought
    risks.append({
        "type": "DROUGHT",
        "level": indicators.get("drought_risk_no_irrigation", "UNKNOWN"),
        "with_irrigation_level": indicators.get("drought_risk", "UNKNOWN"),
        "evidence": [
            f"annual_rainfall_mm_est={indicators.get('annual_rainfall_mm_est')}",
            f"max_dry_spell_days_est={indicators.get('max_dry_spell_days_est')}",
            f"aridity_class={indicators.get('aridity_class')}",
            f"irrigation_available={constraints.get('irrigation_available')}"
        ],
        "mitigation": [
            "Drip irrigation where feasible",
            "Mulching / soil cover to reduce evaporation",
            "Drought-tolerant varieties"
        ]
    })

    # Salinity (soil + water)
    soil_ec = soil.get("ec_dS_m") if soil else None
    water_ec = constraints.get("water_ec_dS_m")

    risks.append({
        "type": "SALINITY",
        "level": indicators.get("salinity_risk", "UNKNOWN"),
        "water_salinity_level": indicators.get("water_salinity_risk", "UNKNOWN"),
        "evidence": [
            f"soil_ec_dS_m={soil_ec}" if soil_ec is not None else "soil_ec_dS_m=missing",
            f"water_ec_dS_m={water_ec}" if water_ec is not None else "water_ec_dS_m=missing"
        ],
        "mitigation": [
            "Water EC/SAR testing",
            "Improve organic matter",
            "Leaching strategy when feasible",
            "Choose salt-tolerant crops/varieties"
        ]
    })

    # Heat stress
    risks.append({
        "type": "HEAT",
        "level": "HIGH" if (indicators.get("hot_days_ge_40_per_year_est", 0) or 0) > 30 else "MEDIUM",
        "evidence": [
            f"hot_days_ge_35_per_year_est={indicators.get('hot_days_ge_35_per_year_est')}",
            f"hot_days_ge_40_per_year_est={indicators.get('hot_days_ge_40_per_year_est')}",
        ],
        "mitigation": [
            "Heat-tolerant varieties",
            "Shade nets (for sensitive crops)",
            "Irrigation scheduling to reduce heat stress"
        ]
    })

    return risks


# ----------------------------
# Routes
# ----------------------------
@app.get("/")
def root():
    return {"message": "Tunisia GeoAI API is running. Go to /docs"}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/v1/site-analysis")
async def site_analysis(req: AnalyzeRequest):
    if req.constraints.country != "TN":
        raise HTTPException(400, "This service is configured for Tunisia (TN) only.")

    validate_point_in_tunisia(req.site.lat, req.site.lon)

    # Climate: 10-year history
    start_date, end_date = _date_10y_window_end_today()
    raw = await fetch_daily_history(
        lat=req.site.lat,
        lon=req.site.lon,
        start_date=start_date,
        end_date=end_date
    )
    daily = raw.get("daily") or {}
    climate = summarize_10y_daily(daily)

    # Drought risks
    drought = drought_risk_from_rainfall(
        climate.get("annual_rainfall_mm_est"),
        req.constraints.irrigation_available
    )

    # Soil salinity
    soil_ec = req.soil_test.ec_dS_m if req.soil_test else None
    salinity_risk = salinity_risk_from_soil_ec(soil_ec)

    # Water salinity
    w_sal_risk = water_salinity_risk(req.constraints.water_ec_dS_m)

    # Aridity class
    arid_class = aridity_class(climate.get("annual_rainfall_mm_est"))

    # Build indicators (single reusable object)
    indicators = {
        **climate,
        "aridity_class": arid_class,
        "drought_risk": drought["with_irrigation"],
        "drought_risk_no_irrigation": drought["without_irrigation"],
        "salinity_risk": salinity_risk,
        "water_salinity_risk": w_sal_risk,
    }

    # Build risks
    soil_dump = req.soil_test.model_dump() if req.soil_test else None
    constraints_dump = req.constraints.model_dump()

    # Pass latitude as internal hint (no need to expose)
    constraints_dump["_lat_for_region"] = req.site.lat

    risks = build_risks(indicators, constraints_dump, soil_dump)

    # Recommendations
    recs = build_recommendations_tn(indicators, constraints_dump, soil=soil_dump)

    # Confidence (simple MVP)
    conf = "MEDIUM"
    if req.constraints.irrigation_available is None:
        conf = "LOW"
    if req.constraints.irrigation_available is True and req.constraints.water_ec_dS_m is None:
        conf = "LOW"  # missing critical info

    return {
        "report_id": f"rep_{int(datetime.now().timestamp())}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site": req.site.model_dump(),
        "constraints": req.constraints.model_dump(),
        "data_sources": [
            {
                "type": "weather_history",
                "provider": "open-meteo",
                "range": f"{start_date}..{end_date}",
                "kind": "measured/derived"
            },
            {
                "type": "soil_test",
                "provider": "user",
                "kind": "measured" if soil_ec is not None else "missing"
            },
            {
                "type": "water_test",
                "provider": "user",
                "kind": "measured" if req.constraints.water_ec_dS_m is not None else "missing"
            }
        ],
        "indicators": indicators,
        "risks": risks,
        "recommendations": recs,
        "confidence": {
            "overall": conf,
            "drivers": [
                "10-year climate history used",
                "Dry-spell and heat indicators included",
                "Rules engine is deterministic",
                "Add satellite/NDVI later for parcel-level validation"
            ]
        },
        "notes": [
            "Weather indicators are computed from 10-year daily history.",
            "radius_m is stored for future AOI/satellite analysis; weather remains point-based in MVP."
        ],
        "disclaimers": [
            "Decision-support only. Validate with field expertise and local agronomist.",
            "Accuracy improves with lab soil & water tests and parcel boundaries."
        ]
    }
