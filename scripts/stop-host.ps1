$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
foreach ($Service in @('bridge', 'ollama')) {
    $PidFile = Join-Path $ProjectRoot ('data\' + $Service + '.pid')
    if (Test-Path -LiteralPath $PidFile) {
        $ServiceId = [int](Get-Content -LiteralPath $PidFile)
        $Process = Get-CimInstance Win32_Process -Filter "ProcessId=$ServiceId"
        # Verify the PID still belongs to this project before stopping anything.
        if ($Process -and $Process.CommandLine -like ('*' + $ProjectRoot + '*')) {
            Stop-Process -Id $ServiceId
        }
    }
}
& 'C:\Program Files\Tailscale\tailscale.exe' serve --tcp=8787 off
Write-Output 'This project host processes and its Tailscale forwarding port are stopped.'
