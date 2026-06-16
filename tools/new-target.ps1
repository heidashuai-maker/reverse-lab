param(
  [Parameter(Mandatory=$true)][string]$Name,
  [ValidateSet('none', 'python-protocol', 'node-protocol', 'vm-sandbox', 'wasm-helper', 'browser-auto-fallback')]
  [string]$Runner = 'none',
  [string]$Root
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ([string]::IsNullOrWhiteSpace($Root)) {
  $scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $Root = (Resolve-Path (Join-Path $scriptRoot '..')).Path
}

if ($Name -match '[\\/:*?"<>|]') {
  throw "Invalid target name: $Name"
}

$targetRoot = Join-Path $Root "targets\$Name"
if (Test-Path -LiteralPath $targetRoot) {
  throw "Target already exists: $targetRoot"
}

foreach ($dir in @('source', 'scripts', 'samples', 'output', 'scripts\env', 'scripts\replay')) {
  New-Item -ItemType Directory -Force -Path (Join-Path $targetRoot $dir) | Out-Null
}

$template = Join-Path $Root 'templates\target-notes-template.md'
$notes = Join-Path $targetRoot 'notes.md'
if (Test-Path -LiteralPath $template) {
  $content = Get-Content -LiteralPath $template -Raw -Encoding UTF8
  $content = $content.Replace('<source-name>', $Name)
  Set-Content -LiteralPath $notes -Value $content -Encoding UTF8
} else {
  Set-Content -LiteralPath $notes -Value "# 逆向分析记录：$Name`n" -Encoding UTF8
}

$task = [ordered]@{
  taskId = $Name
  slug = $Name
  targetUrl = ''
  goal = ''
  currentStage = 'Observe'
  targetContext = [ordered]@{
    pageUrl = ''
    targetRequest = [ordered]@{
      method = ''
      url = ''
      notes = ''
    }
    triggerAction = ''
    candidateScripts = @()
  }
  successCriteria = [ordered]@{
    localRebuild = 'unknown'
    serverAcceptance = 'unknown'
    browserAlignment = 'unknown'
    notes = ''
  }
  currentSummary = ''
}
$taskPath = Join-Path $targetRoot 'samples\task.json'
$task | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskPath -Encoding UTF8

foreach ($file in @(
  'samples\network.jsonl',
  'samples\scripts.jsonl',
  'samples\runtime-evidence.jsonl',
  'samples\timeline.jsonl'
)) {
  New-Item -ItemType File -Force -Path (Join-Path $targetRoot $file) | Out-Null
}

Set-Content -LiteralPath (Join-Path $targetRoot 'scripts\env\capture.json') -Value "{}" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $targetRoot 'samples\browser-env-camoufox.json') -Value "{}" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $targetRoot 'samples\browser-env-cloakbrowser.json') -Value "{}" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $targetRoot 'samples\local-env-baseline.json') -Value "{}" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $targetRoot 'samples\env-diff.json') -Value "{}" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $targetRoot 'scripts\env\entry.js') -Value "// Node local rebuild entry. Fill after Observe/Capture evidence is stable.`n" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $targetRoot 'scripts\env\env.js') -Value "// Minimal host environment patches. Keep patches driven by first divergence evidence.`n" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $targetRoot 'scripts\env\polyfills.js') -Value "// Narrow polyfills and diagnostics for local rebuild.`n" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $targetRoot 'scripts\env\patch-plan.md') -Value "# 环境补丁计划`n`n- 浏览器基准：Camoufox / CloakBrowser / 其它`n- 本地运行入口：`n- First divergence：`n- 本轮最小补丁：`n- 验证结果：`n" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $targetRoot 'scripts\replay\actions.json') -Value "[]" -Encoding UTF8

if ($Runner -ne 'none') {
  $scaffoldRoot = Join-Path $Root "templates\scaffold\$Runner"
  if (-not (Test-Path -LiteralPath $scaffoldRoot)) {
    throw "Runner scaffold not found: $scaffoldRoot"
  }

  $runnerDestinations = @{
    'python-protocol' = 'output'
    'node-protocol' = 'output'
    'vm-sandbox' = 'scripts\env'
    'wasm-helper' = 'output\wasm-helper'
    'browser-auto-fallback' = 'output\browser-auto'
  }

  $dest = Join-Path $targetRoot $runnerDestinations[$Runner]
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  Get-ChildItem -LiteralPath $scaffoldRoot -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force
  }

  $task.runner = $Runner
  $task | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskPath -Encoding UTF8
}

Write-Host "Created target: $targetRoot"
if ($Runner -ne 'none') {
  Write-Host "Initialized runner scaffold: $Runner"
}
