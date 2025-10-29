import uuid
import json
import boto3
from fastapi import HTTPException
from app.settings import (
    AWS_DEFAULT_REGION,
    AWS_STEP_FUNCTION_ARN,
    AWS_S3_BUCKET_NAME,
)

stepfunctions_client = boto3.client("stepfunctions", region_name=AWS_DEFAULT_REGION)


def start_single_analysis(s3_key: str, project_name: str):
    """Trigger Step Function for a single uploaded file."""
    try:
        payload = {
            "detail": {
                "bucket": {"name": AWS_S3_BUCKET_NAME},
                "object": {"key": s3_key},
            }
        }
        response = stepfunctions_client.start_execution(
            stateMachineArn=AWS_STEP_FUNCTION_ARN,
            input=json.dumps(payload),
            name=f"{project_name}-{uuid.uuid4()}",
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {e}")


def start_batch_analysis(project_name: str, s3_keys: list[str]):
    """Trigger Step Function for multiple uploaded files."""
    try:
        payload = {
            "detail": {
                "bucket": {"name": AWS_S3_BUCKET_NAME},
                "objects": [{"key": key} for key in s3_keys],
                "projectName": project_name,
            }
        }
        response = stepfunctions_client.start_execution(
            stateMachineArn=AWS_STEP_FUNCTION_ARN,
            input=json.dumps(payload),
            name=f"{project_name}-{uuid.uuid4()}",
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {e}")
