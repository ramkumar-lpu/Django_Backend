"""
Fuel Station Data Preprocessing Pipeline
=========================================
Cleans the assessment CSV, deduplicates by OPIS Truckstop ID (keeping lowest price),
filters to US-only stations, and geocodes each station's city+state to obtain coordinates.

Geocoding Strategy:
- Geocodes unique CITY+STATE combinations (not individual addresses) to minimize API calls.
- Uses the Photon geocoder (OpenStreetMap-based, free, no API key required).
- Implements persistent cache so the script is fully resumable.
- Falls back gracefully for failed geocodes.

Usage:
    python scripts/preprocess_fuel_data.py
"""

import csv
import json
import os
import sys
import time
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
CSV_PATH = os.path.join(DATA_DIR, 'fuel-prices-for-be-assessment.csv')
CACHE_PATH = os.path.join(DATA_DIR, 'geocoding_cache.json')
FAILED_PATH = os.path.join(DATA_DIR, 'geocoding_failed.json')
COORDS_OUTPUT_PATH = os.path.join(DATA_DIR, 'fuel_station_coordinates.json')
STATIONS_OUTPUT_PATH = os.path.join(DATA_DIR, 'fuel_stations.json')

US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
}

# Full state names for geocoding queries
STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia'
}

GEOCODE_DELAY = 1.5  # seconds between requests (respect rate limits)


def log(msg):
    print(msg, flush=True)


def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def validate_us_coordinates(lat, lon):
    """Validate coordinates are plausibly within the USA."""
    if lat is None or lon is None:
        return False
    # Contiguous US + Alaska + Hawaii rough bounds
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return False
    # Contiguous US
    if 24.0 <= lat <= 50.0 and -125.0 <= lon <= -66.0:
        return True
    # Alaska
    if 51.0 <= lat <= 72.0 and -175.0 <= lon <= -129.0:
        return True
    # Hawaii
    if 18.0 <= lat <= 23.0 and -161.0 <= lon <= -154.0:
        return True
    return False


GEOCODE_DELAY = 0.2  # 5 requests per second (OpenMeteo limit is 600/min)

def geocode_openmeteo(city, state, max_retries=3):
    """Geocode using OpenMeteo (free, no API key, 10k/day limit)."""
    import requests
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {'name': city, 'count': 10, 'format': 'json'}
    state_full = STATE_NAMES.get(state, state)
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for r in data.get('results', []):
                    if r.get('country_code') == 'US' and r.get('admin1', '').lower() == state_full.lower():
                        return float(r['latitude']), float(r['longitude'])
                return None, None
            elif resp.status_code == 429:
                wait = 10 * (attempt + 1)
                log(f"  Rate limit hit (attempt {attempt+1}/{max_retries}), sleeping {wait}s...")
                time.sleep(wait)
            else:
                log(f"  OpenMeteo returned HTTP {resp.status_code} for '{city}, {state}'")
                return None, None
        except Exception as e:
            log(f"  Geocoding error for '{city}, {state}': {e}")
            time.sleep(2)
    return None, None


def clean_and_deduplicate(df):
    """Clean, filter US, validate prices, deduplicate by OPIS ID keeping lowest price."""
    df.columns = [col.strip() for col in df.columns]

    # Clean string fields
    for col in ['Truckstop Name', 'Address', 'City', 'State']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Filter US
    df['State_clean'] = df['State'].str.upper()
    us_df = df[df['State_clean'].isin(US_STATES)].copy()

    # Validate prices
    us_df['numeric_price'] = pd.to_numeric(us_df['Retail Price'], errors='coerce')
    us_df = us_df.dropna(subset=['numeric_price', 'OPIS Truckstop ID']).copy()

    # Remove zero/negative prices
    us_df = us_df[us_df['numeric_price'] > 0].copy()

    # Deduplicate: sort by price ascending, keep first (lowest) per OPIS ID
    us_df = us_df.sort_values(
        by=['numeric_price', 'OPIS Truckstop ID'],
        ascending=[True, True]
    )
    dedup_df = us_df.drop_duplicates(subset=['OPIS Truckstop ID'], keep='first').copy()

    return dedup_df


def geocode_city_states(city_state_pairs, cache, failed):
    """Geocode unique city+state pairs, using cache for resume support."""
    total = len(city_state_pairs)
    geocoded_count = 0
    failed_count = 0
    api_calls = 0

    for i, (city, state) in enumerate(city_state_pairs):
        cache_key = f"{city}, {state}"

        if cache_key in cache:
            geocoded_count += 1
            continue

        if cache_key in failed:
            failed_count += 1
            continue

        lat, lon = geocode_openmeteo(city, state)
        api_calls += 1
        time.sleep(GEOCODE_DELAY)

        if lat is not None and validate_us_coordinates(lat, lon):
            cache[cache_key] = {'lat': lat, 'lon': lon}
            geocoded_count += 1
        else:
            failed[cache_key] = f"Not found or invalid: city='{city}', state='{state}'"
            failed_count += 1

        # Save caches periodically
        if api_calls % 50 == 0:
            save_json(CACHE_PATH, cache)
            save_json(FAILED_PATH, failed)
            log(f"  Progress: {i+1}/{total} city+state pairs processed "
                f"(cached: {geocoded_count}, failed: {failed_count}, API calls: {api_calls})")

    # Final save
    save_json(CACHE_PATH, cache)
    save_json(FAILED_PATH, failed)

    return geocoded_count, failed_count, api_calls


def main():
    log("=" * 60)
    log("FUEL STATION DATA PREPROCESSING PIPELINE")
    log("=" * 60)

    if not os.path.exists(CSV_PATH):
        log(f"ERROR: CSV not found at {CSV_PATH}")
        sys.exit(1)

    # Step 1: Load and clean
    log("\n[Step 1] Loading CSV...")
    df = pd.read_csv(CSV_PATH)
    raw_rows = len(df)
    log(f"  Raw rows: {raw_rows}")

    log("\n[Step 2] Cleaning, filtering US, deduplicating...")
    dedup_df = clean_and_deduplicate(df)
    unique_stations = len(dedup_df)
    log(f"  Unique US stations (lowest price per OPIS ID): {unique_stations}")

    # Step 3: Get unique city+state combos for geocoding
    log("\n[Step 3] Identifying unique city+state combinations...")
    city_state_pairs = list(
        dedup_df[['City', 'State_clean']].drop_duplicates().itertuples(index=False, name=None)
    )
    log(f"  Unique city+state pairs to geocode: {len(city_state_pairs)}")

    # Step 4: Geocode
    log("\n[Step 4] Geocoding city+state pairs (resumable with cache)...")
    cache = load_json(CACHE_PATH)
    failed = load_json(FAILED_PATH)

    # Count how many are already cached
    already_cached = sum(1 for c, s in city_state_pairs if f"{c}, {s}" in cache)
    already_failed = sum(1 for c, s in city_state_pairs if f"{c}, {s}" in failed)
    remaining = len(city_state_pairs) - already_cached - already_failed
    log(f"  Already cached: {already_cached}")
    log(f"  Already failed: {already_failed}")
    log(f"  Remaining to geocode: {remaining}")

    if remaining > 0:
        est_time = remaining * GEOCODE_DELAY
        log(f"  Estimated time: {est_time/60:.1f} minutes ({remaining} API calls)")

    geocoded_count, failed_count, api_calls = geocode_city_states(
        city_state_pairs, cache, failed
    )
    log(f"  Geocoding complete: {geocoded_count} success, {failed_count} failed, {api_calls} API calls made")

    # Step 5: Build output
    log("\n[Step 5] Building station coordinate map and final station list...")
    coords_map = {}  # OPIS ID -> {lat, lon}
    stations_list = []

    for _, row in dedup_df.iterrows():
        opis_id = str(int(row['OPIS Truckstop ID']))
        city = str(row['City']).strip()
        state = str(row['State_clean']).strip()
        cache_key = f"{city}, {state}"

        if cache_key in cache:
            lat = cache[cache_key]['lat']
            lon = cache[cache_key]['lon']
            coords_map[opis_id] = {'lat': lat, 'lon': lon}
            stations_list.append({
                'opis_truckstop_id': int(row['OPIS Truckstop ID']),
                'truckstop_name': str(row['Truckstop Name']).strip(),
                'address': str(row['Address']).strip(),
                'city': city,
                'state': state,
                'retail_price': round(float(row['numeric_price']), 6),
                'latitude': lat,
                'longitude': lon
            })

    save_json(COORDS_OUTPUT_PATH, coords_map)
    save_json(STATIONS_OUTPUT_PATH, stations_list)

    geocoded_stations = len(stations_list)
    failed_stations = unique_stations - geocoded_stations
    success_rate = (geocoded_stations / unique_stations * 100) if unique_stations > 0 else 0

    log("\n" + "=" * 60)
    log("PREPROCESSING COMPLETE")
    log("=" * 60)
    log(f"  Raw rows:                {raw_rows}")
    log(f"  Unique US stations:      {unique_stations}")
    log(f"  Successfully geocoded:   {geocoded_stations}")
    log(f"  Failed geocoding:        {failed_stations}")
    log(f"  Success rate:            {success_rate:.1f}%")
    log(f"  Coordinate map:          {COORDS_OUTPUT_PATH}")
    log(f"  Station list:            {STATIONS_OUTPUT_PATH}")
    log("=" * 60)


if __name__ == "__main__":
    main()
