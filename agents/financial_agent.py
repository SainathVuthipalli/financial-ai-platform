import anthropic
import os
import requests
from google.cloud import bigquery

PROJECT_ID = "financial-ai-platform-sv"
PREDICT_ENDPOINT = "https://us-central1-financial-ai-platform-sv.cloudfunctions.net/predict-signal"

# Define all tools the agent can use
TOOLS = [
    {
        "name": "query_signals",
        "description": "Get recent market signal data for a symbol from BigQuery. Returns price change, volume, day range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker e.g. NVDA, AAPL"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_ml_prediction",
        "description": "Get ML signal strength prediction for a symbol. Returns probability of strong move.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker e.g. NVDA, AAPL"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_forecast",
        "description": "Get Prophet 7-day price forecast for a symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker e.g. NVDA, AAPL"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "compare_symbols",
        "description": "Compare multiple symbols side by side on key metrics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tickers to compare e.g. ['NVDA', 'AMD', 'INTC']"
                }
            },
            "required": ["symbols"]
        }
    },
    {
        "name": "get_top_movers",
        "description": "Get top bullish and bearish movers from the signal database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["bullish", "bearish", "both"],
                    "description": "Which movers to return"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results",
                    "default": 5
                }
            },
            "required": ["direction"]
        }
    }
]

def query_signals(symbol: str) -> dict:
    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT symbol, trade_date, signal_text, avg_volume,
               avg_pct_change, day_high, day_low, avg_typical_price
        FROM `{PROJECT_ID}.raw_market_data.signal_embeddings`
        WHERE symbol = '{symbol.upper()}'
        ORDER BY trade_date DESC
        LIMIT 3
    """
    rows = list(client.query(query).result())
    if not rows:
        return {"error": f"No data found for {symbol}"}
    return [dict(row) for row in rows]

def get_ml_prediction(symbol: str) -> dict:
    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT avg_volume, day_high, day_low, avg_pct_change, avg_typical_price
        FROM `{PROJECT_ID}.raw_market_data.signal_embeddings`
        WHERE symbol = '{symbol.upper()}'
        ORDER BY trade_date DESC
        LIMIT 1
    """
    rows = list(client.query(query).result())
    if not rows:
        return {"error": f"No data for {symbol}"}
    row = dict(rows[0])
    try:
        payload = {
            "symbol": symbol.upper(),
            "avg_volume": float(row["avg_volume"]),
            "day_high": float(row["day_high"]),
            "day_low": float(row["day_low"]),
            "avg_pct_change": float(row["avg_pct_change"]),
            "avg_typical_price": float(row["avg_typical_price"]),
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
    except Exception as e:
        return {"error": str(e)}

def get_forecast(symbol: str) -> dict:
    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT forecast_date, predicted_close, lower_bound, upper_bound, trend
        FROM `{PROJECT_ID}.raw_market_data.market_data_forecasts`
        WHERE symbol = '{symbol.upper()}'
        ORDER BY forecast_date ASC
        LIMIT 7
    """
    rows = list(client.query(query).result())
    if not rows:
        return {"error": f"No forecast for {symbol}"}
    return [dict(row) for row in rows]

def compare_symbols(symbols: list) -> dict:
    client = bigquery.Client(project=PROJECT_ID)
    symbols_str = ", ".join([f"'{s.upper()}'" for s in symbols])
    query = f"""
        SELECT symbol, trade_date, avg_pct_change, avg_volume,
               day_high, day_low, avg_typical_price
        FROM `{PROJECT_ID}.raw_market_data.signal_embeddings`
        WHERE symbol IN ({symbols_str})
        ORDER BY trade_date DESC, symbol
    """
    rows = list(client.query(query).result())
    return [dict(row) for row in rows]

def get_top_movers(direction: str, limit: int = 5) -> dict:
    client = bigquery.Client(project=PROJECT_ID)
    if direction == "bullish":
        where = "avg_pct_change > 0"
        order = "avg_pct_change DESC"
    elif direction == "bearish":
        where = "avg_pct_change < 0"
        order = "avg_pct_change ASC"
    else:
        where = "1=1"
        order = "ABS(avg_pct_change) DESC"

    query = f"""
        SELECT symbol, trade_date, avg_pct_change, avg_volume, day_high, day_low
        FROM `{PROJECT_ID}.raw_market_data.signal_embeddings`
        WHERE {where}
        ORDER BY trade_date DESC, {order}
        LIMIT {limit}
    """
    rows = list(client.query(query).result())
    return [dict(row) for row in rows]

def run_tool(tool_name: str, tool_input: dict) -> str:
    try:
        if tool_name == "query_signals":
            result = query_signals(tool_input["symbol"])
        elif tool_name == "get_ml_prediction":
            result = get_ml_prediction(tool_input["symbol"])
        elif tool_name == "get_forecast":
            result = get_forecast(tool_input["symbol"])
        elif tool_name == "compare_symbols":
            result = compare_symbols(tool_input["symbols"])
        elif tool_name == "get_top_movers":
            result = get_top_movers(
                tool_input["direction"],
                tool_input.get("limit", 5)
            )
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
        return str(result)
    except Exception as e:
        return str({"error": str(e)})

def run_agent(question: str) -> dict:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    messages = [{"role": "user", "content": question}]
    tool_calls_log = []

    system = """You are an autonomous financial market analyst agent.
You have access to tools that query real market data from BigQuery.
Use multiple tools to gather comprehensive data before answering.
Always use at least 2-3 tools to give a well-rounded answer.
Be specific — cite prices, percentages, and prediction scores."""

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=system,
            tools=TOOLS,
            messages=messages
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    result = run_tool(tool_name, tool_input)

                    tool_calls_log.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "result": result[:200]
                    })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            final_answer = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_answer = block.text
                    break
            return {
                "answer": final_answer,
                "tool_calls": tool_calls_log
            }

if __name__ == "__main__":
    result = run_agent("Should I watch NVDA or AMD today?")
    print("Tool calls:", len(result["tool_calls"]))
    for tc in result["tool_calls"]:
        print(f"  - {tc['tool']}({tc['input']})")
    print("\nAnswer:", result["answer"])