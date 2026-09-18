#Requires -Version 5.1
<#
.SYNOPSIS
    Start (or stop) the entire Financial AI Platform with one command.

.USAGE
    cd C:\black_paper\Projects\financial-ai-platform
    .\Run-All.ps1                 # start everything
    .\Run-All.ps1 -SkipPatch      # start without re-writing consumer.py
    .\Run-All.ps1 -NoBrowser      # don't open http://localhost:5173
    .\Run-All.ps1 -Stop           # tear everything down

.NOTES
    Opens four separate PowerShell windows:
      uvicorn (API)  |  scraper  |  consumer  |  vite (frontend)
    Tracks their PIDs in .run-state.json so -Stop can clean up.
#>
param(
    [string]$ProjectRoot = $PSScriptRoot,
    [switch]$Stop,
    [switch]$SkipPatch,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$BackendDir  = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$StateFile   = Join-Path $ProjectRoot ".run-state.json"

# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────
function Say([string]$msg, [string]$color = "Gray") {
    Write-Host ("  {0}" -f $msg) -ForegroundColor $color
}
function Header([string]$msg) {
    Write-Host ""
    Write-Host ("  ── {0}" -f $msg) -ForegroundColor Cyan
}

function Wait-Healthy([string]$Container, [int]$TimeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $status = (& docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $Container 2>$null)
        if ($status -eq "healthy" -or $status -eq "running") { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Test-Venv {
    $activate = Join-Path $BackendDir ".venv\Scripts\Activate.ps1"
    if (-not (Test-Path $activate)) {
        throw "backend\.venv not found. Create it first:`n    cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r ..\requirements.txt"
    }
    return $activate
}

function Save-State($obj) {
    $obj | ConvertTo-Json -Depth 5 | Set-Content -Path $StateFile -Encoding UTF8
}
function Read-State {
    if (Test-Path $StateFile) { return Get-Content $StateFile -Raw | ConvertFrom-Json }
    return $null
}
function Clear-State {
    if (Test-Path $StateFile) { Remove-Item $StateFile -Force }
}

# ────────────────────────────────────────────────────────────────────────────
# -Stop path
# ────────────────────────────────────────────────────────────────────────────
if ($Stop) {
    Header "Stopping Financial AI Platform"
    $state = Read-State

if ($state) {
    foreach ($entry in $state.Processes) {
        $procId = $entry.Pid
        if ($procId) {
            try {
                $null = Get-Process -Id $procId -ErrorAction Stop
                Say ("Killing PID {0} ({1})" -f $procId, $entry.Name)
                & taskkill /PID $procId /T /F 2>&1 | Out-Null
            } catch { }
        }
    }
    Clear-State
} else {
        Say "No .run-state.json found - killing by name as fallback" "Yellow"
        Get-Process python,uvicorn -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -like "$BackendDir*" -or $_.Path -like "$ProjectRoot*" } |
            ForEach-Object { Say ("Killing python PID {0}" -f $_.Id); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
        Get-Process node -ErrorAction SilentlyContinue |
            ForEach-Object { Say ("Killing node PID {0}" -f $_.Id); Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    }

    Header "Docker down"
    Push-Location $ProjectRoot
    & docker compose down 2>&1 | ForEach-Object { Say $_ "DarkGray" }
    Pop-Location

    Write-Host ""
    Say "Done. Everything stopped." "Green"
    Write-Host ""
    exit 0
}

# ────────────────────────────────────────────────────────────────────────────
# Pre-flight
# ────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Financial AI Platform - Run-All" -ForegroundColor Cyan
Write-Host ("  Project root: {0}" -f $ProjectRoot)
Write-Host ""

Header "Pre-flight"
try { & docker info *> $null } catch {
    Say "Docker is not running. Start Docker Desktop and retry." "Red"
    exit 1
}
Say "Docker: OK" "Green"

$activate = Test-Venv
Say "venv: OK" "Green"

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Say "node_modules missing - running npm install (this takes a minute)" "Yellow"
    Push-Location $FrontendDir
    & npm install
    Pop-Location
}
Say "node_modules: OK" "Green"

# ────────────────────────────────────────────────────────────────────────────
# Patch consumer.py (Ollama-optional, offset=earliest)
# ────────────────────────────────────────────────────────────────────────────
if (-not $SkipPatch) {
    Header "Patching backend/ai_engine/consumer.py"

    $consumerPath = Join-Path $BackendDir "ai_engine\consumer.py"
    if (-not (Test-Path $consumerPath)) { throw "consumer.py not found at $consumerPath" }

    $bak = "$consumerPath.bak"
    if (-not (Test-Path $bak)) { Copy-Item $consumerPath $bak }

    $newConsumer = @'
import asyncio, json, logging
from datetime import datetime
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import select
from ai_engine.llm_processor import OllamaExtractor
from ai_engine.sentiment import FinBERTSentiment
from common.config import settings
from database.db import SessionLocal, init_db
from database.models import News, Analysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-consumer")

# Defaults used when Ollama is unreachable so the article still lands in Postgres.
_OLLAMA_FALLBACK = {
    "company": None, "ticker": None, "sector": None,
    "event": None, "impact": "Unknown",
    "risk_level": "Unknown", "category": "Market News",
}


async def run() -> None:
    await init_db()

    consumer = AIOKafkaConsumer(
        "financial-news-raw",
        bootstrap_servers=settings.kafka_url,
        group_id="financial-ai-workers",
        enable_auto_commit=False,
        # earliest: read backlog on first run when the group has no offset yet.
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode()),
        max_poll_records=1,
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_url,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await consumer.start()
    await producer.start()

    sentiment = FinBERTSentiment()
    extractor = OllamaExtractor()

    try:
        async for message in consumer:
            article = message.value
            try:
                async with SessionLocal() as session:
                    if await session.scalar(select(News).where(News.url == article["url"])):
                        await consumer.commit()
                        continue

                    news = News(
                        id=article["id"],
                        title=article["title"],
                        description=article.get("description"),
                        source=article["source"],
                        url=article["url"],
                        published_time=datetime.fromisoformat(article["published_time"]),
                    )
                    session.add(news)
                    await session.flush()

                    result = sentiment.analyze(
                        f'{article["title"]}. {article.get("description", "")}'
                    )

                    # Ollama is optional. If it's down, keep FinBERT results and
                    # fill entity fields with fallbacks so the row still commits.
                    try:
                        result.update(await extractor.extract(
                            article["title"], article.get("description", "")
                        ))
                    except Exception as exc:
                        logger.warning("Ollama unavailable, skipping entities: %s", exc)
                        result.update(_OLLAMA_FALLBACK)

                    session.add(Analysis(
                        news_id=news.id,
                        sentiment_score=result["score"],
                        sentiment_label=result["sentiment"],
                        company=result.get("company"),
                        ticker=result.get("ticker"),
                        sector=result.get("sector"),
                        event=result.get("event"),
                        impact=result.get("impact"),
                        risk_level=result.get("risk_level"),
                        category=result.get("category"),
                    ))
                    await session.commit()

                await producer.send_and_wait("financial-news-results", {**article, **result})
                await consumer.commit()
                logger.info(
                    "Processed: %s | %s (%.3f)",
                    article["title"][:60], result["sentiment"], result["score"]
                )

            except Exception:
                logger.exception("Processing failed for %s", article.get("url", "unknown"))
                await producer.send_and_wait(
                    "financial-news-dlq", {"article": article, "error": "see consumer logs"}
                )
                await consumer.commit()

    finally:
        sentiment.unload()
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
'@
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($consumerPath, $newConsumer, $utf8NoBom)
    Say "consumer.py rewritten (Ollama optional, offset=earliest)" "Green"
    Say "backup: backend\ai_engine\consumer.py.bak" "DarkGray"
} else {
    Header "Skipping consumer patch (-SkipPatch)"
}

# ────────────────────────────────────────────────────────────────────────────
# Kill any stale processes from previous runs
# ────────────────────────────────────────────────────────────────────────────
Header "Cleaning up stale processes"
$stale = Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and ($_.Path -like "$BackendDir*" -or $_.Path -like "$ProjectRoot*") }
if ($stale) {
    foreach ($p in $stale) {
        Say ("Killing stale python PID {0}" -f $p.Id) "Yellow"
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
} else {
    Say "No stale python processes"
}
Get-Process node -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and $_.Path -like "$FrontendDir*" } |
    ForEach-Object {
        Say ("Killing stale node PID {0}" -f $_.Id) "Yellow"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }

# ────────────────────────────────────────────────────────────────────────────
# Infra
# ────────────────────────────────────────────────────────────────────────────
Header "Starting Docker infra"
Push-Location $ProjectRoot
& docker compose up -d postgres zookeeper kafka kafka-init 2>&1 | ForEach-Object { Say $_ "DarkGray" }
Pop-Location

Say "Waiting for postgres to be healthy..." 
if (-not (Wait-Healthy "finai-postgres" 90)) {
    Say "postgres did not become healthy in 90s" "Red"
    Say "Check: docker logs finai-postgres" "Red"
    exit 1
}
Say "postgres: healthy" "Green"

Say "Waiting for kafka to be healthy..."
if (-not (Wait-Healthy "finai-kafka" 90)) {
    Say "kafka did not become healthy in 90s" "Red"
    Say "Check: docker logs finai-kafka" "Red"
    exit 1
}
Say "kafka: healthy" "Green"

# Wait for kafka-init to actually finish creating topics
Start-Sleep -Seconds 3

# ────────────────────────────────────────────────────────────────────────────
# Application processes (each in its own window)
# ────────────────────────────────────────────────────────────────────────────
Header "Launching application processes"

function Start-Service-Window {
    param(
        [string]$Name,
        [string]$WorkingDir,
        [string]$Command
    )
    $inner = "Set-Location '$WorkingDir'; " +
             "`$Host.UI.RawUI.WindowTitle = '$Name'; " +
             "Write-Host '  ── $Name ──' -ForegroundColor Cyan; " +
             "& '$activate'; " +
             $Command
    $proc = Start-Process powershell `
        -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $inner `
        -PassThru
    return $proc
}

$procs = @()

# 1. API
$api = Start-Service-Window -Name "uvicorn :8000" -WorkingDir $BackendDir `
    -Command "uvicorn api.main:app --port 8001"
Say ("uvicorn: PID {0}" -f $api.Id) "Green"
$procs += [pscustomobject]@{ Name = "uvicorn"; Pid = $api.Id }

# Give the API a moment to bind the port before starting the consumers of its output
Start-Sleep -Seconds 4

# 2. Scraper
$scraper = Start-Service-Window -Name "scraper" -WorkingDir $BackendDir `
    -Command "python -m scraper.rss_worker"
Say ("scraper: PID {0}" -f $scraper.Id) "Green"
$procs += [pscustomobject]@{ Name = "scraper"; Pid = $scraper.Id }

# Let the scraper produce a couple of articles before the consumer connects
Start-Sleep -Seconds 6

# 3. Consumer
$consumer = Start-Service-Window -Name "consumer" -WorkingDir $BackendDir `
    -Command "python -m ai_engine.consumer"
Say ("consumer: PID {0}" -f $consumer.Id) "Green"
$procs += [pscustomobject]@{ Name = "consumer"; Pid = $consumer.Id }

# 4. Frontend
$frontend = Start-Service-Window -Name "vite :5173" -WorkingDir $FrontendDir `
    -Command "npm run dev"
Say ("frontend: PID {0}" -f $frontend.Id) "Green"
$procs += [pscustomobject]@{ Name = "frontend"; Pid = $frontend.Id }

Save-State @{ Processes = $procs; StartedAt = (Get-Date).ToString("o") }

# ────────────────────────────────────────────────────────────────────────────
# Post-flight
# ────────────────────────────────────────────────────────────────────────────
Header "Waiting for services to settle (15s)"
for ($i = 15; $i -gt 0; $i--) {
    Write-Host ("  {0,2}s..." -f $i) -NoNewline
    Start-Sleep -Seconds 1
}
Write-Host ""

Header "Health checks"

# API
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8001/system-status" -UseBasicParsing -TimeoutSec 5
    Say ("API /system-status -> {0}" -f $r.StatusCode) "Green"
} catch {
    Say "API not responding yet - give it a few more seconds" "Yellow"
}

# DB row count
try {
    $rows = (& docker exec finai-postgres psql -U financial -d financial_ai -t -c "select count(*) from news;" 2>$null).Trim()
    Say ("Postgres news rows: {0}" -f $rows) "Green"
} catch {
    Say "Could not query Postgres" "Yellow"
}

# Frontend
try {
    $r = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 5
    Say ("Frontend :5173 -> {0}" -f $r.StatusCode) "Green"
} catch {
    Say "Frontend not up yet - Vite usually takes 2-4s" "Yellow"
}

if (-not $NoBrowser) {
    Say "Opening browser..." "Green"
    Start-Process "http://localhost:5173"
}

# ────────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("  ────────────────────────────────────────────────────────────") -ForegroundColor DarkCyan
Write-Host "  Running:" -ForegroundColor Cyan
Say "API         http://localhost:8001       (docs at /docs)"
Say "Frontend    http://localhost:5173"
Say "Postgres    localhost:5432              (financial/financial)"
Say "Kafka       localhost:9092"
Write-Host ""
Say "Each service runs in its own window. Ctrl+C there stops it individually." "DarkGray"
Say "To stop everything at once:" "DarkGray"
Write-Host "      .\Run-All.ps1 -Stop" -ForegroundColor White
Write-Host ""
Say "If events still don't appear after ~30s, check the 'consumer' window." "DarkGray"
Say "Ollama is optional now - articles will still land in Postgres with FinBERT scores." "DarkGray"
Write-Host ""
