$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = 'D:\anaconda\python.exe'
$RuntimeExe = Join-Path $ProjectRoot '.runtime\ollama\ollama.exe'
$LogDir = Join-Path $ProjectRoot 'data\logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
if (!(Test-Path -LiteralPath $RuntimeExe)) { throw 'Run install_ollama.py first.' }
if (!(Test-Path -LiteralPath (Join-Path $ProjectRoot '.env'))) { & $PythonExe (Join-Path $PSScriptRoot 'bootstrap.py') }
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path $ProjectRoot 'data\ollama-models'
$env:OLLAMA_CONTEXT_LENGTH = '4096'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_MAX_QUEUE = '8'
$env:OLLAMA_KEEP_ALIVE = '10m'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_VULKAN = '1'
$env:OLLAMA_FLASH_ATTENTION = '1'
$env:OLLAMA_KV_CACHE_TYPE = 'q8_0'
try { $Existing = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 } catch { $Existing = $null }
if (!$Existing) {
    $Ollama = Start-Process -FilePath $RuntimeExe -ArgumentList 'serve' -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LogDir 'ollama.stdout.log') -RedirectStandardError (Join-Path $LogDir 'ollama.stderr.log')
    $Ollama.Id | Set-Content (Join-Path $ProjectRoot 'data\ollama.pid')
}
$Running = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*model-bridge*host_bridge.py*' }
if (!$Running) {
    $Bridge = Start-Process -FilePath $PythonExe -ArgumentList @('-u', (Join-Path $ProjectRoot 'src\host_bridge.py')) -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LogDir 'bridge.stdout.log') -RedirectStandardError (Join-Path $LogDir 'bridge.stderr.log')
    $Bridge.Id | Set-Content (Join-Path $ProjectRoot 'data\bridge.pid')
}
Write-Output 'Ollama and host bridge started. Logs: data\logs'
# Tailscale owns the inbound listener, avoiding the need for an elevated firewall change.
& 'C:\Program Files\Tailscale\tailscale.exe' serve --bg --tcp=8787 tcp://127.0.0.1:8787
if ($LASTEXITCODE -ne 0) { throw 'Tailscale TCP forwarding failed.' }
