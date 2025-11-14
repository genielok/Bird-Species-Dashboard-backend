from typing import Optional
from app.models.schemas import DownloadRequest
from fastapi import APIRouter, HTTPException
from app.services.dynamo_service import get_all_detections
from app.db import table, enriched_table
from boto3.dynamodb.conditions import Key, Attr

import boto3, os
from fastapi.responses import Response

router = APIRouter()
GSI_NAME = "project-time-index"
s3_client = boto3.client("s3")
AWS_S3_BUCKET_NAME = os.environ.get("AWS_S3_BUCKET_NAME")


@router.get("/detections")
def get_detections(
    projectName: Optional[str] = None,
    startTime: Optional[int] = None,
    endTime: Optional[int] = None,
):
    filter_conditions = []
    if projectName:
        filter_conditions.append(Attr("projectName").contains(projectName))
    if startTime and endTime:
        filter_conditions.append(Attr("create_time").between(startTime, endTime))
    elif startTime:
        filter_conditions.append(Attr("create_time").gte(startTime))
    elif endTime:
        filter_conditions.append(Attr("create_time").lte(endTime))
    try:
        scan_args = {}
        if filter_conditions:
            final_filter = None
            if filter_conditions:
                from functools import reduce

                final_filter = reduce(lambda a, b: a & b, filter_conditions)

            if final_filter:
                scan_args["FilterExpression"] = final_filter
        response = table.scan(**scan_args)

        items = response.get("Items", [])
        items.sort(key=lambda x: x.get("create_time", 0), reverse=True)

        return {
            "code": 200,
            "message": f"Successfully retrieved {len(items)} analysis sessions (via Scan).",
            "data": items,
        }
    except Exception as e:
        print(f"Error scanning DynamoDB: {e}")
        raise HTTPException(status_code=500, detail="Failed to query database.")


@router.get("/download")
def download_csv(session_id: str):
    try:
        response = table.get_item(Key={"session_id": session_id})
        item = response.get("Item")

        if not item:
            raise HTTPException(status_code=404, detail="Session not found")

        detections = item.get("detections", [])
        print(f"Found {len(detections)} detections")

        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "scientific_name",
                "common_name",
                "label",
                "confidence",
                "start_time",
                "end_time",
                "source_filename",
                "source_s3_key",
            ]
        )

        for det in detections:
            writer.writerow(
                [
                    det.get("scientific_name"),
                    det.get("common_name"),
                    det.get("label"),
                    det.get("confidence"),
                    det.get("start_time"),
                    det.get("end_time"),
                    det.get("source_filename"),
                    det.get("source_s3_key"),
                ]
            )
        print(output.getvalue())

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={session_id}.csv"},
        )

    except Exception as e:
        print(f"Error generating CSV for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/generate-download-url")
def generate_download_url(req: DownloadRequest):
    """
    Generate a temporary (pre-signed) download URL for a stored S3 object.
    """
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": AWS_S3_BUCKET_NAME, "Key": req.s3_key},
            ExpiresIn=86400,  # valid for 24 hours
        )
        return {"download_url": url}
    except Exception as e:
        print(f"Error generating download URL: {e}")
        raise HTTPException(status_code=500, detail="Could not generate download URL.")


@router.get("/detections-detail")
def get_detections_detail(session_id: str):
    """
    Retrieve complete details for a single analysis session.
        1. Retrieve session metadata (status, projectName) from the main table (table).
        2. Retrieve processed birds from the results table (enriched_table).
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        # if project is still "PROCESSING")
        session_meta_response = table.get_item(Key={"session_id": session_id})
        session_data = session_meta_response.get("Item")

        if not session_data:
            raise HTTPException(
                status_code=404, detail=f"Session with ID {session_id} not found."
            )

        # --- Acquire a rich list of birds (EnrichmentLambda)---
        enriched_response = enriched_table.query(
            KeyConditionExpression=Key("session_id").eq(session_id)
        )

        enriched_items = enriched_response.get("Items", [])

        return {
            "code": 200,
            "message": "Successfully retrieved session details.",
            "data": {
                "session": session_data,
                # enriched_species: (detection_count, protection_level 等)
                "enriched_species": enriched_items,
            },
        }
    except Exception as e:
        import traceback

        print(f"Error querying session details for {session_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
