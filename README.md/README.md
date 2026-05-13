# Financial AI Platform

Real-time financial signal intelligence platform built on GCP.

## Architecture
## Stack
- **Ingestion**: Python + yfinance → Google BigQuery
- **Transform**: dbt (coming Week 2)
- **AI Layer**: Embeddings + RAG chatbot (coming Week 3)
- **Infrastructure**: Terraform (coming Week 2)
- **Monitoring**: Great Expectations (coming Week 2)

## Data
- 15 symbols (expanding to 100+)
- 5-minute OHLCV bars
- Ingested daily at market open

## Setup
```bash
pip install google-cloud-bigquery yfinance pandas
gcloud auth application-default login
python ingestion/ingest_to_bigquery.py
```

## Project Structure
financial-ai-platform/
├── ingestion/          # Data ingestion scripts
├── dataflow/           # Apache Beam pipelines
├── dbt/                # Transformation layer
├── embeddings/         # Vector embedding pipeline
├── rag/                # RAG chatbot
├── ml/                 # Prediction models
├── terraform/          # Infrastructure as code
└── monitoring/         # Data quality checks