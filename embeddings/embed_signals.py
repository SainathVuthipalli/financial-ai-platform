from google.cloud import bigquery
import hashlib
from datetime import datetime, timezone

PROJECT_ID = "financial-ai-platform-sv"
DATASET_ID = "raw_market_data"
SOURCE_TABLE = "market_data_raw"
EMBEDDINGS_TABLE = "signal_embeddings"

def create_embeddings_table(client: bigquery.Client):
    schema = [
        bigquery.SchemaField("symbol", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("trade_date", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("signal_text", "STRING"),
        bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
        bigquery.SchemaField("avg_volume", "FLOAT64"),
        bigquery.SchemaField("avg_pct_change", "FLOAT64"),
        bigquery.SchemaField("day_high", "FLOAT64"),
        bigquery.SchemaField("day_low", "FLOAT64"),
        bigquery.SchemaField("embedded_at", "TIMESTAMP"),
    ]
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{EMBEDDINGS_TABLE}"
    try:
        client.get_table(table_ref)
        print(f"Table {EMBEDDINGS_TABLE} already exists")
    except Exception:
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table)
        print(f"Created table {EMBEDDINGS_TABLE}")

def fetch_signal_summary(client: bigquery.Client) -> list:
    query = f"""
        SELECT
            symbol,
            CAST(DATE(timestamp) AS STRING) as trade_date,
            COUNT(*) as total_bars,
            ROUND(MIN(low), 2) as day_low,
            ROUND(MAX(high), 2) as day_high,
            ROUND(AVG(volume), 0) as avg_volume,
            ROUND(AVG((close - open) / open * 100), 4) as avg_pct_change,
            ROUND(AVG((high + low + close) / 3), 2) as avg_typical_price
        FROM `{PROJECT_ID}.{DATASET_ID}.{SOURCE_TABLE}`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
        GROUP BY symbol, trade_date
        ORDER BY symbol, trade_date DESC
    """
    rows = client.query(query).result()
    return [dict(row) for row in rows]

def create_signal_text(row: dict) -> str:
    direction = "bullish" if row["avg_pct_change"] > 0 else "bearish"
    volume_desc = "high" if row["avg_volume"] > 1000000 else "normal"
    return (
        f"{row['symbol']} on {row['trade_date']}: "
        f"{direction} with {row['avg_pct_change']}% average change. "
        f"Day range ${row['day_low']} to ${row['day_high']}. "
        f"Average volume {volume_desc} at {int(row['avg_volume']):,}. "
        f"Typical price ${row['avg_typical_price']}."
    )

def get_embedding(text: str) -> list:
    # Generate 256-dimensional embedding using repeated hashing
    embedding = []
    for i in range(8):
        hash_input = f"{text}_{i}"
        hash_val = hashlib.sha256(hash_input.encode()).hexdigest()
        chunk = [int(hash_val[j:j+2], 16) / 255.0 for j in range(0, 64, 2)]
        embedding.extend(chunk)
    return embedding

def load_embeddings(records: list, client: bigquery.Client):
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{EMBEDDINGS_TABLE}"
    errors = client.insert_rows_json(table_ref, records)
    if errors:
        print(f"BQ errors: {errors}")
    else:
        print(f"Loaded {len(records)} embeddings")

def main():
    bq_client = bigquery.Client(project=PROJECT_ID)
    create_embeddings_table(bq_client)
    print("Fetching signal summaries...")
    signals = fetch_signal_summary(bq_client)
    print(f"Found {len(signals)} signal summaries")
    records = []
    for signal in signals:
        text = create_signal_text(signal)
        print(f"Embedding: {signal['symbol']} {signal['trade_date']}")
        embedding = get_embedding(text)
        records.append({
            "symbol": signal["symbol"],
            "trade_date": str(signal["trade_date"]),
            "signal_text": text,
            "embedding": embedding,
            "avg_volume": float(signal["avg_volume"]),
            "avg_pct_change": float(signal["avg_pct_change"]),
            "day_high": float(signal["day_high"]),
            "day_low": float(signal["day_low"]),
            "embedded_at": datetime.now(timezone.utc).isoformat(),
        })
    load_embeddings(records, bq_client)
    print("Done.")

if __name__ == "__main__":
    main()