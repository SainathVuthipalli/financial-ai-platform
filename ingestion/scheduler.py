import schedule
import time
import subprocess
from datetime import datetime
import pytz

def run_ingestion():
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')} ET] Running ingestion...")
    subprocess.run(["python", "ingestion/ingest_to_bigquery.py"])

# Run at 9:35 AM ET every weekday (5 mins after market open)
schedule.every().monday.at("09:35").do(run_ingestion)
schedule.every().tuesday.at("09:35").do(run_ingestion)
schedule.every().wednesday.at("09:35").do(run_ingestion)
schedule.every().thursday.at("09:35").do(run_ingestion)
schedule.every().friday.at("09:35").do(run_ingestion)

if __name__ == "__main__":
    print("Scheduler started. Waiting for market open...")
    run_ingestion()  # Run once immediately on start
    while True:
        schedule.run_pending()
        time.sleep(60)