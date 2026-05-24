# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A cloud-native financial market analysis platform on GCP. It ingests real-time market data (yfinance → BigQuery), transforms it (dbt), trains ML models (RandomForest + Prophet), generates embeddings, and exposes an AI-powered dashboard backed by Claude API.

## Common Commands

```bash
# Dashboard (FastAPI backend + HTML frontend)
python dashboard/main.py

# Data ingestion
python ingestion/ingest_to_bigquery.py      # Watchlist (15 symbols, 5-min bars)
python ingestion/daily_incremental.py       # Full S&P 500 (135 symbols)
python ingestion/scheduler.py              # Scheduled run at 9:35 AM ET weekdays

# dbt transforms
dbt run                                    # Run all models
dbt test                                   # Run data quality tests

# ML
python ml/signal_classifier.py             # Train RandomForest, saves signal_model.pkl
python ml/forecaster.py                    # Generate 7-day Prophet forecasts

# Embeddings
python embeddings/embed_signals.py

# Dataflow pipeline (Apache Beam)
python dataflow/market_pipeline.py local       # Local DirectRunner (no GCP)
python dataflow/market_pipeline.py batch       # Batch mode on Cloud Dataflow
python dataflow/market_pipeline.py streaming   # Streaming from Pub/Sub

# Monitoring
python monitoring/data_quality.py

# AI components
python rag/chatbot.py                      # Interactive Claude-backed chatbot
python agents/financial_agent.py           # Autonomous agent with 5 tools
```

## Architecture

**Data flow:** yfinance → BigQuery (`raw_market_data.market_data_raw`) → dbt staging/marts → ML models + embeddings → FastAPI dashboard + Claude AI

### Key components

| Component | Path | Purpose |
|-----------|------|---------|
| Ingestion | `ingestion/` | yfinance → BigQuery; daily incremental + historical backfill |
| Dataflow | `dataflow/market_pipeline.py` | Apache Beam with streaming/batch/local modes |
| dbt | `dbt/` | Staging (views) → Marts (tables); raw → clean aggregates |
| ML | `ml/` | RandomForest signal classifier + Prophet 7-day forecasting |
| Embeddings | `embeddings/embed_signals.py` | 256-dim signal embeddings (SHA256-based) stored in BigQuery |
| RAG | `rag/chatbot.py` | Claude Sonnet 4.6 with BigQuery signal context |
| Agent | `agents/financial_agent.py` | Tool-using Claude agent with 5 financial tools |
| Dashboard | `dashboard/` | FastAPI backend + HTML/JS frontend |
| Terraform | `terraform/` | GCP IaC (BigQuery, Pub/Sub, GCS, us-central1) |
| Monitoring | `monitoring/data_quality.py` | 7-point post-ingestion quality checks |

### BigQuery schema
- `raw_market_data.market_data_raw` — partitioned by day, clustered by symbol
- `dbt_transforms.stg_market_data` (view) — cleaned with derived fields
- `dbt_transforms.mart_symbol_stats` (table) — daily per-symbol aggregates
- `market_data_forecasts` — Prophet 7-day forecasts
- `signal_embeddings` — 256-dim embeddings with signal metadata

### Claude API usage
- `rag/chatbot.py` and `agents/financial_agent.py` both use `claude-sonnet-4-6`
- `dashboard/main.py` exposes `/api/chat` (single-turn) and `/api/agent` (tool-use loop)
- Agent tools: `query_signals`, `get_ml_prediction`, `get_forecast`, `compare_symbols`, `get_top_movers`

### dbt model layers
- **Staging** (`dbt/models/staging/`): Views over raw source; adds `price_range`, `pct_change`, `typical_price`, `trade_date`
- **Marts** (`dbt/models/marts/`): Tables with daily aggregates per symbol

## GCP Infrastructure

- **Project region:** us-central1 (Dataflow uses us-east1 to avoid zone capacity issues)
- **Terraform state:** `.terraform/` and `*.tfstate` are gitignored; `credentials.json` is also gitignored
- **CI/CD:** GitHub Actions — daily ingestion at 14:35 UTC (9:35 AM ET) weekdays; manual workflow dispatch for Dataflow
- **GCP secret:** `GCP_CREDENTIALS` in GitHub Actions secrets

## ML Notes

- Signal classifier threshold: >0.05% price change = "strong move expected"
- Classifier features: `range_pct`, `volume_zscore`, `day_of_week`, `abs_pct_change`, `avg_price_range`, `total_bars`
- Trained model saved to `ml/signal_model.pkl`; also deployed as Cloud Function REST endpoint
- Prophet forecasts: 7 business days, 80% confidence intervals, `weekly_seasonality=True`, `yearly_seasonality=True`
