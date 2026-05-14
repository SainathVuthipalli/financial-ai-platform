from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "sainath",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="financial_data_pipeline",
    default_args=default_args,
    description="Daily financial market data pipeline",
    schedule_interval="35 14 * * 1-5",  # 9:35 AM ET weekdays
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["financial", "market-data", "production"],
) as dag:

    ingest = BashOperator(
        task_id="ingest_market_data",
        bash_command="python /home/airflow/gcs/dags/ingestion/ingest_to_bigquery.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /home/airflow/gcs/dags/dbt && dbt run --profiles-dir /home/airflow/gcs/dags/dbt",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /home/airflow/gcs/dags/dbt && dbt test --profiles-dir /home/airflow/gcs/dags/dbt",
    )

    data_quality = BashOperator(
        task_id="data_quality_checks",
        bash_command="python /home/airflow/gcs/dags/monitoring/data_quality.py",
    )

    # Pipeline order
    ingest >> dbt_run >> dbt_test >> data_quality