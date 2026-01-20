"""
Pydantic schemas for Tracker API.
Extracted from tracker.py for better code organization.
"""
from typing import Optional
from pydantic import BaseModel


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
