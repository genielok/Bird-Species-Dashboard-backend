from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import upload, analysis, detections

app = FastAPI(title="BirdNET API (Modular Architecture)")

# -----------------------------------------------------------
# Middleware
# -----------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------
# Routers
# -----------------------------------------------------------
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(detections.router, prefix="/api", tags=["Detections"])


@app.get("/")
def root():
    """Health check endpoint."""
    return {"message": "Welcome to the BirdNET API (Modular Serverless Version)"}
