# ============================================
# Face Segregation System - Start Worker
# ============================================
# Double-click this file or right-click -> Run with PowerShell

$Host.UI.RawUI.WindowTitle = "Face Segregation - Worker"

# Navigate to project directory
Set-Location $PSScriptRoot

# Activate virtual environment
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Face Segregation System - WORKER" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1

# Start worker
Set-Location backend
Write-Host "Starting worker process..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Gray

python scripts/run_worker.py

# Keep window open on error
Write-Host "`nWorker stopped. Press any key to exit..." -ForegroundColor Yellow
pause

