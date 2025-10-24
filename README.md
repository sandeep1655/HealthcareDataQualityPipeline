# Serverless Healthcare Data Quality & Compliance Checker

This project demonstrates a robust, automated pipeline for ensuring data quality, standardization, and compliance of healthcare data ingested into a data lake. It acts as a crucial gatekeeper, preventing low-quality or non-compliant data from reaching downstream analytics systems.

## Architecture Overview

The solution leverages AWS serverless services and the Great Expectations framework to create an event-driven data quality workflow:

1.  **Ingestion**: Raw healthcare data (e.g., patient CSV files) is uploaded to an S3 "Raw Data" bucket.
2.  **Trigger**: An S3 ObjectCreated event on the `RawDataBucket` invokes an `InitiatorFunction` Lambda.
3.  **Orchestration**: The `InitiatorFunction` starts an AWS Step Functions state machine, passing the S3 bucket and key of the newly ingested file.
4.  **Data Quality Check**: The Step Functions workflow first invokes the `QualityCheckerFunction` Lambda. This function downloads the raw data and runs a Great Expectations suite against it, checking for common healthcare data issues (e.g., valid patient IDs, correct ICD-10 codes, reasonable dates, age ranges).
5.  **Routing**: Based on the Great Expectations validation result, the Step Functions state machine makes a choice:
    *   **PASS**: If the data passes all quality checks, it proceeds to the `TransformData` step.
    *   **FAIL**: If the data fails any quality checks, it proceeds to the `MoveToQuarantine` step.
6.  **Quarantine**: The `MoveToQuarantine` Lambda function copies the original raw file to a "Quarantined Data" S3 bucket and then deletes it from the `RawDataBucket`. The workflow then ends.
7.  **Transformation & Curated Storage**: For data that passes validation, the `TransformerFunction` Lambda downloads the raw CSV, converts it to Parquet format, and uploads it to a "Curated Data" S3 bucket. The original raw CSV is then deleted from the `RawDataBucket`. The workflow then ends successfully.

```
+-----------------------+
|  S3 Raw Data Bucket   |
| (e.g., patient.csv)   |
+-----------+-----------+
            | ObjectCreate Event
            V
+-----------+-----------+
| Initiator Lambda      |
| (Start Step Function) |
+-----------+-----------+
            | Start Execution
            V
+-------------------------------------------------------------+
|                   AWS Step Functions Workflow               |
|   +-------------------+    +-------------------+            |
|   | RunQualityChecks  | -> | CheckValidation   |            |
|   | (QualityChecker   |    | (Choice State)    |            |
|   |   Lambda)         |    +---------+---------+            |
|   +-------------------+              |                      |
|                                      | Fail                 |
|                                      V                      |
|                               +------+--------+             |
|                               | MoveToQuarantine|           |
|                               | (Mover Lambda)  |           |
|                               +------+--------+             |
|                                      | End (Failure)        |
|                                      V                      |
|         Pass                       +-----------------------+
|         +------------------------->| TransformData         |
|         |                          | (Transformer Lambda)  |
|         V                          +----------+------------+
|   +-----------+                               |            |
|   |           |                               V            |
|   |  Success  |                          +-----------------------+
|   |           |                          |  S3 Curated Data      |
|   +-----------+                          | (e.g., patient.parquet)|
|                                          +-----------------------+
+-------------------------------------------------------------+
```

## AWS Services Used

*   **Amazon S3**: Scalable object storage for raw, quarantined, and curated data.
*   **AWS Lambda**: Serverless compute for event-driven functions (Initiator, Quality Checker, Transformer, Mover).
*   **AWS Step Functions**: Serverless workflow orchestration to manage the multi-step data pipeline with built-in error handling and state management.
*   **AWS IAM**: Manages permissions for Lambda functions and Step Functions to interact with other AWS services.
*   **AWS Serverless Application Model (SAM)**: Infrastructure as Code framework to define and deploy all serverless resources.
*   **Great Expectations**: Open-source data quality framework used within the `QualityCheckerFunction` to define and validate data expectations.

## Generated Files

This project contains the following files and directories:

```
.gitignore
README.md
requirements.txt
samconfig.toml
template.yaml

great_expectations/
├── checkpoints/
│   └── health_data_checkpoint.py  # Dummy file, checkpoint defined in great_expectations.yml
├── great_expectations.yml
└── expectations/
    └── health_data_suite.json

sample_data/
├── patient_records.csv        # Sample good data
└── patient_records_bad.csv    # Sample bad data to test quarantine

scripts/
└── ingest.py                  # Helper script to simulate data ingestion to S3

src/
├── initiator/
│   └── app.py                 # Lambda to trigger Step Functions from S3 event
├── mover/
│   └── app.py                 # Lambda to move failed files to quarantine
├── quality_checker/
│   └── app.py                 # Lambda to run Great Expectations data quality checks
│   └── great_expectations/    # Great Expectations project embedded for deployment
│       ├── ...                # (Contents of great_expectations/ - same as root GE dir)
└── transformer/
    └── app.py                 # Lambda to transform CSV to Parquet
```

## Prerequisites

Before deploying and running this project, ensure you have the following installed:

*   **AWS CLI**: Configured with credentials that have sufficient permissions to deploy and manage serverless applications (`AdministratorAccess` for simplicity, or more granular permissions).
*   **AWS SAM CLI**: Version 1.100.0 or later.
*   **Python 3.8+**: The runtime for the Lambda functions and helper scripts.
*   **Docker**: Required by `sam build --use-container` to build Lambda functions with Python dependencies.

## Deployment Steps

1.  **Clone the repository** (if applicable) or create the project structure from the generated files.
2.  **Build the SAM application**: This command packages your Lambda code and dependencies.
    ```bash
    sam build --use-container
    ```
    *Note: `--use-container` ensures that dependencies are built in a Lambda-like environment, preventing compatibility issues.*
3.  **Deploy the SAM application**: This command deploys your serverless resources to AWS.
    ```bash
    sam deploy --guided
    ```
    *   When prompted for `Stack Name`, provide a unique name (e.g., `HealthcareDataQualityStack`).
    *   For `AWS Region`, choose your desired AWS region (e.g., `us-east-1`).
    *   Confirm changes before deployment (yes).
    *   Allow SAM CLI to create IAM roles (yes).
    *   Save arguments to `samconfig.toml` (yes).

    The deployment will create the S3 buckets, Lambda functions, IAM roles, and the Step Functions state machine.

4.  **Retrieve S3 Bucket Name**: After successful deployment, SAM CLI will output the names of the created S3 buckets. Note the `RawDataBucketName` as you'll need it for ingestion.
    Alternatively, you can find the bucket names in the AWS S3 console or by running:
    ```bash
    aws cloudformation describe-stacks --stack-name <YOUR_STACK_NAME> --query 'Stacks[0].Outputs'
    ```

## Running the Project

To test the data quality workflow, you will simulate data ingestion using the provided `ingest.py` script.

### 1. Ingest Good Data (Expected: Pass Validation, Transform to Parquet)

Use the `patient_records.csv` file, which is designed to pass all Great Expectations checks.

```bash
python scripts/ingest.py <YourRawDataBucketName> sample_data/patient_records.csv
```

**Expected Outcome:**

*   The file `patient_records.csv` will be uploaded to your `RawDataBucket`.
*   This will trigger the Step Functions workflow.
*   The `QualityCheckerFunction` will validate the data, and it should pass.
*   The `TransformerFunction` will convert the `patient_records.csv` to `patient_records.parquet` and upload it to the `CuratedDataBucket`.
*   The original `patient_records.csv` will be deleted from the `RawDataBucket`.
*   You should see `patient_records.parquet` in your `CuratedDataBucket`.
*   Monitor the AWS Step Functions console for the execution status. It should succeed.

### 2. Ingest Bad Data (Expected: Fail Validation, Move to Quarantine)

Use the `patient_records_bad.csv` file, which contains deliberately introduced data quality issues to fail the Great Expectations checks.

```bash
python scripts/ingest.py <YourRawDataBucketName> sample_data/patient_records_bad.csv
```

**Expected Outcome:**

*   The file `patient_records_bad.csv` will be uploaded to your `RawDataBucket`.
*   This will trigger the Step Functions workflow.
*   The `QualityCheckerFunction` will validate the data, and it should fail due to the bad data.
*   The `MoveToQuarantine` Lambda will copy `patient_records_bad.csv` to the `QuarantinedDataBucket`.
*   The original `patient_records_bad.csv` will be deleted from the `RawDataBucket`.
*   You should see `patient_records_bad.csv` in your `QuarantinedDataBucket`.
*   Monitor the AWS Step Functions console for the execution status. The execution should end with a 'Failed' status, specifically at the `MoveToQuarantine` step.

## Cleanup

To remove all deployed AWS resources and avoid incurring unwanted charges, run the following command:

```bash
sam delete --stack-name <YOUR_STACK_NAME>
```

Replace `<YOUR_STACK_NAME>` with the stack name you used during deployment (e.g., `HealthcareDataQualityStack`). Confirm the deletion when prompted.