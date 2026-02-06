"""
Job and batch database operations.
Handles job configuration, images, batches, and commit log.
"""
import json
from enum import Enum
from typing import Optional
from pathlib import Path

from .db import get_db, get_db_transaction


class BatchState(str, Enum):
    """Batch state machine states."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"


# ============================================================================
# Job Configuration
# ============================================================================

async def get_job_config() -> dict:
    """Get current job configuration."""
    db = await get_db()
    
    # Ensure optional columns exist
    for col in ("selected_person_ids", "selected_image_paths", "group_mode", "group_folder_name"):
        try:
            await db.execute(f"ALTER TABLE job_config ADD COLUMN {col} TEXT")
            await db.commit()
        except Exception:
            pass
    cursor = await db.execute(
        "SELECT source_root, output_root, selected_person_ids, selected_image_paths, group_mode, group_folder_name FROM job_config WHERE config_id = 1"
    )
    raw = await cursor.fetchone()
    row = dict(raw) if raw else {}
    
    # Parse selected_person_ids JSON
    selected_ids = []
    if row.get("selected_person_ids"):
        try:
            selected_ids = json.loads(row["selected_person_ids"])
        except json.JSONDecodeError:
            selected_ids = []
    
    # Parse selected_image_paths JSON
    selected_paths = []
    if row.get("selected_image_paths"):
        try:
            selected_paths = json.loads(row["selected_image_paths"])
        except json.JSONDecodeError:
            selected_paths = []
    
    # Parse group_mode (stored as "1" or "0" text)
    group_mode = row.get("group_mode") == "1"
    
    return {
        "source_root": row.get("source_root"),
        "output_root": row.get("output_root"),
        "selected_person_ids": selected_ids,
        "selected_image_paths": selected_paths if selected_paths else None,
        "group_mode": group_mode,
        "group_folder_name": row.get("group_folder_name")
    }


async def save_job_config(
    source_root: str,
    output_root: str,
    selected_person_ids: list = None,
    selected_image_paths: list = None,
    group_mode: bool = False,
    group_folder_name: str = None,
) -> None:
    """Save job configuration."""
    db = await get_db()
    
    for col in ("selected_person_ids", "selected_image_paths", "group_mode", "group_folder_name"):
        try:
            await db.execute(f"ALTER TABLE job_config ADD COLUMN {col} TEXT")
            await db.commit()
        except Exception:
            pass
    
    selected_json = json.dumps(selected_person_ids) if selected_person_ids else None
    selected_paths_json = json.dumps(selected_image_paths) if selected_image_paths else None
    group_mode_str = "1" if group_mode else "0"
    
    await db.execute(
        """UPDATE job_config 
           SET source_root = ?, output_root = ?, selected_person_ids = ?, selected_image_paths = ?, 
               group_mode = ?, group_folder_name = ?, updated_at = datetime('now')
           WHERE config_id = 1""",
        (source_root, output_root, selected_json, selected_paths_json, group_mode_str, group_folder_name)
    )
    await db.commit()


async def get_job_status() -> str:
    """Get current job status (configured, running, stopped, completed)."""
    db = await get_db()
    
    # Check if job_status column exists, if not create it
    try:
        cursor = await db.execute(
            "SELECT job_status FROM job_config WHERE config_id = 1"
        )
        row = await cursor.fetchone()
        return row["job_status"] if row and row["job_status"] else "configured"
    except Exception:
        # Column doesn't exist, add it
        await db.execute(
            "ALTER TABLE job_config ADD COLUMN job_status TEXT DEFAULT 'configured'"
        )
        await db.commit()
        return "configured"


async def set_job_status(status: str) -> None:
    """Set job status."""
    db = await get_db()
    
    # Ensure column exists
    try:
        await db.execute(
            "ALTER TABLE job_config ADD COLUMN job_status TEXT DEFAULT 'configured'"
        )
    except Exception:
        pass  # Column already exists
    
    await db.execute(
        "UPDATE job_config SET job_status = ? WHERE config_id = 1",
        (status,)
    )
    await db.commit()


# ============================================================================
# Jobs
# ============================================================================

async def create_job(source_root: str, output_root: str) -> int:
    """Create a new job. Returns job_id."""
    db = await get_db()
    
    cursor = await db.execute(
        "INSERT INTO jobs (source_root, output_root) VALUES (?, ?)",
        (source_root, output_root)
    )
    await db.commit()
    
    return cursor.lastrowid


async def get_active_job() -> Optional[dict]:
    """Get the most recent non-completed job."""
    db = await get_db()
    
    cursor = await db.execute(
        """SELECT * FROM jobs 
           WHERE status IN ('created', 'running')
           ORDER BY created_at DESC LIMIT 1"""
    )
    row = await cursor.fetchone()
    
    return dict(row) if row else None


async def update_job_status(job_id: int, status: str) -> None:
    """Update job status."""
    db = await get_db()
    
    if status == "running":
        await db.execute(
            "UPDATE jobs SET status = ?, started_at = datetime('now') WHERE job_id = ?",
            (status, job_id)
        )
    elif status == "completed":
        await db.execute(
            "UPDATE jobs SET status = ?, completed_at = datetime('now') WHERE job_id = ?",
            (status, job_id)
        )
    else:
        await db.execute(
            "UPDATE jobs SET status = ? WHERE job_id = ?",
            (status, job_id)
        )
    await db.commit()


async def update_job_image_counts(job_id: int, total: int, processed: int) -> None:
    """Update job image counts."""
    db = await get_db()
    
    await db.execute(
        "UPDATE jobs SET total_images = ?, processed_images = ? WHERE job_id = ?",
        (total, processed, job_id)
    )
    await db.commit()


# ============================================================================
# Images
# ============================================================================

async def add_image(
    job_id: int,
    source_path: str,
    filename: str,
    extension: str,
    ordering_idx: int,
    sha256: Optional[str] = None
) -> int:
    """Add an image to a job. Returns image_id."""
    db = await get_db()
    
    cursor = await db.execute(
        """INSERT INTO images (job_id, source_path, filename, extension, sha256, ordering_idx)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (job_id, source_path, filename, extension, sha256, ordering_idx)
    )
    await db.commit()
    
    return cursor.lastrowid


async def add_images_batch(job_id: int, images: list[dict]) -> None:
    """Add multiple images in a single transaction."""
    async with get_db_transaction() as db:
        await db.executemany(
            """INSERT INTO images (job_id, source_path, filename, extension, sha256, ordering_idx)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (job_id, img["source_path"], img["filename"], img["extension"], 
                 img.get("sha256"), img["ordering_idx"])
                for img in images
            ]
        )


async def get_images_for_batch(batch_id: int) -> list[dict]:
    """Get all images for a batch."""
    db = await get_db()
    
    cursor = await db.execute(
        """SELECT i.* FROM images i
           INNER JOIN batches b ON i.job_id = b.job_id
           WHERE b.batch_id = ?
             AND i.ordering_idx >= b.start_idx
             AND i.ordering_idx <= b.end_idx
           ORDER BY i.ordering_idx""",
        (batch_id,)
    )
    rows = await cursor.fetchall()
    
    return [dict(row) for row in rows]


async def update_image_hash(image_id: int, sha256: str) -> None:
    """Update image SHA-256 hash."""
    db = await get_db()
    
    await db.execute(
        "UPDATE images SET sha256 = ? WHERE image_id = ?",
        (sha256, image_id)
    )
    await db.commit()


async def get_image_count(job_id: int) -> int:
    """Get total image count for a job."""
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM images WHERE job_id = ?",
        (job_id,)
    )
    row = await cursor.fetchone()
    
    return row["cnt"]


# ============================================================================
# Batches
# ============================================================================

async def create_batches(job_id: int, batch_size: int) -> int:
    """
    Create batches for a job based on image count.
    Returns number of batches created.
    """
    db = await get_db()
    
    # Get image count
    cursor = await db.execute(
        "SELECT MAX(ordering_idx) as max_idx FROM images WHERE job_id = ?",
        (job_id,)
    )
    row = await cursor.fetchone()
    max_idx = row["max_idx"]
    
    if max_idx is None:
        return 0
    
    # Create batches
    batch_count = 0
    start_idx = 0
    
    async with get_db_transaction() as db:
        while start_idx <= max_idx:
            end_idx = min(start_idx + batch_size - 1, max_idx)
            
            await db.execute(
                "INSERT INTO batches (job_id, start_idx, end_idx) VALUES (?, ?, ?)",
                (job_id, start_idx, end_idx)
            )
            
            batch_count += 1
            start_idx = end_idx + 1
    
    return batch_count


async def get_pending_batches(job_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    """Get pending batches for processing."""
    db = await get_db()
    
    if job_id:
        cursor = await db.execute(
            """SELECT * FROM batches 
               WHERE job_id = ? AND state = ?
               ORDER BY start_idx LIMIT ?""",
            (job_id, BatchState.PENDING.value, limit)
        )
    else:
        cursor = await db.execute(
            """SELECT * FROM batches 
               WHERE state = ?
               ORDER BY batch_id LIMIT ?""",
            (BatchState.PENDING.value, limit)
        )
    
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_batches_by_state(state: BatchState) -> list[dict]:
    """Get all batches in a specific state."""
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT * FROM batches WHERE state = ? ORDER BY batch_id",
        (state.value,)
    )
    rows = await cursor.fetchall()
    
    return [dict(row) for row in rows]


async def get_batch_by_id(batch_id: int) -> Optional[dict]:
    """Get a specific batch by ID."""
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT * FROM batches WHERE batch_id = ?",
        (batch_id,)
    )
    row = await cursor.fetchone()
    
    return dict(row) if row else None


async def update_batch_state(batch_id: int, state: BatchState) -> None:
    """Update batch state."""
    db = await get_db()
    
    if state == BatchState.PROCESSING:
        await db.execute(
            "UPDATE batches SET state = ?, started_at = datetime('now') WHERE batch_id = ?",
            (state.value, batch_id)
        )
    elif state == BatchState.COMMITTED:
        await db.execute(
            "UPDATE batches SET state = ?, committed_at = datetime('now') WHERE batch_id = ?",
            (state.value, batch_id)
        )
    else:
        await db.execute(
            "UPDATE batches SET state = ? WHERE batch_id = ?",
            (state.value, batch_id)
        )
    await db.commit()


async def get_committed_batch_count(job_id: int) -> int:
    """Get count of committed batches for a job."""
    db = await get_db()
    
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM batches WHERE job_id = ? AND state = ?",
        (job_id, BatchState.COMMITTED.value)
    )
    row = await cursor.fetchone()
    
    return row["cnt"]


# ============================================================================
# Image Results
# ============================================================================

async def save_image_result(
    image_id: int,
    batch_id: int,
    face_count: int,
    matched_count: int,
    unknown_count: int,
    matched_person_ids: list[int]
) -> int:
    """Save image processing result."""
    db = await get_db()
    
    cursor = await db.execute(
        """INSERT INTO image_results 
           (image_id, batch_id, face_count, matched_count, unknown_count, matched_person_ids)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(image_id) DO UPDATE SET
               face_count = excluded.face_count,
               matched_count = excluded.matched_count,
               unknown_count = excluded.unknown_count,
               matched_person_ids = excluded.matched_person_ids,
               processed_at = datetime('now')""",
        (image_id, batch_id, face_count, matched_count, unknown_count, 
         json.dumps(matched_person_ids))
    )
    await db.commit()
    
    return cursor.lastrowid


async def get_image_results_for_batch(batch_id: int) -> list[dict]:
    """Get all image results for a batch."""
    db = await get_db()
    
    cursor = await db.execute(
        """SELECT ir.*, i.source_path, i.filename, i.sha256
           FROM image_results ir
           INNER JOIN images i ON ir.image_id = i.image_id
           WHERE ir.batch_id = ?""",
        (batch_id,)
    )
    rows = await cursor.fetchall()
    
    results = []
    for row in rows:
        result = dict(row)
        result["matched_person_ids"] = json.loads(result["matched_person_ids"] or "[]")
        results.append(result)
    
    return results


