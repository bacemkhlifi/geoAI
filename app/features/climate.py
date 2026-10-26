# app/features/climate.py
from datetime import datetime
from typing import Optional
from math import isfinite

def _valid(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)

def _safe_mean(xs):
    xs = [x for x in xs if _valid(x)]
    return (sum(xs) / len(xs)) if xs else None

def _count_ge(xs, threshold: float) -> int:
    return sum(1 for x in xs if _valid(x) and x >= threshold)

def _count_le(xs, threshold: float) -> int:
    return sum(1 for x in xs if _valid(x) and x <= threshold)

def _max_consecutive_dry_days(precip, dry_threshold_mm: float = 1.0) -> int:
    """
    Max consecutive days where precipitation < dry_threshold_mm.
    """
    max_streak = 0
    streak = 0
    for p in precip:
        if _valid(p) and p >= 0 and p < dry_threshold_mm:
            streak += 1
            if streak > max_streak:
                max_streak = streak
        else:
            streak = 0
    return max_streak

def summarize_10y_daily(daily: dict) -> dict:
    """
    daily = response["daily"] from Open-Meteo archive.
    Returns robust, agriculture-friendly indicators for 10y.
    """
    dates = daily.get("time") or []
    pr = daily.get("precipitation_sum") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    tmean = daily.get("temperature_2m_mean") or []

    if not dates:
        return {"error": "no daily climate data returned"}

    # Coverage window
    try:
        d0 = datetime.fromisoformat(dates[0]).date()
        d1 = datetime.fromisoformat(dates[-1]).date()
        days = max(1, (d1 - d0).days + 1)
        years = days / 365.25
        date_range = f"{d0}..{d1}"
    except Exception:
        years = max(1.0, len(dates) / 365.25)
        date_range = None

    # Reject incomplete or malformed series rather than converting missing rain to drought.
    series = {"precipitation": pr, "maximum_temperature": tmax, "minimum_temperature": tmin, "mean_temperature": tmean}
    coverage = {key: sum(1 for x in values if _valid(x)) / len(dates) for key, values in series.items()}
    try:
        ordered_dates = [datetime.fromisoformat(item).date() for item in dates]
        contiguous = all((right - left).days == 1 for left, right in zip(ordered_dates, ordered_dates[1:]))
    except (ValueError, TypeError):
        contiguous = False
    if not contiguous or any(len(values) != len(dates) for values in series.values()) or min(coverage.values()) < 0.95:
        return {"error": "insufficient climate coverage", "coverage": coverage, "period_days": len(dates)}
    if any(_valid(x) and x < 0 for x in pr):
        return {"error": "invalid precipitation values", "coverage": coverage}
    total_rain = sum(x for x in pr if _valid(x))
    annual_rain_mm_est = total_rain / years

    # Heat / cold thresholds
    hot35_per_year = _count_ge(tmax, 35.0) / years
    hot40_per_year = _count_ge(tmax, 40.0) / years
    hot30_per_year = _count_ge(tmax, 30.0) / years
    frost0_per_year = _count_le(tmin, 0.0) / years

    # Dry spell
    max_dry_spell_days = _max_consecutive_dry_days(pr, dry_threshold_mm=1.0)

    return {
        "date_range": date_range,
        "period_days": len(dates),
        "coverage": coverage,

        "annual_rainfall_mm_est": round(annual_rain_mm_est, 1),
        "max_dry_spell_days_est": int(max_dry_spell_days),

        "hot_days_ge_30_per_year_est": int(round(hot30_per_year)),
        "hot_days_ge_35_per_year_est": int(round(hot35_per_year)),
        "hot_days_ge_40_per_year_est": int(round(hot40_per_year)),
        "frost_days_le_0_per_year_est": int(round(frost0_per_year)),

        "avg_tmax_c": round(_safe_mean(tmax), 2) if _safe_mean(tmax) is not None else None,
        "avg_tmin_c": round(_safe_mean(tmin), 2) if _safe_mean(tmin) is not None else None,
        "avg_tmean_c": round(_safe_mean(tmean), 2) if _safe_mean(tmean) is not None else None,
    }

def drought_risk_from_rainfall(annual_rain_mm_est: Optional[float], irrigation_available: Optional[bool]) -> dict:
    """
    Returns drought risk with vs without irrigation. Conservative Tunisia buckets.
    """
    if annual_rain_mm_est is None:
        return {"with_irrigation": "UNKNOWN", "without_irrigation": "UNKNOWN"}

    if annual_rain_mm_est < 200:
        base = "HIGH"
    elif annual_rain_mm_est < 350:
        base = "MEDIUM"
    elif annual_rain_mm_est < 550:
        base = "LOW"
    else:
        base = "LOW"

    with_irrig = base
    if irrigation_available is True:
        if base == "HIGH":
            with_irrig = "MEDIUM"
        elif base == "MEDIUM":
            with_irrig = "LOW"

    return {"with_irrigation": with_irrig, "without_irrigation": base}

def aridity_class(annual_rain_mm_est: Optional[float]) -> str:
    if annual_rain_mm_est is None:
        return "UNKNOWN"
    if annual_rain_mm_est < 100:
        return "EXTREME_ARID"
    if annual_rain_mm_est < 250:
        return "ARID"
    if annual_rain_mm_est < 450:
        return "SEMI_ARID"
    return "SUB_HUMID_PLUS"
