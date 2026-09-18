"""
Route Evaluator Service
=======================
Evaluates multiple route candidates returned by OSRM to find the most cost-effective.
"""
import os
from .fuel_service import StationRepository
from .spatial_service import SpatialService
from .optimization_service import OptimizationService

class RouteEvaluatorService:
    @classmethod
    def evaluate_candidates(cls, candidate_routes: list[dict]) -> dict:
        """
        Evaluate candidate routes and select the best one based on fuel cost.

        Args:
            candidate_routes: list of route dicts (with geometry, distance_miles, duration_minutes)

        Returns:
            dict containing:
                - best_route: the selected route evaluation
                - comparisons: list of all evaluated routes
        """
        all_stations = StationRepository.get_all_stations()
        radius = float(os.environ.get('ROUTE_STATION_RADIUS_MILES', 10.0))
        max_range = float(os.environ.get('VEHICLE_MAX_RANGE_MILES', 500.0))
        mpg = float(os.environ.get('VEHICLE_MPG', 10.0))

        evaluated_routes = []

        for idx, route in enumerate(candidate_routes):
            total_distance_miles = route['distance_miles']
            duration_minutes = route['duration_minutes']
            total_consumed = round(total_distance_miles / mpg, 2)

            candidate_info = {
                "route_index": idx,
                "distance_miles": total_distance_miles,
                "duration_minutes": duration_minutes,
                "fuel_consumed_gallons": total_consumed,
                "geometry": route['geometry'],
                "feasible": False,
                "fuel_cost": float('inf'),
                "fuel_purchased_gallons": 0.0,
                "stop_count": 0,
                "fuel_stops": [],
                "selected": False
            }

            try:
                candidate_stations = SpatialService.filter_and_project_stations(
                    route['geometry'], all_stations, radius_miles=radius,
                )

                for s in candidate_stations:
                    s['distance_from_start'] = round(
                        s['route_ratio'] * total_distance_miles, 2
                    )
                    s['price'] = s['price_per_gallon']

                optimization_result = OptimizationService.calculate_optimal_stops(
                    route_distance_miles=total_distance_miles,
                    stations=candidate_stations,
                    max_range_miles=max_range,
                    mpg=mpg,
                )

                candidate_info["feasible"] = True
                candidate_info["fuel_cost"] = optimization_result['total_cost']
                candidate_info["fuel_purchased_gallons"] = optimization_result['total_purchased_gallons']
                candidate_info["fuel_stops"] = optimization_result['fuel_stops']
                candidate_info["stop_count"] = len(optimization_result['fuel_stops'])

            except Exception:
                # If optimization fails (e.g., Destination cannot be reached), leave feasible=False
                pass

            evaluated_routes.append(candidate_info)

        feasible_routes = [r for r in evaluated_routes if r['feasible']]
        if not feasible_routes:
            raise Exception("Destination cannot be reached with the available fuel stations on any route.")

        # Tie-breakers: 1. Cost (min), 2. Distance (min), 3. Duration (min)
        feasible_routes.sort(key=lambda r: (r['fuel_cost'], r['distance_miles'], r['duration_minutes']))
        best_route = feasible_routes[0]

        for r in evaluated_routes:
            r['selected'] = (r['route_index'] == best_route['route_index'])

        return {
            "selected_route": best_route,
            "route_comparison": evaluated_routes
        }
