import json
import os
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sfn = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ['StepFunctionsStateMachineArn']

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")

    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        input_data = {"s3_input_bucket": bucket, "s3_input_key": key}

        try:
            sfn.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                input=json.dumps(input_data),
                name=f"{key.replace('/', '-')}-{context.aws_request_id}"
            )
            logger.info(f"Started Step Functions for file: {key}")
        except Exception as e:
            logger.error(f"Error starting Step Function for {key}: {e}")
            raise

    return {"statusCode": 200, "body": "Step Function started successfully"}
