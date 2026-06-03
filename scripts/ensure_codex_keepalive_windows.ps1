param(
    [string]$AccountSearchRoot = $(if ($env:CODEX_ACCOUNT_SEARCH_ROOT) { $env:CODEX_ACCOUNT_SEARCH_ROOT } else { $HOME }),
    [string]$TrustedWorkdir = $(if ($env:CODEX_TRUSTED_WORKDIR) { $env:CODEX_TRUSTED_WORKDIR } else { $HOME }),
    [string]$HostName = $(if ($env:CODEX_SWITCHER_HOST) { $env:CODEX_SWITCHER_HOST } else { "127.0.0.1" }),
    [int]$Port = $(if ($env:CODEX_SWITCHER_PORT) { [int]$env:CODEX_SWITCHER_PORT } else { 8765 }),
    [switch]$StartWeb
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Split-Path -Parent $ScriptDir
$LogDir = Join-Path $AppDir "logs"
$LogFile = Join-Path $LogDir "codex-keepalive-windows.log"
$KeepaliveStateFile = if ($env:KEEPALIVE_STATE_FILE) { $env:KEEPALIVE_STATE_FILE } else { Join-Path $AppDir "keepalive_state.json" }
$PidStateFile = if ($env:KEEPALIVE_WINDOWS_PID_FILE) { $env:KEEPALIVE_WINDOWS_PID_FILE } else { Join-Path $AppDir "keepalive_windows_pids.json" }

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    $line | Tee-Object -FilePath $LogFile -Append
}

function Get-PythonCommand {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $python3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3) { return $python3.Source }
    throw "python not found"
}

function Test-AuthUsable {
    param([string]$AuthPath)
    try {
        $data = Get-Content -Raw -Encoding UTF8 -Path $AuthPath | ConvertFrom-Json
    } catch {
        return $false
    }
    if ($null -eq $data) { return $false }
    if ($data.OPENAI_API_KEY -is [string] -and $data.OPENAI_API_KEY.Trim()) { return $true }
    $tokens = $data.tokens
    if ($null -eq $tokens) { return $false }
    $hasAccount = $tokens.account_id -is [string] -and $tokens.account_id.Trim()
    $hasToken = @("access_token", "id_token", "refresh_token") | Where-Object {
        $tokens.$_ -is [string] -and $tokens.$_.Trim()
    }
    return [bool]($hasAccount -and $hasToken)
}

function Should-Keepalive {
    param([string]$AccountId)
    try {
        $state = Get-Content -Raw -Encoding UTF8 -Path $KeepaliveStateFile | ConvertFrom-Json
    } catch {
        return $true
    }
    $entry = $state.accounts.$AccountId
    if ($null -eq $entry) { return $true }
    return $entry.mode -ne "off"
}

function Ensure-TrustedProject {
    param(
        [string]$CodexHome,
        [string]$ProjectDir
    )
    $configPath = Join-Path $CodexHome "config.toml"
    $header = '[projects."{0}"]' -f $ProjectDir
    if (Test-Path $configPath) {
        $text = Get-Content -Raw -Encoding UTF8 -Path $configPath
    } else {
        $text = ""
    }
    if ($text.Contains($header) -and $text.Contains('trust_level = "trusted"')) {
        return
    }
    $addition = "`r`n$header`r`ntrust_level = `"trusted`"`r`n"
    Add-Content -Encoding UTF8 -Path $configPath -Value $addition
}

function Load-PidState {
    try {
        $state = Get-Content -Raw -Encoding UTF8 -Path $PidStateFile | ConvertFrom-Json
    } catch {
        $state = [pscustomobject]@{ accounts = [pscustomobject]@{}; web = $null }
    }
    if ($null -eq $state.accounts) {
        $state | Add-Member -MemberType NoteProperty -Name accounts -Value ([pscustomobject]@{})
    }
    return $state
}

function Save-PidState {
    param($State)
    $State | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -Path $PidStateFile
}

function Test-PidRunning {
    param($PidValue)
    if ($null -eq $PidValue) { return $false }
    return [bool](Get-Process -Id ([int]$PidValue) -ErrorAction SilentlyContinue)
}

function Start-WebService {
    param($State)
    $url = "http://${HostName}:${Port}/api/accounts"
    try {
        Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null
        Write-Log "web already running: $url"
        return
    } catch {
    }
    $python = Get-PythonCommand
    $command = @"
`$env:CODEX_ACCOUNT_SEARCH_ROOT = '$AccountSearchRoot'
`$env:CODEX_SWITCHER_HOST = '$HostName'
`$env:CODEX_SWITCHER_PORT = '$Port'
Set-Location '$AppDir'
& '$python' app.py
"@
    $process = Start-Process powershell -ArgumentList @("-NoExit", "-Command", $command) -PassThru
    $State.web = [pscustomobject]@{ pid = $process.Id; port = $Port; host = $HostName }
    Write-Log "start web pid=$($process.Id): http://${HostName}:${Port}"
}

$pidState = Load-PidState
if ($StartWeb) {
    Start-WebService -State $pidState
}

$homes = Get-ChildItem -Path $AccountSearchRoot -Directory -Filter ".codex-*" -ErrorAction SilentlyContinue
$foundCount = 0
foreach ($home in $homes) {
    $accountId = $home.Name.Substring(".codex-".Length)
    if (-not $accountId) { continue }
    $foundCount += 1
    $authPath = Join-Path $home.FullName "auth.json"
    if (-not (Test-Path $authPath)) {
        Write-Log "skip codex-${accountId}: missing $authPath"
        continue
    }
    if (-not (Test-AuthUsable -AuthPath $authPath)) {
        Write-Log "skip codex-${accountId}: invalid or expired-looking auth.json"
        continue
    }
    if (-not (Should-Keepalive -AccountId $accountId)) {
        Write-Log "skip codex-${accountId}: keepalive disabled by policy"
        continue
    }
    Ensure-TrustedProject -CodexHome $home.FullName -ProjectDir $TrustedWorkdir
    $oldPid = $pidState.accounts.$accountId.pid
    if (Test-PidRunning -PidValue $oldPid) {
        Write-Log "ok codex-${accountId}: already running pid=$oldPid"
        continue
    }
    $command = @"
`$env:CODEX_HOME = '$($home.FullName)'
Set-Location '$TrustedWorkdir'
codex --cd '$TrustedWorkdir'
"@
    $process = Start-Process powershell -ArgumentList @("-NoExit", "-Command", $command) -PassThru
    $pidState.accounts | Add-Member -Force -MemberType NoteProperty -Name $accountId -Value ([pscustomobject]@{ pid = $process.Id; home = $home.FullName })
    Write-Log "start codex-${accountId} pid=$($process.Id) with CODEX_HOME=$($home.FullName)"
}

if ($foundCount -eq 0) {
    Write-Log "no account directories found under $AccountSearchRoot"
}

Save-PidState -State $pidState
Write-Log "done"
