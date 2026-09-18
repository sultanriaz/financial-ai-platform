#Requires -Version 5.1
<#
.SYNOPSIS
    Verify all 19 patches applied by patch.py are present and correct.
    Run from the project root after Apply-Patches.ps1 completes.

    Usage:
        cd C:\black_paper\Projects\financial-ai-platform
        .\Test-Patches.ps1
#>
param([string]$ProjectRoot = $PSScriptRoot)

Set-StrictMode -Version Latest
$pass = 0
$fail = 0

# ---- helpers -----------------------------------------------------------------

function Pass([string]$id, [string]$desc) {
    Write-Host ("  PASS  [{0,-5}]  {1}" -f $id, $desc) -ForegroundColor Green
    $script:pass++
}

function Fail([string]$id, [string]$desc, [string]$reason) {
    Write-Host ("  FAIL  [{0,-5}]  {1}" -f $id, $desc) -ForegroundColor Red
    Write-Host ("         --> {0}" -f $reason) -ForegroundColor DarkRed
    $script:fail++
}

function Test-Contains([string]$id, [string]$desc, [string]$file, [string]$needle) {
    $full = Join-Path $ProjectRoot $file
    if (-not (Test-Path $full)) { Fail $id $desc "File not found: $file"; return }
    $content = [System.IO.File]::ReadAllText($full)
    if ($content.Contains($needle)) { Pass $id $desc }
    else { Fail $id $desc "Expected to find: $needle" }
}

function Test-Excludes([string]$id, [string]$desc, [string]$file, [string]$needle) {
    $full = Join-Path $ProjectRoot $file
    if (-not (Test-Path $full)) { Fail $id $desc "File not found: $file"; return }
    $content = [System.IO.File]::ReadAllText($full)
    if (-not $content.Contains($needle)) { Pass $id $desc }
    else { Fail $id $desc "Must NOT contain: $needle" }
}

function Test-Exists([string]$id, [string]$desc, [string]$file) {
    $full = Join-Path $ProjectRoot $file
    if (Test-Path $full) { Pass $id $desc }
    else { Fail $id $desc "File not found: $file" }
}

function Test-PythonCheck([string]$id, [string]$desc, [string]$file, [string]$pyExpr) {
    # Run a one-liner Python expression that prints True/False against the file content.
    $full = (Join-Path $ProjectRoot $file) -replace '\\', '/'
    $result = python -c "
src = open('$full', encoding='utf-8').read()
print(bool($pyExpr))
" 2>&1
    if ($result -match "True") { Pass $id $desc }
    else { Fail $id $desc "Python check returned: $result" }
}

# ---- header ------------------------------------------------------------------

Write-Host ""
Write-Host "  Financial AI Platform - Patch Verification" -ForegroundColor Cyan
Write-Host ("  Project root : {0}" -f $ProjectRoot)
Write-Host ""

# ==============================================================================
# BACKEND CHECKS
# ==============================================================================

Write-Host "  BACKEND" -ForegroundColor White
Write-Host ("  {0}" -f ("-" * 60))

# --- Fix #1: UUID (rss_worker.py) ---
Test-Contains "#1-a" "rss_worker: uuid5 used for article_id" `
    "backend\scraper\rss_worker.py" "uuid.uuid5(uuid.NAMESPACE_URL"

Test-Contains "#1-b" "rss_worker: uuid on the import line" `
    "backend\scraper\rss_worker.py" "asyncio, logging, uuid"

Test-Excludes "#1-c" "rss_worker: hashlib sha256 removed from id generation" `
    "backend\scraper\rss_worker.py" "hashlib.sha256"

# --- Fix #2: FinBERT reload (consumer.py) ---
# sentiment.unload() must NOT appear as a real call inside the async-for loop.
# It IS allowed in comments and in the finally block.
Test-PythonCheck "#2-a" "consumer: unload() not called inside message loop" `
    "backend\ai_engine\consumer.py" `
    "not any(l.strip().startswith('sentiment.unload()') for l in src.splitlines()[:90])"

Test-Contains "#2-b" "consumer: single unload present in finally block" `
    "backend\ai_engine\consumer.py" "sentiment.unload()"

Test-Contains "#2-c" "consumer: models instantiated once before loop" `
    "backend\ai_engine\consumer.py" "sentiment  = FinBERTSentiment"

# --- Fix #7: model name ---
Test-Contains "#7-a" "config: ollama_model default is quantised model" `
    "backend\common\config.py" "mistral:latest"

Test-Excludes "#7-b" ".env: OLLAMA_MODEL assignment not mistral:latest" `
    ".env" "OLLAMA_MODEL=mistral:latest"

Test-Contains "#7-c" ".env: OLLAMA_MODEL set to quantised model" `
    ".env" "mistral:latest"

# --- Fix #13: CORS ---
Test-Contains "#13-a" "api/main: CORS reads settings.cors_origins" `
    "backend\api\main.py" "settings.cors_origins"

Test-Excludes "#13-b" "api/main: hardcoded localhost:5173 removed" `
    "backend\api\main.py" "localhost:5173"

Test-Contains "#13-c" "config: cors_origins field present" `
    "backend\common\config.py" "cors_origins"

# --- Fix #14: lifespan ---
Test-Contains "#14-a" "api/main: lifespan context manager used" `
    "backend\api\main.py" "lifespan"

Test-PythonCheck "#14-b" "api/main: @app.on_event decorator removed" `
    "backend/api/main.py" `
    "not any(l.strip().startswith(chr(64)+chr(97)+chr(112)+chr(112)+chr(46)+chr(111)+chr(110)+chr(95)) for l in src.splitlines())"

# --- Fix #15: broadcaster retry ---
Test-Contains "#15-a" "api/main: broadcaster has retry backoff" `
    "backend\api\main.py" "backoff"

Test-Contains "#15-b" "api/main: broadcaster retries on exception" `
    "backend\api\main.py" "backoff * 2"

# --- Fix #11: docker-compose services ---
Test-Exists "#11-a" "backend/Dockerfile exists" "backend\Dockerfile"

Test-Contains "#11-b" "docker-compose: finai-api service present" `
    "docker-compose.yml" "finai-api"

Test-Contains "#11-c" "docker-compose: finai-scraper service present" `
    "docker-compose.yml" "finai-scraper"

Test-Contains "#11-d" "docker-compose: finai-consumer service present" `
    "docker-compose.yml" "finai-consumer"

# ==============================================================================
# FRONTEND CHECKS
# ==============================================================================

Write-Host ""
Write-Host "  FRONTEND" -ForegroundColor White
Write-Host ("  {0}" -f ("-" * 60))

# --- Fix #9: index.html ---
Test-Contains "#9-a" "index.html: DOCTYPE present" `
    "frontend\index.html" "<!DOCTYPE html>"

Test-Contains "#9-b" "index.html: charset meta present" `
    "frontend\index.html" "charset"

Test-Contains "#9-c" "index.html: viewport meta present" `
    "frontend\index.html" "viewport"

Test-Contains "#9-d" "index.html: title element present" `
    "frontend\index.html" "<title>"

# --- Fix #8: WebSocket reconnect ---
Test-Exists "#8-a" "useWebSocket.ts hook created" `
    "frontend\src\hooks\useWebSocket.ts"

Test-Contains "#8-b" "useWebSocket: onclose handler present" `
    "frontend\src\hooks\useWebSocket.ts" "ws.onclose"

Test-Contains "#8-c" "useWebSocket: onerror handler present" `
    "frontend\src\hooks\useWebSocket.ts" "ws.onerror"

Test-Contains "#8-d" "useWebSocket: exponential backoff present" `
    "frontend\src\hooks\useWebSocket.ts" "delay * 2"

Test-Contains "#8-e" "App.tsx: uses useWebSocket hook" `
    "frontend\src\App.tsx" "useWebSocket"

Test-Excludes "#8-f" "App.tsx: raw new WebSocket() removed" `
    "frontend\src\App.tsx" "new WebSocket("

# --- Fix #10: env URLs ---
Test-Contains "#10-a" "App.tsx: reads import.meta.env for API URL" `
    "frontend\src\App.tsx" "import.meta.env"

Test-Contains "#10-b" "App.tsx: localhost fallback gated behind ?? operator" `
    "frontend\src\App.tsx" "VITE_API_BASE_URL ?? "

Test-Exists "#10-c" ".env.local.example created" `
    "frontend\.env.local.example"

Test-Contains "#10-d" ".env.local.example has VITE_API_BASE_URL" `
    "frontend\.env.local.example" "VITE_API_BASE_URL"

# --- Fix #3: StatusBar real data ---
Test-Contains "#3-a" "StatusBar: fetches /system-status endpoint" `
    "frontend\src\components\StatusBar.tsx" "system-status"

Test-Excludes "#3-b" "StatusBar: hardcoded 3.2 / 4 GB removed" `
    "frontend\src\components\StatusBar.tsx" "3.2 / 4 GB"

Test-Excludes "#3-c" "StatusBar: hardcoded 42 / MIN removed" `
    "frontend\src\components\StatusBar.tsx" "42 / MIN"

Test-Contains "#3-d" "StatusBar: polling interval with setInterval" `
    "frontend\src\components\StatusBar.tsx" "setInterval"

# --- Fix #4 / #5: PipelineGraph animated edges ---
Test-Contains "#5-a" "PipelineGraph: animated: true at top-level edge property" `
    "frontend\src\components\PipelineGraph.tsx" "animated:  true"

Test-Excludes "#5-b" "PipelineGraph: animated not buried inside style object" `
    "frontend\src\components\PipelineGraph.tsx" "strokeWidth: 2, animated"

# --- Fix #6: shared sentiment threshold ---
Test-Exists "#6-a" "sentiment.ts utility created" `
    "frontend\src\utils\sentiment.ts"

Test-Contains "#6-b" "sentiment.ts: SENTIMENT_THRESHOLD constant defined" `
    "frontend\src\utils\sentiment.ts" "SENTIMENT_THRESHOLD = 0.15"

Test-Contains "#6-c" "NewsStream: imports getSentimentBucket from shared util" `
    "frontend\src\components\NewsStream.tsx" "getSentimentBucket"

Test-Contains "#6-d" "Analytics: imports getSentimentBucket from shared util" `
    "frontend\src\components\Analytics.tsx" "getSentimentBucket"

# --- Fix #18/#19: Analytics charts ---
Test-Contains "#18"  "Analytics: color-coded Cell components in bar chart" `
    "frontend\src\components\Analytics.tsx" "<Cell"

Test-Contains "#19"  "Analytics: AreaChart for sentiment timeline" `
    "frontend\src\components\Analytics.tsx" "AreaChart"

# --- Fix #20-23: NewsStream UX ---
Test-Contains "#20"  "NewsStream: article URL used as link href" `
    "frontend\src\components\NewsStream.tsx" "href={item.url}"

Test-Contains "#21"  "NewsStream: formatRelativeTime used for timestamps" `
    "frontend\src\components\NewsStream.tsx" "formatRelativeTime"

Test-Contains "#22"  "NewsStream: empty state class present" `
    "frontend\src\components\NewsStream.tsx" "news-empty"

Test-Contains "#23"  "NewsStream: filter controls rendered" `
    "frontend\src\components\NewsStream.tsx" "filter-btn"

# --- Fix #24-27: styles ---
Test-Excludes "#24-a" "styles.css: min-width CSS rule not in body block" `
    "frontend\src\styles.css" "min-width: 1100px"

Test-Contains "#24-b" "styles.css: responsive @media breakpoint added" `
    "frontend\src\styles.css" "@media"

Test-Contains "#25"  "NewsStream: aria-live on feed list" `
    "frontend\src\components\NewsStream.tsx" "aria-live"

Test-Contains "#26"  "styles.css: custom scrollbar styles present" `
    "frontend\src\styles.css" "::-webkit-scrollbar"

Test-Contains "#27"  "styles.css: card hover transition present" `
    "frontend\src\styles.css" ".news-card:hover"

# --- Fix #28: ConnectionBadge ---
Test-Exists "#28-a" "ConnectionBadge.tsx component created" `
    "frontend\src\components\ConnectionBadge.tsx"

Test-Contains "#28-b" "App.tsx: renders ConnectionBadge" `
    "frontend\src\App.tsx" "ConnectionBadge"

# --- Fix #12: package.json ---
Test-Excludes "#12"  "package.json: lucide-react dependency removed" `
    "frontend\package.json" "lucide-react"

# ==============================================================================
# SUMMARY
# ==============================================================================

$total = $pass + $fail
Write-Host ""
Write-Host ("  {0}" -f ("=" * 62))
if ($fail -eq 0) {
    Write-Host ("  RESULT: {0} / {0} checks PASSED." -f $total) -ForegroundColor Green
    Write-Host ""
    Write-Host "  All patches verified. Next steps:" -ForegroundColor Green
    Write-Host "    docker compose up -d"
    Write-Host "    ollama pull mistral:latest"
    Write-Host "    cd frontend && npm install && npm run dev"
} else {
    Write-Host ("  RESULT: {0} passed, {1} FAILED (of {2} total)." -f $pass, $fail, $total) -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Re-run: python patch.py (project root) to re-apply patches." -ForegroundColor Yellow
}
Write-Host ""
