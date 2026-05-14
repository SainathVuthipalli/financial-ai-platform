import anthropic
import os
from google.cloud import bigquery
from datetime import datetime

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
    context = build_context(signals)

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=f"""You are a financial market analyst assistant. 
Answer questions about market data using only the provided signal data.
Be specific, cite symbols and dates, and highlight notable patterns.

{context}""",
        messages=[
            {"role": "user", "content": question}
        ]
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