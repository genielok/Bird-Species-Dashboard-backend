from fastapi import APIRouter
from app.services.dynamo_service import get_all_detections

router = APIRouter()


@router.get("/detections")
def get_detections():
    """Fetch all detection sessions from DynamoDB."""
    items = get_all_detections()
    return {
        "code": 200,
        "message": f"Successfully retrieved {len(items)} analysis sessions.",
        "data": items,
    }
