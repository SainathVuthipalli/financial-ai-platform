from google.cloud import bigquery
import yfinance as yf
import pandas as pd
from datetime import datetime

# Project config
PROJECT_ID = "financial-ai-platform-sv"
DATASET_ID = "raw_market_data"
TABLE_ID = "market_data_raw"

# Your watchlist - same as SweepScanner
SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "SPY",
    "QQQ", "AMZN", "META", "GOOGL", "AMD",
    "NFLX", "PLTR", "COIN", "HOOD", "MSTR"
]

def fetch_market_data(symbol: str) -> list:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="5m")
        
        if hist.empty:
            print(f"  No data for {symbol}")
            return []
        
        records = []
        for ts, row in hist.iterrows():
            records.append({
                "symbol": symbol,
                "timestamp": ts.isoformat(),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
                "ingested_at": datetime.utcnow().isoformat()
            })
        return records
    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")
        return []

def create_table_if_not_exists(client: bigquery.Client):
    dataset_ref = client.dataset(DATASET_ID)
    
    # Create dataset if not exists
    try:
        client.get_dataset(dataset_ref)
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset)
        print(f"Created dataset {DATASET_ID}")

    # Define schema
    schema = [
        bigquery.SchemaField("symbol", "STRING"),
        bigquery.SchemaField("timestamp", "STRING"),
        bigquery.SchemaField("open", "FLOAT"),
        bigquery.SchemaField("high", "FLOAT"),
        bigquery.SchemaField("low", "FLOAT"),
        bigquery.SchemaField("close", "FLOAT"),
        bigquery.SchemaField("volume", "INTEGER"),
        bigquery.SchemaField("ingested_at", "STRING"),
    ]

    table_ref = dataset_ref.table(TABLE_ID)
    try:
        client.get_table(table_ref)
        print(f"Table {TABLE_ID} already exists")
    except Exception:
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table)
        print(f"Created table {TABLE_ID}")

def load_to_bigquery(records: list, client: bigquery.Client):
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    errors = client.insert_rows_json(table_ref, records)
    if errors:
        print(f"  BQ errors: {errors}")
    else:
        print(f"  Loaded {len(records)} rows")

def main():
    print("Starting ingestion...")
    client = bigquery.Client(project=PROJECT_ID)
    
    # Create dataset + table if first run
    create_table_if_not_exists(client)
    
    total = 0
    for symbol in SYMBOLS:
        print(f"Fetching {symbol}...")
        records = fetch_market_data(symbol)
        if records:
            load_to_bigquery(records, client)
            total += len(records)
    
    print(f"\nDone. Total rows loaded: {total}")

if __name__ == "__main__":
    main()