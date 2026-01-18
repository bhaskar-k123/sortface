# ============================================
# Face Segregation System - Start Server
# ============================================
# Double-click this file or right-click -> Run with PowerShell

$Host.UI.RawUI.WindowTitle = "Face Segregation - Server"

# Navigate to project directory
Set-Location $PSScriptRoot

# Activate virtual environment
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Face Segregation System - SERVER" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Start server
Set-Location backend
Write-Host "Starting server at http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Gray

python scripts/run_server.py

# Keep window open on error
Write-Host "`nServer stopped. Press any key to exit..." -ForegroundColor Yellow
pause

