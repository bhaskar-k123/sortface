"""
Image ingestion and batching engine.
Handles deterministic discovery, SHA-256 hashing, and batch creation.
"""
import hashlib
from pathlib import Path
from typing import Generator

from ..config import settings
from ..db.jobs import (
    create_job,
    add_images_batch,
    create_batches,
    get_active_job,
    update_job_image_counts,
    get_image_count,
)
from ..storage.paths import compute_file_hash


class ImageDiscovery:
    """
    Discovers and catalogs images from a source directory.
    
    Features:
    - Deterministic ordering (sorted by path)
    - Supports .jpg, .jpeg, .arw extensions
    - Computes SHA-256 for deduplication
    """
    
    def __init__(self, source_root: Path):
        self.source_root = source_root
        self.supported_extensions = settings.supported_extensions
    
    def discover(self) -> Generator[dict, None, None]:
        """
        Discover all images in the source directory.
        
        Yields:
            Dict with keys: source_path, filename, extension, ordering_idx
        
        Images are yielded in deterministic order (sorted by full path).
        """
        # Collect all image paths
        image_paths = []
        
        for ext in self.supported_extensions:
            # Case-insensitive matching
            image_paths.extend(self.source_root.rglob(f"*{ext}"))
            image_paths.extend(self.source_root.rglob(f"*{ext.upper()}"))
        
        # Sort for deterministic ordering
        image_paths = sorted(set(image_paths))
        
        # Yield with ordering index
        for idx, path in enumerate(image_paths):
            yield {
                "source_path": str(path),
                "filename": path.name,
                "extension": path.suffix.lower(),
                "ordering_idx": idx
            }
    
    def count(self) -> int:
        """Count total images without loading all paths."""
        count = 0
        for ext in self.supported_extensions:
            count += len(list(self.source_root.rglob(f"*{ext}")))
            count += len(list(self.source_root.rglob(f"*{ext.upper()}")))
        return count


class IngestEngine:
    """
    Manages the full ingestion process.
    
    Steps:
    1. Discover images from source
    2. Compute SHA-256 hashes
    3. Create job and image records
    4. Create atomic batches
    """
    
    def __init__(self, source_root: Path, output_root: Path):
        self.source_root = source_root
        self.output_root = output_root
        self.batch_size = settings.atomic_batch_size
        self.discovery = ImageDiscovery(source_root)
    
    async def run(self, compute_hashes: bool = True, force_rediscover: bool = True) -> dict:
        """
        Run the full ingestion process.
        
        Args:
            compute_hashes: If True, compute SHA-256 for all images
                           (slower but enables deduplication)
            force_rediscover: If True, always re-discover images (default)
        
        Returns:
            Dict with job_id, image_count, batch_count
        """
        # Check for existing active job (only if not forcing rediscovery)
        if not force_rediscover:
            existing_job = await get_active_job()
            if existing_job:
                # Resume existing job
                image_count = await get_image_count(existing_job["job_id"])
                return {
                    "job_id": existing_job["job_id"],
                    "image_count": image_count,
                    "batch_count": 0,  # Already created
                    "resumed": True
                }
        
        # Create new job
        job_id = await create_job(
            str(self.source_root),
            str(self.output_root)
        )
        
        # Discover and catalog images
        images = []
        for image_info in self.discovery.discover():
            if compute_hashes:
                try:
                    image_info["sha256"] = compute_file_hash(
                        Path(image_info["source_path"])
                    )
                except Exception as e:
                    print(f"Warning: Could not hash {image_info['source_path']}: {e}")
                    image_info["sha256"] = None
            
            images.append(image_info)
            
            # Batch insert every 1000 images for efficiency
            if len(images) >= 1000:
                await add_images_batch(job_id, images)
                images = []
        
        # Insert remaining images
        if images:
            await add_images_batch(job_id, images)
        
        # Get total count
        image_count = await get_image_count(job_id)
        
        # Update job counts
        await update_job_image_counts(job_id, image_count, 0)
        
        # Create batches
        batch_count = await create_batches(job_id, self.batch_size)
        
        return {
            "job_id": job_id,
            "image_count": image_count,
            "batch_count": batch_count,
            "resumed": False
        }
    
    async def get_super_batch_info(self, job_id: int, batch_id: int) -> str:
        """
        Get super-batch identifier for a batch.
        Super-batches are organizational groupings of ~3000-4000 images.
        """
        from ..db.jobs import get_batch_by_id
        
        batch = await get_batch_by_id(batch_id)
        if not batch:
            return "Unknown"
        
        # Calculate super-batch based on image range
        # Each super-batch is ~3500 images (70 atomic batches of 50)
        super_batch_size = 3500
        super_batch_num = batch["start_idx"] // super_batch_size + 1
        
        return f"Super-Batch {super_batch_num}"
    
    async def get_image_range_str(self, batch_id: int) -> str:
        """Get human-readable image range for a batch."""
        from ..db.jobs import get_images_for_batch
        
        images = await get_images_for_batch(batch_id)
        if not images:
            return "--"
        
        first_name = Path(images[0]["filename"]).stem
        last_name = Path(images[-1]["filename"]).stem
        
        return f"{first_name} - {last_name}"


async def run_ingestion(source_root: Path, output_root: Path) -> dict:
    """
    Convenience function to run ingestion.
    
    Args:
        source_root: Path to source images (external HDD, read-only)
        output_root: Path to output directory (external HDD, append-only)
    
    Returns:
        Dict with ingestion results
    """
    engine = IngestEngine(source_root, output_root)
    return await engine.run()

