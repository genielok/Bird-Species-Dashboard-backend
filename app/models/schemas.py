from pydantic import BaseModel
from pydantic import BaseModel
from typing import List, Optional


class PresignRequest(BaseModel):
    filename: str


class MultiPresignRequest(BaseModel):
    filenames: list[str]


class AnalysisRequest(BaseModel):
    audio_file: str
    species: list[str] | None = None


class BatchAnalysisRequest(BaseModel):
    job_ids: List[str]


class DownloadRequest(BaseModel):
    job_id: str
