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

            # 3. Get driving route (cached, single API call)
            route_data = RoutingService.get_route(start_coords, finish_coords)
            total_distance_miles = route_data['distance_miles']

            # 4. Load stations and filter spatially
            all_stations = StationRepository.get_all_stations()
            radius = float(os.environ.get('ROUTE_STATION_RADIUS_MILES', 10.0))
            candidate_stations = SpatialService.filter_and_project_stations(
                route_data['geometry'], all_stations, radius_miles=radius,
            )

            # Convert route_ratio to absolute distance and prepare for optimizer
            for s in candidate_stations:
                s['distance_from_start'] = round(
                    s['route_ratio'] * total_distance_miles, 2
                )
                s['price'] = s['price_per_gallon']

            # 5. Run fuel optimization
            max_range = float(os.environ.get('VEHICLE_MAX_RANGE_MILES', 500))
            mpg = float(os.environ.get('VEHICLE_MPG', 10))

            optimization_result = OptimizationService.calculate_optimal_stops(
                route_distance_miles=total_distance_miles,
                stations=candidate_stations,
                max_range_miles=max_range,
                mpg=mpg,
            )

            # 6. Build response
            # Clean up fuel stops for response (remove internal keys)
            clean_stops = []
            for stop in optimization_result['fuel_stops']:
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

            total_consumed = round(total_distance_miles / mpg, 2)

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
                    "distance_miles": total_distance_miles,
                    "duration_minutes": route_data['duration_minutes'],
                    "geometry": route_data['geometry'],
                },
                "vehicle": {
                    "max_range_miles": max_range,
                    "mpg": mpg,
                },
                "fuel": {
                    "total_consumed_gallons": total_consumed,
                    "total_purchased_gallons": optimization_result['total_purchased_gallons'],
                    "total_cost": optimization_result['total_cost'],
                },
                "fuel_stops": clean_stops,
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Route calculation failed")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
