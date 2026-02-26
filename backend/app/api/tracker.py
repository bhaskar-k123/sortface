"""
Tracker API endpoints.
Read-only endpoints that read state files only.
"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import settings
from ..db.jobs import get_job_results_summary


router = APIRouter()


class BatchInfo(BaseModel):
    """Information about a single batch."""
    batch_id: int
    state: str
    image_range: str


class ProgressResponse(BaseModel):
    """Response model for progress data."""
    total_images: int = 0
    processed_images: int = 0
    completion_percent: float = 0.0
    current_superbatch: Optional[str] = None
    current_batch_id: Optional[int] = None
    current_batch_state: Optional[str] = None
    current_image_range: Optional[str] = None
    current_image: Optional[str] = None
    last_committed_person: Optional[str] = None
    last_committed_image: Optional[str] = None
    last_committed_time: Optional[str] = None
    recent_batches: list[BatchInfo] = []
    source_root: Optional[str] = None
    output_root: Optional[str] = None
    # Time tracking
    elapsed_formatted: Optional[str] = None
    estimated_remaining_formatted: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    estimated_remaining_seconds: Optional[float] = None
    images_per_second: Optional[float] = None


class WorkerStatusResponse(BaseModel):
    """Response model for worker status."""
    online: bool
    last_heartbeat: Optional[str] = None
    status: Optional[str] = None
    pid: Optional[int] = None


@router.get("/progress", response_model=ProgressResponse)
async def get_progress():
    """
    Get current progress from state files.
    This is a read-only endpoint.
    """
    progress_file = settings.state_dir / "progress.json"
    
    if not progress_file.exists():
        return ProgressResponse()
    
    try:
        with open(progress_file, "r") as f:
            data = json.load(f)
        
        return ProgressResponse(
            total_images=data.get("total_images", 0),
            processed_images=data.get("processed_images", 0),
            completion_percent=data.get("completion_percent", 0.0),
            current_superbatch=data.get("current_superbatch"),
            current_batch_id=data.get("current_batch_id"),
            current_batch_state=data.get("current_batch_state"),
            current_image_range=data.get("current_image_range"),
            current_image=data.get("current_image"),
            last_committed_person=data.get("last_committed_person"),
            last_committed_image=data.get("last_committed_image"),
            last_committed_time=data.get("last_committed_time"),
            recent_batches=[],
            source_root=data.get("source_root"),
            output_root=data.get("output_root"),
            elapsed_formatted=data.get("elapsed_formatted"),
            estimated_remaining_formatted=data.get("estimated_remaining_formatted"),
            elapsed_seconds=data.get("elapsed_seconds"),
            estimated_remaining_seconds=data.get("estimated_remaining_seconds"),
            images_per_second=data.get("images_per_second")
        )
        
    except Exception as e:
        # Return empty progress on any error
        return ProgressResponse()


@router.get("/worker-status", response_model=WorkerStatusResponse)
async def get_worker_status():
    """
    Check if worker is online by reading heartbeat file.
    Worker is considered online if heartbeat is within last 10 seconds.
    """
    heartbeat_file = settings.state_dir / "worker_heartbeat.json"
    
    if not heartbeat_file.exists():
        return WorkerStatusResponse(online=False)
    
    try:
        with open(heartbeat_file, "r") as f:
            data = json.load(f)
        
        last_heartbeat = data.get("timestamp")
        status = data.get("status", "unknown")
        pid = data.get("pid")
        
        if last_heartbeat:
            # Parse ISO timestamp
            heartbeat_time = datetime.fromisoformat(last_heartbeat)
            now = datetime.now()
            
            # Worker is online if heartbeat within 10 seconds
            if (now - heartbeat_time).total_seconds() < 10:
                return WorkerStatusResponse(
                    online=True,
                    last_heartbeat=last_heartbeat,
                    status=status,
                    pid=pid
                )
        
        return WorkerStatusResponse(
            online=False,
            last_heartbeat=last_heartbeat,
            status=status,
            pid=pid
        )
        
    except Exception:
        return WorkerStatusResponse(online=False)


# ============================================================================
# Results Summary
# ============================================================================

class PersonResult(BaseModel):
    """Per-person match result."""
    person_id: int
    name: str
    folder: str
    photo_count: int


class ResultsSummaryResponse(BaseModel):
    """Response model for job results summary."""
    job_id: Optional[int] = None
    job_status: Optional[str] = None
    total_images: int = 0
    total_processed: int = 0
    total_unknown: int = 0
    persons: list[PersonResult] = []


@router.get("/results-summary", response_model=ResultsSummaryResponse)
async def get_results_summary():
    """
    Get per-person match results for the most recent job.
    Read-only endpoint querying commit_log and image_results.
    """
    try:
        data = await get_job_results_summary()
        if not data:
            return ResultsSummaryResponse()
        return ResultsSummaryResponse(**data)
    except Exception:
        return ResultsSummaryResponse()
