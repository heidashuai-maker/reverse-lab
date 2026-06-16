param(
  [string]$Root
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ([string]::IsNullOrWhiteSpace($Root)) {
  $scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $Root = (Resolve-Path (Join-Path $scriptRoot '..')).Path
}

$library = Join-Path $Root 'skills-library'
if (-not (Test-Path -LiteralPath $library)) {
  throw "skills-library not found: $library"
}

Get-ChildItem -LiteralPath $library -Recurse -Filter 'SKILL.md' |
  Sort-Object FullName |
  ForEach-Object {
    $skillDir = Split-Path $_.FullName -Parent
    $group = Split-Path (Split-Path $skillDir -Parent) -Leaf
    $name = Split-Path $skillDir -Leaf
    $agentsActive = Test-Path -LiteralPath (Join-Path $Root ".agents\skills\$name")
    $codexActive = Test-Path -LiteralPath (Join-Path $Root ".codex\skills\$name")
    [PSCustomObject]@{
      Group = $group
      Name = $name
      Agents = if ($agentsActive) { 'active' } else { '-' }
      Codex = if ($codexActive) { 'active' } else { '-' }
      Path = $skillDir
    }
  } | Format-Table -AutoSize
