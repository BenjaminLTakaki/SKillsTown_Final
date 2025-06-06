# projects/skillstown/check_setup.ps1

Write-Host "🔍 SkillsTown Local Development Setup Check" -ForegroundColor Green
Write-Host "=" * 50

$allGood = $true

# Check environment variables
Write-Host "`n📋 Environment Variables:" -ForegroundColor Cyan
$envVars = @('OPENAI_API_KEY', 'GROQ_API_KEY', 'GEMINI_API_KEY')

foreach ($var in $envVars) {
    if ([Environment]::GetEnvironmentVariable($var)) {
        Write-Host "✅ $var`: Set" -ForegroundColor Green
    } else {
        Write-Host "❌ $var`: Not set" -ForegroundColor Red
        $allGood = $false
    }
}

# Check required commands
Write-Host "`n🛠️  Required Commands:" -ForegroundColor Cyan
$commands = @('python', 'go')

foreach ($cmd in $commands) {
    try {
        $null = & $cmd --version 2>$null
        Write-Host "✅ $cmd`: Available" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ $cmd`: Not found" -ForegroundColor Red
        $allGood = $false
    }
}

# Function to test service
function Test-Service {
    param(
        [string]$Name,
        [string]$Url
    )
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 5 -UseBasicParsing
        Write-Host "✅ $Name`: Running (HTTP $($response.StatusCode))" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ $Name`: Not accessible at $Url" -ForegroundColor Red
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Check services
Write-Host "`n🌐 Required Services:" -ForegroundColor Cyan
$services = @(
    @{Name = "Qdrant Vector DB"; Url = "http://localhost:6333"},
    @{Name = "Chisel API"; Url = "http://localhost:8080"},
    @{Name = "NarreteX API"; Url = "http://localhost:8100"}
)

foreach ($service in $services) {
    if (-not (Test-Service -Name $service.Name -Url $service.Url)) {
        $allGood = $false
    }
}

Write-Host "`n$('=' * 50)"

if ($allGood) {
    Write-Host "🎉 All checks passed! You're ready to run SkillsTown locally." -ForegroundColor Green
    Write-Host "`nNext steps:" -ForegroundColor Cyan
    Write-Host "1. Set execution policy: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Yellow
    Write-Host "2. Run: .\start_local.ps1" -ForegroundColor Yellow
} else {
    Write-Host "⚠️  Some requirements are missing. Please address the issues above." -ForegroundColor Yellow
    Write-Host "`nSetup instructions:" -ForegroundColor Cyan
    Write-Host "1. Set missing environment variables in PowerShell:" -ForegroundColor Yellow
    Write-Host "   `$env:OPENAI_API_KEY = 'your-key-here'" -ForegroundColor Gray
    Write-Host "   `$env:GROQ_API_KEY = 'your-key-here'" -ForegroundColor Gray
    Write-Host "   `$env:GEMINI_API_KEY = 'your-key-here'" -ForegroundColor Gray
    Write-Host "`n2. Start missing services:" -ForegroundColor Yellow
    Write-Host "   Qdrant: docker run -p 6333:6333 qdrant/qdrant" -ForegroundColor Gray
    Write-Host "   Chisel: cd path\to\chisel; go run ." -ForegroundColor Gray
    Write-Host "   NarreteX: cd path\to\narretex; go run ." -ForegroundColor Gray
}

if ($allGood) { exit 0 } else { exit 1 }