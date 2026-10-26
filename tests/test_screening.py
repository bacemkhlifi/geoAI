import unittest
from datetime import date, timedelta
from app.features.climate import summarize_10y_daily, _max_consecutive_dry_days
from app.recommendations.tunisia import build_recommendations_tn

class ClimateTests(unittest.TestCase):
    def daily(self):
        return {"time": [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(366)],
                "precipitation_sum": [1.0]*366, "temperature_2m_max": [25]*366,
                "temperature_2m_min": [10]*366, "temperature_2m_mean": [18]*366}

    def test_valid_year(self):
        result = summarize_10y_daily(self.daily())
        self.assertEqual(result["annual_rainfall_mm_est"], 365.2)
        self.assertEqual(result["coverage"]["precipitation"], 1)
        self.assertEqual(result["frost_days_le_0_per_year_est"], 0)

    def test_missing_rain_is_not_zero(self):
        daily = self.daily()
        daily["precipitation_sum"] = [None]*366
        result = summarize_10y_daily(daily)
        self.assertIn("error", result)
        self.assertNotIn("annual_rainfall_mm_est", result)

    def test_nonfinite_and_misaligned_series(self):
        for values in ([float('nan')]*366, [1]*10):
            daily = self.daily(); daily["precipitation_sum"] = values
            self.assertIn("error", summarize_10y_daily(daily))

    def test_missing_calendar_day(self):
        daily = self.daily(); daily["time"][10] = daily["time"][9]
        self.assertIn("error", summarize_10y_daily(daily))

    def test_dry_spell_breaks_at_missing_day(self):
        self.assertEqual(_max_consecutive_dry_days([0, 0, None, 0]), 2)

class RecommendationTests(unittest.TestCase):
    def indicators(self):
        return {"annual_rainfall_mm_est": 80, "aridity_class": "EXTREME_ARID", "salinity_risk": "UNKNOWN"}

    def test_no_irrigation_no_date_palm(self):
        results = build_recommendations_tn(self.indicators(), {"irrigation_available": False, "_lat_for_region": 33})
        self.assertFalse(any(r.get("crop_key") == "date_palm" for r in results))

    def test_diagnostics_are_not_crops(self):
        results = build_recommendations_tn(self.indicators(), {"irrigation_available": True, "_lat_for_region": 33})
        quality = next(r for r in results if r["activity"] == "Irrigation water quality test")
        self.assertEqual(quality["category"], "management")
        self.assertIsNone(quality["crop_key"])
        self.assertTrue(all(r["confidence"] == "LOW" for r in results))

    def test_soil_ph_is_used(self):
        results = build_recommendations_tn(self.indicators(), {"irrigation_available": True}, {"ph": 4})
        olive = next(r for r in results if r.get("crop_key") == "olive")
        self.assertEqual(olive["status"], "not_suitable")

    def test_irrigation_low_reliability_caps_fit(self):
        results = build_recommendations_tn(self.indicators(), {"irrigation_available": True, "water_source_reliability": "LOW"})
        self.assertTrue(all(r["fit"] == "LOW" for r in results if r["crop_key"]))

if __name__ == '__main__':
    unittest.main()
