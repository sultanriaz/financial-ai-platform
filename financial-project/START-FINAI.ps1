# ==========================================================
# FINAI ONE CLICK STARTUP (START-FINAI.ps1)
# Docker: Kafka + PostgreSQL + Zookeeper
# Migrations: Company Intelligence Schema Migration
# Local: FastAPI + Price Poller + Scraper + AI Consumer + React
# ==========================================================

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "    FINAI FULL STACK INITIALIZING"   -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $ROOT

# -----------------------------
# 1. Start Docker Infrastructure
# -----------------------------
Write-Host "[1/6] Starting Docker infrastructure (Kafka, Postgres, Zookeeper)..." -ForegroundColor Yellow

docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker compose startup failed." -ForegroundColor Red
    exit 1
}

Write-Host "Waiting for database and message broker to become healthy..." -ForegroundColor Gray
Start-Sleep -Seconds 10


# -----------------------------
# 2. Check Backend Environment
# -----------------------------
Write-Host "[2/6] Checking Python backend dependencies..." -ForegroundColor Yellow

Set-Location "$ROOT\backend"

python -c "import fastapi,aiokafka,asyncpg,feedparser,yfinance" 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing missing backend dependencies from requirements.txt..." -ForegroundColor Gray
    pip install -r requirements.txt
}


# -----------------------------
# 3. Database Migration
# -----------------------------
Write-Host "[3/6] Running database migrations for Company Intelligence..." -ForegroundColor Yellow

python -m database.migrate

if ($LASTEXITCODE -ne 0) {
    Write-Host "Database migration warning (continuing startup)..." -ForegroundColor Magenta
} else {
    Write-Host "Database schema and company tables up to date." -ForegroundColor Green
}


# -----------------------------
# 4. Start FastAPI API & Stream
# -----------------------------
Write-Host "[4/6] Starting FastAPI API backend (port 8000)..." -ForegroundColor Yellow

Start-Process powershell `
    -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$ROOT\backend'; $env:PYTHONPATH='$ROOT\backend'; python -m uvicorn api.main:app --reload --port 8000"


# -----------------------------
# 5. Start Workers
# -----------------------------
Write-Host "[5/6] Starting Scraper & AI Engine Consumer..." -ForegroundColor Yellow

# RSS Scraper Worker
Start-Process powershell `
    -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$ROOT\backend'; $env:PYTHONPATH='$ROOT\backend'; python -m scraper.rss_worker"

# AI Consumer with Entity Extraction & Company Enrichment
Start-Process powershell `
    -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$ROOT\backend'; $env:PYTHONPATH='$ROOT\backend'; python -m ai_engine.consumer"


# -----------------------------
# 6. Start Frontend
# -----------------------------
Write-Host "[6/6] Starting React dashboard frontend..." -ForegroundColor Yellow

Start-Process powershell `
    -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$ROOT\frontend'; npm run dev"


Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "    FINAI PLATFORM RUNNING"          -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Dashboard:  http://localhost:5173" -ForegroundColor White
Write-Host "REST API:   http://localhost:8000" -ForegroundColor White
Write-Host "API Docs:   http://localhost:8000/docs" -ForegroundColor White
Write-Host "WebSocket:  ws://localhost:8000/ws/news-stream" -ForegroundColor White
Write-Host "Company Endpoint: http://localhost:8000/api/company/{ticker}" -ForegroundColor White
Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
