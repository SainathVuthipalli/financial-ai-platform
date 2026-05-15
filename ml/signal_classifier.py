import pandas as pd
import numpy as np
from google.cloud import bigquery
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, precision_score, recall_score
import pickle
import os

PROJECT_ID = "financial-ai-platform-sv"

def fetch_training_data(client: bigquery.Client) -> pd.DataFrame:
    query = """
        SELECT
            symbol,
            trade_date,
            total_bars,
            day_low,
            day_high,
            avg_volume,
            avg_pct_change,
            avg_price_range,
            avg_typical_price,
            -- Label: did price move more than 0.1% (relaxed for small dataset)
            CASE WHEN ABS(avg_pct_change) > 0.05 THEN 1 ELSE 0 END as strong_move
        FROM `financial-ai-platform-sv.dbt_transforms.mart_symbol_stats`
        ORDER BY trade_date DESC
    """
    df = client.query(query).to_dataframe()
    return df

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Price range as percentage of typical price
    df["range_pct"] = (df["day_high"] - df["day_low"]) / df["avg_typical_price"] * 100

    # Volume zscore within dataset
    df["volume_zscore"] = (df["avg_volume"] - df["avg_volume"].mean()) / (df["avg_volume"].std() + 1e-8)

    # Day of week from trade_date
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["day_of_week"] = df["trade_date"].dt.dayofweek

    # Absolute pct change
    df["abs_pct_change"] = df["avg_pct_change"].abs()

    return df

FEATURES = [
    "range_pct",
    "volume_zscore",
    "day_of_week",
    "abs_pct_change",
    "avg_price_range",
    "total_bars"
]

def train_model(df: pd.DataFrame):
    df = engineer_features(df)

    X = df[FEATURES].fillna(0)
    y = df["strong_move"]

    print(f"Dataset: {len(df)} rows, {y.sum()} strong moves ({y.mean()*100:.1f}%)")

    if len(df) < 10:
        print("Not enough data yet — need more days of ingestion")
        print("Training on full dataset without split for now...")
        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(X, y)
        print("Model trained on full dataset")
        return model

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        random_state=42
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\nModel Performance:")
    print(classification_report(y_test, y_pred))

    # Feature importance
    importance = pd.DataFrame({
        "feature": FEATURES,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)
    print("\nFeature Importance:")
    print(importance.to_string(index=False))

    return model

def save_model(model, path: str = "ml/signal_model.pkl"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)
    print(f"\nModel saved to {path}")

def predict(model, symbol: str, avg_volume: float,
            day_high: float, day_low: float,
            avg_pct_change: float, avg_typical_price: float,
            total_bars: int, day_of_week: int) -> dict:

    range_pct = (day_high - day_low) / avg_typical_price * 100
    volume_zscore = (avg_volume - 1000000) / 500000
    abs_pct_change = abs(avg_pct_change)
    avg_price_range = day_high - day_low

    features = pd.DataFrame([{
        "range_pct": range_pct,
        "volume_zscore": volume_zscore,
        "day_of_week": day_of_week,
        "abs_pct_change": abs_pct_change,
        "avg_price_range": avg_price_range,
        "total_bars": total_bars
    }])

    proba = model.predict_proba(features)[0]
    classes = model.classes_

    if 1 in classes:
        prob = proba[list(classes).index(1)]
    else:
        prob = 0.0

    prediction = int(prob > 0.5)

    return {
        "symbol": symbol,
        "strong_move_probability": round(float(prob), 4),
        "prediction": "strong move expected" if prediction else "normal activity",
        "confidence": "high" if abs(prob - 0.5) > 0.3 else "medium"
    }

def main():
    client = bigquery.Client(project=PROJECT_ID)

    print("Fetching training data from BigQuery...")
    df = fetch_training_data(client)
    print(f"Fetched {len(df)} rows")

    print("\nTraining model...")
    model = train_model(df)

    save_model(model)

    print("\nTest prediction for NVDA:")
    result = predict(
        model,
        symbol="NVDA",
        avg_volume=3963983,
        day_high=236.05,
        day_low=229.35,
        avg_pct_change=0.11,
        avg_typical_price=233.06,
        total_bars=27,
        day_of_week=2
    )
    print(result)

if __name__ == "__main__":
    main()