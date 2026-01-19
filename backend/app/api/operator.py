"""
Operator API endpoints.
Handles job configuration and person seeding.
"""
import io
import json
import os
import string
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image
import numpy as np

from ..config import settings
from ..db.registry import (
    get_all_persons,
    get_person_by_id,
    create_person,
    add_person_embedding,
    delete_person,
)
from ..db.jobs import get_job_config, save_job_config, get_job_status, set_job_status
from ..engine.faces import FaceEngine


def get_thumbnails_dir() -> Path:
    """Get the thumbnails directory, creating it if needed."""
    thumbnails_dir = settings.hot_storage_root / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    return thumbnails_dir


def save_face_thumbnail(person_id: int, image_data: bytes, bbox: list) -> Path:
    """
    Crop and save a face thumbnail from the image.
    
    Args:
        person_id: The person's ID
        image_data: Raw image bytes
        bbox: Face bounding box [x1, y1, x2, y2]
    
    Returns:
        Path to saved thumbnail
    """
    # Open image
    img = Image.open(io.BytesIO(image_data))
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    # Extract bbox with some padding
    x1, y1, x2, y2 = [int(coord) for coord in bbox]
    width = x2 - x1
    height = y2 - y1
    
    # Add 20% padding
    padding = int(max(width, height) * 0.2)
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(img.width, x2 + padding)
    y2 = min(img.height, y2 + padding)
    
    # Crop face
    face_crop = img.crop((x1, y1, x2, y2))
    
    # Resize to thumbnail (128x128 max, preserve aspect)
    face_crop.thumbnail((128, 128), Image.Resampling.LANCZOS)
    
    # Save thumbnail
    thumbnail_path = get_thumbnails_dir() / f"{person_id}.jpg"
    face_crop.save(thumbnail_path, "JPEG", quality=85)
    
    return thumbnail_path


router = APIRouter()


# ============================================================================
# Folder Browser API
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


@router.get("/browse-folders", response_model=FolderListResponse)
async def browse_folders(path: Optional[str] = Query(None)):
    """
    Browse folders on the local file system.
    If path is None, returns available drives (Windows) or root (Unix).
    """
    # Windows: list drives if no path specified
    if path is None or path == "":
        if os.name == 'nt':  # Windows
            drives = []
            for letter in string.ascii_uppercase:
                drive_path = f"{letter}:\\"
                if os.path.exists(drive_path):
                    drives.append(FolderItem(
                        name=f"{letter}:",
                        path=drive_path,
                        is_drive=True
                    ))
            return FolderListResponse(
                current_path="",
                parent_path=None,
                folders=drives
            )
        else:  # Unix/Linux/Mac
            path = "/"
    
    # Normalize path
    folder_path = Path(path).resolve()
    
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    
    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")
    
    # Get parent path
    parent_path = None
    if os.name == 'nt':  # Windows
        if len(folder_path.parts) > 1:
            parent_path = str(folder_path.parent)
        # If at drive root (e.g., E:\), parent is drive list
    else:  # Unix
        if str(folder_path) != "/":
            parent_path = str(folder_path.parent)
    
    # List subdirectories
    folders = []
    try:
        for item in sorted(folder_path.iterdir()):
            if item.is_dir():
                # Skip hidden folders and system folders
                if item.name.startswith('.') or item.name.startswith('$'):
                    continue
                try:
                    # Check if we can access the folder
                    list(item.iterdir())
                    folders.append(FolderItem(
                        name=item.name,
                        path=str(item)
                    ))
                except PermissionError:
                    # Include but mark as inaccessible (could add flag)
                    pass
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")
    
    return FolderListResponse(
        current_path=str(folder_path),
        parent_path=parent_path,
        folders=folders
    )


# ============================================================================
# Image Picker (for "only selected images" mode)
# ============================================================================

class ImageInFolderItem(BaseModel):
    source_path: str
    filename: str


class ImagesInFolderResponse(BaseModel):
    images: list[ImageInFolderItem]


def _path_under_root(p: Path, root: Path) -> bool:
    """True if p is under root (or equal)."""
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


@router.get("/images-in-folder", response_model=ImagesInFolderResponse)
async def images_in_folder(
    path: str = Query(..., description="Folder path (under source_root when it is configured)"),
    recursive: bool = Query(False, description="Include images in subfolders"),
):
    """
    List image files (.jpg, .jpeg, .arw) in a folder. If recursive=True, include all subfolders.
    When source_root is configured, path must be under it.
    """
    path = (path or "").strip()
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")

    config = await get_job_config()
    source_root = config.get("source_root")

    folder = Path(path).resolve()
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail="Path must be a directory")

    if source_root:
        src = Path(source_root).resolve()
        if not _path_under_root(folder, src):
            raise HTTPException(status_code=400, detail="Path must be under source directory. Save Configuration first if you changed the source.")

    exts = {e.lower() for e in settings.supported_extensions}
    images = []
    if recursive:
        for ext in exts:
            for f in folder.rglob(f"*{ext}"):
                if f.is_file():
                    images.append(ImageInFolderItem(source_path=str(f.resolve()), filename=f.name))
            for f in folder.rglob(f"*{ext.upper()}"):
                if f.is_file():
                    images.append(ImageInFolderItem(source_path=str(f.resolve()), filename=f.name))
        images = list({(x.source_path, x.filename): x for x in images}.values())
        images.sort(key=lambda x: x.source_path)
    else:
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.suffix.lower() in exts:
                images.append(ImageInFolderItem(source_path=str(f.resolve()), filename=f.name))
    return ImagesInFolderResponse(images=images)


class JobConfigRequest(BaseModel):
    """Request model for job configuration."""
    source_root: str
    output_root: str
    selected_person_ids: Optional[list[int]] = None  # None means all persons
    selected_image_paths: Optional[list[str]] = None  # None or empty means all images in source


class JobConfigResponse(BaseModel):
    """Response model for job configuration."""
    source_root: Optional[str] = None
    output_root: Optional[str] = None
    selected_person_ids: Optional[list[int]] = None  # None or empty means all persons
    selected_image_paths: Optional[list[str]] = None  # None or empty means all images in source


class PersonResponse(BaseModel):
    """Response model for a person."""
    person_id: int
    name: str
    output_folder_rel: str
    embedding_count: int


class PersonsListResponse(BaseModel):
    """Response model for persons list."""
    persons: list[PersonResponse]


@router.get("/job-config", response_model=JobConfigResponse)
async def get_job_configuration():
    """Get current job configuration."""
    config = await get_job_config()
    return JobConfigResponse(
        source_root=config.get("source_root"),
        output_root=config.get("output_root"),
        selected_person_ids=config.get("selected_person_ids"),
        selected_image_paths=config.get("selected_image_paths"),
    )


@router.post("/job-config")
async def set_job_configuration(request: JobConfigRequest):
    """Set job configuration (source and output directories)."""
    source_path = Path(request.source_root)
    output_path = Path(request.output_root)
    
    # Validate source exists
    if not source_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Source directory does not exist: {request.source_root}"
        )
    
    if not source_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Source path is not a directory: {request.source_root}"
        )
    
    # Validate selected_image_paths when provided
    if request.selected_image_paths:
        for p in request.selected_image_paths:
            pp = Path(p)
            if not pp.exists():
                raise HTTPException(
                    status_code=400,
                    detail=f"Selected image does not exist: {p}"
                )
            if not pp.is_file():
                raise HTTPException(
                    status_code=400,
                    detail=f"Selected path is not a file: {p}"
                )
            if not _path_under_root(pp, source_path):
                raise HTTPException(
                    status_code=400,
                    detail=f"Selected image must be under source directory: {p}"
                )
            ext = pp.suffix.lower()
            if ext not in (".jpg", ".jpeg", ".arw"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported extension for: {p} (use .jpg, .jpeg, .arw)"
                )
    
    # Create output directory if needed
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create output directory: {e}"
        )
    
    # Save configuration
    await save_job_config(
        request.source_root,
        request.output_root,
        request.selected_person_ids,
        request.selected_image_paths,
    )
    
    return {"status": "ok", "message": "Configuration saved"}


@router.get("/persons", response_model=PersonsListResponse)
async def list_persons():
    """Get all registered persons."""
    persons = await get_all_persons()
    return PersonsListResponse(persons=[
        PersonResponse(
            person_id=p["person_id"],
            name=p["name"],
            output_folder_rel=p["output_folder_rel"],
            embedding_count=p["embedding_count"]
        )
        for p in persons
    ])


@router.post("/seed-person")
async def seed_person(
    name: str = Form(...),
    folder_name: str = Form(...),
    reference_image: UploadFile = File(...)
):
    """
    Seed a new person identity from a reference image.
    
    Requirements:
    - Reference image must contain exactly ONE face
    - Name and folder_name are required
    """
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/jpg"}
    if reference_image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Reference image must be JPEG or PNG"
        )
    
    # Read image data
    image_data = await reference_image.read()
    
    # Detect faces and get embedding
    face_engine = FaceEngine()
    faces = face_engine.detect_and_embed(image_data)
    
    if len(faces) == 0:
        raise HTTPException(
            status_code=400,
            detail="No face detected in reference image"
        )
    
    if len(faces) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Reference image must contain exactly ONE face, found {len(faces)}"
        )
    
    # Get the single face embedding and bbox
    face = faces[0]
    embedding = face["embedding"]
    bbox = face["bbox"]
    
    # Create person in registry
    person_id = await create_person(name, folder_name)
    
    # Add the embedding
    await add_person_embedding(person_id, embedding)
    
    # Save face thumbnail
    save_face_thumbnail(person_id, image_data, bbox)
    
    return {
        "status": "ok",
        "person_id": person_id,
        "name": name,
        "folder_name": folder_name
    }


@router.get("/persons/{person_id}/thumbnail")
async def get_person_thumbnail(person_id: int):
    """
    Get the face thumbnail for a person.
    Returns a JPEG image of the person's face.
    """
    thumbnail_path = get_thumbnails_dir() / f"{person_id}.jpg"
    
    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    
    return FileResponse(
        thumbnail_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "max-age=3600"}  # Cache for 1 hour
    )


@router.post("/persons/{person_id}/add-reference")
async def add_reference_image(
    person_id: int,
    reference_image: UploadFile = File(...)
):
    """
    Add another reference image to an existing person.
    This improves matching accuracy by averaging multiple embeddings.
    
    Each person can have up to 30 reference embeddings.
    """
    # Check if person exists
    person = await get_person_by_id(person_id)
    if not person:
        raise HTTPException(
            status_code=404,
            detail=f"Person with ID {person_id} not found"
        )
    
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/jpg"}
    if reference_image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Reference image must be JPEG or PNG"
        )
    
    # Read image data
    image_data = await reference_image.read()
    
    # Detect faces and get embedding
    face_engine = FaceEngine()
    faces = face_engine.detect_and_embed(image_data)
    
    if len(faces) == 0:
        raise HTTPException(
            status_code=400,
            detail="No face detected in reference image"
        )
    
    if len(faces) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Reference image must contain exactly ONE face, found {len(faces)}"
        )
    
    # Get the single face embedding and bbox
    face = faces[0]
    embedding = face["embedding"]
    bbox = face["bbox"]
    
    # Add the embedding
    await add_person_embedding(person_id, embedding)
    
    # Create thumbnail if it doesn't exist yet (for existing persons without thumbnails)
    thumbnail_path = get_thumbnails_dir() / f"{person_id}.jpg"
    if not thumbnail_path.exists():
        save_face_thumbnail(person_id, image_data, bbox)
    
    return {
        "status": "ok",
        "message": f"Added reference image to {person['name']}",
        "person_id": person_id
    }


@router.delete("/persons/{person_id}")
async def remove_person(person_id: int):
    """
    Delete a person from the registry.
    This removes the person and all their embeddings.
    """
    # Check if person exists
    person = await get_person_by_id(person_id)
    if not person:
        raise HTTPException(
            status_code=404,
            detail=f"Person with ID {person_id} not found"
        )
    
    # Delete the person
    await delete_person(person_id)
    
    return {
        "status": "ok",
        "message": f"Person '{person['name']}' deleted successfully"
    }


# ============================================================================
# Job Control API
# ============================================================================

class JobStatusResponse(BaseModel):
    """Response model for job status."""
    status: str  # configured, ready, running, completed, stopped, terminating
    can_start: bool
    message: str
    source_root: Optional[str] = None
    output_root: Optional[str] = None


@router.get("/job-status", response_model=JobStatusResponse)
async def get_job_status_endpoint():
    """Get current job status."""
    config = await get_job_config()
    status = await get_job_status()
    persons = await get_all_persons()

    has_config = bool(config.get("source_root") and config.get("output_root"))
    has_persons = len(persons) > 0
    can_start = has_config and has_persons and status not in ("running", "terminating")

    if not has_config:
        message = "Configure source and output directories first"
    elif not has_persons:
        message = "Add at least one person to the registry"
    elif status == "running":
        message = "Job is running..."
    elif status == "terminating":
        message = "Terminating: no new photos will be analysed. Finishing writes to output, then stopping."
    elif status == "completed":
        message = "Job completed! Click Start to run again"
    elif status == "stopped":
        message = "Job stopped. Click Start to resume"
    else:
        message = "Ready to start"

    return JobStatusResponse(
        status=status or "configured",
        can_start=can_start,
        message=message,
        source_root=config.get("source_root"),
        output_root=config.get("output_root"),
    )


@router.post("/start-job")
async def start_job():
    """
    Start or resume the processing job.
    The worker will automatically re-discover images when this is called.
    """
    config = await get_job_config()
    persons = await get_all_persons()
    
    # Validate source directory exists
    source_path = Path(config.get("source_root", ""))
    if not source_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Source directory does not exist: {source_path}"
        )
    
    # Validate
    if not config.get("source_root") or not config.get("output_root"):
        raise HTTPException(
            status_code=400,
            detail="Configure source and output directories first"
        )
    
    if len(persons) == 0:
        raise HTTPException(
            status_code=400,
            detail="Add at least one person to the registry first"
        )
    
    # Set job status to running
    await set_job_status("running")
    
    return {"status": "ok", "message": "Job started"}


@router.post("/stop-job")
async def stop_job():
    """Stop after the current batch completes (including writes)."""
    await set_job_status("stopped")
    return {"status": "ok", "message": "Job will stop after the current batch completes."}


@router.post("/terminate-job")
async def terminate_job():
    """
    Terminate: no new photos will be matched/analysed. Only in-flight writes
    to output will finish, then the job stops.
    """
    await set_job_status("terminating")
    return {"status": "ok", "message": "Terminating: finishing writes, then stopping."}

