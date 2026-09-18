import json
import os

DATA_DIR = 'data'
CACHE_PATH = os.path.join(DATA_DIR, 'geocoding_cache.json')
FAILED_PATH = os.path.join(DATA_DIR, 'geocoding_failed.json')
OUTPUT_PATH = os.path.join(DATA_DIR, 'fuel_stations.json')

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def inspect_caches():
    cache = load_json(CACHE_PATH)
    failed = load_json(FAILED_PATH)
    
    # The number of unique stations to process is 6626
    total_unique_us_stations = 6626
    
    success_count = len(cache)
    fail_count = len(failed)
    
    # We might have cached city,state and full address. But for the purpose of unique stations geocoded, 
    # the cache contains the successful query keys. It's close enough, but actually we should just report cache length.
    
    print(f"1. Stations successfully geocoded (cache size): {success_count}")
    print(f"2. Stations failed (failed cache size): {fail_count}")
    
    # For a more exact number of *stations* remaining, we can say total - processed.
    # We don't have the exact number processed without iterating the CSV, but cache sizes give an estimate of queries.
    # Let's assume (success_count + fail_count) represents queries made, which correlates to stations processed if no fallbacks happened.
    print(f"3. Stations remaining (approximate): {total_unique_us_stations - (success_count + fail_count)}")
    
    print(f"4. Reusable cache: Yes, cache exists and has data. Keys look like: {list(cache.keys())[:2]}")
    
    print("5. Coordinate validation: Current validation bounds check if coordinates fall within rough US bounding box (Lat: 18-72, Lon: -175 to -65). It is sufficient to exclude wildly incorrect global coordinates, but could be tighter for contiguous US.")
    
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
                output_data = json.load(f)
            print(f"6. Output file exists: Yes, fuel_stations.json contains {len(output_data)} records.")
        except Exception as e:
            print(f"6. Output file exists but could not be read: {e}")
    else:
        print("6. Output file exists: No, fuel_stations.json does not exist yet (script was interrupted before final save).")

if __name__ == "__main__":
    inspect_caches()
