$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceDir = Join-Path $PSScriptRoot "demo_data"
$runtimeDir = Join-Path $repoRoot "runtime-data"
$requiredFiles = @("clinic_faq.json", "doctor_availability.csv")

Write-Host ""
Write-Host "DEMO ONLY: this script copies fabricated FAQs and appointment slots."
Write-Host "These records are not real, current, or approved by a clinic."
Write-Host "The script will not overwrite or reuse an existing runtime-data directory."
Write-Host ""

$confirmation = Read-Host "Type DEMO-ONLY to prepare a disposable local demo"
if ($confirmation -cne "DEMO-ONLY") {
    throw "Confirmation did not match. No files were copied."
}

if (Test-Path -LiteralPath $runtimeDir) {
    throw "Refusing to continue because runtime-data already exists. Inspect it manually; this script never overwrites existing runtime data."
}

foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceDir $file) -PathType Leaf)) {
        throw "Required synthetic demo file is missing: $file"
    }
}

$createdDirectory = $false
try {
    New-Item -ItemType Directory -Path $runtimeDir | Out-Null
    $createdDirectory = $true
    foreach ($file in $requiredFiles) {
        Copy-Item -LiteralPath (Join-Path $sourceDir $file) -Destination (Join-Path $runtimeDir $file)
    }
    Write-Host "Synthetic demo files were copied to ignored runtime-data\."
    Write-Host "Next: configure OPENAI_API_KEY and API_ACCESS_TOKEN in your local .env, then run docker compose config --quiet and docker compose up --build."
}
catch {
    if ($createdDirectory -and (Test-Path -LiteralPath $runtimeDir)) {
        Remove-Item -LiteralPath $runtimeDir -Recurse -Force
    }
    throw
}
