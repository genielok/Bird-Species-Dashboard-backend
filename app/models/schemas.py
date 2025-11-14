from pydantic import BaseModel
from typing import List, Dict


class PresignRequest(BaseModel):
    filename: str
    contentType: str
    projectName: str


class MultiPresignRequest(BaseModel):
    projectName: str
    files: List[Dict[str, str]]  # [{"filename": "...", "contentType": "..."}]


class AnalysisRequest(BaseModel):
    s3_key: str
    projectName: str


class BatchAnalysisRequest(BaseModel):
    projectName: str
    s3_keys: List[str]


class DownloadRequest(BaseModel):
    s3_key: str
