"""
Pydantic schemas for Operator API.
Extracted from operator.py for better code organization.
"""
from typing import Optional
from pydantic import BaseModel


# ============================================================================
# Folder Browser Schemas
# ============================================================================

class FolderItem(BaseModel):
    """A folder in the file system."""
    name: str
    path: str
    is_drive: bool = False


class FolderListResponse(BaseModel):
    """Response for folder listing."""
    current_path: str
    parent_path: Optional[str]
    folders: list[FolderItem]


# ============================================================================
# Image Picker Schemas
# ============================================================================

class ImageInFolderItem(BaseModel):
    """An image file in a folder."""
    source_path: str
    filename: str


class ImagesInFolderResponse(BaseModel):
    """Response for images in folder listing."""
    images: list[ImageInFolderItem]


# ============================================================================
# Job Configuration Schemas
# ============================================================================

class JobConfigRequest(BaseModel):
    """Request model for job configuration."""
    source_root: str
    output_root: str
    selected_person_ids: Optional[list[int]] = None
    selected_image_paths: Optional[list[str]] = None


class JobConfigResponse(BaseModel):
    """Response model for job configuration."""
    source_root: Optional[str] = None
    output_root: Optional[str] = None
    selected_person_ids: Optional[list[int]] = None
    selected_image_paths: Optional[list[str]] = None


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    status: str
    can_start: bool
    message: str
    source_root: Optional[str] = None
    output_root: Optional[str] = None


# ============================================================================
# Person Registry Schemas
# ============================================================================

class PersonResponse(BaseModel):
    """Response model for a person."""
    person_id: int
    name: str
    output_folder_rel: str
    embedding_count: int


class PersonsListResponse(BaseModel):
    """Response model for persons list."""
    persons: list[PersonResponse]


class SeedPersonResponse(BaseModel):
    """Response model for person creation."""
    person_id: int
    name: str
    output_folder_rel: str
    embedding_count: int
    message: str


class AddReferenceResponse(BaseModel):
    """Response model for adding a reference image."""
    person_id: int
    embedding_id: int
    embedding_count: int
    message: str


class DeletePersonResponse(BaseModel):
    """Response model for person deletion."""
    deleted: bool
    message: str
