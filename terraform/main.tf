terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = "financial-ai-platform-sv"
  region  = "us-central1"
}

# BigQuery Dataset - Raw market data
resource "google_bigquery_dataset" "raw_market_data" {
  dataset_id    = "raw_market_data"
  friendly_name = "Raw Market Data"
  description   = "Raw OHLCV market data ingested from yfinance"
  location      = "US"
}

# BigQuery Dataset - dbt transforms
resource "google_bigquery_dataset" "dbt_transforms" {
  dataset_id    = "dbt_transforms"
  friendly_name = "DBT Transforms"
  description   = "Transformed market data models built with dbt"
  location      = "US"
}

# BigQuery Table - Raw market data
resource "google_bigquery_table" "market_data_raw" {
  dataset_id = google_bigquery_dataset.raw_market_data.dataset_id
  table_id   = "market_data_raw"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  clustering = ["symbol"]

  schema = jsonencode([
    { name = "symbol",       type = "STRING",    mode = "REQUIRED" },
    { name = "timestamp",    type = "TIMESTAMP",  mode = "REQUIRED" },
    { name = "open",         type = "FLOAT64",   mode = "NULLABLE" },
    { name = "high",         type = "FLOAT64",   mode = "NULLABLE" },
    { name = "low",          type = "FLOAT64",   mode = "NULLABLE" },
    { name = "close",        type = "FLOAT64",   mode = "NULLABLE" },
    { name = "volume",       type = "INT64",     mode = "NULLABLE" },
    { name = "ingested_at",  type = "TIMESTAMP", mode = "NULLABLE" }
  ])
}

# Pub/Sub Topic - Market data stream
resource "google_pubsub_topic" "market_data" {
  name = "market-data-stream"
}

# Cloud Storage Bucket - Data lake
resource "google_storage_bucket" "data_lake" {
  name     = "financial-ai-platform-sv-data-lake"
  location = "US"

  lifecycle_rule {
    condition { age = 90 }
    action    { type = "Delete" }
  }
}