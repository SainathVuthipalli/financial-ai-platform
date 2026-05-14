import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition
import json
import logging
from datetime import datetime, timezone

PROJECT_ID = "financial-ai-platform-sv"
REGION = "us-central1"
PUBSUB_TOPIC = f"projects/{PROJECT_ID}/topics/market-data-stream"
BQ_TABLE = f"{PROJECT_ID}:raw_market_data.market_data_raw"
TEMP_LOCATION = f"gs://{PROJECT_ID}-data-lake/temp"

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
            record = json.loads(element.decode("utf-8"))
            yield record
        except Exception as e:
            logging.error(f"Failed to parse: {element} — {e}")

class ValidateRecord(beam.DoFn):
    def process(self, element):
        # Validate required fields
        if not element.get("symbol"):
            logging.warning(f"Missing symbol: {element}")
            return
        if not element.get("timestamp"):
            logging.warning(f"Missing timestamp: {element}")
            return
        if element.get("volume", 0) <= 0:
            logging.warning(f"Invalid volume for {element.get('symbol')}")
            return
        yield element

class EnrichRecord(beam.DoFn):
    def process(self, element):
        # Add ingestion timestamp if missing
        if not element.get("ingested_at"):
            element["ingested_at"] = datetime.now(timezone.utc).isoformat()

        # Add derived fields
        if element.get("open") and element.get("close"):
            element["pct_change"] = round(
                (element["close"] - element["open"]) / element["open"] * 100, 4
            )
        yield element

def run_streaming_pipeline():
    """
    Streaming pipeline: Pub/Sub → Dataflow → BigQuery
    Reads market data from Pub/Sub topic in real-time,
    validates, enriches, and writes to BigQuery.
    """
    options = PipelineOptions([
        f"--project={PROJECT_ID}",
        f"--region={REGION}",
        f"--temp_location={TEMP_LOCATION}",
        f"--job_name=market-data-streaming-pipeline",
        "--runner=DataflowRunner",
        "--streaming",
        "--enable_streaming_engine",
    ])
    options.view_as(StandardOptions).streaming = True

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
    """
    Batch pipeline: GCS → Dataflow → BigQuery
    For backfilling historical data from Cloud Storage.
    """
    options = PipelineOptions([
        f"--project={PROJECT_ID}",
        f"--region={REGION}",
        f"--temp_location={TEMP_LOCATION}",
        f"--job_name=market-data-batch-pipeline",
        "--runner=DataflowRunner",
    ])

    input_path = f"gs://{PROJECT_ID}-data-lake/raw/*.json"

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

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "streaming"
    if mode == "batch":
        print("Running batch pipeline...")
        run_batch_pipeline()
    else:
        print("Running streaming pipeline...")
        run_streaming_pipeline()