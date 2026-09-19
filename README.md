# Fuel Route Optimizer

## Overview
A Django REST API and Vanilla JavaScript frontend that calculates the optimal driving route between two US locations and identifies cost-effective fuel stops along the way.

## Problem
Identifying the optimal route across the US is not just a function of the shortest distance. Fuel prices vary significantly by location and state. The objective is to calculate a route and refueling strategy that minimizes the total fuel purchase cost while traveling from a start location to a destination.

## Key Features
- **Multi-Route Optimization:** Evaluates multiple driving alternatives from OSRM to determine the most economically viable path.
- **Deterministic Refueling:** Calculates exact stops using a cheapest-forward greedy strategy without random variables.
- **Interactive Map:** Leaflet/MapLibre UI to visualize candidate routes, selected routes, and dynamic fuel-stop markers.
- **Offline Dataset Integration:** Seamlessly integrates real assessment fuel data and city/state geographic approximations.

## Architecture
The application flow executes sequentially:
```text
Request
  ↓
Geocode start/end
  ↓
OSRM route alternatives
  ↓
RouteEvaluatorService
  ↓
Route-specific station filtering
  ↓
Deterministic fuel optimization
  ↓
Route cost comparison
  ↓
Selected route
  ↓
API response + map
```

## How the Optimization Works
For every candidate route:
1. Identify stations near that route using Shapely spatial filtering.
2. Optimize fuel purchases along the corridor.
3. Calculate fuel consumed, fuel purchased, and total fuel purchase cost.
4. Determine route feasibility based on vehicle constraints.

## Multi-Route Cost-Aware Selection
The system extends the conventional shortest-route-plus-refueling workflow by evaluating multiple routing alternatives together with fuel procurement economics. Each candidate route receives deterministic fuel-stop optimization, after which feasible candidates are compared by total fuel purchase cost, with distance and duration used as tie-breakers.

Route selection objective:
- **PRIMARY:** minimum total fuel purchase cost
- **TIE-BREAKER 1:** minimum distance
- **TIE-BREAKER 2:** minimum duration

## Fuel Model
The algorithm adheres to the following fixed vehicle assumptions:
- Maximum range: 500 miles
- Fuel economy: 10 MPG
- Tank capacity: 50 gallons
- Vehicle starts with a full tank
- Initial fuel is treated as free

**Important Distinction:**
- Fuel consumed = route distance / 10 MPG
- Fuel purchased depends on the starting fuel level and optimized refueling decisions
- Therefore, **fuel consumed and fuel purchased are not necessarily equal**. 

The fuel optimization uses a deterministic cheapest-forward refueling strategy for the candidate route to identify where and how much fuel to purchase.

## Dataset and Preprocessing
- **Source:** Real fuel-price assessment dataset (`fuel-prices-for-be-assessment.csv`)
- **Preprocessing:** Duplicate OPIS station IDs are handled (lowest price retained).
- **Coordinates:** Station coordinates are generated through offline city/state geocoding. These are **APPROXIMATE city/state coordinates**, not exact truck-stop coordinates.
- **Runtime:** Processed runtime JSON station files are loaded directly into memory to prevent live geocoding blocks.

## API
**POST `/api/route/`**

**Example Request:**
```json
{
  "start": "Dallas, TX",
  "finish": "Los Angeles, CA"
}
```

**Example Response:**
The actual response contains the complete route geometry and fuel-stop details.
```json
{
  "route": {
    "distance_miles": 1437.57,
    "duration_minutes": 1335.2,
    "geometry": { "type": "LineString", "coordinates": [...] }
  },
  "fuel": {
    "total_cost": 260.41,
    "total_purchased_gallons": 93.76,
    "total_consumed_gallons": 143.76
  },
  "fuel_stops": [
    {
      "station_id": "123",
      "truckstop_name": "Example Stop",
      "city": "Example City",
      "state": "TX",
      "price_per_gallon": 2.75,
      "gallons_purchased": 45.0,
      "cost": 123.75,
      "latitude": 32.0,
      "longitude": -96.0
    }
  ],
  "route_comparison": [
    {
      "route_index": 0,
      "distance_miles": 1437.57,
      "fuel_cost": 260.41,
      "feasible": true,
      "selected": true
    },
    {
      "route_index": 1,
      "distance_miles": 1435.03,
      "fuel_cost": 275.82,
      "feasible": true,
      "selected": false
    }
  ]
}
```

## Frontend
The frontend is a vanilla HTML/JS single-page application served through Django. It includes:
- Start and destination inputs
- Calculate route action button (with loading/error states)
- Route summary
- Interactive map
- Selected route and alternative route visualizations
- Route comparison panel
- Optimized fuel-stop markers

**Marker Semantics:**
- **Green `S`:** Start location
- **Blue `E`:** Destination location
- **Numbered Red Markers:** Fuel stops in travel order
- Popups display station information, price, purchased quantity, and cost.

## Map
The interactive map utilizes a Leaflet/MapLibre-based implementation relying on OpenFreeMap as the basemap. Appropriate attribution is provided in the UI. The OSRM route geometry is rendered dynamically.

## Project Structure
```text
Backend_Django/
│   manage.py
│   requirements.txt
│   Dockerfile
│   docker-compose.yml
│   README.md
│
├── api/
│   ├── services/
│   │   ├── fuel_service.py
│   │   ├── geocoding_service.py
│   │   ├── optimization_service.py
│   │   ├── route_evaluator_service.py
│   │   ├── routing_service.py
│   │   └── spatial_service.py
│   ├── tests/
│   │   ├── test_api.py
│   │   ├── test_optimization.py
│   │   └── test_route_evaluator.py
│   ├── serializers.py
│   ├── urls.py
│   └── views.py
│
├── frontend/
│   └── index.html
│
├── data/
│   ├── fuel-prices-for-be-assessment.csv
│   ├── fuel_stations.json
│   └── fuel_station_coordinates.json
│
└── scripts/
    ├── inspect_dataset.py
    └── preprocess_fuel_data.py
```

## Setup

**1. Clone the repository**
```bash
git clone <repository-url>
cd Backend_Django
```

**2. Virtual Environment (Windows-friendly)**
```bash
python -m venv venv
venv\Scripts\activate
```

**3. Install Dependencies**
```bash
pip install -r requirements.txt
```

**4. Run Server**
```bash
python manage.py migrate
python manage.py runserver
```

## Docker
A complete Dockerized environment is provided.
```bash
docker compose build
docker compose up -d
```
The Django application will be available at `http://localhost:8000`.

## Testing
The current test suite consists of **27 tests**. All 27 tests pass, covering:
- API behavior
- Route evaluation
- Multi-route handling
- Fuel-cost selection
- Tie-breakers
- Infeasible candidates
- Existing fuel constraints
- Regression behavior

To run tests natively:
```bash
python manage.py test api.tests
```
To run tests inside Docker:
```bash
docker exec fuel_route_api python manage.py test api.tests
```

## Example Result
A verified demonstration using **Dallas, TX → Los Angeles, CA**:

- **Route 0:** 1437.57 miles, $260.41 fuel cost, 4 fuel stops *(selected)*
- **Route 1:** 1435.03 miles, $275.82 fuel cost *(not selected)*

**Observation:** Route 1 is slightly shorter, but Route 0 has a lower optimized fuel procurement cost, so the system selects Route 0 according to the configured economic objective. *(These values are from a real validation run and are NOT hard-coded).*

## Design Decisions

**Why not just use the shortest route?**
Fuel prices vary by location, so minimizing distance alone does not necessarily minimize fuel procurement cost. The application therefore evaluates available route alternatives and optimizes refueling independently for each candidate. 

**Performance:**
Design decisions like preprocessing station coordinates offline, loading processed station data into memory, utilizing Shapely for spatial filtering, caching Geocoding requests, and requesting route alternatives in a single OSRM call ensure efficient and responsive execution in the normal flow.

## Error Handling
The application explicitly handles:
- Invalid or missing input coordinates
- Geocoding and routing failures
- No route returned by OSRM
- Infeasible routes (gaps greater than 500 miles between stations)
- Scenarios where all candidate routes are infeasible
- Graceful single-route OSRM fallback

## Limitations
- OSRM determines the candidate road routes. The number and diversity of alternatives depends entirely on OSRM.
- Station coordinates are city/state geocoding approximations rather than exact truck-stop coordinates.
- The fuel optimization operates strictly on the available station dataset and candidate route corridor.
- OpenFreeMap is used as a public map tile/style service and does not provide an SLA.
- Fuel prices are those contained in the supplied assessment dataset and may not represent current live prices.

## Future Improvements
- Implement exact coordinate parsing from an address API to replace city/state approximations.
- Add live fuel price integration.
- Persist routing/cost logs in a database for analytical tracking.
