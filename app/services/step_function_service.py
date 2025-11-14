import uuid
import json
import boto3
from fastapi import HTTPException
import os
from app.settings import (
    AWS_DEFAULT_REGION,
    AWS_STEP_FUNCTION_ARN,
    AWS_S3_BUCKET_NAME,
)
from datetime import datetime
from app.db import table

stepfunctions_client = boto3.client("stepfunctions", region_name=AWS_DEFAULT_REGION)

def start_batch_analysis(project_name: str, s3_keys: list[str]):
    """Trigger Step Function for multiple uploaded files."""
    session_id = str(uuid.uuid4()) 
    create_time = int(datetime.now().timestamp() * 1000)
    # Create project save into db
    try:
        audio_files_list = [
            {
                "filename": os.path.basename(key),
                "s3_key": key,
                "bucket": AWS_S3_BUCKET_NAME
            } for key in s3_keys
        ]
        
        item_to_save = {
            'session_id': session_id,
            'projectName': project_name,
            'create_time': create_time,
            'timestamp': create_time,
            'file_count': len(s3_keys),
            'total_detections': 0, 
            'detections': [],     
            'audio_files': audio_files_list,
            'model': 'BirdNET',
            'status': 'PROCESSING',   
            'result_prefix': None  
        }
        table.put_item(Item=item_to_save)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create DynamoDB processing entry: {e}")
    
    # start step funtion
    try:
        payload = {
            "detail": {
                "bucket": {"name": AWS_S3_BUCKET_NAME},
                "objects": [{"key": key} for key in s3_keys],
                "projectName": project_name,
                "sessionId": session_id
            }
        }
        execution_name = f"{project_name}-{session_id}"
        
        response = stepfunctions_client.start_execution(
            stateMachineArn=AWS_STEP_FUNCTION_ARN,
            input=json.dumps(payload),
            name=execution_name,
        )
        return {
            "executionArn": response["executionArn"],
            "sessionId": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {e}")
