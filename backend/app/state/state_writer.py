"""
State writer for tracker UI.
Writes state files atomically for read-only consumption.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import settings


class StateWriter:
    """
    Writes state files for the tracker UI.
    
    All writes are atomic (write to temp file, then rename).
    Files are written to hot storage only.
    """
    
    def __init__(self):
        self.state_dir = settings.state_dir
        self.batches_dir = self.state_dir / "batches"
        
        # Ensure directories exist
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.batches_dir.mkdir(parents=True, exist_ok=True)
    
    def _atomic_write(self, file_path: Path, data: dict) -> None:
        """Write data atomically using temp file + rename."""
        temp_path = file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        temp_path.replace(file_path)
    
    def write_progress(
        self,
        total_images: int,
        processed_images: int,
        current_superbatch: Optional[str] = None,
        current_batch_id: Optional[int] = None,
        current_batch_state: Optional[str] = None,
        current_image_range: Optional[str] = None,
        last_committed_person: Optional[str] = None,
        last_committed_image: Optional[str] = None,
        start_time: Optional[datetime] = None,
    ) -> None:
        """
        Write main progress file.
        
        This is the primary file read by the tracker UI.
        """
        completion_percent = 0.0
        if total_images > 0:
            completion_percent = (processed_images / total_images) * 100
        
        # Calculate time estimates
        elapsed_seconds = None
        estimated_remaining_seconds = None
        estimated_total_seconds = None
        elapsed_formatted = None
        remaining_formatted = None
        
        if start_time and processed_images > 0:
            elapsed = datetime.now() - start_time
            elapsed_seconds = elapsed.total_seconds()
            
            # Calculate rate and estimate remaining time
            images_per_second = processed_images / elapsed_seconds
            remaining_images = total_images - processed_images
            
            if images_per_second > 0:
                estimated_remaining_seconds = remaining_images / images_per_second
                estimated_total_seconds = total_images / images_per_second
            
            # Format times
            elapsed_formatted = self._format_duration(elapsed_seconds)
            if estimated_remaining_seconds:
                remaining_formatted = self._format_duration(estimated_remaining_seconds)
        
        data = {
            "total_images": total_images,
            "processed_images": processed_images,
            "completion_percent": round(completion_percent, 2),
            "current_superbatch": current_superbatch,
            "current_batch_id": current_batch_id,
            "current_batch_state": current_batch_state,
            "current_image_range": current_image_range,
            "last_committed_person": last_committed_person,
            "last_committed_image": last_committed_image,
            "last_committed_time": datetime.now().isoformat() if last_committed_image else None,
            "updated_at": datetime.now().isoformat(),
            # Time tracking
            "start_time": start_time.isoformat() if start_time else None,
            "elapsed_seconds": elapsed_seconds,
            "elapsed_formatted": elapsed_formatted,
            "estimated_remaining_seconds": estimated_remaining_seconds,
            "estimated_remaining_formatted": remaining_formatted,
            "estimated_total_seconds": estimated_total_seconds,
        }
        
        progress_file = self.state_dir / "progress.json"
        self._atomic_write(progress_file, data)
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    
    def write_batch_state(
        self,
        batch_id: int,
        state: str,
        start_idx: int,
        end_idx: int,
        image_range: Optional[str] = None
    ) -> None:
        """
        Write individual batch state file.
        
        Used for batch history in tracker UI.
        """
        if image_range is None:
            image_range = f"IMG_{start_idx:05d} - IMG_{end_idx:05d}"
        
        data = {
            "batch_id": batch_id,
            "state": state,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "image_range": image_range,
            "updated_at": datetime.now().isoformat()
        }
        
        batch_file = self.batches_dir / f"{batch_id}.json"
        self._atomic_write(batch_file, data)
    
    def clear_batch_states(self) -> None:
        """Clear all batch state files (for new job)."""
        for batch_file in self.batches_dir.glob("*.json"):
            try:
                batch_file.unlink()
            except Exception:
                pass

