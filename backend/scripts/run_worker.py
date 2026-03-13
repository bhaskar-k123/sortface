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
from app.utils.logger import setup_logging, console
from rich.panel import Panel
from rich.table import Table


def main():
    """Start the batch processing worker."""
    setup_logging()
    
    # Create beautiful banner
    info_table = Table(show_header=False, box=None, padding=(0, 1))
    info_table.add_row("[cyan]Hot Storage:[/]", f"{settings.hot_storage_root.absolute()}")
    info_table.add_row("[cyan]Batch Size:[/]",  f"{settings.atomic_batch_size} images")
    
    console.print(Panel(
        info_table,
        title="[bold green]Face-Based Photo Segregation System - Worker[/bold green]",
        subtitle="[yellow]Press Ctrl+C to stop[/yellow]",
        expand=False,
        border_style="green"
    ))
    
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

