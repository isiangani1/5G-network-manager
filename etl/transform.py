from typing import List, Dict, Any
import pandas as pd

def filter_kpi_data(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cleans, validates, and transforms raw KPI data using pandas.
    """
    if not raw_data:
        return []

    df = pd.DataFrame(raw_data)

    required_columns = {'slice_id', 'timestamp', 'latency', 'throughput', 'connected_devices'}
    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        raise ValueError(f"Missing required columns in raw data: {missing}")

    # Convert timestamp to datetime objects and handle errors
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df.dropna(subset=['timestamp'], inplace=True) # Drop rows where timestamp conversion failed

    kpi_df = df[list(required_columns)].copy()

    # Fill missing numeric values with 0
    for col in ['latency', 'throughput', 'connected_devices']:
        kpi_df[col] = pd.to_numeric(kpi_df[col], errors='coerce').fillna(0)

    return kpi_df.to_dict('records')
