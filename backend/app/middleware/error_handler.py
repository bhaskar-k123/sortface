"""
Centralized Error Handling Middleware.
Provides consistent error responses across all API endpoints.
"""
import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError


class APIError(Exception):
    """Base class for API errors with consistent response format."""
    
    def __init__(self, message: str, status_code: int = 400, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(APIError):
    """Resource not found error."""
    
    def __init__(self, message: str = "Resource not found", details: dict = None):
        super().__init__(message, status_code=404, details=details)


class ValidationAPIError(APIError):
    """Validation error."""
    
    def __init__(self, message: str = "Validation failed", details: dict = None):
        super().__init__(message, status_code=422, details=details)


class ConflictError(APIError):
    """Conflict error (e.g., duplicate resource)."""
    
    def __init__(self, message: str = "Resource conflict", details: dict = None):
        super().__init__(message, status_code=409, details=details)


def create_error_response(
    status_code: int,
    message: str,
    error_type: str = "error",
    details: dict = None
) -> dict:
    """
    Create a consistent error response format.
    
    Format:
    {
        "success": false,
        "error": {
            "type": "error_type",
            "message": "Human readable message",
            "details": {}  # Optional additional context
        }
    }
    """
    response = {
        "success": False,
        "error": {
            "type": error_type,
            "message": message,
        }
    }
    
    if details:
        response["error"]["details"] = details
    
    return response


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers on the FastAPI app.
    Call this in main.py after creating the app.
    """
    
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        """Handle custom API errors."""
        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                status_code=exc.status_code,
                message=exc.message,
                error_type=exc.__class__.__name__,
                details=exc.details
            )
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle FastAPI HTTPExceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                status_code=exc.status_code,
                message=str(exc.detail),
                error_type="HTTPException"
            )
        )
    
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        """Handle Pydantic validation errors."""
        return JSONResponse(
            status_code=422,
            content=create_error_response(
                status_code=422,
                message="Validation failed",
                error_type="ValidationError",
                details={"errors": exc.errors()}
            )
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected errors with a generic response."""
        # Log the full traceback for debugging
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content=create_error_response(
                status_code=500,
                message="An unexpected error occurred",
                error_type="InternalServerError"
            )
        )
