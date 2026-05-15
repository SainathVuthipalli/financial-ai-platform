import yfinance as yf
import pandas as pd
from google.cloud import bigquery
from datetime import datetime, timezone, timedelta
import time

PROJECT_ID = "financial-ai-platform-sv"
DATASET_ID = "raw_market_data"
TABLE_ID = "market_data_daily"

def get_sp500_symbols() -> list:
    # S&P 500 symbols - major components
    return [
        # Mega cap tech
        "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA",
        "AVGO", "ORCL", "CRM", "ADBE", "AMD", "INTC", "QCOM", "TXN",
        "AMAT", "MU", "LRCX", "KLAC", "MRVL", "SNPS", "CDNS", "FTNT",
        # Financials
        "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "BLK",
        "SPGI", "MCO", "AXP", "USB", "PNC", "TFC", "COF", "SCHW",
        # Healthcare
        "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "DHR",
        "BMY", "AMGN", "GILD", "ISRG", "SYK", "BSX", "MDT", "ELV",
        # Consumer
        "AMZN", "HD", "MCD", "NKE", "SBUX", "TGT", "COST", "WMT",
        "PG", "KO", "PEP", "PM", "MO", "CL", "EL", "MNST",
        # Energy
        "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO",
        # Industrials
        "CAT", "DE", "BA", "HON", "UPS", "RTX", "LMT", "GE",
        "MMM", "EMR", "ETN", "PH", "ROK", "CMI", "IR", "GD",
        # ETFs
        "SPY", "QQQ", "IWM", "DIA", "XLF", "XLK", "XLE", "XLV",
        "XLI", "XLY", "XLP", "ARKK", "GLD", "SLV", "TLT",
        # High momentum / meme
        "PLTR", "COIN", "HOOD", "MSTR", "MARA", "RIOT", "GME",
        "AMC", "SOUN", "BBAI", "PATH", "AI", "SNAP", "UBER", "LYFT",
        # Growth
        "NFLX", "SNOW", "DDOG", "NET", "CRWD", "ZS", "OKTA", "MDB",
        "HUBS", "TEAM", "WDAY", "NOW", "VEEV", "ZM", "DOCU", "BILL",
    ]

def get_last_loaded_date(client: bigquery.Client) -> str:
    query = f"""
        SELECT MAX(date) as last_date
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
    """
    result = list(client.query(query).result())
    return str(result[0]["last_date"])

def fetch_incremental(symbols: list, start_date: str) -> pd.DataFrame:
    df = yf.download(
        tickers=symbols,
        start=start_date,
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
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"
    errors = client.insert_rows_json(table_ref, records)
    if errors:
        print(f"BQ errors: {errors[:2]}")
    else:
        print(f"Loaded {len(records)} rows")

def main():
    client = bigquery.Client(project=PROJECT_ID)

    last_date = get_last_loaded_date(client)
    print(f"Last loaded date: {last_date}")

    # Start from next day after last loaded
    start_date = str(
        datetime.strptime(last_date, "%Y-%m-%d").date() + timedelta(days=1)
    )
    print(f"Fetching from: {start_date}")

    symbols = get_sp500_symbols()
    print(f"Symbols: {len(symbols)}")

    batch_size = 50
    total = 0

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        try:
            df = fetch_incremental(batch, start_date)
            records = parse_batch(df, batch)
            load_to_bigquery(records, client)
            total += len(records)
        except Exception as e:
            print(f"Batch error: {e}")
        time.sleep(1)

    print(f"Incremental load complete. Rows loaded: {total}")

if __name__ == "__main__":
    main()