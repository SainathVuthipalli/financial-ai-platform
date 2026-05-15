from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import anthropic
import requests
import os
from google.cloud import bigquery

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ID = "financial-ai-platform-sv"
PREDICT_ENDPOINT = "https://us-central1-financial-ai-platform-sv.cloudfunctions.net/predict-signal"

class ChatRequest(BaseModel):
    question: str

def fetch_signals():
    client = bigquery.Client(project=PROJECT_ID)
    query = """
        SELECT symbol, trade_date, signal_text, avg_volume,
               avg_pct_change, day_high, day_low
        FROM `financial-ai-platform-sv.raw_market_data.signal_embeddings`
        ORDER BY trade_date DESC
        LIMIT 20
    """
    rows = client.query(query).result()
    return [dict(row) for row in rows]

def get_prediction(signal: dict):
    try:
        payload = {
            "symbol": signal["symbol"],
            "avg_volume": float(signal["avg_volume"]),
            "day_high": float(signal["day_high"]),
            "day_low": float(signal["day_low"]),
            "avg_pct_change": float(signal["avg_pct_change"]),
            "avg_typical_price": (float(signal["day_high"]) + float(signal["day_low"])) / 2,
            "total_bars": 27,
            "day_of_week": 2
        }
        response = requests.post(
            PREDICT_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        return response.json()
    except:
        return {}

@app.get("/api/signals")
def get_signals():
    signals = fetch_signals()
    for s in signals:
        pred = get_prediction(s)
        s["prediction"] = pred.get("prediction", "unknown")
        s["probability"] = pred.get("strong_move_probability", 0)
        s["confidence"] = pred.get("confidence", "unknown")
        s["trade_date"] = str(s["trade_date"])
    return signals

@app.post("/api/chat")
def chat(req: ChatRequest):
    signals = fetch_signals()
    context = "Recent market signal data:\n\n"
    for s in signals:
        context += f"- {s['signal_text']}\n"

    predictions = {}
    for s in signals[:3]:
        pred = get_prediction(s)
        if pred:
            predictions[s["symbol"]] = pred

    if predictions:
        context += "\n\nML Predictions:\n"
        for symbol, pred in predictions.items():
            context += f"- {symbol}: {pred.get('prediction')} (prob: {pred.get('strong_move_probability')})\n"

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=f"""You are a financial market analyst assistant.
Answer questions about market data using the provided signal data and ML predictions.
Be specific, cite symbols and prediction scores.

{context}""",
        messages=[{"role": "user", "content": req.question}]
    )
    return {"answer": response.content[0].text}

@app.get("/api/health")
def health():
    return {"status": "ok"}