from google.cloud import bigquery
import pandas as pd
from datetime import datetime, timezone

PROJECT_ID = "financial-ai-platform-sv"
DATASET_ID = "raw_market_data"
TABLE_ID = "market_data_raw"

def fetch_latest_data() -> pd.DataFrame:
    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)
        LIMIT 10000
    """
    return client.query(query).to_dataframe()

def run_quality_checks(df: pd.DataFrame):
    print(f"\nRunning data quality checks on {len(df)} rows...")
    print(f"Timestamp: {datetime.now(timezone.utc)}")
    print("-" * 50)

    results = {}

    # Check 1: Row count
    row_count = len(df)
    min_expected = 100
    results["row_count"] = {
        "value": row_count,
        "passed": row_count >= min_expected,
        "message": f"Row count {row_count} >= {min_expected}"
    }

    # Check 2: No null symbols
    null_symbols = df["symbol"].isnull().sum()
    results["null_symbols"] = {
        "value": null_symbols,
        "passed": null_symbols == 0,
        "message": f"Null symbols: {null_symbols}"
    }

    # Check 3: No null timestamps
    null_timestamps = df["timestamp"].isnull().sum()
    results["null_timestamps"] = {
        "value": null_timestamps,
        "passed": null_timestamps == 0,
        "message": f"Null timestamps: {null_timestamps}"
    }

    # Check 4: No negative prices
    negative_prices = (df["close"] < 0).sum()
    results["negative_prices"] = {
        "value": negative_prices,
        "passed": negative_prices == 0,
        "message": f"Negative close prices: {negative_prices}"
    }

    # Check 5: Expected symbols present
    expected_symbols = {"AAPL", "MSFT", "NVDA", "TSLA", "SPY"}
    actual_symbols = set(df["symbol"].unique())
    missing = expected_symbols - actual_symbols
    results["expected_symbols"] = {
        "value": list(missing),
        "passed": len(missing) == 0,
        "message": f"Missing symbols: {missing if missing else 'None'}"
    }

    # Check 6: Volume > 0
    zero_volume = (df["volume"] <= 0).sum()
    results["zero_volume"] = {
        "value": zero_volume,
        "passed": zero_volume == 0,
        "message": f"Zero volume rows: {zero_volume}"
    }

    # Check 7: Price range sanity (high >= low)
    invalid_range = (df["high"] < df["low"]).sum()
    results["price_range"] = {
        "value": invalid_range,
        "passed": invalid_range == 0,
        "message": f"Invalid price ranges (high < low): {invalid_range}"
    }

    # Print results
    passed = 0
    failed = 0
    for check, result in results.items():
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {check}: {result['message']}")
        if result["passed"]:
            passed += 1
        else:
            failed += 1

    print("-" * 50)
    print(f"Total: {passed} passed, {failed} failed")

    if failed > 0:
        raise Exception(f"Data quality checks failed: {failed} failures")
    else:
        print("All checks passed!")

def main():
    df = fetch_latest_data()
    if df.empty:
        print("WARNING: No data found for today. Pipeline may not have run.")
        return
    run_quality_checks(df)

if __name__ == "__main__":
    main()