"""
FastAPI application entry point.
Serves Operator UI and Tracker UI.
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from .config import settings
from .api import operator, tracker
from .db.db import init_database

# Initialize FastAPI app
app = FastAPI(
    title="Face-Based Photo Segregation System",
    description="Offline face recognition system for event photo sorting",
    version="1.0.0"
)

# Setup templates and static files
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include API routers
app.include_router(operator.router, prefix="/api/operator", tags=["operator"])
app.include_router(tracker.router, prefix="/api/tracker", tags=["tracker"])


@app.on_event("startup")
async def startup_event():
    """Initialize system on startup."""
    # Ensure all hot storage directories exist
    settings.ensure_directories()
    # Initialize database
    await init_database()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with links to Operator and Tracker UIs."""
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/operator", response_class=HTMLResponse)
async def operator_ui(request: Request):
    """Operator control plane UI."""
    return templates.TemplateResponse("operator.html", {"request": request})


@app.get("/tracker", response_class=HTMLResponse)
async def tracker_ui(request: Request):
    """Read-only progress tracker UI."""
    return templates.TemplateResponse("tracker.html", {"request": request})

