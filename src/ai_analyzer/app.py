import json
import os
import io
import csv
import boto3
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3 = boto3.client('s3')

def lambda_handler(event, context):
    logger.info(f"AI Analyzer received event: {json.dumps(event)}")

    curated_bucket = event.get("s3_output_bucket")
    curated_key = event.get("s3_output_key")

    insights_bucket = os.environ.get("InsightsBucketName")
    prefix = os.environ.get("InsightsPrefix", "insights/")

    obj = s3.get_object(Bucket=curated_bucket, Key=curated_key)
    lines = obj['Body'].read().decode('utf-8').splitlines()
    reader = csv.DictReader(lines)

    total, anomalies = 0, 0
    fields_flagged, anomaly_rows = set(), []

    for row in reader:
        total += 1
        try:
            age = int(row.get("age", -1))
        except:
            age = -1
        if age < 0 or age > 120:
            anomalies += 1
            fields_flagged.add("age")
            anomaly_rows.append({"idx": total, "reason": "age_out_of_range"})

        ad = row.get("admission_date")
        dd = row.get("discharge_date")
        if ad and dd and ad > dd:
            anomalies += 1
            fields_flagged.update(["admission_date", "discharge_date"])
            anomaly_rows.append({"idx": total, "reason": "discharge_before_admission"})

    report = {
        "file": curated_key,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "records": total,
        "anomalies_detected": anomalies,
        "fields_flagged": list(fields_flagged),
        "sample_anomalies": anomaly_rows[:20]
    }

    report_key = f"{prefix}{os.path.basename(curated_key).replace('.csv', '')}_insight_report.json"
    s3.put_object(Bucket=insights_bucket, Key=report_key, Body=json.dumps(report, indent=2).encode('utf-8'))

    return {"statusCode": 200, "anomalies_detected": anomalies}
