## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         DATA SOURCES                │
                    │  yfinance · Pub/Sub · Dataflow       │
                    │  GitHub Actions (9:35 AM ET daily)   │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │        BIGQUERY RAW LAYER           │
                    │     raw_market_data.market_data_raw  │
                    │  Partitioned by DAY · Clustered by   │
                    │  symbol · 15 symbols · 5-min bars    │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │         DBT TRANSFORMS              │
                    │  stg_market_data (view)              │
                    │  mart_symbol_stats (table)           │
                    │  4 data tests · 7 quality checks     │
                    └──────┬───────────────────┬──────────┘
                           │                   │
           ┌───────────────▼───┐         ┌─────▼──────────────┐
           │   EMBEDDINGS      │         │   TERRAFORM IaC    │
           │ 256-dim vectors   │         │ BigQuery · Pub/Sub  │
           │ in BigQuery       │         │ GCS · provisioned   │
           └───────┬───────────┘         └────────────────────┘
                   │
           ┌───────▼───────────┐
           │   RAG CHATBOT     │
           │ Claude API        │
           │ + BigQuery data   │
           └───────────────────┘
```