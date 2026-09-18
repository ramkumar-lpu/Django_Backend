"""
Geocoding Service
==================
Geocodes start/finish location strings into (latitude, longitude) coordinates.
Results are cached in Django's cache framework.

Providers:
- Primary: Nominatim (OpenStreetMap) — free, no API key needed
- Optional: OpenRouteService — if GEOCODING_API_KEY is set in environment
"""
import os
import requests
from django.core.cache import cache


class GeocodingService:

    CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', 86400 * 30))

    @classmethod
    def geocode(cls, location_string: str) -> tuple:
        """
        Geocode a location string to (latitude, longitude).

        Args:
            location_string: A human-readable location, e.g. "New York, NY"

        Returns:
            Tuple of (latitude, longitude)

        Raises:
            Exception: If the location cannot be geocoded.
        """
        cache_key = f"geocode_{location_string.strip().lower()}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        api_key = os.environ.get('GEOCODING_API_KEY')

        if api_key:
            lat, lon = cls._geocode_ors(location_string, api_key)
        else:
            lat, lon = cls._geocode_nominatim(location_string)

        if lat is None or lon is None:
            raise Exception(f"Unable to geocode location: {location_string}")

        result = (lat, lon)
        cache.set(cache_key, result, timeout=cls.CACHE_TIMEOUT)
        return result

    @classmethod
    def _geocode_ors(cls, location_string: str, api_key: str) -> tuple:
        """Geocode using OpenRouteService (requires free API key)."""
        url = "https://api.openrouteservice.org/geocode/search"
        headers = {"Authorization": api_key}
        params = {"text": location_string, "boundary.country": "US", "size": 1}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("features"):
                    coords = data["features"][0]["geometry"]["coordinates"]
                    return coords[1], coords[0]  # lat, lon
        except Exception:
            pass
        return None, None

    @classmethod
    def _geocode_nominatim(cls, location_string: str) -> tuple:
        """Geocode using Nominatim (free, no API key, 1 req/sec rate limit)."""
        url = "https://nominatim.openstreetmap.org/search"
        headers = {'User-Agent': 'Mozilla/5.0 (FuelRouteAssessment/1.0)'}
        params = {
            'q': f"{location_string}, USA",
            'format': 'json',
            'limit': 1,
            'countrycodes': 'us',
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return float(data[0]['lat']), float(data[0]['lon'])
        except Exception:
            pass

        return None, None
