from fastapi import APIRouter, HTTPException
from app.models.schemas import PresignRequest, MultiPresignRequest
from app.services.s3_service import generate_presigned_url, generate_multi_presigned

router = APIRouter()


@router.post("/generate-presigned-url")
async def generate_url(request: PresignRequest):
    """Return a presigned URL for single file upload."""
    try:
        return generate_presigned_url(
            request.filename, request.contentType, request.projectName
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Presigned URL generation failed: {e}"
        )


@router.post("/generate-multi-presigned")
async def generate_multi(request: MultiPresignRequest):
    """Return multiple presigned URLs for batch uploads."""
    try:
        return generate_multi_presigned(request.files, request.projectName)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-URL generation failed: {e}")
