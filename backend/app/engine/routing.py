"""
Fan-out routing engine.
Handles append-only copy from staging to external output folders.

Routing Policy:
- Compress image ONCE in staging
- Fan-out copy to ALL matched person folders
- Append-only: never overwrite existing files
- Idempotent: deterministic filename + skip if exists
"""
import shutil
from pathlib import Path
from typing import Optional

from ..config import settings
from ..storage.paths import generate_deterministic_filename
from ..db.registry import get_person_by_id


class RoutingEngine:
    """
    Handles fan-out routing of compressed images to person folders.
    
    Flow:
    1. Image is compressed ONCE to staging directory
    2. For each matched person: if output exists, skip; else copy from staging
    3. Clean up staging file
    
    Idempotency: deterministic filename (stem__hash.jpg) + skip when file exists.
    """
    
    def __init__(
        self,
        output_root: Path,
        staging_dir: Optional[Path] = None
    ):
        self.output_root = output_root
        self.staging_dir = staging_dir or settings.staging_dir
        
        # Ensure directories exist
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.output_root.mkdir(parents=True, exist_ok=True)
    
    async def route_image(
        self,
        batch_id: int,
        image_id: int,
        staged_path: Path,
        original_stem: str,
        file_hash: str,
        matched_person_ids: list[int]
    ) -> list[dict]:
        """
        Route a staged image to all matched person folders.
        
        Args:
            batch_id: Current batch ID
            image_id: Image database ID
            staged_path: Path to compressed image in staging
            original_stem: Original filename stem (without extension)
            file_hash: SHA-256 hash for deterministic naming
            matched_person_ids: List of person IDs to route to
        
        Returns:
            List of routing results with destination info
        """
        if not matched_person_ids:
            # No matches - nothing to route
            return []
        
        # Generate deterministic output filename
        output_filename = generate_deterministic_filename(original_stem, file_hash)
        
        results = []
        
        for person_id in matched_person_ids:
            result = await self._route_to_person(
                batch_id=batch_id,
                image_id=image_id,
                person_id=person_id,
                staged_path=staged_path,
                output_filename=output_filename
            )
            results.append(result)
        
        return results
    
    async def _route_to_person(
        self,
        batch_id: int,
        image_id: int,
        person_id: int,
        staged_path: Path,
        output_filename: str
    ) -> dict:
        """
        Route image to a single person's folder.
        Idempotent: skip if output exists (deterministic name).
        """
        person = await get_person_by_id(person_id)
        if not person:
            return {"person_id": person_id, "status": "error", "error": "Person not found"}

        person_folder = self.output_root / person["output_folder_rel"]
        output_path = person_folder / output_filename
        output_path_str = str(output_path)

        if output_path.exists():
            return {
                "person_id": person_id,
                "person_name": person["name"],
                "output_path": output_path_str,
                "status": "skipped",
                "reason": "exists",
            }

        try:
            person_folder.mkdir(parents=True, exist_ok=True)
            temp_output = output_path.with_suffix(".tmp")
            shutil.copy2(staged_path, temp_output)
            temp_output.rename(output_path)
            return {
                "person_id": person_id,
                "person_name": person["name"],
                "output_path": output_path_str,
                "status": "success",
            }
        except Exception as e:
            return {
                "person_id": person_id,
                "person_name": person["name"],
                "output_path": output_path_str,
                "status": "error",
                "error": str(e),
            }
    
    async def route_image_to_group(
        self,
        batch_id: int,
        image_id: int,
        staged_path: Path,
        original_stem: str,
        file_hash: str,
        group_folder_name: str
    ) -> list[dict]:
        """
        Route a staged image to a group folder (for group mode).
        
        Instead of routing to individual person folders, routes to a single
        group folder containing photos where ALL selected people appear.
        
        Args:
            batch_id: Current batch ID
            image_id: Image database ID
            staged_path: Path to compressed image in staging
            original_stem: Original filename stem (without extension)
            file_hash: SHA-256 hash for deterministic naming
            group_folder_name: Name of the group output folder
        
        Returns:
            List with single routing result
        """
        # Generate deterministic output filename
        output_filename = generate_deterministic_filename(original_stem, file_hash)
        
        # Create group folder path
        group_folder = self.output_root / group_folder_name
        output_path = group_folder / output_filename
        output_path_str = str(output_path)
        
        # Idempotent: skip if output exists
        if output_path.exists():
            return [{
                "group_folder": group_folder_name,
                "output_path": output_path_str,
                "status": "skipped",
                "reason": "exists",
            }]
        
        try:
            # Create group folder if it doesn't exist
            group_folder.mkdir(parents=True, exist_ok=True)
            
            # Atomic write: copy to temp, then rename
            temp_output = output_path.with_suffix(".tmp")
            shutil.copy2(staged_path, temp_output)
            temp_output.rename(output_path)
            
            return [{
                "group_folder": group_folder_name,
                "person_name": group_folder_name,  # For compatibility with progress display
                "output_path": output_path_str,
                "status": "success",
            }]
        except Exception as e:
            return [{
                "group_folder": group_folder_name,
                "output_path": output_path_str,
                "status": "error",
                "error": str(e),
            }]
    
    def cleanup_staged_file(self, staged_path: Path) -> None:
        """
        Remove a file from staging after successful routing.
        Silently ignores errors.
        """
        try:
            staged_path.unlink()
        except Exception:
            pass
    
    def get_staging_path(self, filename: str) -> Path:
        """Get the path for a file in staging."""
        return self.staging_dir / filename

