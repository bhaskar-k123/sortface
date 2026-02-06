"""
Worker runner - batch processing loop.
Runs as a separate process from the server.
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from ..config import settings
from ..db.db import init_database
from ..db.jobs import get_job_config, get_pending_batches, get_job_status, set_job_status
from ..engine.batch_engine import BatchEngine
from ..state.state_writer import StateWriter


class WorkerRunner:
    """
    Main worker process that runs the batch processing loop.
    
    Responsibilities:
    - Initialize system on startup
    - Run resume logic for interrupted batches
    - Process batches in order
    - Write heartbeat for status monitoring (background task)
    - Re-initialize when job config changes
    """
    
    def __init__(self):
        self.state_writer = StateWriter()
        self.batch_engine: BatchEngine | None = None
        self.running = True
        self._heartbeat_task: asyncio.Task | None = None
        self._current_status: str = "starting"
        self._job_initialized: bool = False  # Track if current job was initialized
    
    async def run(self):
        """Main worker loop."""
        # Initialize database
        await init_database()
        
        # Start background heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        try:
            # Run resume logic first
            self._current_status = "resuming"
            await self._resume_interrupted()
            
            # Display CPU usage information
            self._display_cpu_usage_info()
            
            self._current_status = "idle"
            
            # Main processing loop
            while self.running:
                try:
                    # Check if we have a job configured
                    job_config = await get_job_config()
                    if not job_config.get("source_root") or not job_config.get("output_root"):
                        self._current_status = "waiting_for_config"
                        self._job_initialized = False
                        self.batch_engine = None
                        print("No job configured. Waiting...")
                        await asyncio.sleep(3)
                        continue
                    
                    # Check job status - only process if "running"
                    job_status = await get_job_status()
                    if job_status == "terminating":
                        await set_job_status("stopped")
                        job_status = "stopped"
                    if job_status != "running":
                        self._current_status = "waiting_for_start"
                        self._job_initialized = False
                        if job_status == "stopped":
                            print("Job stopped. Waiting for start command...")
                        else:
                            print("Waiting for job to be started...")
                        await asyncio.sleep(3)
                        continue
                    
                    # Initialize/re-initialize when job not yet initialized
                    # This happens every time "Start Job" is clicked
                    if not self._job_initialized:
                        self._current_status = "discovering_images"
                        
                        # Always clear old job data for fresh start
                        print("Clearing old job data...")
                        await self._clear_old_job_data()
                        
                        print(f"Discovering images in: {job_config['source_root']}")
                        
                        # Get selected persons (if any)
                        selected_person_ids = job_config.get("selected_person_ids")
                        if selected_person_ids:
                            print(f"Searching for {len(selected_person_ids)} selected person(s)")
                        else:
                            print("Searching for ALL registered persons")
                        
                        selected_image_paths = job_config.get("selected_image_paths")
                        if selected_image_paths:
                            print(f"Processing only {len(selected_image_paths)} selected image(s)")
                        
                        # Get group mode settings
                        group_mode = job_config.get("group_mode", False)
                        group_folder_name = job_config.get("group_folder_name")
                        if group_mode:
                            print(f"GROUP MODE: Only photos with ALL {len(selected_person_ids)} selected people → folder '{group_folder_name}'")
                        
                        self.batch_engine = BatchEngine(
                            source_root=Path(job_config["source_root"]),
                            output_root=Path(job_config["output_root"]),
                            state_writer=self.state_writer,
                            selected_person_ids=selected_person_ids,
                            selected_image_paths=selected_image_paths,
                            group_mode=group_mode,
                            group_folder_name=group_folder_name,
                        )
                        # Discover and create batches
                        result = await self.batch_engine.discover_images()
                        print(f"Discovered {result['image_count']} images in {result['batch_count']} batches")
                        
                        self._job_initialized = True
                        
                        if result['image_count'] == 0:
                            print("WARNING: No images found! Check your source folder.")
                            print(f"  Source: {job_config['source_root']}")
                            print("  Supported formats: .jpg, .jpeg, .arw")
                    
                    # Get next pending batch
                    batch = await get_pending_batches(limit=1)
                    
                    if not batch:
                        self._current_status = "completed"
                        print("All batches completed!")
                        await set_job_status("completed")
                        self._job_initialized = False  # Allow restart
                        await asyncio.sleep(5)
                        continue
                    
                    batch = batch[0]
                    
                    # Process the batch
                    self._current_status = f"processing_batch_{batch['batch_id']}"
                    print(f"Processing batch {batch['batch_id']}...")
                    result = await self.batch_engine.process_batch(batch["batch_id"])
                    print(f"Batch {batch['batch_id']} completed: {result}")
                    
                except Exception as e:
                    self._current_status = f"error: {str(e)[:50]}"
                    print(f"Error in worker loop: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    # CRITICAL FIX: Reset batch state if we were processing one
                    # Otherwise it stays stuck in PROCESSING and is never retried
                    if 'batch' in locals() and isinstance(batch, dict) and batch.get("batch_id"):
                        try:
                            # Import here to avoid circular dependencies if any, though top-level is better
                            from ..db.jobs import update_batch_state, BatchState
                            print(f"  ⚠ Resetting batch {batch['batch_id']} to PENDING due to error")
                            await update_batch_state(batch["batch_id"], BatchState.PENDING)
                        except Exception as reset_error:
                            print(f"  Failed to reset batch state: {reset_error}")
                            
                    await asyncio.sleep(5)
        finally:
            # Stop heartbeat task
            self.running = False
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
    
    async def _heartbeat_loop(self):
        """
        Background task that writes heartbeat every 3 seconds.
        Runs independently of main processing loop.
        """
        while self.running:
            try:
                self._write_heartbeat()
            except Exception as e:
                print(f"Heartbeat error: {e}")
            await asyncio.sleep(3)
    
    async def _clear_old_job_data(self):
        """Clear old job data when config changes."""
        from ..db.db import get_db
        
        db = await get_db()
        
        # Delete old batches, images, results, and commit log
        # This allows starting fresh with new config
        await db.execute("DELETE FROM commit_log")
        await db.execute("DELETE FROM image_results")
        await db.execute("DELETE FROM batches")
        await db.execute("DELETE FROM images")
        await db.execute("DELETE FROM jobs")
        await db.commit()
        
        # Clear state files
        self.state_writer.clear_batch_states()
        
        print("Old job data cleared.")
    
    async def _resume_interrupted(self):
        """
        Resume logic on startup.
        - PROCESSING batches → reset to PENDING
        - COMMITTING batches → re-run commit phase (_commit_batch), then COMMITTED
        - COMMITTED batches → skip forever
        """
        from ..db.jobs import (
            get_batches_by_state,
            update_batch_state,
            get_job_config,
            BatchState,
        )
        
        print("Running resume logic...")
        
        processing = await get_batches_by_state(BatchState.PROCESSING)
        for b in processing:
            print(f"  Resetting batch {b['batch_id']} from PROCESSING to PENDING")
            await update_batch_state(b["batch_id"], BatchState.PENDING)
        
        committing = await get_batches_by_state(BatchState.COMMITTING)
        if committing:
            job_config = await get_job_config()
            src = job_config.get("source_root") or "."
            out = job_config.get("output_root")
            if out:
                be = BatchEngine(
                    Path(src),
                    Path(out),
                    state_writer=self.state_writer,
                )
                for b in committing:
                    print(f"  Finishing batch {b['batch_id']} (was COMMITTING)")
                    await be._commit_batch(b["batch_id"])
            else:
                print("  No output_root in config; cannot finish COMMITTING batches")
        print("Resume logic complete.")
    
    def _display_cpu_usage_info(self):
        """Display CPU usage configuration and warnings."""
        import os
        
        cpu_count = os.cpu_count() or 4
        worker_count = settings.get_worker_count()
        usage_percent = (worker_count / cpu_count) * 100
        
        print("\n" + "="*60)
        print("PARALLEL PROCESSING CONFIGURATION")
        print("="*60)
        print(f"CPU Cores Available: {cpu_count}")
        print(f"CPU Usage Mode: {settings.cpu_usage_mode}")
        print(f"Workers: {worker_count}")
        print(f"Estimated CPU Usage: ~{usage_percent:.0f}%")
        
        # Display warning if applicable
        warning = settings.get_cpu_usage_warning()
        if warning:
            print(f"\n{warning}")
        else:
            print(f"\n✅ CPU usage is within comfortable limits.")
        
        print("\nTo change CPU usage:")
        print("  - Edit hot_storage/config or set environment variable:")
        print("    CPU_USAGE_MODE=low      (2 workers, ~40% CPU)")
        print("    CPU_USAGE_MODE=balanced (4 workers, ~67% CPU)")
        print("    CPU_USAGE_MODE=high     (max workers, ~90% CPU)")
        print("    CPU_USAGE_MODE=adaptive (auto-detect based on cores)")
        print("="*60 + "\n")
    
    def _write_heartbeat(self):
        """Write heartbeat file for status monitoring."""
        heartbeat_file = settings.state_dir / "worker_heartbeat.json"
        heartbeat_data = {
            "timestamp": datetime.now().isoformat(),
            "pid": os.getpid(),
            "status": self._current_status
        }
        
        # Atomic write
        temp_file = heartbeat_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(heartbeat_data, f)
        temp_file.replace(heartbeat_file)

