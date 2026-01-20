"""
API Schemas Package.
Centralized Pydantic models for all API endpoints.
"""
from .operator import (
    FolderItem,
    FolderListResponse,
    ImageInFolderItem,
    ImagesInFolderResponse,
    JobConfigRequest,
    JobConfigResponse,
    JobStatusResponse,
    PersonResponse,
    PersonsListResponse,
    SeedPersonResponse,
    AddReferenceResponse,
    DeletePersonResponse,
)
from .tracker import (
    BatchInfo,
    ProgressResponse,
    WorkerStatusResponse,
)

__all__ = [
    # Operator schemas
    "FolderItem",
    "FolderListResponse",
    "ImageInFolderItem",
    "ImagesInFolderResponse",
    "JobConfigRequest",
    "JobConfigResponse",
    "JobStatusResponse",
    "PersonResponse",
    "PersonsListResponse",
    "SeedPersonResponse",
    "AddReferenceResponse",
    "DeletePersonResponse",
    # Tracker schemas
    "BatchInfo",
    "ProgressResponse",
    "WorkerStatusResponse",
]
