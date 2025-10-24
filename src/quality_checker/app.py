import json
import os
import io
import logging
import pandas as pd
import boto3
import great_expectations as ge
from great_expectations.checkpoint import Checkpoint

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    logger.info(f"Received event for quality checker: {json.dumps(event)}")
    s3_bucket = event['s3_bucket']
    s3_key = event['s3_key']

    try:
        # Download the S3 object
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        data_body = response['Body'].read().decode('utf-8')
        
        # Load data into pandas DataFrame
        df = pd.read_csv(io.StringIO(data_body))
        
        # Initialize Great Expectations DataContext
        # The 'great_expectations' directory is expected to be a sibling to app.py
        # within the Lambda deployment package (i.e., at /var/task/).
        ge_context = ge.data_context.DataContext()

        # Create a temporary GE Dataframe (Validator) from the pandas DataFrame
        batch_request = {
            "datasource_name": "my_s3_datasource",
            "data_connector_name": "default_runtime_data_connector",
            "data_asset_name": "patient_records",
            "runtime_parameters": {"batch_data": df},
            "batch_identifiers": {"pipeline_run_id": context.aws_request_id}
        }

        # Get the checkpoint
        checkpoint_name = "health_data_checkpoint"
        checkpoint = ge_context.get_checkpoint(checkpoint_name=checkpoint_name)

        # Run the checkpoint
        checkpoint_result = checkpoint.run(batch_request=batch_request)

        validation_passed = checkpoint_result.success
        logger.info(f"Validation result for {s3_key}: {'PASS' if validation_passed else 'FAIL'}")

        return {
            "s3_input_bucket": s3_bucket,
            "s3_input_key": s3_key,
            "validation_passed": validation_passed
        }

    except Exception as e:
        logger.error(f"Error during quality check for {s3_key}: {e}")
        # Re-raise to fail the Step Functions task, which will then route to quarantine.
        # The SFN workflow itself handles the routing based on success/failure of this task.
        raise e
