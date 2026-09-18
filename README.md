# Fuel Route Optimizer API

A Django REST API that calculates the optimal driving route between two US locations and identifies cost-effective fuel stops along the way.

## Project Overview

Given a start and finish location within the USA, the API:
1. Geocodes both locations to coordinates
2. Calculates the driving route using OSRM (Open Source Routing Machine)
3. Identifies fuel stations near the route from the assessment dataset
4. Applies a cost-minimizing fuel stop optimization algorithm
5. Returns the route, fuel stops, and total cost breakdown

## Architecture

```
POST /api/route/
    ↓
Input Validation (DRF Serializer)
    ↓
Geocode Start/Finish (Nominatim, cached)
    ↓
Get Driving Route (OSRM, cached, 1 API call)
    ↓
Load Preprocessed Stations (in-memory)
    ↓
Spatial Filtering (Shapely bounding box + distance)
    ↓
Project Stations onto Route (distance along route)
    ↓
Fuel Optimization (Cheapest-Forward Greedy)
    ↓
JSON Response
```

### Key Design Decisions

- **Routing**: OSRM — free, no API key, returns GeoJSON geometry
- **Geocoding**: Nominatim (start/finish only, cached) — free, no API key
- **Spatial**: Shapely for route geometry operations
- **Station Data**: Preprocessed offline, loaded once at startup
- **Caching**: Django LocMemCache (no Redis dependency)
- **Optimization**: Cheapest-Forward greedy algorithm (provably optimal for fixed-route single-vehicle)

## Setup

```bash
git clone <repository-url>
cd Backend_Django

python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Key variables:
| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `True` | Django debug mode |
| `SECRET_KEY` | — | Django secret key |
| `GEOCODING_API_KEY` | — | Optional: OpenRouteService API key |
| `ROUTE_STATION_RADIUS_MILES` | `10` | Max distance (miles) from route to consider a station |
| `VEHICLE_MAX_RANGE_MILES` | `500` | Vehicle max range on full tank |
| `VEHICLE_MPG` | `10` | Vehicle fuel efficiency |

## Fuel Data Preprocessing

The assessment CSV (`data/fuel-prices-for-be-assessment.csv`) must be preprocessed to geocode station locations:

```bash
python scripts/preprocess_fuel_data.py
```

This script:
1. Cleans and validates the CSV (8,151 raw rows)
2. Filters to US-only stations (7,531 rows)
3. Deduplicates by OPIS Truckstop ID, keeping the lowest price (6,626 stations)
4. Geocodes unique city+state combinations via Nominatim
5. Saves results to `data/fuel_stations.json` and `data/fuel_station_coordinates.json`

**Resume support**: The script uses `data/geocoding_cache.json` to persist results. If interrupted, re-running continues from where it stopped.

## Running the Server

```bash
python manage.py migrate
python manage.py runserver
```

## API Usage

### POST `/api/route/`

**Request:**
```json
{
  "start": "New York, NY",
  "finish": "Los Angeles, CA"
}
```

**cURL:**
```bash
curl -X POST http://localhost:8000/api/route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "New York, NY", "finish": "Los Angeles, CA"}'
```

**Response:**
```json
{
  "start": {
    "input": "New York, NY",
    "latitude": 40.7128,
    "longitude": -74.006
  },
  "finish": {
    "input": "Los Angeles, CA",
    "latitude": 34.0522,
    "longitude": -118.2437
  },
  "route": {
    "distance_miles": 2789.42,
    "duration_minutes": 2510.0,
    "geometry": { "type": "LineString", "coordinates": [...] }
  },
  "vehicle": {
    "max_range_miles": 500,
    "mpg": 10
  },
  "fuel": {
    "total_consumed_gallons": 278.94,
    "total_purchased_gallons": 228.94,
    "total_cost": 824.67
  },
  "fuel_stops": [
    {
      "station_id": "12345",
      "truckstop_name": "Example Station",
      "city": "Example City",
      "state": "PA",
      "latitude": 40.0,
      "longitude": -79.0,
      "distance_from_start_miles": 350.5,
      "distance_from_route_miles": 1.2,
      "price_per_gallon": 3.19,
      "gallons_purchased": 35.05,
      "cost": 111.81
    }
  ]
}
```

### Error Responses

```json
{"error": "Unable to geocode location: InvalidPlace"}
{"error": "Start and finish locations cannot be identical."}
{"error": "Destination cannot be reached with the available fuel stations."}
```

## Fuel Optimization Algorithm

The optimizer uses a **Cheapest-Forward Greedy** strategy:

1. **Vehicle starts with a full tank** (50 gallons = 500 miles range)
2. At each position, look ahead at all reachable stations within range
3. **If a cheaper-or-equal station exists ahead**: buy only enough fuel to reach it
4. **If no cheaper station ahead**: fill the tank completely and drive to the cheapest reachable station
5. **Finish is always "free"** (price = 0), so if the destination is reachable, drive directly

This is a mathematically verified cost-minimizing greedy strategy for the fixed-route continuous-refueling model because:
- We never buy expensive fuel when cheap fuel is reachable ahead
- We fill up completely only when the current station is the cheapest option within range
- We buy the minimum amount at expensive stations

**The initial full tank is NOT counted as a purchase.**

## Performance

- **Preprocessing**: Station data is geocoded offline (one-time), not during API requests
- **Caching**: Geocoding and routing results are cached in memory (24h TTL)
- **Spatial filtering**: Bounding box pre-filter + Shapely distance check — O(stations) with constant factor optimization
- **Minimal API calls**: 1 routing call + 2 geocoding calls per request (all cached on repeat)
- **No CSV parsing at runtime**: Preprocessed JSON is loaded once into memory

## Testing

```bash
python manage.py test api.tests -v 2
```

Test coverage:
- **14 optimization tests**: within-range, one stop, cheaper-future, multiple stops, unreachable, max-range, partial fill, duplicates, identical prices
- **9 API tests**: validation errors, geocoding failure, routing failure, successful response, method not allowed

All tests use mocked external services — no live API calls.

## Project Structure

```
Backend_Django/
├── manage.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── data/
│   ├── fuel-prices-for-be-assessment.csv   # Assessment source data
│   ├── fuel_stations.json                   # Preprocessed station list
│   └── fuel_station_coordinates.json        # OPIS ID → coordinates map
│
├── scripts/
│   ├── preprocess_fuel_data.py              # ETL + geocoding pipeline
│   └── inspect_dataset.py                   # CSV analysis utility
│
├── Backend_Django/                          # Django project settings
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
└── api/                                     # Django app
    ├── urls.py
    ├── views.py                             # RouteView (orchestrator)
    ├── serializers.py                       # Request validation
    │
    ├── services/
    │   ├── routing_service.py               # OSRM integration
    │   ├── geocoding_service.py             # Nominatim integration
    │   ├── fuel_service.py                  # StationRepository
    │   ├── spatial_service.py               # Route-station matching
    │   └── optimization_service.py          # Fuel stop optimizer
    │
    └── tests/
        ├── test_optimization.py             # Algorithm tests
        └── test_api.py                      # Endpoint tests
```
