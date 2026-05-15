import pandas as pd
from prophet import Prophet
from google.cloud import bigquery
from datetime import datetime, timezone
import warnings
warnings.filterwarnings("ignore")

PROJECT_ID = "financial-ai-platform-sv"
DATASET_ID = "raw_market_data"
SOURCE_TABLE = "market_data_daily"
FORECAST_TABLE = "market_data_forecasts"

SCHEMA = [
    bigquery.SchemaField("symbol", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("forecast_date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("predicted_close", "FLOAT64"),
    bigquery.SchemaField("lower_bound", "FLOAT64"),
    bigquery.SchemaField("upper_bound", "FLOAT64"),
    bigquery.SchemaField("trend", "STRING"),
    bigquery.SchemaField("generated_at", "TIMESTAMP"),
]

def create_forecast_table(client: bigquery.Client):
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{FORECAST_TABLE}"
    try:
        client.get_table(table_ref)
        print(f"Table {FORECAST_TABLE} already exists")
    except Exception:
        table = bigquery.Table(table_ref, schema=SCHEMA)
        client.create_table(table)
        print(f"Created table {FORECAST_TABLE}")

def fetch_historical(client: bigquery.Client, symbol: str) -> pd.DataFrame:
    query = f"""
        SELECT date, close
        FROM `{PROJECT_ID}.{DATASET_ID}.{SOURCE_TABLE}`
        WHERE symbol = '{symbol}'
        ORDER BY date ASC
    """
    df = client.query(query).to_dataframe()
    return df

def forecast_symbol(df: pd.DataFrame, symbol: str, days: int = 7) -> pd.DataFrame:
    # Prophet requires columns named ds and y
    prophet_df = df.rename(columns={"date": "ds", "close": "y"})
    prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])
    prophet_df = prophet_df.dropna()

    if len(prophet_df) < 30:
        print(f"  {symbol}: Not enough data ({len(prophet_df)} rows)")
        return None

    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=0.05,
        interval_width=0.80
    )
    model.fit(prophet_df)

    future = model.make_future_dataframe(periods=days, freq="B")  # B = business days
    forecast = model.predict(future)

    # Get only the future predictions
    last_date = prophet_df["ds"].max()
    future_forecast = forecast[forecast["ds"] > last_date].copy()

    now = datetime.now(timezone.utc).isoformat()
    records = []
    for _, row in future_forecast.iterrows():
        predicted = round(float(row["yhat"]), 4)
        lower = round(float(row["yhat_lower"]), 4)
        upper = round(float(row["yhat_upper"]), 4)
        last_close = float(prophet_df["y"].iloc[-1])
        trend = "bullish" if predicted > last_close else "bearish"

        records.append({
            "symbol": symbol,
            "forecast_date": str(row["ds"].date()),
            "predicted_close": predicted,
            "lower_bound": lower,
            "upper_bound": upper,
            "trend": trend,
            "generated_at": now,
        })

    return records

def load_forecasts(records: list, client: bigquery.Client):
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{FORECAST_TABLE}"
    errors = client.insert_rows_json(table_ref, records)
    if errors:
        print(f"  BQ errors: {errors[:1]}")
    else:
        print(f"  Loaded {len(records)} forecast rows")

def get_symbols(client: bigquery.Client) -> list:
    query = f"""
        SELECT DISTINCT symbol
        FROM `{PROJECT_ID}.{DATASET_ID}.{SOURCE_TABLE}`
        ORDER BY symbol
    """
    rows = client.query(query).result()
    return [row["symbol"] for row in rows]

def main():
    client = bigquery.Client(project=PROJECT_ID)
    create_forecast_table(client)

    symbols = get_symbols(client)
    print(f"Forecasting {len(symbols)} symbols...")

    total = 0
    failed = 0

    for symbol in symbols:
        try:
            df = fetch_historical(client, symbol)
            records = forecast_symbol(df, symbol)
            if records:
                load_forecasts(records, client)
                total += len(records)
                print(f"  {symbol}: 7-day forecast generated ✓")
        except Exception as e:
            print(f"  {symbol}: Error — {e}")
            failed += 1

    print(f"\nDone. {total} forecast rows loaded. {failed} failed.")

if __name__ == "__main__":
    main()