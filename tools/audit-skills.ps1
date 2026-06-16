param(
  [string]$Root
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ([string]::IsNullOrWhiteSpace($Root)) {
  $scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $Root = (Resolve-Path (Join-Path $scriptRoot '..')).Path
}

$skillRoots = @(
  (Join-Path $Root 'skills-library'),
  (Join-Path $Root '.agents\skills'),
  (Join-Path $Root '.codex\skills'),
  (Join-Path $Root '.claude\skills')
) | Where-Object { Test-Path -LiteralPath $_ }

$skillFiles = foreach ($rootPath in $skillRoots) {
  Get-ChildItem -LiteralPath $rootPath -Recurse -Filter 'SKILL.md'
}

$rows = foreach ($file in $skillFiles) {
  $dir = Split-Path $file.FullName -Parent
  $name = Split-Path $dir -Leaf
  $text = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
  $frontmatterOk = $text -match '(?s)^---\s*(.*?)\s*---'
  $frontmatter = if ($frontmatterOk) { $Matches[1] } else { '' }
  $declaredName = ''
  if ($frontmatterOk -and $frontmatter -match '(?m)^name:\s*(.+)$') {
    $declaredName = $Matches[1].Trim()
  }
  $hasDescription = $frontmatterOk -and $frontmatter -match '(?m)^description:'
  [PSCustomObject]@{
    Name = $name
    DeclaredName = $declaredName
    HasFrontmatter = $frontmatterOk
    HasDescription = $hasDescription
    NameMatchesDir = if ($declaredName) { $declaredName -eq $name } else { $false }
    Path = $file.FullName
  }
}

$rows | Sort-Object Path | Format-Table -AutoSize

$problems = $rows | Where-Object { -not $_.HasFrontmatter -or -not $_.HasDescription -or ($_.DeclaredName -and -not $_.NameMatchesDir) }
if ($problems) {
  Write-Host ''
  Write-Host 'Potential issues:' -ForegroundColor Yellow
  $problems | Format-Table -AutoSize
  exit 1
}

Write-Host ''
Write-Host 'Audit passed.'
