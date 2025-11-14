# app/db.py

import boto3
from app.settings import (
    DYNAMODB_TABLE_NAME,
    AWS_DEFAULT_REGION,
    DYNAMODB_ENRICHED_TABLE_NAME,
)

dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_DEFAULT_REGION)
table = dynamodb_resource.Table(DYNAMODB_TABLE_NAME)
enriched_table = dynamodb_resource.Table(DYNAMODB_ENRICHED_TABLE_NAME)
