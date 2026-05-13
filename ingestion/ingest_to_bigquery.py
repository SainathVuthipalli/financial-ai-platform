from google.cloud import bigquery
import yfinance as yf
from datetime import datetime, timezone

# Project config
PROJECT_ID = "financial-ai-platform-sv"
DATASET_ID = "raw_market_data"
TABLE_ID = "market_data_raw"

# Watchlist
SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "SPY",
    "QQQ", "AMZN", "META", "GOOGL", "AMD",
    "NFLX", "PLTR", "COIN", "HOOD", "MSTR"
]

SCHEMA = [
    bigquery.SchemaField("symbol", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("open", "FLOAT64"),
    bigquery.SchemaField("high", "FLOAT64"),
    bigquery.SchemaField("low", "FLOAT64"),
    bigquery.SchemaField("close", "FLOAT64"),
    bigquery.SchemaField("volume", "INT64"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP"),
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
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            })
        return records
    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")
        return []

def create_dataset_and_table(client: bigquery.Client):
    # Create dataset
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    dataset_ref.location = "US"
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset {DATASET_ID} already exists")
    except Exception:
        client.create_dataset(dataset_ref)
        print(f"Created dataset {DATASET_ID}")

    # Create table with partitioning
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    try:
        client.get_table(table_ref)
        print(f"Table {TABLE_ID} already exists")
    except Exception:
        table = bigquery.Table(table_ref, schema=SCHEMA)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="timestamp"
        )
        table.clustering_fields = ["symbol"]
        client.create_table(table)
        print(f"Created partitioned table {TABLE_ID}")

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
    create_dataset_and_table(client)

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