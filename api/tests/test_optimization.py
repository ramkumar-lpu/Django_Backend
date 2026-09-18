"""
Tests for the fuel stop optimization algorithm.

Each test uses explicitly defined station positions and prices.
No external APIs or live services are needed.
"""
from django.test import TestCase
from api.services.optimization_service import OptimizationService


class TestDestinationWithinInitialRange(TestCase):
    """When the destination is reachable on the initial full tank, no stops needed."""

    def test_short_trip_no_stops(self):
        stations = [
            {"station_id": "A", "distance_from_start": 100, "price": 3.00},
        ]
        result = OptimizationService.calculate_optimal_stops(400, stations)
        self.assertEqual(len(result['fuel_stops']), 0)
        self.assertEqual(result['total_cost'], 0.0)
        self.assertEqual(result['total_purchased_gallons'], 0.0)

    def test_exactly_500_miles(self):
        stations = [
            {"station_id": "A", "distance_from_start": 250, "price": 3.00},
        ]
        result = OptimizationService.calculate_optimal_stops(500, stations)
        self.assertEqual(len(result['fuel_stops']), 0)
        self.assertEqual(result['total_cost'], 0.0)

    def test_zero_distance(self):
        result = OptimizationService.calculate_optimal_stops(0, [])
        self.assertEqual(len(result['fuel_stops']), 0)
        self.assertEqual(result['total_cost'], 0.0)


class TestOneFuelStop(TestCase):
    """Routes requiring exactly one fuel stop."""

    def test_single_stop_buy_minimum(self):
        """700 mile trip. Full tank covers 500. Must stop and buy enough to finish."""
        stations = [
            {"station_id": "A", "distance_from_start": 300, "price": 3.00},
        ]
        # At start: 50 gallons, can go 500 miles.
        # Station A at 300: arrive with 50 - 30 = 20 gallons.
        # Need to reach 700: remaining 400 miles = 40 gallons needed.
        # Shortfall = 40 - 20 = 20 gallons. Cost = 20 * 3.00 = $60.
        result = OptimizationService.calculate_optimal_stops(700, stations)
        self.assertEqual(len(result['fuel_stops']), 1)
        self.assertEqual(result['fuel_stops'][0]['station_id'], "A")
        self.assertEqual(result['fuel_stops'][0]['gallons_purchased'], 20.0)
        self.assertEqual(result['fuel_stops'][0]['cost'], 60.0)
        self.assertEqual(result['total_cost'], 60.0)


class TestCheaperFutureStation(TestCase):
    """Algorithm should prefer buying at cheaper stations ahead."""

    def test_skip_expensive_for_cheap(self):
        """Two stations: expensive near, cheap far. Should buy at cheaper one."""
        stations = [
            {"station_id": "EXP", "distance_from_start": 100, "price": 5.00},
            {"station_id": "CHEAP", "distance_from_start": 400, "price": 2.00},
        ]
        # Route: 800 miles.
        # At start (price=inf): first cheaper ahead is EXP (5.00 < inf).
        # Buy just enough to reach EXP: 100mi / 10mpg = 10gal needed, have 50. No purchase.
        # Drive to EXP. Arrive with 50-10=40 gal.
        # At EXP (price=5.00): cheaper ahead is CHEAP (2.00 < 5.00).
        # Need to reach CHEAP: 300mi = 30 gal. Have 40. No purchase needed.
        # Drive to CHEAP. Arrive with 40-30=10 gal.
        # At CHEAP (price=2.00): finish is cheaper (0.0 < 2.00). But can we reach?
        # Dist to finish: 400mi = 40 gal. Have 10. Shortfall = 30 gal.
        # Buy 30 gal at $2.00 = $60.
        result = OptimizationService.calculate_optimal_stops(800, stations)
        self.assertEqual(result['total_cost'], 60.0)
        self.assertEqual(len(result['fuel_stops']), 1)
        self.assertEqual(result['fuel_stops'][0]['station_id'], "CHEAP")
        self.assertEqual(result['fuel_stops'][0]['gallons_purchased'], 30.0)

    def test_buy_minimum_at_expensive_when_cheap_is_close(self):
        """Expensive station first, cheap station reachable. Buy min at expensive."""
        stations = [
            {"station_id": "EXP", "distance_from_start": 450, "price": 5.00},
            {"station_id": "CHEAP", "distance_from_start": 600, "price": 2.00},
        ]
        # Route: 900 miles. Start with 50 gal (500 mi range).
        # At start: first cheaper is EXP (5 < inf). Need 45 gal to reach EXP, have 50. No buy.
        # Drive to EXP. Arrive with 50-45=5 gal.
        # At EXP (5.00): CHEAP is cheaper (2.00 < 5.00). Need 150mi=15 gal. Have 5. Shortfall=10.
        # Buy 10 gal at $5.00 = $50.
        # Drive to CHEAP. Arrive with 15-15=0 gal.
        # At CHEAP (2.00): finish at 900, 300mi away = 30 gal. Have 0. Buy 30 at $2 = $60.
        # Total: $110.
        result = OptimizationService.calculate_optimal_stops(900, stations)
        self.assertEqual(result['total_cost'], 110.0)
        self.assertEqual(len(result['fuel_stops']), 2)
        self.assertEqual(result['fuel_stops'][0]['station_id'], "EXP")
        self.assertEqual(result['fuel_stops'][0]['gallons_purchased'], 10.0)
        self.assertEqual(result['fuel_stops'][1]['station_id'], "CHEAP")
        self.assertEqual(result['fuel_stops'][1]['gallons_purchased'], 30.0)


class TestMultipleFuelStops(TestCase):
    """Routes requiring multiple fuel stops."""

    def test_three_stops(self):
        stations = [
            {"station_id": "A", "distance_from_start": 400, "price": 2.50},
            {"station_id": "B", "distance_from_start": 800, "price": 2.00},
            {"station_id": "C", "distance_from_start": 1200, "price": 3.00},
        ]
        # Route: 1500 miles.
        # START: 50 gal. Cheaper ahead = A (2.50 < inf). Need 40 gal, have 50. No buy. Drive.
        # A (400mi, 2.50): arrive 10 gal. Cheaper ahead = B (2.00 < 2.50).
        #   Need 400mi=40 gal. Have 10. Shortfall=30. Buy 30 @ $2.50 = $75. Fuel=40.
        #   Drive to B. Arrive with 0 gal.
        # B (800mi, 2.00): No cheaper ahead in range (C=3.00 > 2.00). FINISH is 0.0 but 700mi away > 500.
        #   Fill up: buy 50 gal @ $2.00 = $100. Fuel=50.
        #   Cheapest reachable = C. Drive to C (400mi=40 gal). Arrive with 10 gal.
        # C (1200mi, 3.00): FINISH cheaper (0.0 < 3.00). 300mi = 30 gal. Have 10. Shortfall=20.
        #   Buy 20 @ $3.00 = $60. Drive to finish.
        # Total: 75 + 100 + 60 = $235.
        result = OptimizationService.calculate_optimal_stops(1500, stations)
        self.assertEqual(result['total_cost'], 235.0)
        self.assertEqual(len(result['fuel_stops']), 3)
        self.assertEqual(result['fuel_stops'][0]['station_id'], "A")
        self.assertEqual(result['fuel_stops'][0]['gallons_purchased'], 30.0)
        self.assertEqual(result['fuel_stops'][1]['station_id'], "B")
        self.assertEqual(result['fuel_stops'][1]['gallons_purchased'], 50.0)
        self.assertEqual(result['fuel_stops'][2]['station_id'], "C")
        self.assertEqual(result['fuel_stops'][2]['gallons_purchased'], 20.0)


class TestUnreachableDestination(TestCase):
    """When there's a gap > 500 miles with no station."""

    def test_no_stations_long_route(self):
        with self.assertRaises(Exception) as ctx:
            OptimizationService.calculate_optimal_stops(700, [])
        self.assertIn("cannot be reached", str(ctx.exception))

    def test_gap_too_large(self):
        stations = [
            {"station_id": "A", "distance_from_start": 200, "price": 3.00},
            # Gap of 600 miles to next station — unreachable
            {"station_id": "B", "distance_from_start": 800, "price": 3.00},
        ]
        with self.assertRaises(Exception):
            OptimizationService.calculate_optimal_stops(1000, stations)


class TestStationExactlyAtMaxRange(TestCase):
    """Station exactly 500 miles from start or another station."""

    def test_station_at_500(self):
        stations = [
            {"station_id": "A", "distance_from_start": 500, "price": 3.00},
        ]
        # Route: 700 mi. Arrive at A with 0 gal. Need 200mi = 20 gal. Buy 20 @ $3 = $60.
        result = OptimizationService.calculate_optimal_stops(700, stations)
        self.assertEqual(len(result['fuel_stops']), 1)
        self.assertEqual(result['fuel_stops'][0]['gallons_purchased'], 20.0)
        self.assertEqual(result['total_cost'], 60.0)


class TestFinalPartialFuel(TestCase):
    """The last stop should only buy enough fuel to reach the destination."""

    def test_partial_fill_at_last_stop(self):
        stations = [
            {"station_id": "A", "distance_from_start": 450, "price": 3.00},
        ]
        # Route: 510 mi. At start: 50 gal, range 500.
        # Can't reach finish directly. First cheaper = A (3.00 < inf). Need 45 gal, have 50. No buy.
        # Drive to A. Arrive with 5 gal.
        # At A: finish is 60mi away = 6 gal. Have 5. Shortfall=1.
        # Buy 1 gal @ $3.00 = $3.
        result = OptimizationService.calculate_optimal_stops(510, stations)
        self.assertEqual(len(result['fuel_stops']), 1)
        self.assertEqual(result['fuel_stops'][0]['gallons_purchased'], 1.0)
        self.assertEqual(result['total_cost'], 3.0)


class TestDuplicateStationHandling(TestCase):
    """Stations with identical IDs but different prices — optimizer uses what it receives."""

    def test_same_location_different_prices(self):
        # The deduplication happens in fuel_service; optimizer just uses the list it gets
        stations = [
            {"station_id": "A", "distance_from_start": 300, "price": 2.00},
        ]
        result = OptimizationService.calculate_optimal_stops(700, stations)
        self.assertEqual(result['fuel_stops'][0]['price'], 2.00)


class TestIdenticalPrices(TestCase):
    """All stations have the same price."""

    def test_all_same_price(self):
        stations = [
            {"station_id": "A", "distance_from_start": 400, "price": 3.00},
            {"station_id": "B", "distance_from_start": 800, "price": 3.00},
        ]
        # Route: 1100. No station is cheaper than another.
        # START: A is cheaper (3 < inf). Need 40 gal, have 50. No buy. Drive.
        # A (400): arrive 10 gal. B is same price (3.00 <= 3.00), so "cheaper ahead" = B.
        #   Need 400mi = 40 gal. Have 10. Shortfall=30. Buy 30 @ $3 = $90. Drive.
        # B (800): arrive 0 gal. Finish cheaper (0 < 3). 300mi = 30 gal. Buy 30 @ $3 = $90.
        # Total: $180.
        result = OptimizationService.calculate_optimal_stops(1100, stations)
        self.assertEqual(result['total_cost'], 180.0)


class TestNoStationsShortRoute(TestCase):
    """Route under 500 miles with no stations available."""

    def test_reachable_without_stations(self):
        result = OptimizationService.calculate_optimal_stops(200, [])
        self.assertEqual(len(result['fuel_stops']), 0)
        self.assertEqual(result['total_cost'], 0.0)
