import csv
import json
import os
import pandas as pd
from django.conf import settings

class StationRepository:
    """
    StationRepository loads station information from the authoritative CSV,
    and coordinates from a separated coordinate JSON file.
    Only stations with valid coordinates are returned for optimization.
    """
    _stations = None

    @classmethod
    def get_all_stations(cls):
        if cls._stations is not None:
            return cls._stations

        base_dir = getattr(settings, 'BASE_DIR', os.getcwd())
        csv_path = os.path.join(base_dir, 'data', 'fuel-prices-for-be-assessment.csv')
        coords_path = os.path.join(base_dir, 'data', 'fuel_station_coordinates.json')

        if not os.path.exists(csv_path):
            cls._stations = []
            return []

        # Load CSV using pandas for robust cleaning (as discovered during inspection)
        df = pd.read_csv(csv_path)
        df.columns = [col.strip() for col in df.columns]
        
        # Filter USA only
        us_states = {'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                     'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 
                     'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 
                     'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 
                     'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'}
        df['State_clean'] = df['State'].astype(str).str.strip().str.upper()
        df = df[df['State_clean'].isin(us_states)]
        
        # Valid prices
        df['numeric_price'] = pd.to_numeric(df['Retail Price'], errors='coerce')
        df = df.dropna(subset=['numeric_price', 'OPIS Truckstop ID'])
        
        # Deduplicate
        df = df.sort_values(by=['numeric_price', 'OPIS Truckstop ID'], ascending=[True, True])
        df = df.drop_duplicates(subset=['OPIS Truckstop ID'], keep='first')
        
        # Load coordinates (Mapping of OPIS ID -> {lat, lon})
        # If it doesn't exist, we just don't have coordinates.
        coords_map = {}
        if os.path.exists(coords_path):
            try:
                with open(coords_path, 'r', encoding='utf-8') as f:
                    coords_map = json.load(f)
            except Exception:
                pass

        stations = []
        for _, row in df.iterrows():
            opis_id = str(int(row['OPIS Truckstop ID']))
            
            # Only include if we have coordinates for it
            if opis_id in coords_map:
                stations.append({
                    "station_id": opis_id,
                    "truckstop_name": str(row['Truckstop Name']).strip(),
                    "address": str(row['Address']).strip(),
                    "city": str(row['City']).strip(),
                    "state": str(row['State']).strip(),
                    "price_per_gallon": float(row['numeric_price']),
                    "latitude": coords_map[opis_id]['lat'],
                    "longitude": coords_map[opis_id]['lon']
                })
        
        cls._stations = stations
        return stations
