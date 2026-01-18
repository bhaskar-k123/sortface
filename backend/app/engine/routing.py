"""
Fan-out routing engine.
Handles append-only copy from staging to external output folders.

Routing Policy:
- Compress image ONCE in staging
- Fan-out copy to ALL matched person folders
- Append-only: never overwrite existing files
- Idempotent: same input always produces same output
"""
import shutil
from pathlib import Path
from typing import Optional

from ..config import settings
from ..storage.paths import (
    PathManager,
    generate_deterministic_filename,
    StorageError,
)
from ..db.jobs import (
    add_commit_entry,
    update_commit_status,
    check_output_exists_in_log,
)
from ..db.registry import get_person_by_id


class RoutingEngine:
    """
    Handles fan-out routing of compressed images to person folders.
    
    Flow:
    1. Image is compressed ONCE to staging directory
    2. For each matched person:
       a. Generate deterministic output filename
       b. Check if already committed (idempotency)
       c. Copy from staging to person folder
       d. Record in commit log
    3. Clean up staging file
    
    Invariants:
    - Output folders are append-only (no overwrites)
    - Deterministic filenames ensure idempotency
    - Commit log enables crash recovery
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
        
        Handles:
        - Idempotency check (skip if already exists)
        - Append-only enforcement
        - Commit log recording
        """
        # Get person info
        person = await get_person_by_id(person_id)
        if not person:
            return {
                "person_id": person_id,
                "status": "error",
                "error": "Person not found"
            }
        
        # Determine output path
        person_folder = self.output_root / person["output_folder_rel"]
        output_path = person_folder / output_filename
        output_path_str = str(output_path)
        
        # Check commit log for idempotency
        already_committed = await check_output_exists_in_log(output_path_str)
        if already_committed:
            return {
                "person_id": person_id,
                "person_name": person["name"],
                "output_path": output_path_str,
                "status": "skipped",
                "reason": "already_committed"
            }
        
        # Check if file exists (append-only)
        if output_path.exists():
            # File exists but not in log - add to log as verified
            commit_id = await add_commit_entry(
                batch_id, image_id, person_id, output_filename, output_path_str
            )
            await update_commit_status(commit_id, "verified")
            
            return {
                "person_id": person_id,
                "person_name": person["name"],
                "output_path": output_path_str,
                "status": "exists",
                "reason": "file_already_present"
            }
        
        # Create commit log entry (pending)
        commit_id = await add_commit_entry(
            batch_id, image_id, person_id, output_filename, output_path_str
        )
        
        try:
            # Ensure person folder exists
            person_folder.mkdir(parents=True, exist_ok=True)
            
            # Copy from staging to output
            # Use atomic copy: write to temp then rename
            temp_output = output_path.with_suffix(".tmp")
            shutil.copy2(staged_path, temp_output)
            
            # Rename to final name (atomic on same filesystem)
            temp_output.rename(output_path)
            
            # Update commit status
            await update_commit_status(commit_id, "written")
            
            # Verify the write
            if output_path.exists() and output_path.stat().st_size > 0:
                await update_commit_status(commit_id, "verified")
                status = "success"
            else:
                status = "unverified"
            
            return {
                "person_id": person_id,
                "person_name": person["name"],
                "output_path": output_path_str,
                "status": status,
                "commit_id": commit_id
            }
            
        except Exception as e:
            return {
                "person_id": person_id,
                "person_name": person["name"],
                "output_path": output_path_str,
                "status": "error",
                "error": str(e),
                "commit_id": commit_id
            }
    
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


class CommitReconciliation:
    """
    Handles commit reconciliation for crash recovery.
    
    Called during resume when a batch was in COMMITTING state.
    Ensures all pending commits are completed or verified.
    """
    
    def __init__(self, output_root: Path, staging_dir: Optional[Path] = None):
        self.output_root = output_root
        self.staging_dir = staging_dir or settings.staging_dir
    
    async def reconcile_batch(self, batch_id: int) -> dict:
        """
        Reconcile all commits for a batch.
        
        Checks each pending commit:
        - If output exists: mark as verified
        - If output missing but staged exists: copy and verify
        - If both missing: mark as failed
        
        Returns:
            Dict with reconciliation results
        """
        from ..db.jobs import get_pending_commits
        
        pending = await get_pending_commits(batch_id)
        
        results = {
            "verified": 0,
            "copied": 0,
            "failed": 0,
            "details": []
        }
        
        for commit in pending:
            output_path = Path(commit["output_path"])
            
            if output_path.exists():
                # Output already present - verify
                await update_commit_status(commit["commit_id"], "verified")
                results["verified"] += 1
                results["details"].append({
                    "commit_id": commit["commit_id"],
                    "action": "verified"
                })
            
            else:
                # Try to find in staging and copy
                staged_path = self.staging_dir / commit["output_filename"]
                
                if staged_path.exists():
                    try:
                        # Copy from staging
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(staged_path, output_path)
                        await update_commit_status(commit["commit_id"], "verified")
                        results["copied"] += 1
                        results["details"].append({
                            "commit_id": commit["commit_id"],
                            "action": "copied"
                        })
                    except Exception as e:
                        results["failed"] += 1
                        results["details"].append({
                            "commit_id": commit["commit_id"],
                            "action": "failed",
                            "error": str(e)
                        })
                else:
                    # Both missing - cannot recover
                    results["failed"] += 1
                    results["details"].append({
                        "commit_id": commit["commit_id"],
                        "action": "unrecoverable"
                    })
        
        return results

