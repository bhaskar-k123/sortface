"""
Export module.
Provides functionality for creating ZIP archives of segregated photos.
"""
import asyncio
import os
import shutil
import time
from pathlib import Path

from fastapi import HTTPException

from ..config import settings
from ..db.registry import get_person_by_id
from ..db.jobs import get_job_config


async def create_person_export_zip(person_id: int) -> Path:
    """
    Look up a person's photos and compress them into a temporary ZIP file.
    Runs asynchronously using a thread pool.

    Args:
        person_id: The ID of the person to export.

    Returns:
        The Path to the generated .zip file in hot_storage/temp.
    """
    # 1. Look up person and output root
    person = await get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    config = await get_job_config()
    output_root = config.get("output_root")
    
    if not output_root:
        raise HTTPException(status_code=400, detail="Output directory not configured")
        
    output_root_path = Path(output_root)
    # The output folder relative path (e.g., "john_smith" or "group/john_smith")
    output_folder_rel = person.get("output_folder_rel")
    
    if not output_folder_rel:
         raise HTTPException(status_code=400, detail="Person has no valid output folder configured")
         
    person_dir = output_root_path / output_folder_rel

    # 2. Check if the folder exists and is not empty
    if not person_dir.exists() or not person_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"No photos found. Folder does not exist yet: {output_folder_rel}")
        
    # Check if there are actually files in the directory
    # We only check the primary directory level since we don't have deep nested structures
    files = list(person_dir.glob("*.[jJ][pP][gG]")) + list(person_dir.glob("*.[jJ][pP][eE][gG]"))
    if not files:
         raise HTTPException(status_code=404, detail="No photos found in the person's folder.")

    # 3. Create temp zip in hot_storage
    temp_dir = settings.hot_storage_root / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename: Export_Name_Timestamp.zip
    safe_name = "".join(c if c.isalnum() else "_" for c in person["name"])
    timestamp = int(time.time())
    zip_stem = f"Export_{safe_name}_{timestamp}"
    zip_output_path_without_ext = temp_dir / zip_stem
    
    # Run the heavy I/O zip process in a thread pool to avoid blocking async loop
    def _make_archive():
        # shutil.make_archive adds the .zip extension automatically
        return shutil.make_archive(
            base_name=str(zip_output_path_without_ext),
            format='zip',
            root_dir=str(person_dir.parent),
            base_dir=person_dir.name
        )

    zip_file_path_str = await asyncio.to_thread(_make_archive)
    
    return Path(zip_file_path_str)

