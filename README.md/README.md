Market Data (yfinance / Polygon.io)
↓
Pub/Sub Topic  ←→  Dataflow (Apache Beam)
↓
BigQuery raw_market_data
(partitioned by DAY, clustered by symbol)
↓
dbt transforms
stg_market_data → mart_symbol_stats
↓                ↓
Embeddings pipeline   Data quality
(signal_embeddings)   (7 assertions)
↓
RAG Chatbot
(Claude API + BigQuery)

## Stack

| Layer | Technology |
|-------|-----------|
| Ingestion | Python + yfinance → BigQuery |
| Streaming | Apache Beam / Dataflow + Pub/Sub |
| Transformation | dbt Core (staging + marts) |
| Infrastructure | Terraform (BigQuery, GCS, Pub/Sub) |
| Orchestration | GitHub Actions + Airflow DAG |
| Monitoring | Custom data quality checks (7 assertions) |
| Embeddings | 256-dim signal vectors in BigQuery |
| AI Layer | RAG chatbot powered by Claude API |

## Features

- **15 symbols** tracked with 5-minute OHLCV bars
- **Automated daily pipeline** runs at 9:35 AM ET via GitHub Actions
- **dbt models** with staging views, mart tables, and 4 data tests
- **7 data quality checks** — null rates, row counts, price validation
- **Signal embeddings** stored in BigQuery for vector similarity search
- **RAG chatbot** answers natural language questions about market signals
- **Terraform IaC** — all GCP resources provisioned as code

## RAG Chatbot Demo
Q: Which symbols had the highest percentage change recently?
A: Based on signal data for May 14, 2026:
🟢 MSTR +0.17%, COIN +0.14%, NVDA +0.11% (high volume)
🔴 AMZN -0.03%, AAPL -0.01%
Notable: NVDA is the only high-volume signal — 3.9M avg volume

## Setup

```bash
# Install dependencies
pip install google-cloud-bigquery yfinance pandas dbt-bigquery

# Authenticate to GCP
gcloud auth application-default login

# Run ingestion
python ingestion/ingest_to_bigquery.py

# Run dbt transforms
cd dbt && dbt run && dbt test

# Run data quality checks
python monitoring/data_quality.py

# Run RAG chatbot
export ANTHROPIC_API_KEY=your_key
python rag/chatbot.py
```

## Project Structure
financial-ai-platform/
├── .github/workflows/     # GitHub Actions CI/CD
├── ingestion/             # yfinance → BigQuery pipeline
├── dataflow/              # Apache Beam streaming pipeline
├── dbt/
│   └── models/
│       ├── staging/       # stg_market_data
│       └── marts/         # mart_symbol_stats
├── embeddings/            # Signal embedding pipeline
├── rag/                   # RAG chatbot (Claude + BigQuery)
├── monitoring/            # Data quality checks + Airflow DAG
└── terraform/             # GCP infrastructure as code

## GCP Resources

All provisioned via Terraform:
- BigQuery dataset `raw_market_data` — partitioned + clustered table
- BigQuery dataset `dbt_transforms` — staging views + mart tables
- Pub/Sub topic `market-data-stream`
- Cloud Storage bucket `financial-ai-platform-sv-data-lake`

## Roadmap

- [ ] ML signal prediction model (Cloud Function endpoint)
- [ ] Semantic vector search in RAG layer
- [ ] Expand to 100+ symbols
- [ ] Real-time Dataflow streaming deployment