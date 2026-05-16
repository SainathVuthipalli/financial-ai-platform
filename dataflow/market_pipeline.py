import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions, GoogleCloudOptions, SetupOptions
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition
import json
import logging
import sys
from datetime import datetime, timezone

PROJECT_ID = "financial-ai-platform-sv"
REGION = "us-east1"
PUBSUB_TOPIC = f"projects/{PROJECT_ID}/topics/market-data-stream"
BQ_TABLE = f"{PROJECT_ID}:raw_market_data.market_data_raw"
TEMP_LOCATION = f"gs://{PROJECT_ID}-data-lake/temp"
STAGING_LOCATION = f"gs://{PROJECT_ID}-data-lake/staging"

TABLE_SCHEMA = {
    "fields": [
        {"name": "symbol",      "type": "STRING",    "mode": "REQUIRED"},
        {"name": "timestamp",   "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "open",        "type": "FLOAT64",   "mode": "NULLABLE"},
        {"name": "high",        "type": "FLOAT64",   "mode": "NULLABLE"},
        {"name": "low",         "type": "FLOAT64",   "mode": "NULLABLE"},
        {"name": "close",       "type": "FLOAT64",   "mode": "NULLABLE"},
        {"name": "volume",      "type": "INT64",     "mode": "NULLABLE"},
        {"name": "ingested_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ]
}

class ParseMarketData(beam.DoFn):
    def process(self, element):
        try:
            if isinstance(element, bytes):
                element = element.decode("utf-8")
            record = json.loads(element)
            yield record
        except Exception as e:
            logging.error(f"Failed to parse: {element} — {e}")

class ValidateRecord(beam.DoFn):
    def process(self, element):
        if not element.get("symbol"):
            return
        if not element.get("timestamp"):
            return
        if element.get("volume", 0) <= 0:
            return
        yield element

class EnrichRecord(beam.DoFn):
    def process(self, element):
        if not element.get("ingested_at"):
            element["ingested_at"] = datetime.now(timezone.utc).isoformat()
        yield element

def run_streaming_pipeline():
    options = PipelineOptions()
    gcp_options = options.view_as(GoogleCloudOptions)
    gcp_options.project = PROJECT_ID
    gcp_options.region = REGION
    gcp_options.temp_location = TEMP_LOCATION
    gcp_options.staging_location = STAGING_LOCATION
    gcp_options.job_name = "market-data-streaming"
    options.view_as(StandardOptions).runner = "DataflowRunner"
    options.view_as(StandardOptions).streaming = True
    options.view_as(SetupOptions).save_main_session = True

    print(f"Starting streaming pipeline — reading from {PUBSUB_TOPIC}")

    with beam.Pipeline(options=options) as p:
        (
            p
            | "Read from Pub/Sub" >> beam.io.ReadFromPubSub(topic=PUBSUB_TOPIC)
            | "Parse JSON"        >> beam.ParDo(ParseMarketData())
            | "Validate Records"  >> beam.ParDo(ValidateRecord())
            | "Enrich Records"    >> beam.ParDo(EnrichRecord())
            | "Write to BigQuery" >> WriteToBigQuery(
                table=BQ_TABLE,
                schema=TABLE_SCHEMA,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )

def run_batch_pipeline():
    """Batch mode — reads from GCS, writes to BigQuery"""
    options = PipelineOptions()
    gcp_options = options.view_as(GoogleCloudOptions)
    gcp_options.project = PROJECT_ID
    gcp_options.region = REGION
    gcp_options.temp_location = TEMP_LOCATION
    gcp_options.staging_location = STAGING_LOCATION
    gcp_options.job_name = "market-data-batch"
    options.view_as(StandardOptions).runner = "DataflowRunner"
    options.view_as(SetupOptions).save_main_session = True

    input_path = f"gs://{PROJECT_ID}-data-lake/raw/*.json"
    print(f"Starting batch pipeline — reading from {input_path}")

    with beam.Pipeline(options=options) as p:
        (
            p
            | "Read from GCS"     >> beam.io.ReadFromText(input_path)
            | "Parse JSON"        >> beam.Map(json.loads)
            | "Validate Records"  >> beam.ParDo(ValidateRecord())
            | "Enrich Records"    >> beam.ParDo(EnrichRecord())
            | "Write to BigQuery" >> WriteToBigQuery(
                table=BQ_TABLE,
                schema=TABLE_SCHEMA,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )

def run_local_test():
    """Local DirectRunner test — no GCP needed"""
    print("Running local pipeline test with DirectRunner...")
    options = PipelineOptions()
    options.view_as(StandardOptions).runner = "DirectRunner"

    test_records = [
        json.dumps({"symbol": "NVDA", "timestamp": "2026-05-15T10:00:00", "open": 229.0, "high": 236.0, "low": 228.0, "close": 233.0, "volume": 1000000}),
        json.dumps({"symbol": "AAPL", "timestamp": "2026-05-15T10:00:00", "open": 297.0, "high": 300.0, "low": 296.0, "close": 298.0, "volume": 500000}),
    ]

    with beam.Pipeline(options=options) as p:
        results = (
            p
            | "Create test data"  >> beam.Create(test_records)
            | "Parse JSON"        >> beam.ParDo(ParseMarketData())
            | "Validate Records"  >> beam.ParDo(ValidateRecord())
            | "Enrich Records"    >> beam.ParDo(EnrichRecord())
            | "Print results"     >> beam.Map(print)
        )

    print("Local test complete.")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "local"
    if mode == "streaming":
        run_streaming_pipeline()
    elif mode == "batch":
        run_batch_pipeline()
    else:
        run_local_test()