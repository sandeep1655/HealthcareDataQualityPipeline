import json
import os
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3 = boto3.client('s3')

def lambda_handler(event, context):
    source_bucket = event.get('s3_input_bucket')
    source_key = event.get('s3_input_key')
    dest_bucket = os.environ['QuarantinedDataBucketName']

    try:
        copy_source = {'Bucket': source_bucket, 'Key': source_key}
        s3.copy_object(CopySource=copy_source, Bucket=dest_bucket, Key=source_key)
        s3.delete_object(Bucket=source_bucket, Key=source_key)
        logger.info(f"Moved {source_key} → quarantine")
        return {"statusCode": 200, "body": f"File moved to {dest_bucket}"}
    except Exception as e:
        logger.error(f"Error moving file: {e}")
        raise
