"""
Spatial Service
================
Filters fuel stations to those near the driving route and computes each
station's projected position along the route.

Uses Shapely for geometric operations:
- Bounding box pre-filter (fast)
- Precise distance-to-line check
- Point projection onto line for distance-along-route
"""
import os
from shapely.geometry import shape, Point


# Approximate conversion: 1 degree latitude ≈ 69 miles
# For longitude it varies by latitude, but 69 is a reasonable average for the US
MILES_PER_DEGREE = 69.0


class SpatialService:

    @staticmethod
    def filter_and_project_stations(
        route_geojson: dict,
        stations: list,
        radius_miles: float = None,
    ) -> list:
        """
        Filter stations to those near the route and compute distance along route.

        Args:
            route_geojson: GeoJSON dict with type 'LineString' and coordinates
            stations: list of station dicts with 'latitude' and 'longitude'
            radius_miles: max distance from route to consider a station

        Returns:
            list of candidate station dicts, each augmented with:
                - 'route_ratio': fractional position along route [0, 1]
                - 'distance_from_route_miles': perpendicular distance to route
        """
        if radius_miles is None:
            radius_miles = float(os.environ.get('ROUTE_STATION_RADIUS_MILES', 10.0))

        route_line = shape(route_geojson)
        route_length_deg = route_line.length

        if route_length_deg == 0:
            return []

        # Convert radius to approximate degrees for bounding box
        deg_radius = radius_miles / MILES_PER_DEGREE

        # Bounding box pre-filter
        minx, miny, maxx, maxy = route_line.bounds
        bbox_minx = minx - deg_radius
        bbox_miny = miny - deg_radius
        bbox_maxx = maxx + deg_radius
        bbox_maxy = maxy + deg_radius

        candidates = []
        for station in stations:
            lat = station['latitude']
            lon = station['longitude']

            # Quick bounding box check
            if not (bbox_miny <= lat <= bbox_maxy and bbox_minx <= lon <= bbox_maxx):
                continue

            pt = Point(lon, lat)

            # Distance to route line in degrees, converted to approximate miles
            dist_deg = route_line.distance(pt)
            dist_miles = dist_deg * MILES_PER_DEGREE

            if dist_miles <= radius_miles:
                # Project point onto route to get position along route
                projected_dist_deg = route_line.project(pt)
                ratio = projected_dist_deg / route_length_deg

                s_copy = dict(station)
                s_copy['route_ratio'] = ratio
                s_copy['distance_from_route_miles'] = round(dist_miles, 2)
                candidates.append(s_copy)

        return candidates
