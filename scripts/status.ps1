$ProjectRoot = Split-Path -Parent $PSScriptRoot
Write-Output '=== Model runtime ==='
& (Join-Path $ProjectRoot '.runtime\ollama\ollama.exe') ps
& (Join-Path $ProjectRoot '.runtime\ollama\ollama.exe') list
Write-Output '=== Private network ==='
& 'C:\Program Files\Tailscale\tailscale.exe' serve status
Write-Output '=== Host service logs ==='
Get-Content -LiteralPath (Join-Path $ProjectRoot 'data\logs\ollama.stderr.log') -Tail 8
Get-Content -LiteralPath (Join-Path $ProjectRoot 'data\logs\bridge.stderr.log') -Tail 5
