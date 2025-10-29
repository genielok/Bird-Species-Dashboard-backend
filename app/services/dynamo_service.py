import boto3
from fastapi import HTTPException
from app.settings import AWS_DEFAULT_REGION, DYNAMODB_TABLE_NAME

dynamodb = boto3.resource("dynamodb", region_name=AWS_DEFAULT_REGION)
table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def get_all_detections():
    """Retrieve detection results from DynamoDB."""
    try:
        response = table.scan()
        items = response.get("Items", [])
        sorted_items = sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)
        return sorted_items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading DynamoDB: {e}")
