import functions_framework
import pickle
import pandas as pd
import os

model = None

def load_model():
    global model
    if model is None:
        model_path = os.path.join(os.path.dirname(__file__), "signal_model.pkl")
        with open(model_path, "rb") as f:
            model = pickle.load(f)
    return model

@functions_framework.http
def predict_signal(request):
    # Handle CORS
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        return ("", 204, headers)

    headers = {"Access-Control-Allow-Origin": "*"}

    try:
        data = request.get_json()
        if not data:
            return ({"error": "No JSON body provided"}, 400, headers)

        required = ["symbol", "avg_volume", "day_high", "day_low",
                   "avg_pct_change", "avg_typical_price", "total_bars", "day_of_week"]
        missing = [f for f in required if f not in data]
        if missing:
            return ({"error": f"Missing fields: {missing}"}, 400, headers)

        symbol = data["symbol"]
        avg_volume = float(data["avg_volume"])
        day_high = float(data["day_high"])
        day_low = float(data["day_low"])
        avg_pct_change = float(data["avg_pct_change"])
        avg_typical_price = float(data["avg_typical_price"])
        total_bars = int(data["total_bars"])
        day_of_week = int(data["day_of_week"])

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

        m = load_model()
        proba = m.predict_proba(features)[0]
        classes = m.classes_
        prob = proba[list(classes).index(1)] if 1 in classes else 0.0

        result = {
            "symbol": symbol,
            "strong_move_probability": round(float(prob), 4),
            "prediction": "strong move expected" if prob > 0.5 else "normal activity",
            "confidence": "high" if abs(prob - 0.5) > 0.3 else "medium"
        }

        return (result, 200, headers)

    except Exception as e:
        return ({"error": str(e)}, 500, headers)