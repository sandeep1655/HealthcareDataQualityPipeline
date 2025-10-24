import json
import os
import io
import boto3
import pandas as pd
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3 = boto3.client('s3')

def lambda_handler(event, context):
    logger.info(f"Transformer event: {json.dumps(event)}")
    source_bucket = event['s3_input_bucket']
    source_key = event['s3_input_key']
    destination_bucket = os.environ['CuratedDataBucketName']

    try:
        obj = s3.get_object(Bucket=source_bucket, Key=source_key)
        df = pd.read_csv(io.BytesIO(obj['Body'].read()))
        # Example cleanup
        df.columns = [c.strip().lower() for c in df.columns]
        curated_key = f"curated/{os.path.basename(source_key)}"

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        s3.put_object(Bucket=destination_bucket, Key=curated_key, Body=csv_buffer.getvalue())
        s3.delete_object(Bucket=source_bucket, Key=source_key)

        return {
            "statusCode": 200,
            "s3_output_bucket": destination_bucket,
            "s3_output_key": curated_key
        }

    except Exception as e:
        logger.error(f"Transformer error: {e}")
        raise
