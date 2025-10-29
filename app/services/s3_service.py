import uuid
import boto3
from botocore.client import Config
from app.settings import AWS_S3_BUCKET_NAME, AWS_DEFAULT_REGION


# Initialize once
s3_client = boto3.client(
    "s3", region_name=AWS_DEFAULT_REGION, config=Config(signature_version="s3v4")
)


def generate_presigned_url(filename: str, content_type: str, project_name: str):
    """Generate a presigned PUT URL for uploading to S3."""
    s3_key = f"uploads/{project_name}/{uuid.uuid4()}-{filename}"
    url = s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": AWS_S3_BUCKET_NAME,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=300,  # URL valid for 5 minutes
    )
    return {"upload_url": url, "s3_key": s3_key}


def generate_multi_presigned(files, project_name: str):
    """Generate multiple presigned URLs for batch uploads."""
    urls = []
    for f in files:
        urls.append(
            generate_presigned_url(f["filename"], f["contentType"], project_name)
        )
    return {"urls": urls}
