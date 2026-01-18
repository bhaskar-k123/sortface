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


def main():
    """Start the FastAPI server."""
    print("=" * 60)
    print("Face-Based Photo Segregation System - Server")
    print("=" * 60)
    print(f"Operator UI: http://{settings.server_host}:{settings.server_port}/operator")
    print(f"Tracker UI:  http://{settings.server_host}:{settings.server_port}/tracker")
    print(f"Hot Storage: {settings.hot_storage_root.absolute()}")
    print("=" * 60)
    
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()

