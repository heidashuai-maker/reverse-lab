param(
  [Parameter(Mandatory=$true)][string]$Name,
  [ValidateSet('agents','codex')][string[]]$Targets = @('agents','codex'),
  [switch]$Replace,
  [string]$Root
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ([string]::IsNullOrWhiteSpace($Root)) {
  $scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $Root = (Resolve-Path (Join-Path $scriptRoot '..')).Path
}

$source = Get-ChildItem -LiteralPath (Join-Path $Root 'skills-library') -Recurse -Directory |
  Where-Object { $_.Name -eq $Name -and (Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md')) } |
  Select-Object -First 1

if (-not $source) {
  throw "Skill not found in skills-library: $Name"
}

foreach ($target in $Targets) {
  $parent = switch ($target) {
    'agents' { Join-Path $Root '.agents\skills' }
    'codex' { Join-Path $Root '.codex\skills' }
  }

  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  $dest = Join-Path $parent $Name

  if (Test-Path -LiteralPath $dest) {
    if (-not $Replace) {
      Write-Host "SKIP existing $target skill: $dest"
      continue
    }
    $resolvedParent = (Resolve-Path -LiteralPath $parent).Path
    $resolvedDest = (Resolve-Path -LiteralPath $dest).Path
    if (-not $resolvedDest.StartsWith($resolvedParent, [StringComparison]::OrdinalIgnoreCase)) {
      throw "Refusing to remove path outside active skill directory: $resolvedDest"
    }
    Remove-Item -LiteralPath $dest -Recurse -Force
  }

  Copy-Item -LiteralPath $source.FullName -Destination $dest -Recurse
  Write-Host "Enabled $Name for $target"
}
