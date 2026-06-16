param(
  [Parameter(Mandatory=$true)][string]$Name,
  [ValidateSet('agents','codex')][string[]]$Targets = @('agents','codex'),
  [string]$Root
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ([string]::IsNullOrWhiteSpace($Root)) {
  $scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $Root = (Resolve-Path (Join-Path $scriptRoot '..')).Path
}

foreach ($target in $Targets) {
  $parent = switch ($target) {
    'agents' { Join-Path $Root '.agents\skills' }
    'codex' { Join-Path $Root '.codex\skills' }
  }
  $dest = Join-Path $parent $Name

  if (-not (Test-Path -LiteralPath $dest)) {
    Write-Host "Not active for ${target}: $Name"
    continue
  }

  $resolvedParent = (Resolve-Path -LiteralPath $parent).Path
  $resolvedDest = (Resolve-Path -LiteralPath $dest).Path
  if (-not $resolvedDest.StartsWith($resolvedParent, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove path outside active skill directory: $resolvedDest"
  }

  Remove-Item -LiteralPath $dest -Recurse -Force
  Write-Host "Disabled $Name for $target"
}
