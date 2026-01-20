"""
FastAPI application entry point.
Serves Operator UI and Tracker UI.
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

from .config import settings
from .api import operator, tracker
from .db.db import init_database
from .middleware import setup_exception_handlers

# Initialize FastAPI app
app = FastAPI(
    title="Face-Based Photo Segregation System",
    description="Offline face recognition system for event photo sorting",
    version="1.0.0"
)

# Setup centralized error handling
setup_exception_handlers(app)

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


# ============================================================================
# Health Check & Info Endpoints
# ============================================================================

@app.get("/api/health", tags=["system"])
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns service status and basic info.
    """
    return {
        "status": "healthy",
        "service": "Face-Based Photo Segregation System",
        "version": "1.0.0"
    }


@app.get("/api/info", tags=["system"])
async def system_info():
    """
    Get system configuration info.
    Useful for debugging and diagnostics.
    """
    return {
        "version": "1.0.0",
        "hot_storage_root": str(settings.hot_storage_root.absolute()),
        "batch_size": settings.atomic_batch_size,
        "cpu_mode": settings.cpu_usage_mode,
        "worker_count": settings.get_worker_count(),
        "thresholds": {
            "strict": settings.threshold_strict,
            "loose": settings.threshold_loose
        }
    }


# ============================================================================
# UI Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with links to Operator and Tracker UIs."""
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/operator", response_class=HTMLResponse)
async def operator_ui(request: Request):
    """Operator control plane UI."""
    return templates.TemplateResponse("operator.html", {"request": request})


@app.get("/tracker")
async def tracker_redirect():
    """Progress is now in Operator; redirect."""
    return RedirectResponse(url="/operator", status_code=302)


