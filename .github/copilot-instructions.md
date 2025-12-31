# AI Coding Guidelines for Tunisia GeoAI MVP

## Architecture Overview
This is a FastAPI-based microservice for agricultural site analysis in Tunisia. Core flow: receive site coordinates/constraints → fetch climate data from Open-Meteo → compute indicators/risks → generate recommendations via rule-based engine.

**Key Components:**
- `app/main.py`: FastAPI routes and request models (Pydantic)
- `app/connectors/`: Async HTTP clients for external APIs (Open-Meteo, SoilGrids)
- `app/features/`: Data processing logic (climate summaries, risk calculations)
- `app/recommendations/`: Country-specific rule engines (e.g., `tunisia.py` with hardcoded rules)

**Data Flow Pattern:**
```python
# Example from main.py /v1/site-analysis
raw_data = await fetch_daily_history(lat, lon, start_date, end_date)
indicators = summarize_10y_daily(raw_data["daily"])
risks = build_risks(indicators, constraints, soil)
recs = build_recommendations_tn(indicators, constraints, soil)
```

## Coding Patterns
- **Async HTTP**: Use `httpx.AsyncClient` for external API calls with timeouts (30-40s)
- **Error Handling**: Raise `HTTPException` for API failures; return structured errors in responses
- **Models**: Pydantic `BaseModel` with `Field` constraints; use `model_dump()` for serialization
- **Indicators/Risks**: Dict-based with keys like `annual_rainfall_mm_est`, `drought_risk`; include evidence lists for transparency
- **Recommendations Engine**: In `recommendations/*.py`, use `add(activity, fit, score, why, requirements, ...)` to build ranked lists. Fit levels: HIGH/MEDIUM/LOW. Sort by `_rank_sort_key` (fit priority, rank_hint, -score)
- **Validation**: Simple bounding box checks (e.g., Tunisia coords); expand for other countries
- **Confidence**: "HIGH"/"MEDIUM"/"LOW" based on data completeness (irrigation, water EC)

## Developer Workflows
- **Run Locally**: `uvicorn app.main:app --reload` (port 8000 default)
- **API Docs**: Visit `/docs` for Swagger UI
- **Testing**: No automated tests yet; manually test endpoints with sample Tunisia coords (e.g., lat=36.8, lon=10.2)
- **Dependencies**: `pip install -r requirements.txt`; uses virtual env (`.venv/`)

## Project-Specific Conventions
- **File Naming**: Snake_case for modules/functions; PascalCase for Pydantic models
- **Internal Helpers**: Prefix with `_` (e.g., `_safe_mean`, `_date_10y_window_end_today`)
- **Evidence Transparency**: Every risk/recommendation includes `evidence` list with key metrics (e.g., `"annual_rainfall_mm_est=350"`)
- **Tunisia Focus**: Hardcoded for TN; extend to other countries by adding `recommendations/{country}.py` with similar `build_recommendations_{code}` function
- **MVP Scope**: Point-based analysis; `radius_m` stored for future AOI expansion
- **Extensibility**: `rules/` directory reserved for future rule engine (currently empty)

## Examples
- **Adding New Indicator**: In `features/climate.py`, add to `summarize_10y_daily` return dict, then reference in `main.py` indicators
- **New Recommendation Rule**: In `recommendations/tunisia.py`, use `add()` with conditional logic based on indicators/constraints
- **New Connector**: Follow `open_meteo.py` pattern: async function returning dict, handle HTTP errors

Avoid over-engineering; keep MVP simple and deterministic.</content>
<parameter name="filePath">c:\IT_Consulting\OILEDOLIVE\geoai-mvp\.github\copilot-instructions.md