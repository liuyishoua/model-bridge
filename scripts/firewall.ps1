# Run elevated. The model engine remains loopback-only; only the bridge is reachable.
$ErrorActionPreference = 'Stop'
$Name = 'Leo Model Bridge from leo-ubuntu'
if (!(Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $Name -Direction Inbound -Action Allow -Protocol TCP -LocalAddress '100.70.120.18' -LocalPort 8787 -RemoteAddress '100.73.83.110' -Profile Any | Out-Null
}
Write-Output 'Cloud-only bridge firewall rule is ready.'
