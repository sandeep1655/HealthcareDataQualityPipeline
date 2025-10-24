import boto3
import pandas as pd
import io
import os
from datetime import datetime

s3 = boto3.client("s3")

def lambda_handler(event, context):
    """
    Transformer Lambda
    ------------------------------------------
    - Reads raw healthcare CSV file from S3
    - Cleans and standardizes data
    - Performs quality checks (nulls, invalid ages, dates)
    - Uploads cleaned file to Curated S3 bucket
    - Returns validation result for Step Functions
    """

    print("🔹 Received event:", event)

    # Extract parameters from Step Functions input
    s3_input_bucket = event.get("s3_input_bucket")
    s3_input_key = event.get("s3_input_key")
    curated_bucket = os.environ.get("CuratedDataBucketName")

    # Initialize validation result
    validation_passed = True
    issues = []

    try:
        # 1️⃣ Read raw CSV from S3
        print(f"📥 Reading file: s3://{s3_input_bucket}/{s3_input_key}")
        obj = s3.get_object(Bucket=s3_input_bucket, Key=s3_input_key)
        df = pd.read_csv(io.BytesIO(obj["Body"].read()))

        # 2️⃣ Basic schema validation
        expected_columns = {"patient_id", "age", "gender", "admission_date", "discharge_date", "diagnosis"}
        missing_cols = expected_columns - set(df.columns)
        if missing_cols:
            validation_passed = False
            issues.append(f"Missing columns: {', '.join(missing_cols)}")

        # 3️⃣ Data cleaning and standardization
        df.columns = df.columns.str.strip().str.lower()  # normalize headers
        df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        if "gender" in df.columns:
            df["gender"] = df["gender"].str.title()

        # Convert date columns safely
        for col in ["admission_date", "discharge_date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # 4️⃣ Quality checks
        if "age" in df.columns:
            invalid_ages = df[(df["age"] < 0) | (df["age"] > 120)]
            if not invalid_ages.empty:
                validation_passed = False
                issues.append(f"Invalid ages detected in {len(invalid_ages)} rows.")

        if "admission_date" in df.columns and "discharge_date" in df.columns:
            bad_dates = df[df["discharge_date"] < df["admission_date"]]
            if not bad_dates.empty:
                validation_passed = False
                issues.append(f"Discharge before admission found in {len(bad_dates)} rows.")

        # Check for nulls in required fields
        required_fields = ["patient_id", "age", "admission_date", "discharge_date"]
        missing_values = df[required_fields].isnull().sum()
        if missing_values.any():
            validation_passed = False
            issues.append(f"Missing values found in: {', '.join(missing_values[missing_values > 0].index)}")

        # Drop duplicates
        df.drop_duplicates(inplace=True)

        # 5️⃣ Save cleaned data to Curated bucket
        curated_key = f"curated/{os.path.basename(s3_input_key)}"
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        s3.put_object(Bucket=curated_bucket, Key=curated_key, Body=csv_buffer.getvalue())
        print(f"✅ Cleaned file uploaded to: s3://{curated_bucket}/{curated_key}")

        # 6️⃣ Return result
        result = {
            "statusCode": 200,
            "validation_passed": validation_passed,
            "curated_key": curated_key,
            "issues_found": issues,
        }

        print("🔸 Transformation Summary:", result)
        return result

    except Exception as e:
        print("❌ Error during transformation:", str(e))
        return {
            "statusCode": 500,
            "validation_passed": False,
            "error": str(e),
        }
