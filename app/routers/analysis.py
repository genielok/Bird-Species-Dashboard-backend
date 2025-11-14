from fastapi import APIRouter
from app.models.schemas import AnalysisRequest, BatchAnalysisRequest
from app.services.step_function_service import (
    start_batch_analysis,
)

router = APIRouter()



@router.post("/start-analysis-batch")
async def start_batch(request: BatchAnalysisRequest):
    """Trigger Step Function for multiple files."""
    response = start_batch_analysis(request.projectName, request.s3_keys)
    return {
        "message": f"Started analysis for {len(request.s3_keys)} files",
        "executionArn": response["executionArn"],
        "sessionId": response["sessionId"]
    }
