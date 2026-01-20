"""
Middleware Package.
Centralized middleware for error handling, logging, etc.
"""
from .error_handler import setup_exception_handlers

__all__ = ["setup_exception_handlers"]
