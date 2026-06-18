param(
  [string]$Root
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ([string]::IsNullOrWhiteSpace($Root)) {
  $scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $Root = (Resolve-Path (Join-Path $scriptRoot '..')).Path
}

$caseRoot = Join-Path $Root 'cases'
if (-not (Test-Path -LiteralPath $caseRoot)) {
  throw "cases directory not found: $caseRoot"
}

$requiredSections = @(
  '## 参数特征',
  '## Phase 处理流程',
  '## 链路图',
  '## (核心代码模板|还原代码模板)',
  '## 验证方法',
  '## 可验证事实清单'
)

$caseFiles = Get-ChildItem -LiteralPath $caseRoot -Recurse -File -Filter '*.md' |
  Where-Object { $_.Name -notin @('README.md', '_template.md') }

$rows = foreach ($file in $caseFiles) {
  $text = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
  $missing = foreach ($section in $requiredSections) {
    if ($text -notmatch $section) { $section }
  }
  [PSCustomObject]@{
    File = $file.FullName.Replace($Root + [IO.Path]::DirectorySeparatorChar, '')
    Missing = ($missing -join '; ')
    Pass = -not $missing
  }
}

$rows | Sort-Object File | Format-Table -AutoSize

$readme = Join-Path $caseRoot 'README.md'
$brokenLinks = @()
if (Test-Path -LiteralPath $readme) {
  $readmeText = Get-Content -LiteralPath $readme -Raw -Encoding UTF8
  $matches = [regex]::Matches($readmeText, '\]\(([^)]+\.md)\)')
  foreach ($match in $matches) {
    $target = $match.Groups[1].Value
    if ($target -match '^(https?:|#)') { continue }
    $resolved = Join-Path (Split-Path $readme -Parent) $target
    if (-not (Test-Path -LiteralPath $resolved)) {
      $brokenLinks += "$target"
    }
  }
}

if ($brokenLinks) {
  Write-Host ''
  Write-Host 'Broken README links:' -ForegroundColor Yellow
  $brokenLinks | ForEach-Object { Write-Host "  $_" }
}

$failed = $rows | Where-Object { -not $_.Pass }
if ($failed -or $brokenLinks) {
  Write-Host ''
  Write-Host 'Case audit failed.' -ForegroundColor Yellow
  exit 1
}

Write-Host ''
Write-Host 'Case audit passed.'

