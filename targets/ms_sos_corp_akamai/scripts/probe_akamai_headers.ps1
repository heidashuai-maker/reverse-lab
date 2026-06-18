param(
    [string]$SearchUrl = "https://corp.sos.ms.gov/corp/portal/c/page/corpbusinessidsearch/portal.aspx",
    [string]$DetailUrl = "https://corp.sos.ms.gov/corp/portal/c/page/corpbusinessidsearch/ViewXSLTFileByName.aspx?providerName=MSBSD_CorporationBusinessDetails&FilingId=31734e49-817e-4e9f-9ea0-4ec10aa212a9"
)

$ErrorActionPreference = "Stop"

$TargetRoot = Split-Path -Parent $PSScriptRoot
$SamplesDir = Join-Path $TargetRoot "samples"
$SourceDir = Join-Path $TargetRoot "source"
$StatePath = Join-Path $SamplesDir "browser-state-camoufox.json"

New-Item -ItemType Directory -Force -Path $SamplesDir, $SourceDir | Out-Null

$UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"

curl.exe -sS -L -I --max-time 30 $SearchUrl `
    | Out-File -Encoding utf8 (Join-Path $SamplesDir "http_probe_search_head.txt")

curl.exe -sS -L -D (Join-Path $SamplesDir "http_probe_search_get.headers.txt") --max-time 30 `
    -A $UserAgent `
    -o (Join-Path $SourceDir "search_page_anonymous_get.html") `
    $SearchUrl

if (Test-Path -LiteralPath $StatePath) {
    $state = Get-Content -Raw -Encoding utf8 -LiteralPath $StatePath | ConvertFrom-Json
    $cookieHeader = ($state.cookies |
        Where-Object { $_.domain -eq "corp.sos.ms.gov" -or $_.domain -eq ".corp.sos.ms.gov" -or $_.domain -eq ".ms.gov" } |
        ForEach-Object { "{0}={1}" -f $_.name, $_.value }) -join "; "

    curl.exe -sS -L -D (Join-Path $SamplesDir "http_probe_detail_browser_cookie.headers.txt") --max-time 30 `
        -A $UserAgent `
        -H "Accept: */*" `
        -H "X-Requested-With: XMLHttpRequest" `
        -H "Referer: $SearchUrl" `
        -H "Cookie: $cookieHeader" `
        -o (Join-Path $SourceDir "detail_636136_browser_cookie.html") `
        $DetailUrl
}

