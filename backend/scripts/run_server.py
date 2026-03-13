#!/usr/bin/env python
"""
Run the FastAPI server for Operator and Tracker UIs.
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from app.config import settings
from app.utils.logger import setup_logging, console
from rich.panel import Panel
from rich.table import Table


def main():
    """Start the FastAPI server."""
    setup_logging()
    
    # Create beautiful banner
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[cyan]Operator UI:[/]", f"http://{settings.server_host}:{settings.server_port}/operator")
    table.add_row("[cyan]Tracker UI:[/]",  f"http://{settings.server_host}:{settings.server_port}/tracker")
    table.add_row("[cyan]Hot Storage:[/]", f"{settings.hot_storage_root.absolute()}")
    
    console.print(Panel(
        table,
        title="[bold cyan]Face-Based Photo Segregation System - Server[/bold cyan]",
        expand=False,
        border_style="cyan"
    ))
    
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()

