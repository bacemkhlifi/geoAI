import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app, _date_10y_window_end_today

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_schema_and_health(self):
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.assertEqual(self.client.post('/v1/site-analysis', json={"site": {"lat": 100, "lon": 10}}).status_code, 422)

    def test_country_and_bounds_rejected_without_provider_call(self):
        self.assertEqual(self.client.post('/v1/site-analysis', json={"site": {"lat": 50, "lon": 10}}).status_code, 400)

    def test_complete_year_window(self):
        start, end = _date_10y_window_end_today()
        self.assertTrue(start.endswith('-01-01')); self.assertTrue(end.endswith('-12-31'))
        self.assertEqual(int(end[:4]) - int(start[:4]), 9)

    def test_missing_climate_is_provider_failure(self):
        with patch('app.main.fetch_daily_history', new=AsyncMock(return_value={"daily": {}})):
            result = self.client.post('/v1/site-analysis', json={"site": {"lat": 35, "lon": 10}})
        self.assertEqual(result.status_code, 502)

    def test_contract_preserves_constraints_and_adds_crop_ids(self):
        start, end = _date_10y_window_end_today()
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        days = (last-first).days+1
        daily = {"time": [(first+timedelta(days=i)).isoformat() for i in range(days)],
                 "precipitation_sum": [1]*days, "temperature_2m_max": [25]*days,
                 "temperature_2m_min": [10]*days, "temperature_2m_mean": [18]*days}
        body = {"site": {"lat": 35, "lon": 10}, "constraints": {"irrigation_available": False, "water_ec_dS_m": 2}, "soil_test": {"ph": 4, "ec_dS_m": 1}}
        with patch('app.main.fetch_daily_history', new=AsyncMock(return_value={"daily": daily})):
            response = self.client.post('/v1/site-analysis', json=body)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertFalse(result['constraints']['irrigation_available'])
        self.assertEqual(result['confidence']['overall'], 'LOW')
        self.assertEqual(result['data_sources'][0]['kind'], 'modeled/reanalysis-derived')
        olive = next(r for r in result['recommendations'] if r['crop_key'] == 'olive')
        self.assertEqual(olive['status'], 'not_suitable')
        self.assertIn('rule_score', olive)

if __name__ == '__main__':
    unittest.main()
