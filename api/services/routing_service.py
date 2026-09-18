"""
Routing Service
================
Provides driving route information between two coordinate pairs.
Uses OSRM (Open Source Routing Machine) — free, no API key required.

The service is behind an abstraction so the routing provider can be
swapped by changing only this file.

Returns:
    - distance_miles: Total driving distance
    - duration_minutes: Estimated driving duration
    - geometry: GeoJSON LineString of the route
"""
import os
import requests
from django.core.cache import cache


class RoutingService:

    BASE_URL = "http://router.project-osrm.org/route/v1/driving"
    CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', 86400))

    @classmethod
    def get_route(cls, start_coords: tuple, finish_coords: tuple) -> dict:
        """
        Get driving route between two coordinate pairs.

        Args:
            start_coords: (latitude, longitude) of start location
            finish_coords: (latitude, longitude) of finish location

        Returns:
            dict with keys: distance_miles, duration_minutes, geometry

        Raises:
            Exception: If the routing API fails or returns no route.
        """
        cache_key = (
            f"route_{start_coords[0]:.6f}_{start_coords[1]:.6f}_"
            f"{finish_coords[0]:.6f}_{finish_coords[1]:.6f}"
        )
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        # OSRM expects lon,lat order
        url = (
            f"{cls.BASE_URL}/"
            f"{start_coords[1]},{start_coords[0]};"
            f"{finish_coords[1]},{finish_coords[0]}"
        )
        params = {
            "overview": "full",
            "geometries": "geojson",
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        if data.get("code") != "Ok":
            raise Exception(
                f"Routing failed: {data.get('message', 'Unknown error')}"
            )

        route = data["routes"][0]

        # OSRM returns distance in meters and duration in seconds
        distance_miles = round(route["distance"] * 0.000621371, 2)
        duration_minutes = round(route["duration"] / 60.0, 2)

        result = {
            "distance_miles": distance_miles,
            "duration_minutes": duration_minutes,
            "geometry": route["geometry"],  # GeoJSON LineString
        }

        cache.set(cache_key, result, timeout=cls.CACHE_TIMEOUT)
        return result
