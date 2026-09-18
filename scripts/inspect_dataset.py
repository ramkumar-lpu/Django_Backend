import pandas as pd
import os
import sys

def inspect_dataset(csv_path):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} does not exist.")
        sys.exit(1)

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    print("--- REAL DATASET STATISTICS ---")
    
    # 1. Total rows
    total_rows = len(df)
    print(f"1. Total number of rows: {total_rows}")
    
    # 2. Exact column names
    print(f"2. Exact column names: {list(df.columns)}")
    
    # 3. Data types
    print("3. Data types:")
    for col, dtype in df.dtypes.items():
        print(f"   - {col}: {dtype}")
        
    # Clean column names (strip whitespace) for easier access
    df.columns = [col.strip() for col in df.columns]
    
    # 4. Number of unique OPIS Truckstop ID
    id_col = 'OPIS Truckstop ID' if 'OPIS Truckstop ID' in df.columns else None
    if not id_col:
        print(f"4. Number of unique OPIS Truckstop ID: Column not found")
    else:
        unique_ids = df[id_col].nunique()
        print(f"4. Number of unique OPIS Truckstop ID: {unique_ids}")
        
    # 5. Number of duplicate station IDs
    if not id_col:
        print(f"5. Number of duplicate station IDs: Column not found")
    else:
        duplicate_ids = df.duplicated(subset=[id_col], keep=False).sum()
        print(f"5. Number of duplicate station IDs: {duplicate_ids}")

    # 6 & 7. US vs non-US records
    state_col = 'State' if 'State' in df.columns else None
    us_states = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    }
    
    if not state_col:
        print(f"6. Number of US records: Column not found")
        print(f"7. Number of non-US records: Column not found")
    else:
        df['State_clean'] = df[state_col].astype(str).str.strip().str.upper()
        us_records = df[df['State_clean'].isin(us_states)]
        non_us_records = df[~df['State_clean'].isin(us_states)]
        print(f"6. Number of US records: {len(us_records)}")
        print(f"7. Number of non-US records: {len(non_us_records)}")
        
    # 8. Missing values for every important column
    important_cols = [col for col in ['OPIS Truckstop ID', 'Truckstop Name', 'Address', 'City', 'State', 'Retail Price'] if col in df.columns]
    print(f"8. Missing values for every important column:")
    for col in important_cols:
        missing = df[col].isna().sum() + (df[col] == '').sum()
        print(f"   - {col}: {missing}")
        
    # 9, 10, 11. Retail Price stats
    price_col = 'Retail Price' if 'Retail Price' in df.columns else None
    if not price_col:
        print(f"9. Number of invalid/missing Retail Price records: Column not found")
        print(f"10. Minimum Retail Price: Column not found")
        print(f"11. Maximum Retail Price: Column not found")
        print(f"12. Number of records remaining: N/A")
    else:
        # Convert price to numeric, coercing errors to NaN
        df['numeric_price'] = pd.to_numeric(df[price_col], errors='coerce')
        invalid_price_records = df['numeric_price'].isna().sum()
        print(f"9. Number of invalid/missing Retail Price records: {invalid_price_records}")
        
        valid_prices = df.dropna(subset=['numeric_price'])
        if len(valid_prices) > 0:
            print(f"10. Minimum Retail Price: {valid_prices['numeric_price'].min()}")
            print(f"11. Maximum Retail Price: {valid_prices['numeric_price'].max()}")
        else:
            print(f"10. Minimum Retail Price: No valid prices found")
            print(f"11. Maximum Retail Price: No valid prices found")
            
        # 12. Records remaining
        if id_col and state_col:
            clean_df = df.dropna(subset=['numeric_price', id_col])
            clean_df = clean_df[clean_df['State_clean'].isin(us_states)]
            
            dedup_df = clean_df.sort_values(by='numeric_price', ascending=True).drop_duplicates(subset=[id_col], keep='first')
            print(f"12. Number of records remaining after filtering, removing invalid, and deduplicating: {len(dedup_df)}")
        else:
            print("12. Number of records remaining after filtering, removing invalid, and deduplicating: Cannot calculate due to missing columns")

    print("\n--- SAMPLE ROWS ---")
    cols_to_print = [c for c in ['OPIS Truckstop ID', 'Truckstop Name', 'Address', 'City', 'State', 'Retail Price'] if c in df.columns]
    print(df[cols_to_print].head(5).to_string())


if __name__ == "__main__":
    csv_path = 'data/fuel-prices-for-be-assessment.csv'
    inspect_dataset(csv_path)
