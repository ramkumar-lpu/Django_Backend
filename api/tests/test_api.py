"""
API endpoint tests for POST /api/route/.

All external services (geocoding, routing, station loading) are mocked.
No live API calls are made.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


# A minimal OSRM-like route geometry for mocking
MOCK_ROUTE_GEOMETRY = {
    "type": "LineString",
    "coordinates": [
        [-74.006, 40.713],
        [-75.0, 40.5],
        [-76.0, 40.3],
        [-77.037, 38.907],
    ],
}

MOCK_ROUTE = {
    "distance_miles": 226.0,
    "duration_minutes": 230.0,
    "geometry": MOCK_ROUTE_GEOMETRY,
}

MOCK_STATIONS = [
    {
        "station_id": "100",
        "truckstop_name": "Test Station",
        "address": "123 Highway",
        "city": "Baltimore",
        "state": "MD",
        "price_per_gallon": 3.50,
        "latitude": 39.29,
        "longitude": -76.61,
    },
]


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class RouteAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/route/"

    def test_missing_start(self):
        response = self.client.post(self.url, {"finish": "Los Angeles, CA"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_missing_finish(self):
        response = self.client.post(self.url, {"start": "New York, NY"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_same_start_and_finish(self):
        response = self.client.post(
            self.url,
            {"start": "New York, NY", "finish": "New York, NY"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_body(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("api.views.StationRepository.get_all_stations", return_value=MOCK_STATIONS)
    @patch("api.views.RoutingService.get_routes", return_value=[MOCK_ROUTE])
    @patch("api.views.GeocodingService.geocode")
    def test_successful_short_route(self, mock_geocode, mock_route, mock_stations):
        """A short route within initial tank range — should return 0 fuel stops."""
        mock_geocode.side_effect = [
            (40.7128, -74.0060),  # New York
            (38.9072, -77.0369),  # Washington DC
        ]
        response = self.client.post(
            self.url,
            {"start": "New York, NY", "finish": "Washington, DC"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check response structure
        self.assertIn("start", data)
        self.assertIn("finish", data)
        self.assertIn("route", data)
        self.assertIn("vehicle", data)
        self.assertIn("fuel", data)
        self.assertIn("fuel_stops", data)

        # Short route — no stops needed
        self.assertEqual(len(data["fuel_stops"]), 0)
        self.assertEqual(data["fuel"]["total_cost"], 0.0)

        # Check route info
        self.assertEqual(data["route"]["distance_miles"], 226.0)
        self.assertIn("geometry", data["route"])

    @patch("api.views.GeocodingService.geocode")
    def test_geocoding_failure(self, mock_geocode):
        mock_geocode.side_effect = Exception("Unable to geocode location: InvalidPlace")
        response = self.client.post(
            self.url,
            {"start": "InvalidPlace", "finish": "Washington, DC"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    @patch("api.views.StationRepository.get_all_stations", return_value=[])
    @patch("api.views.RoutingService.get_routes")
    @patch("api.views.GeocodingService.geocode")
    def test_long_route_no_stations(self, mock_geocode, mock_route, mock_stations):
        """Long route with no fuel stations available — should fail gracefully."""
        mock_geocode.side_effect = [
            (40.7128, -74.0060),
            (34.0522, -118.2437),
        ]
        mock_route.return_value = [
            {
                "distance_miles": 2800.0,
                "duration_minutes": 2500.0,
                "geometry": MOCK_ROUTE_GEOMETRY,
            }
        ]
        response = self.client.post(
            self.url,
            {"start": "New York, NY", "finish": "Los Angeles, CA"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    @patch("api.views.RoutingService.get_routes")
    @patch("api.views.GeocodingService.geocode")
    def test_routing_api_failure(self, mock_geocode, mock_route):
        mock_geocode.side_effect = [
            (40.7128, -74.0060),
            (38.9072, -77.0369),
        ]
        mock_route.side_effect = Exception("Routing service unavailable")
        response = self.client.post(
            self.url,
            {"start": "New York, NY", "finish": "Washington, DC"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_get_method_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
