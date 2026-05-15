import yfinance as yf
import pandas as pd
from google.cloud import bigquery
from datetime import datetime, timezone
import time

PROJECT_ID = "financial-ai-platform-sv"
DATASET_ID = "raw_market_data"
TABLE_ID = "market_data_daily"


def get_sp500_symbols() -> list:
    return [
        # Mega cap tech
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
        "AVGO", "ORCL", "CRM", "ADBE", "AMD", "INTC", "QCOM", "TXN",
        "AMAT", "MU", "LRCX", "KLAC", "MRVL", "SNPS", "CDNS", "FTNT",
        # Financials
        "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "BLK",
        "SPGI", "MCO", "AXP", "USB", "PNC", "TFC", "COF", "SCHW",
        # Healthcare
        "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "DHR",
        "BMY", "AMGN", "GILD", "ISRG", "SYK", "BSX", "MDT", "ELV",
        # Consumer
        "HD", "MCD", "NKE", "SBUX", "TGT", "COST", "WMT",
        "PG", "KO", "PEP", "PM", "MO", "CL", "MNST",
        # Energy
        "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO",
        # Industrials
        "CAT", "DE", "BA", "HON", "UPS", "RTX", "LMT", "GE",
        "MMM", "EMR", "ETN", "PH", "ROK", "CMI", "IR", "GD",
        # ETFs
        "SPY", "QQQ", "IWM", "DIA", "XLF", "XLK", "XLE", "XLV",
        "XLI", "XLY", "XLP", "ARKK", "GLD", "TLT",
        # High momentum
        "PLTR", "COIN", "HOOD", "MSTR", "MARA", "RIOT", "GME",
        "SOUN", "BBAI", "AI", "SNAP", "UBER", "LYFT",
        # Growth
        "NFLX", "SNOW", "DDOG", "NET", "CRWD", "ZS", "MDB",
        "HUBS", "TEAM", "WDAY", "NOW", "VEEV", "ZM", "BILL",
    ]

SCHEMA = [
    bigquery.SchemaField("symbol", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("open", "FLOAT64"),
    bigquery.SchemaField("high", "FLOAT64"),
    bigquery.SchemaField("low", "FLOAT64"),
    bigquery.SchemaField("close", "FLOAT64"),
    bigquery.SchemaField("volume", "INT64"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP"),
]

def create_table(client: bigquery.Client):
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
    table_ref = f"{dataset_ref}.{TABLE_ID}"
    try:
        client.get_table(table_ref)
        print(f"Table {TABLE_ID} already exists")
    except Exception:
        table = bigquery.Table(table_ref, schema=SCHEMA)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="date"
        )
        table.clustering_fields = ["symbol"]
        client.create_table(table)
        print(f"Created table {TABLE_ID}")

def fetch_batch(symbols: list, period: str = "max") -> pd.DataFrame:
    df = yf.download(
        tickers=symbols,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False
    )
    return df

def parse_batch(df: pd.DataFrame, symbols: list) -> list:
    records = []
    now = datetime.now(timezone.utc).isoformat()

    for symbol in symbols:
        try:
            if len(symbols) == 1:
                sym_df = df
            else:
                sym_df = df[symbol]

            sym_df = sym_df.dropna(subset=["Close"])

            for date, row in sym_df.iterrows():
                records.append({
                    "symbol": symbol,
                    "date": str(date.date()),
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row["Volume"]),
                    "ingested_at": now,
                })
        except Exception as e:
            print(f"  Error parsing {symbol}: {e}")

    return records

def load_to_bigquery(records: list, client: bigquery.Client):
    if not records:
        return
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    errors = client.insert_rows_json(table_ref, records)
    if errors:
        print(f"  BQ errors: {errors[:2]}")
    else:
        print(f"  Loaded {len(records)} rows")

def main():
    client = bigquery.Client(project=PROJECT_ID)
    create_table(client)

    print("Fetching S&P 500 symbols...")
    symbols = get_sp500_symbols()
    print(f"Found {len(symbols)} symbols")

    # Process in batches of 50 to avoid rate limits
    batch_size = 50
    total_records = 0

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        print(f"\nBatch {i//batch_size + 1}/{len(symbols)//batch_size + 1}: {batch[:3]}...")

        try:
            df = fetch_batch(batch, period="1y")
            records = parse_batch(df, batch)
            load_to_bigquery(records, client)
            total_records += len(records)
            print(f"  Running total: {total_records} rows")
        except Exception as e:
            print(f"  Batch error: {e}")

        # Small delay between batches
        time.sleep(1)

    print(f"\nBackfill complete. Total rows: {total_records}")

if __name__ == "__main__":
    main()