# ==========================================================
# FINAI ONE CLICK STARTUP
# Docker: Kafka + PostgreSQL + Zookeeper
# Local: FastAPI + Scraper + AI Consumer + React
# ==========================================================

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "====================================="
Write-Host "      FINAI LOCAL STACK START"
Write-Host "====================================="
Write-Host ""

Set-Location $ROOT


# -----------------------------
# 1. Start infrastructure
# -----------------------------

Write-Host "[1/5] Starting Docker infrastructure..."

docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker startup failed"
    exit 1
}


Write-Host "Waiting for services..."

Start-Sleep -Seconds 15


# -----------------------------
# 2. Backend dependencies
# -----------------------------

Write-Host "[2/5] Checking Python environment..."

Set-Location "$ROOT\backend"


python -c "import fastapi,aiokafka,asyncpg,feedparser" 2>$null

if ($LASTEXITCODE -ne 0) {

    Write-Host "Installing backend packages..."

    pip install -r requirements.txt
}

Write-Host "Running database migrations..."
python -m database.migrate

# -----------------------------
# 3. Start API
# -----------------------------

Write-Host "[3/5] Starting FastAPI..."

Start-Process powershell `
    -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$ROOT\backend'; python -m uvicorn api.main:app --reload --port 8000"


# -----------------------------
# 4. Start workers
# -----------------------------

Write-Host "[4/5] Starting AI workers..."


Start-Process powershell `
    -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$ROOT\backend'; python -m scraper.rss_worker"


Start-Process powershell `
    -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$ROOT\backend'; python -m ai_engine.consumer"



# -----------------------------
# 5. Start frontend
# -----------------------------

Write-Host "[5/5] Starting frontend..."

Start-Process powershell `
    -ArgumentList `
    "-NoExit",
    "-Command",
    "cd '$ROOT\frontend'; npm install; npm run dev"



Write-Host ""
Write-Host "====================================="
Write-Host " FINAI STARTED"
Write-Host "====================================="
Write-Host ""
Write-Host "Frontend:"
Write-Host " http://localhost:5173"
Write-Host ""
Write-Host "API:"
Write-Host " http://localhost:8000"
Write-Host ""
Write-Host "====================================="