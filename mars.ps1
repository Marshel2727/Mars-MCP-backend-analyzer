param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CliArgs
)

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$Python = Join-Path $Root "venv\Scripts\python.exe"
$EnvFile = Join-Path $Root ".env"
$OllamaTagsUrl = "http://127.0.0.1:11434/api/tags"
$OllamaGenerateUrl = "http://127.0.0.1:11434/api/generate"
$OllamaModel = "qwen2.5-coder:7b"
$OllamaNumCtx = 8192
$OllamaNumGpu = 999
$OllamaMainGpu = 0
$OllamaKeepAlive = "10m"
$StartedOllama = $false
$OllamaProcess = $null

if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match "^\s*OLLAMA_MODEL\s*=\s*(.+?)\s*$") {
      $OllamaModel = $Matches[1].Trim().Trim('"').Trim("'")
    }

    if ($_ -match "^\s*OLLAMA_NUM_CTX\s*=\s*(\d+)\s*$") {
      $OllamaNumCtx = [int]$Matches[1]
    }

    if ($_ -match "^\s*OLLAMA_NUM_GPU\s*=\s*(\d+)\s*$") {
      $OllamaNumGpu = [int]$Matches[1]
    }

    if ($_ -match "^\s*OLLAMA_MAIN_GPU\s*=\s*(\d+)\s*$") {
      $OllamaMainGpu = [int]$Matches[1]
    }

    if ($_ -match "^\s*OLLAMA_KEEP_ALIVE\s*=\s*(.+?)\s*$") {
      $OllamaKeepAlive = $Matches[1].Trim().Trim('"').Trim("'")
    }
  }
}

function Show-Usage {
  Write-Host "Usage:"
  Write-Host "  .\mars.ps1 scan ."
  Write-Host "  .\mars.ps1 project-brief ."
  Write-Host "  .\mars.ps1 project-map ."
  Write-Host "  .\mars.ps1 relevant-files . `"analisis folder models`""
  Write-Host "  .\mars.ps1 read-lines . app/cli.py 1 80"
  Write-Host "  .\mars.ps1 outline . app/cli.py"
  Write-Host "  .\mars.ps1 list . tools"
  Write-Host "  .\mars.ps1 ask . `"jelaskan struktur project ini`""
  Write-Host "  .\mars.ps1 agent . `"analisis struktur project ini`" --depth normal"
  Write-Host "  .\mars.ps1 ask . `"review scanner`" --files core/project_scanner.py core/ignore.py"
  Write-Host "  .\mars.ps1 review-file . app/cli.py"
  Write-Host "  .\mars.ps1 debug . `"error saat scan project`" --files app/cli.py"
  Write-Host "  .\mars.ps1 explain-file . llm/ollama_provider.py"
}

function Test-NvidiaGpuReady {
  try {
    nvidia-smi -L | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Test-OllamaReady {
  try {
    Invoke-WebRequest -Uri $OllamaTagsUrl -UseBasicParsing -TimeoutSec 2 | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Wait-OllamaReady {
  for ($i = 0; $i -lt 30; $i++) {
    if (Test-OllamaReady) {
      return $true
    }

    Start-Sleep -Seconds 1
  }

  return $false
}

function Stop-OllamaModel {
  if (-not (Test-OllamaReady)) {
    return
  }

  try {
    $body = @{
      model = $OllamaModel
      keep_alive = 0
    } | ConvertTo-Json -Compress

    Invoke-RestMethod `
      -Uri $OllamaGenerateUrl `
      -Method Post `
      -Body $body `
      -ContentType "application/json" `
      -TimeoutSec 15 | Out-Null

    Write-Host "Unloaded Ollama model: $OllamaModel"
  } catch {
    Write-Host "Could not unload Ollama model automatically."
  }
}

function Test-OllamaModelUsesGpu {
  try {
    $body = @{
      model = $OllamaModel
      prompt = "OK"
      stream = $false
      keep_alive = $OllamaKeepAlive
      options = @{
        num_predict = 1
        temperature = 0
        num_ctx = $OllamaNumCtx
        num_gpu = $OllamaNumGpu
        main_gpu = $OllamaMainGpu
      }
    } | ConvertTo-Json -Compress -Depth 4

    Invoke-RestMethod `
      -Uri $OllamaGenerateUrl `
      -Method Post `
      -Body $body `
      -ContentType "application/json" `
      -TimeoutSec 120 | Out-Null

    $modelNamePattern = [regex]::Escape($OllamaModel)
    $loadedModel = ollama ps | Where-Object {
      $_ -match $modelNamePattern
    } | Select-Object -First 1

    if (-not $loadedModel) {
      return $false
    }

    return $loadedModel -match "\bGPU\b"
  } catch {
    return $false
  }
}

if ($CliArgs.Count -eq 0) {
  Show-Usage
  exit 1
}

$Command = $CliArgs[0]
$NeedLlm = $Command -in @(
  "ask",
  "ask-file",
  "ask-files",
  "review",
  "review-file",
  "review-files",
  "debug",
  "debug-file",
  "debug-files",
  "agent",
  "chat",
  "explain-file"
)

try {
  if (-not (Test-Path $Python)) {
    throw "Python virtual environment tidak ditemukan: $Python"
  }

  if ($NeedLlm) {
    if (-not (Test-NvidiaGpuReady)) {
      throw "NVIDIA GPU tidak terdeteksi. Command AI tidak dijalankan."
    }

    Write-Host "Checking Ollama..."

    if (-not (Test-OllamaReady)) {
      Write-Host "Ollama belum running. Menyalakan Ollama..."
      $OllamaProcess = Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -PassThru
      $StartedOllama = $true

      Write-Host "Menunggu Ollama siap..."
      if (-not (Wait-OllamaReady)) {
        throw "Gagal menyalakan Ollama. Jalankan manual: ollama serve"
      }
    } else {
      Write-Host "Ollama sudah running."
    }

    Write-Host "Checking whether Ollama model uses GPU..."
    if (-not (Test-OllamaModelUsesGpu)) {
      Stop-OllamaModel
      throw "Model '$OllamaModel' tidak memakai GPU. Command AI tidak dijalankan."
    }

    Write-Host "Ollama model is using GPU: $OllamaModel"
  }

  Set-Location $Root
  & $Python -m app.main @CliArgs
} finally {
  if ($NeedLlm) {
    Write-Host ""
    if ($OllamaKeepAlive -eq "0" -or $OllamaKeepAlive -eq "0s") {
      Write-Host "Releasing Ollama GPU memory..."
      Stop-OllamaModel
    } else {
      Write-Host "Keeping Ollama model loaded for $OllamaKeepAlive."
    }

    if (
      $StartedOllama -and
      $null -ne $OllamaProcess -and
      ($OllamaKeepAlive -eq "0" -or $OllamaKeepAlive -eq "0s")
    ) {
      Write-Host ""
      Write-Host "Stopping Ollama..."
      Stop-Process -Id $OllamaProcess.Id -Force -ErrorAction SilentlyContinue
    }
  }
}
