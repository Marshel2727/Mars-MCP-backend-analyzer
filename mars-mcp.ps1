param()

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$Server = Join-Path $Root "mars_mcp_server.py"
$Python = $env:MARS_MCP_PYTHON

if ([string]::IsNullOrWhiteSpace($Python)) {
  $Python = "python"
}

Set-Location $Root

& $Python $Server
