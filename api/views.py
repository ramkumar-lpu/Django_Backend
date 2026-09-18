"""
Route View
===========
POST /api/route/

Orchestrates the request pipeline:
1. Validate input
2. Geocode start/finish locations (cached)
3. Get driving route from OSRM (cached)
4. Filter fuel stations near the route (spatial)
5. Optimize fuel stops (greedy algorithm)
6. Return JSON response
"""
import logging
import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import RouteRequestSerializer
from .services.geocoding_service import GeocodingService
from .services.routing_service import RoutingService
from .services.fuel_service import StationRepository
from .services.spatial_service import SpatialService
from .services.optimization_service import OptimizationService

logger = logging.getLogger(__name__)


class RouteView(APIView):
    """
    Calculate optimal fuel stops for a driving route between two US locations.
    """

    def post(self, request, *args, **kwargs):
        # 1. Validate input
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid request parameters", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_str = serializer.validated_data['start']
        finish_str = serializer.validated_data['finish']

        try:
            # 2. Geocode start/finish (cached)
            start_coords = GeocodingService.geocode(start_str)
            finish_coords = GeocodingService.geocode(finish_str)

            # 3. Get driving routes (cached, single API call with alternatives)
            candidate_routes = RoutingService.get_routes(start_coords, finish_coords)

            # 4 & 5. Evaluate all routes for fuel optimization
            from .services.route_evaluator_service import RouteEvaluatorService
            evaluation = RouteEvaluatorService.evaluate_candidates(candidate_routes)
            best_route = evaluation["selected_route"]

            # 6. Build response
            # Clean up fuel stops for response (remove internal keys)
            clean_stops = []
            for stop in best_route['fuel_stops']:
                clean_stops.append({
                    "station_id": stop.get('station_id'),
                    "truckstop_name": stop.get('truckstop_name', ''),
                    "city": stop.get('city', ''),
                    "state": stop.get('state', ''),
                    "latitude": stop.get('latitude'),
                    "longitude": stop.get('longitude'),
                    "distance_from_start_miles": stop.get('distance_from_start'),
                    "distance_from_route_miles": stop.get('distance_from_route_miles'),
                    "price_per_gallon": stop.get('price_per_gallon', stop.get('price')),
                    "gallons_purchased": stop.get('gallons_purchased'),
                    "cost": stop.get('cost'),
                })

            max_range = float(os.environ.get('VEHICLE_MAX_RANGE_MILES', 500.0))
            mpg = float(os.environ.get('VEHICLE_MPG', 10.0))

            response_data = {
                "start": {
                    "input": start_str,
                    "latitude": start_coords[0],
                    "longitude": start_coords[1],
                },
                "finish": {
                    "input": finish_str,
                    "latitude": finish_coords[0],
                    "longitude": finish_coords[1],
                },
                "route": {
                    "distance_miles": best_route['distance_miles'],
                    "duration_minutes": best_route['duration_minutes'],
                    "geometry": best_route['geometry'],
                },
                "vehicle": {
                    "max_range_miles": max_range,
                    "mpg": mpg,
                },
                "fuel": {
                    "total_consumed_gallons": best_route['fuel_consumed_gallons'],
                    "total_purchased_gallons": best_route['fuel_purchased_gallons'],
                    "total_cost": best_route['fuel_cost'],
                },
                "fuel_stops": clean_stops,
                "route_comparison": evaluation['route_comparison']
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Route calculation failed")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
