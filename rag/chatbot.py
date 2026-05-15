import anthropic
import os
from google.cloud import bigquery
from datetime import datetime
import requests

PREDICT_ENDPOINT = "https://us-central1-financial-ai-platform-sv.cloudfunctions.net/predict-signal"

def get_ml_prediction(signal: dict) -> dict:
    try:
        payload = {
            "symbol": signal["symbol"],
            "avg_volume": float(signal["avg_volume"]),
            "day_high": float(signal["day_high"]),
            "day_low": float(signal["day_low"]),
            "avg_pct_change": float(signal["avg_pct_change"]),
            "avg_typical_price": float(signal.get("avg_typical_price", 
                (signal["day_high"] + signal["day_low"]) / 2)),
            "total_bars": int(signal.get("total_bars", 27)),
            "day_of_week": 2
        }
        response = requests.post(
            PREDICT_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}

PROJECT_ID = "financial-ai-platform-sv"
DATASET_ID = "raw_market_data"
EMBEDDINGS_TABLE = "signal_embeddings"

def fetch_relevant_signals(query: str, client: bigquery.Client) -> list:
    """Fetch signals from BigQuery based on keyword matching"""
    query_sql = f"""
        SELECT
            symbol,
            trade_date,
            signal_text,
            avg_volume,
            avg_pct_change,
            day_high,
            day_low
        FROM `{PROJECT_ID}.{DATASET_ID}.{EMBEDDINGS_TABLE}`
        ORDER BY trade_date DESC
        LIMIT 20
    """
    rows = client.query(query_sql).result()
    return [dict(row) for row in rows]

def build_context(signals: list) -> str:
    context = "Recent market signal data:\n\n"
    for s in signals:
        context += f"- {s['signal_text']}\n"
    return context

def ask_chatbot(question: str, bq_client: bigquery.Client, anthropic_client: anthropic.Anthropic) -> str:
    signals = fetch_relevant_signals(question, bq_client)
    
    # Get ML predictions for top 3 signals
    predictions = {}
    for s in signals[:3]:
        pred = get_ml_prediction(s)
        if "error" not in pred:
            predictions[s["symbol"]] = pred

    context = build_context(signals)
    
    # Add predictions to context
    if predictions:
        context += "\n\nML Signal Predictions:\n"
        for symbol, pred in predictions.items():
            context += f"- {symbol}: {pred['prediction']} (probability: {pred['strong_move_probability']}, confidence: {pred['confidence']})\n"

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=f"""You are a financial market analyst assistant.
Answer questions about market data using the provided signal data and ML predictions.
Be specific, cite symbols, dates, and prediction scores where relevant.

{context}""",
        messages=[{"role": "user", "content": question}]
    )
    return response.content[0].text

def main():
    bq_client = bigquery.Client(project=PROJECT_ID)
    anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    print("Financial Signal RAG Chatbot")
    print("=" * 40)
    print("Type 'quit' to exit\n")

    questions = [
        "Which symbols had the highest percentage change recently?",
        "Which stocks were bearish and had high volume?",
        "What was NVDA doing over the past few days?",
        "Which symbols look most volatile based on their day range?"
    ]

    for question in questions:
        print(f"Q: {question}")
        answer = ask_chatbot(question, bq_client, anthropic_client)
        print(f"A: {answer}")
        print("-" * 40)

if __name__ == "__main__":
    main()