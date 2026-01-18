#!/usr/bin/env python
"""
Run the batch processing worker.
This is a separate process from the server.
"""
import sys
import asyncio
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.worker.runner import WorkerRunner


def main():
    """Start the batch processing worker."""
    print("=" * 60)
    print("Face-Based Photo Segregation System - Worker")
    print("=" * 60)
    print(f"Hot Storage: {settings.hot_storage_root.absolute()}")
    print(f"Batch Size:  {settings.atomic_batch_size} images")
    print("=" * 60)
    print()
    print("Worker starting... Press Ctrl+C to stop.")
    print()
    
    # Ensure directories exist
    settings.ensure_directories()
    
    # Run the worker
    runner = WorkerRunner()
    try:
        asyncio.run(runner.run())
    except KeyboardInterrupt:
        print("\nWorker stopped by user.")


if __name__ == "__main__":
    main()

