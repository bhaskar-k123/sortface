"""
Batch processing engine.
Implements the atomic batch state machine with crash-safe resume.

State Machine:
    PENDING → PROCESSING → COMMITTING → COMMITTED

Rules:
- PROCESSING: Face detection, embedding, matching. NO external HDD writes.
- COMMITTING: Compress, fan-out route, append-only writes.
- On crash during PROCESSING → reset to PENDING
- On crash during COMMITTING → run commit reconciliation
- COMMITTED batches are never reprocessed
"""
from pathlib import Path
from typing import Optional
from datetime import datetime
import asyncio

from ..config import settings
from ..state.state_writer import StateWriter
from ..db.jobs import (
    BatchState,
    get_batch_by_id,
    get_images_for_batch,
    update_batch_state,
    save_image_result,
    get_image_results_for_batch,
    update_job_image_counts,
    get_active_job,
    get_committed_batch_count,
    get_image_count,
)
from ..db.registry import get_person_by_id
from ..storage.paths import compute_file_hash
from .faces import FaceEngine
from .match import FaceMatcher
from .compress import CompressionEngine
from .raw_convert import RawConversionEngine
from .routing import RoutingEngine, CommitReconciliation
from .ingest import IngestEngine


class BatchEngine:
    """
    Orchestrates batch processing with atomic state transitions.
    
    Guarantees:
    - At most 50 images can be lost on crash
    - No duplicate outputs
    - Resume-safe after any failure
    - Idempotent operations
    """
    
    def __init__(
        self,
        source_root: Path,
        output_root: Path,
        state_writer: Optional[StateWriter] = None,
        selected_person_ids: Optional[list[int]] = None
    ):
        self.source_root = source_root
        self.output_root = output_root
        self.state_writer = state_writer or StateWriter()
        self.selected_person_ids = selected_person_ids
        
        # Initialize engines
        self.face_engine = FaceEngine()
        self.matcher = FaceMatcher(selected_person_ids=selected_person_ids)
        self.compression_engine = CompressionEngine()
        self.raw_engine = RawConversionEngine()
        self.routing_engine = RoutingEngine(output_root)
        self.ingest_engine = IngestEngine(source_root, output_root)
        
        # Track current state for progress reporting
        self.current_job_id: Optional[int] = None
        self.total_images: int = 0
        self.processed_images: int = 0
        self.start_time: Optional[datetime] = None
    
    async def discover_images(self) -> dict:
        """
        Run image discovery and create batches.
        Called once at job start.
        """
        # Skip SHA-256 hashing for faster startup on external HDDs
        result = await self.ingest_engine.run(compute_hashes=False)
        
        self.current_job_id = result["job_id"]
        self.total_images = result["image_count"]
        self.start_time = datetime.now()  # Start timer
        
        # Update progress
        self._update_progress(current_batch_state="READY")
        
        return result
    
    async def process_batch(self, batch_id: int) -> dict:
        """
        Process a single batch through the full state machine.
        
        Flow:
        1. Transition to PROCESSING
        2. Run face detection + matching (no external writes)
        3. Transition to COMMITTING
        4. Compress and route to person folders
        5. Transition to COMMITTED
        
        Returns:
            Dict with processing results
        """
        batch = await get_batch_by_id(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        if batch["state"] == BatchState.COMMITTED.value:
            # Already committed - skip
            return {"batch_id": batch_id, "status": "already_committed"}
        
        # Get batch images
        images = await get_images_for_batch(batch_id)
        if not images:
            # Empty batch - mark as committed
            await update_batch_state(batch_id, BatchState.COMMITTED)
            return {"batch_id": batch_id, "status": "empty"}
        
        # Get image range for progress display
        image_range = await self.ingest_engine.get_image_range_str(batch_id)
        superbatch = await self.ingest_engine.get_super_batch_info(
            batch["job_id"], batch_id
        )
        
        # ================================================================
        # PHASE 1: PROCESSING (no external writes)
        # ================================================================
        
        await update_batch_state(batch_id, BatchState.PROCESSING)
        self._update_progress(
            current_batch_id=batch_id,
            current_batch_state="PROCESSING",
            current_image_range=image_range,
            current_superbatch=superbatch
        )
        
        # Write batch state file
        self.state_writer.write_batch_state(
            batch_id=batch_id,
            state="PROCESSING",
            start_idx=batch["start_idx"],
            end_idx=batch["end_idx"],
            image_range=image_range
        )
        
        # Refresh matcher centroids
        await self.matcher.refresh_centroids()
        
        # Process each image (parallel or sequential based on settings)
        if settings.enable_parallel_processing:
            # Get adaptive worker count
            worker_count = settings.get_worker_count()
            semaphore = asyncio.Semaphore(worker_count)
            
            async def process_with_semaphore(image):
                async with semaphore:
                    return await self._process_image(image, batch_id)
            
            tasks = [process_with_semaphore(img) for img in images]
            results = await asyncio.gather(*tasks)
        else:
            # Sequential processing (fallback)
            results = []
            for image in images:
                result = await self._process_image(image, batch_id)
                results.append(result)
        
        # ================================================================
        # PHASE 2: COMMITTING (external writes, append-only)
        # ================================================================
        
        await update_batch_state(batch_id, BatchState.COMMITTING)
        self._update_progress(current_batch_state="COMMITTING")
        self.state_writer.write_batch_state(
            batch_id=batch_id,
            state="COMMITTING",
            start_idx=batch["start_idx"],
            end_idx=batch["end_idx"],
            image_range=image_range
        )
        
        # Get results with matches
        image_results = await get_image_results_for_batch(batch_id)
        
        # Filter images with matches
        images_with_matches = [r for r in image_results if r["matched_count"] > 0]
        
        # Compress and route images in parallel (with limit to avoid overwhelming external HDD)
        commit_semaphore = asyncio.Semaphore(settings.get_worker_count())
        
        async def commit_with_semaphore(img_result):
            async with commit_semaphore:
                return await self._commit_image(img_result, batch_id)
        
        if images_with_matches:
            commit_tasks = [commit_with_semaphore(r) for r in images_with_matches]
            commit_results = await asyncio.gather(*commit_tasks)
            
            # Update last committed for progress (from last successful route)
            for commit_result in reversed(commit_results):
                if commit_result.get("routed"):
                    last_routed = commit_result["routed"][-1]
                    self._update_progress(
                        last_committed_person=last_routed.get("person_name"),
                        last_committed_image=commit_result.get("output_filename")
                    )
                    break
        else:
            commit_results = []
        
        # ================================================================
        # PHASE 3: COMMITTED
        # ================================================================
        
        await update_batch_state(batch_id, BatchState.COMMITTED)
        self.state_writer.write_batch_state(
            batch_id=batch_id,
            state="COMMITTED",
            start_idx=batch["start_idx"],
            end_idx=batch["end_idx"],
            image_range=image_range
        )
        
        # Update processed count
        self.processed_images += len(images)
        await self._update_job_progress(batch["job_id"])
        
        self._update_progress(current_batch_state="COMMITTED")
        
        # Print progress summary with time estimates
        self._print_progress_summary()
        
        # Count skipped files
        skipped_count = sum(1 for r in results if r.get("skipped"))
        
        return {
            "batch_id": batch_id,
            "status": "committed",
            "images_processed": len(images),
            "faces_detected": sum(r.get("face_count", 0) for r in results),
            "matches": sum(r.get("matched_count", 0) for r in results),
            "unknowns": sum(r.get("unknown_count", 0) for r in results),
            "files_routed": len(commit_results),
            "skipped": skipped_count
        }
    
    async def _process_image(self, image: dict, batch_id: int) -> dict:
        """
        Process a single image: detect faces, compute embeddings, match.
        
        No external writes happen here.
        Gracefully skips files that cannot be processed.
        """
        source_path = Path(image["source_path"])
        is_raw = source_path.suffix.lower() == ".arw"
        
        # Show which image is being processed
        print(f"  📷 Processing: {source_path.name}")
        
        temp_path: Optional[Path] = None
        
        try:
            # Get image for face detection
            if is_raw:
                # Convert RAW to temp JPEG for recognition
                try:
                    temp_path = self.raw_engine.convert_for_recognition(source_path)
                    recognition_path = temp_path
                except Exception as e:
                    # Gracefully skip unsupported/corrupted RAW files
                    error_msg = str(e).replace("b'", "").replace("'", "")
                    print(f"  ⚠ Skipping {source_path.name}: {error_msg}")
                    # Save empty result so we don't retry this file
                    await save_image_result(
                        image_id=image["image_id"],
                        batch_id=batch_id,
                        face_count=0,
                        matched_count=0,
                        unknown_count=0,
                        matched_person_ids=[]
                    )
                    return {
                        "image_id": image["image_id"],
                        "face_count": 0,
                        "matched_count": 0,
                        "unknown_count": 0,
                        "matched_person_ids": [],
                        "skipped": True,
                        "skip_reason": error_msg
                    }
            else:
                recognition_path = source_path
            
            # Detect faces and get embeddings
            try:
                faces = self.face_engine.detect_and_embed(recognition_path)
            except Exception as e:
                # Gracefully skip files that can't be read/processed
                print(f"  ⚠ Skipping {source_path.name}: Could not process image - {e}")
                await save_image_result(
                    image_id=image["image_id"],
                    batch_id=batch_id,
                    face_count=0,
                    matched_count=0,
                    unknown_count=0,
                    matched_person_ids=[]
                )
                return {
                    "image_id": image["image_id"],
                    "face_count": 0,
                    "matched_count": 0,
                    "unknown_count": 0,
                    "matched_person_ids": [],
                    "skipped": True,
                    "skip_reason": str(e)
                }
            
            # Match each face against registry
            matched_ids = []
            unknown_count = 0
            
            for face in faces:
                result = await self.matcher.match(
                    face["embedding"],
                    learn_on_strict=True
                )
                
                if result.is_matched:
                    matched_ids.append(result.person_id)
                else:
                    unknown_count += 1
            
            # Deduplicate matched IDs
            matched_ids = list(set(matched_ids))
            
            # Compute hash if not already done
            if not image.get("sha256"):
                from ..db.jobs import update_image_hash
                sha256 = compute_file_hash(source_path)
                await update_image_hash(image["image_id"], sha256)
                image["sha256"] = sha256
            
            # Save result
            await save_image_result(
                image_id=image["image_id"],
                batch_id=batch_id,
                face_count=len(faces),
                matched_count=len(matched_ids),
                unknown_count=unknown_count,
                matched_person_ids=matched_ids
            )
            
            # Summary for this image
            if len(faces) == 0:
                print(f"      → No faces detected")
            elif len(matched_ids) == 0:
                print(f"      → {len(faces)} face(s), no matches")
            else:
                print(f"      → {len(faces)} face(s), {len(matched_ids)} matched ✓")
            
            return {
                "image_id": image["image_id"],
                "face_count": len(faces),
                "matched_count": len(matched_ids),
                "unknown_count": unknown_count,
                "matched_person_ids": matched_ids
            }
            
        finally:
            # Clean up temp file if created
            if temp_path and temp_path.exists():
                self.raw_engine.cleanup_temp_file(temp_path)
    
    async def _commit_image(self, img_result: dict, batch_id: int) -> dict:
        """
        Commit a single image: compress and route to person folders.
        
        External writes happen here (append-only).
        """
        source_path = Path(img_result["source_path"])
        is_raw = source_path.suffix.lower() == ".arw"
        
        # Generate output filename
        original_stem = source_path.stem
        file_hash = img_result["sha256"]
        
        from ..storage.paths import generate_deterministic_filename
        output_filename = generate_deterministic_filename(original_stem, file_hash)
        
        # Staging path
        staged_path = settings.staging_dir / output_filename
        
        try:
            # Compress to staging (ONCE)
            if is_raw:
                self.raw_engine.convert_for_delivery(source_path, staged_path)
            else:
                self.compression_engine.compress(source_path, staged_path)
            
            # Fan-out route to all matched persons
            routed = await self.routing_engine.route_image(
                batch_id=batch_id,
                image_id=img_result["image_id"],
                staged_path=staged_path,
                original_stem=original_stem,
                file_hash=file_hash,
                matched_person_ids=img_result["matched_person_ids"]
            )
            
            return {
                "image_id": img_result["image_id"],
                "output_filename": output_filename,
                "routed": routed,
                "status": "committed"
            }
            
        finally:
            # Clean up staging file
            self.routing_engine.cleanup_staged_file(staged_path)
    
    async def _update_job_progress(self, job_id: int) -> None:
        """Update job progress in database."""
        committed_batches = await get_committed_batch_count(job_id)
        batch_size = settings.atomic_batch_size
        processed = committed_batches * batch_size
        
        # Cap at total (last batch may be smaller)
        if processed > self.total_images:
            processed = self.total_images
        
        await update_job_image_counts(job_id, self.total_images, processed)
        self.processed_images = processed
    
    def _update_progress(
        self,
        current_batch_id: Optional[int] = None,
        current_batch_state: Optional[str] = None,
        current_image_range: Optional[str] = None,
        current_superbatch: Optional[str] = None,
        last_committed_person: Optional[str] = None,
        last_committed_image: Optional[str] = None
    ) -> None:
        """Write progress state file for tracker UI."""
        self.state_writer.write_progress(
            total_images=self.total_images,
            processed_images=self.processed_images,
            current_superbatch=current_superbatch,
            current_batch_id=current_batch_id,
            current_batch_state=current_batch_state,
            current_image_range=current_image_range,
            last_committed_person=last_committed_person,
            last_committed_image=last_committed_image,
            start_time=self.start_time
        )
    
    def _print_progress_summary(self) -> None:
        """Print progress summary with time estimates to console."""
        if self.total_images == 0:
            return
        
        percent = (self.processed_images / self.total_images) * 100
        
        # Calculate time estimates
        if self.start_time and self.processed_images > 0:
            elapsed = datetime.now() - self.start_time
            elapsed_seconds = elapsed.total_seconds()
            
            images_per_second = self.processed_images / elapsed_seconds
            remaining_images = self.total_images - self.processed_images
            
            if images_per_second > 0:
                remaining_seconds = remaining_images / images_per_second
                
                # Format times
                elapsed_str = self._format_time(elapsed_seconds)
                remaining_str = self._format_time(remaining_seconds)
                
                print(f"\n📊 Progress: {self.processed_images}/{self.total_images} ({percent:.1f}%)")
                print(f"⏱️  Elapsed: {elapsed_str} | Remaining: ~{remaining_str}")
                print(f"⚡ Speed: {images_per_second:.2f} images/sec\n")
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds to human-readable time string."""
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


async def run_resume_logic() -> None:
    """
    Run resume logic on worker startup.
    
    - PROCESSING batches → reset to PENDING
    - COMMITTING batches → run commit reconciliation
    - COMMITTED batches → skip forever
    """
    from ..db.jobs import get_batches_by_state, get_job_config
    
    print("Running batch resume logic...")
    
    # Reset PROCESSING to PENDING
    processing = await get_batches_by_state(BatchState.PROCESSING)
    for batch in processing:
        print(f"  Resetting batch {batch['batch_id']} from PROCESSING to PENDING")
        await update_batch_state(batch["batch_id"], BatchState.PENDING)
    
    # Reconcile COMMITTING batches
    committing = await get_batches_by_state(BatchState.COMMITTING)
    for batch in committing:
        print(f"  Reconciling batch {batch['batch_id']} (was COMMITTING)")
        
        # Get job config for output root
        config = await get_job_config()
        if config.get("output_root"):
            reconciler = CommitReconciliation(Path(config["output_root"]))
            result = await reconciler.reconcile_batch(batch["batch_id"])
            print(f"    Verified: {result['verified']}, Copied: {result['copied']}, Failed: {result['failed']}")
        
        # Mark as committed (reconciliation complete)
        await update_batch_state(batch["batch_id"], BatchState.COMMITTED)
    
    print("Resume logic complete.")

