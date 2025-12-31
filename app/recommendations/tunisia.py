# app/recommendations/tunisia.py
from typing import Any, Optional

FIT_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

def _rank_sort_key(rec: dict) -> tuple:
    return (-FIT_ORDER.get(rec.get("fit", "LOW"), 1), rec.get("rank_hint", 999), -(rec.get("score", 0)))

def _cap_fit(fit: str) -> str:
    return fit if fit in ("HIGH", "MEDIUM", "LOW") else "LOW"

def _water_salinity_risk(water_ec: Optional[float]) -> str:
    if water_ec is None:
        return "UNKNOWN"
    if water_ec < 2.0:
        return "LOW"
    if water_ec < 4.0:
        return "MODERATE"
    return "HIGH"

def build_recommendations_tn(indicators: dict, constraints: dict, soil: dict | None = None) -> list[dict]:
    annual_rain = indicators.get("annual_rainfall_mm_est")
    aridity = indicators.get("aridity_class", "UNKNOWN")
    dry_spell = indicators.get("max_dry_spell_days_est")

    salinity = indicators.get("salinity_risk")  # from soil EC
    irrigation = constraints.get("irrigation_available")

    water_ec = constraints.get("water_ec_dS_m")
    water_rel = constraints.get("water_source_reliability")  # LOW/MEDIUM/HIGH/None
    water_sal_risk = _water_salinity_risk(water_ec)

    lat = (constraints.get("_lat_for_region") or None)  # optional internal
    is_south_hint = isinstance(lat, (int, float)) and lat < 32.0

    recs: list[dict[str, Any]] = []

    def add(activity: str, fit: str, score: int, why: list[str], requirements: list[str],
            warnings: list[str] | None = None, evidence: list[str] | None = None,
            mitigations: list[str] | None = None, rank_hint: int = 50):
        recs.append({
            "activity": activity,
            "fit": _cap_fit(fit),
            "score": int(score),
            "why": why,
            "requirements": requirements,
            "warnings": warnings or [],
            "evidence": evidence or [],
            "mitigations": mitigations or [],
            "rank_hint": rank_hint,
        })

    # Shared evidence helpers
    ev = []
    if isinstance(annual_rain, (int, float)):
        ev.append(f"annual_rainfall_mm_est={annual_rain}")
    if dry_spell is not None:
        ev.append(f"max_dry_spell_days_est={dry_spell}")
    if salinity:
        ev.append(f"soil_salinity_risk={salinity}")
    if irrigation is not None:
        ev.append(f"irrigation_available={irrigation}")
    if water_ec is not None:
        ev.append(f"water_ec_dS_m={water_ec} ({water_sal_risk})")
    if water_rel:
        ev.append(f"water_source_reliability={water_rel}")
    if aridity:
        ev.append(f"aridity_class={aridity}")

    # ---- RULES ----

    # 0) Always recommend water test if irrigation is used but water_ec missing
    if irrigation is True and water_ec is None:
        add(
            "Irrigation water quality test",
            "HIGH",
            95,
            ["Water quality (salinity) is a critical constraint in dry Tunisia zones"],
            ["Measure water EC (dS/m) and SAR if possible"],
            ["Without water test, crop selection may be wrong"],
            evidence=ev,
            mitigations=["Lab test for water", "Adjust crop choices based on water EC"],
            rank_hint=1
        )

    # 1) Extreme aridity gate (south/desert)
    extreme_arid = (aridity == "EXTREME_ARID")
    arid = (aridity in ("EXTREME_ARID", "ARID"))

    # 2) Date palm / oasis option (south hint OR extreme arid + irrigation)
    if (is_south_hint or extreme_arid) and irrigation is True:
        fit = "HIGH"
        score = 86
        why = ["Oasis-style agriculture is often more realistic in extreme arid south when irrigation exists"]
        req = ["Confirm water availability and salinity", "Plan irrigation scheduling"]
        warn = []
        if water_sal_risk == "HIGH":
            fit = "MEDIUM"
            score -= 10
            warn.append("High water salinity may limit productivity; select tolerant varieties and manage salts")
        add(
            "Date palm (oasis agriculture)",
            fit, score, why, req, warn,
            evidence=ev + ["south_hint=True" if is_south_hint else "south_hint=False"],
            mitigations=["Water EC/SAR test", "Salt management plan"],
            rank_hint=10
        )

    # 3) Olive (robust but not magically HIGH in extreme desert)
    olive_fit = "HIGH"
    olive_score = 82
    olive_why = ["Drought-tolerant and widely suitable in Tunisia"]
    olive_req = ["Prefer drip irrigation during establishment (especially in arid zones)"]
    olive_warn = []
    if extreme_arid:
        # In extreme desert: depends heavily on stable irrigation
        olive_fit = "MEDIUM" if irrigation is True else "LOW"
        olive_score -= 15
        olive_warn.append("Extreme aridity: success depends heavily on stable irrigation and soil/water management")
    if salinity == "HIGH":
        olive_fit = "MEDIUM" if olive_fit == "HIGH" else olive_fit
        olive_score -= 10
        olive_warn.append("High soil salinity may reduce yields; choose tolerant varieties and manage salts")
    if water_sal_risk == "HIGH":
        olive_fit = "MEDIUM" if olive_fit == "HIGH" else olive_fit
        olive_score -= 8
        olive_warn.append("High irrigation water salinity increases salinization risk over time")

    add(
        "Olive orchard",
        olive_fit, olive_score,
        olive_why, olive_req,
        olive_warn,
        evidence=ev,
        mitigations=["Drip irrigation", "Organic matter improvement", "Salinity monitoring"],
        rank_hint=20
    )

    # 4) Rainfed priority when irrigation is FALSE
    if irrigation is False:
        # In arid areas, rainfed options are limited
        barley_fit = "LOW" if arid else "MEDIUM"
        add(
            "Barley (rainfed)",
            barley_fit,
            55 if barley_fit == "MEDIUM" else 35,
            ["More resilient under low rainfall than many field crops"],
            ["Planting window depends on rainfall seasonality", "Use adapted varieties"],
            ["Very low rainfall makes rainfed yields unstable"] if arid else [],
            evidence=ev,
            mitigations=["Drought-tolerant varieties", "Soil moisture conservation (mulch/cover)"],
            rank_hint=30
        )
        add(
            "Rangeland / livestock support (natural)",
            "MEDIUM" if arid else "HIGH",
            60,
            ["In very dry zones, extensive systems can be more realistic than crop-intensive plans"],
            ["Plan grazing management", "Protect vegetation cover"],
            evidence=ev,
            mitigations=["Rotational grazing", "Water point planning"],
            rank_hint=31
        )

    # 5) Orchards that require more support (almond/fig/pomegranate)
    # Conservative downgrade in extreme arid unless water reliability is HIGH
    def orchard_fit_base():
        if extreme_arid:
            if irrigation is True and water_rel == "HIGH":
                return "MEDIUM"
            return "LOW"
        if arid:
            return "MEDIUM" if irrigation is True else "LOW"
        return "HIGH" if irrigation is True else "MEDIUM"

    base_fit = orchard_fit_base()

    # Fig
    fig_fit = base_fit
    fig_score = 70 if fig_fit == "MEDIUM" else (55 if fig_fit == "LOW" else 80)
    fig_warn = []
    if water_sal_risk == "HIGH":
        fig_fit = "LOW" if fig_fit != "LOW" else fig_fit
        fig_score -= 10
        fig_warn.append("High water salinity may reduce productivity")
    add(
        "Fig orchard",
        fig_fit, fig_score,
        ["Relatively drought-tolerant; better with reliable irrigation in arid zones"],
        ["Prefer drip irrigation", "Monitor salinity if present"],
        fig_warn,
        evidence=ev,
        mitigations=["Water test", "Salinity management", "Mulching"],
        rank_hint=40
    )

    # Almond
    almond_fit = "LOW" if base_fit == "LOW" else "MEDIUM"
    almond_score = 62 if almond_fit == "MEDIUM" else 45
    almond_warn = []
    if salinity in ("MODERATE", "HIGH"):
        almond_warn.append("Salinity can affect yields; verify tolerance and manage salts")
    add(
        "Almond orchard",
        almond_fit, almond_score,
        ["Can be suitable with supplemental irrigation; sensitive to extreme aridity without stable water"],
        ["Check soil depth", "Drip irrigation recommended"],
        almond_warn,
        evidence=ev,
        mitigations=["Reliable irrigation", "Soil/water salinity monitoring"],
        rank_hint=41
    )

    # Pomegranate
    pomo_fit = "LOW" if base_fit == "LOW" else "MEDIUM"
    pomo_score = 60 if pomo_fit == "MEDIUM" else 42
    pomo_warn = ["Needs stable irrigation scheduling in very dry zones"] if arid else []
    add(
        "Pomegranate orchard",
        pomo_fit, pomo_score,
        ["Potentially suitable with good irrigation management"],
        ["Stable irrigation schedule", "Water quality check recommended"],
        pomo_warn,
        evidence=ev,
        mitigations=["Water test", "Scheduling", "Mulch"],
        rank_hint=42
    )

    # 6) Vegetables / greenhouse — strongly dependent on water quality + reliability
    if irrigation is True:
        if water_sal_risk == "HIGH" or salinity == "HIGH":
            add(
                "Vegetables (caution)",
                "LOW",
                28,
                ["High salinity can severely reduce vegetable yields"],
                ["Consider salinity treatment/management before vegetables", "Choose salt-tolerant crops/varieties"],
                ["Do not invest before confirming water quality and reliability"],
                evidence=ev,
                mitigations=["Water EC/SAR test", "Drip irrigation", "Leaching if feasible"],
                rank_hint=60
            )
        else:
            veg_fit = "MEDIUM"
            veg_score = 66
            veg_warn = []
            if extreme_arid and water_rel != "HIGH":
                veg_fit = "LOW"
                veg_score -= 20
                veg_warn.append("Extreme aridity: vegetables require highly reliable irrigation")
            add(
                "Open-field vegetables (tomato/pepper/onion)",
                veg_fit,
                veg_score,
                ["Irrigation enables higher-value crops"],
                ["Prefer drip irrigation and fertigation", "Market plan recommended"],
                veg_warn,
                evidence=ev,
                mitigations=["Water test", "Scheduling", "Salinity monitoring"],
                rank_hint=61
            )

            gh_fit = "MEDIUM"
            gh_score = 62
            gh_warn = ["Higher CAPEX; needs stable water supply and market plan"]
            if water_rel == "LOW":
                gh_fit = "LOW"
                gh_score -= 18
                gh_warn.append("Low water reliability: greenhouse risk increases")
            add(
                "Greenhouse vegetables (tomato/pepper)",
                gh_fit,
                gh_score,
                ["Controlled environment can improve productivity if water is reliable"],
                ["Higher CAPEX", "Strong water management", "Market plan required"],
                gh_warn,
                evidence=ev,
                mitigations=["Ensure reliability", "Water test", "Irrigation automation"],
                rank_hint=62
            )

    # 7) Salinity management plan if soil or water salinity is moderate/high
    if salinity in ("MODERATE", "HIGH") or water_sal_risk in ("MODERATE", "HIGH"):
        lvl = "HIGH" if (salinity == "HIGH" or water_sal_risk == "HIGH") else "MEDIUM"
        add(
            "Salinity management plan",
            "HIGH",
            90 if lvl == "HIGH" else 75,
            ["Salinity is a limiting factor; management improves crop options"],
            ["Confirm with lab tests (soil EC, water EC, SAR if possible)", "Improve organic matter"],
            ["Some crops remain sensitive even after improvements"] if lvl == "HIGH" else [],
            evidence=ev,
            mitigations=["Leaching strategy (if feasible)", "Gypsum when appropriate", "Monitor EC over time"],
            rank_hint=15
        )

    # Sort + ranks
    recs.sort(key=_rank_sort_key)
    for i, r in enumerate(recs, start=1):
        r["rank"] = i
        r.pop("score", None)
        r.pop("rank_hint", None)

    return recs
