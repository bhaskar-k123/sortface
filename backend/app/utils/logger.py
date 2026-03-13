import logging
import sys
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme

# Custom theme for the console
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "critical": "red reverse",
    "success": "green bold",
})

# Create a shared console instance
console = Console(theme=custom_theme)

def setup_logging(level="INFO"):
    """Set up rich logging configuration."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console, tracebacks_show_locals=True)]
    )
    
    # Mute some noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("insightface").setLevel(logging.WARNING)
    logging.getLogger("onnxruntime").setLevel(logging.ERROR)

def get_logger(name):
    """Get a named logger."""
    return logging.getLogger(name)
