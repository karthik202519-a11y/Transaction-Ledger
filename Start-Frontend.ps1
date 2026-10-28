$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path $PSScriptRoot 'frontend')
if (-not (Test-Path -LiteralPath 'node_modules')) {
    throw 'Frontend dependencies missing. Run npm ci in frontend first.'
}
& npm.cmd run dev
exit $LASTEXITCODE
