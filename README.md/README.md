markdown# Financial AI Platform

> Real-time financial signal intelligence platform built on GCP — institutional-grade market data pipeline with AI/RAG layer.

[![Daily Ingestion](https://github.com/SainathVuthipalli/financial-ai-platform/actions/workflows/daily_ingestion.yml/badge.svg)](https://github.com/SainathVuthipalli/financial-ai-platform/actions/workflows/daily_ingestion.yml)

## Architecture

![Architecture](docs/architecture.svg)

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
Q: Which symbols look most volatile based on their day range?
A: Top volatile names:
COIN  ~7.05% range ($195 - $209)
MSTR  ~6.15% range ($174 - $185)
HOOD  ~4.34% range ($75 - $78)

## Setup

```bash
# Install dependencies
pip install google-cloud-bigquery yfinance pandas dbt-bigquery db-dtypes

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
├── .github/workflows/     # GitHub Actions CI/CD (daily at 9:35 AM ET)
├── ingestion/             # yfinance → BigQuery pipeline
├── dataflow/              # Apache Beam streaming + batch pipelines
├── dbt/
│   └── models/
│       ├── staging/       # stg_market_data (view)
│       └── marts/         # mart_symbol_stats (table)
├── embeddings/            # Signal embedding pipeline → BigQuery
├── rag/                   # RAG chatbot (Claude API + BigQuery)
├── monitoring/            # 7 data quality assertions + Airflow DAG
├── terraform/             # GCP infrastructure as code
└── docs/                  # Architecture diagrams

## GCP Resources

All provisioned via Terraform:

| Resource | Details |
|----------|---------|
| BigQuery `raw_market_data` | Partitioned by DAY, clustered by symbol |
| BigQuery `dbt_transforms` | Staging views + mart tables |
| Pub/Sub `market-data-stream` | Real-time market data topic |
| GCS `data-lake` | 90-day lifecycle, temp storage |

## How the RAG Chatbot Works
User question
↓
Fetch recent signals from BigQuery (signal_embeddings table)
↓
Build context string from signal_text fields
↓
Claude API call with market data injected as system context
↓
Grounded answer using only real BigQuery data

## Roadmap

- [ ] ML signal prediction model (Cloud Function endpoint)
- [ ] Semantic vector search using embedding similarity
- [ ] Expand watchlist to 100+ symbols
- [ ] Real-time Dataflow streaming deployment
- [ ] Looker Studio dashboard over mart tables