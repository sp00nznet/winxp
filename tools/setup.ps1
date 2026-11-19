# One-click setup for winxp-recomp: Windows XP's own userland, statically
# recompiled, with its explorer in a window on this PC. Run it by
# double-clicking Setup.cmd in the repo folder; the README's "Building by
# hand" is the same thing command for command.
#
# It takes I386 from your Windows XP SP3 CD image, expands and rebases the
# files it needs (tools\fetch_xp.sh), lifts and builds explorer and the
# accessories, seeds explorer's registry box and private profile, and leaves
# "Windows XP (recomp).cmd" here. Each step is skipped when its output already
# exists (-Force redoes them). Everything it does goes to setup.log. -Yes
# installs what is missing without asking; -Iso is your CD image (an .iso, or
# a folder or drive holding I386), asked for when not given.
# RECOMP_LAUNCHER=1 skips the "Press Enter" at the end.
param([switch]$Force, [switch]$Yes, [string]$Iso = "")

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
# The toolkit: PCRECOMP, else ../pcrecomp (cloned when missing).
$Parent = Split-Path -Parent $Root
$Toolkit = if ($env:PCRECOMP) { $env:PCRECOMP } else { Join-Path $Parent 'pcrecomp' }
$T = Join-Path $Toolkit 'tools'
$Log = Join-Path $Root 'setup.log'
Set-Location $Root
$Steps = 7
function Log($t) { try { Add-Content -Path $Log -Value $t -Encoding UTF8 -ErrorAction Stop } catch {} }
Log "==== setup $(Get-Date -Format s)"

function Say($t, $c = 'Gray') { Write-Host $t -ForegroundColor $c; Log $t }
function Pause-End { if (-not $env:RECOMP_LAUNCHER) { Read-Host "Press Enter to close" | Out-Null } }
# cmd.exe, which the lift scripts build through, splits a path at '&' and at spaces.
if ($Root -match '[& ]') {
  Say "This folder's path has a space or an '&' in it, which the build cannot handle:" 'Red'
  Say "  $Root" 'Red'
  Say "Move the folder somewhere else (for example C:\winxp-recomp) and run Setup.cmd from there." 'Yellow'
  Pause-End; exit 1
}
function Step($n, $t) { Write-Host ""; Say "[$n/$Steps] $t" 'Cyan' }
function Fail($t) {
  Say "" ; Say "Setup stopped: $t" 'Red'
  Say "The details are in $Log. Fix that and run Setup.cmd again; finished steps are skipped." 'Yellow'
  Pause-End; exit 1
}
function Ask($q) { if ($Yes) { Say "$q yes"; return $true }; $a = Read-Host "$q [Y/n]"; return -not ($a -match '^[nN]') }   # Enter = yes
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
# Run a program with its output in the log. Windows PowerShell turns a native
# program's stderr into errors, so 'Stop' is off while it runs.
function Exec([string[]]$cmd) {
  $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  $rest = @($cmd | Select-Object -Skip 1)   # @(): a one-element slice would splat as characters
  & $cmd[0] @rest 2>&1 | ForEach-Object { Log "$_" }
  $code = $LASTEXITCODE
  $ErrorActionPreference = $old
  return $code
}
function Run($what, [string[]]$cmd) {
  Say "  $what..."
  $code = Exec $cmd
  if ($code -ne 0) { Fail "$what failed (exit code $code)." }
}
function Done($p) { return (-not $Force) -and (Test-Path -LiteralPath $p) }

Clear-Host
Say "Windows XP - static recompilation setup" 'White'
Say "You need your own Windows XP SP3 CD image and about 30 GB free."
Say "Lifting and building take about 2 hours, once."

# ---------------------------------------------------------------- tools
Step 1 "Checking the tools the pipeline needs"
# The scripts run "py -3" (the Python launcher, which python.org's and winget's Python install).
function Py-Ok {
  if (-not (Get-Command py -ErrorAction SilentlyContinue)) { return $false }
  $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  $v = (& py -3 --version 2>&1 | Out-String).Trim()
  $ErrorActionPreference = $old
  return ($v -match '^Python 3\.(\d+)' -and [int]$Matches[1] -ge 10)
}
if (-not (Py-Ok)) {
  Say "  Python 3.10 or newer (with the py launcher) is not installed."
  if (-not (Ask "  Install Python 3.12 now (winget, for your user only, about 30 MB)?")) { Fail "Python 3 is required." }
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Fail "winget is missing. Install 'App Installer' from the Microsoft Store, or install Python from python.org yourself."
  }
  Exec @('winget', 'install', '-e', '--id', 'Python.Python.3.12', '--scope', 'user', '--accept-package-agreements', '--accept-source-agreements') | Out-Null
  Refresh-Path
  if (-not (Py-Ok)) { Fail "Python installed, but Windows has not picked it up yet: close this window and run Setup.cmd again." }
}
Say "  Python: py -3"
if ((Exec @('py', '-3', '-c', 'import pefile, capstone')) -ne 0) {
  Say "  The Python packages pefile and capstone are missing (about 15 MB)."
  if (-not (Ask "  Install them now (pip, for your user only)?")) { Fail "pefile and capstone are required." }
  Run "Installing pefile and capstone" @('py', '-3', '-m', 'pip', 'install', '--user', 'pefile', 'capstone')
}

# Git for Windows: git for pcrecomp, and its bash for the lift scripts (tools\*.sh).
# Not "bash" from PATH: that can be WSL's.
function Find-GitBash {
  $g = Get-Command git -ErrorAction SilentlyContinue
  $cands = @()
  if ($g) { $cands += (Join-Path (Split-Path -Parent (Split-Path -Parent $g.Source)) 'bin\bash.exe') }
  $cands += (Join-Path $env:ProgramFiles 'Git\bin\bash.exe')
  foreach ($c in $cands) { if (Test-Path $c) { return $c } }
  return $null
}
$Bash = Find-GitBash
if (-not $Bash) {
  Say "  Git for Windows (git, and the bash the lift scripts run in) is not installed."
  if (-not (Ask "  Install Git for Windows now (winget, about 300 MB)?")) { Fail "Git for Windows is required." }
  Exec @('winget', 'install', '-e', '--id', 'Git.Git', '--accept-package-agreements', '--accept-source-agreements') | Out-Null
  Refresh-Path
  $Bash = Find-GitBash
  if (-not $Bash) { Fail "Git installed, but Windows has not picked it up yet: close this window and run Setup.cmd again." }
}
Say "  bash: $Bash"

# 7-Zip: the CD image and the CD's compressed files (X.DL_).
function Find-7z {
  foreach ($c in @((Join-Path $env:ProgramFiles '7-Zip\7z.exe'), (Join-Path ${env:ProgramFiles(x86)} '7-Zip\7z.exe'))) { if (Test-Path $c) { return $c } }
  $g = Get-Command 7z -ErrorAction SilentlyContinue
  if ($g) { return $g.Source }
  return $null
}
$SevenZip = Find-7z
if (-not $SevenZip) {
  Say "  7-Zip is not installed."
  if (-not (Ask "  Install 7-Zip now (winget, about 2 MB)?")) { Fail "7-Zip is required." }
  Exec @('winget', 'install', '-e', '--id', '7zip.7zip', '--accept-package-agreements', '--accept-source-agreements') | Out-Null
  $SevenZip = Find-7z
  if (-not $SevenZip) { Fail "7-Zip installed, but it is not where it should be: run Setup.cmd again." }
}
Say "  7-Zip: $SevenZip"
# the lift scripts call "7z" and "py": both on their PATH
$env:Path = (Split-Path -Parent $SevenZip) + ';' + $env:Path

if (-not (Test-Path (Join-Path $T 'lift\drive32.py'))) {
  Say "  The pcrecomp toolkit is not beside this folder ($Toolkit)."
  if (-not (Ask "  Download it now (git, about 30 MB)?")) { Fail "pcrecomp is required at $Toolkit." }
  Run "Cloning pcrecomp" @('git', 'clone', '--depth', '1', 'https://github.com/sp00nznet/pcrecomp', $Toolkit)
}
# The XP support (runtime\native32\ntguest.h): pcrecomp's luna branch or later (Luna: its xp branch draws classic).
$tkOk = { (Test-Path (Join-Path $Toolkit 'runtime\native32\w32kuser.c')) -and (Test-Path (Join-Path $Toolkit 'runtime\native32\ntguest.h')) -and
          (Test-Path (Join-Path $Toolkit 'runtime\native32\w32klayout.c')) }
if (-not (& $tkOk) -and (Test-Path (Join-Path $Toolkit '.git'))) {
  Say "  Your pcrecomp is older than this build needs."
  if (Ask "  Update it now (git pull)?") { Run "Updating pcrecomp" @('git', '-C', $Toolkit, 'pull', '--ff-only') }
}
if (-not (& $tkOk)) { Fail "your pcrecomp at $Toolkit is too old for this build. Update it: git -C `"$Toolkit`" pull" }
$env:PCRECOMP = $Toolkit -replace '\\', '/'
Say "  pcrecomp: $Toolkit"

# The compiler. build.cmd finds Visual Studio itself; this only checks that it
# is there, with CMake and Ninja.
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vs = if (Test-Path $vswhere) { (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath) } else { $null }
if (-not $vs) {
  Say "  Visual Studio 2022 with the C++ tools is not installed."
  if (-not (Ask "  Install the Visual Studio 2022 Build Tools with the C++ workload now (winget, about 3 GB, asks for admin)?")) {
    Fail "Visual Studio 2022 (or its Build Tools) with 'Desktop development with C++' is needed. Install it, then run Setup.cmd again."
  }
  Exec @('winget', 'install', '-e', '--id', 'Microsoft.VisualStudio.2022.BuildTools', '--accept-package-agreements', '--accept-source-agreements',
         '--override', '--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended') | Out-Null
  $vs = if (Test-Path $vswhere) { (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath) } else { $null }
  if (-not $vs) { Fail "the Visual Studio Build Tools did not install. Install them with 'Desktop development with C++', then run Setup.cmd again." }
}
Say "  Visual Studio: $vs"
foreach ($tool in @(@('cmake', 'Kitware.CMake', '30 MB'), @('ninja', 'Ninja-build.Ninja', '1 MB'))) {
  if (Get-Command $tool[0] -ErrorAction SilentlyContinue) { continue }
  Say "  $($tool[0]) is not installed."
  if (-not (Ask "  Install $($tool[0]) now (winget, about $($tool[2]))?")) { Fail "$($tool[0]) is required." }
  Exec @('winget', 'install', '-e', '--id', $tool[1], '--accept-package-agreements', '--accept-source-agreements') | Out-Null
  Refresh-Path
  $env:Path = (Split-Path -Parent $SevenZip) + ';' + $env:Path
  if (-not (Get-Command $tool[0] -ErrorAction SilentlyContinue)) { Fail "$($tool[0]) installed, but Windows has not picked it up yet: close this window and run Setup.cmd again." }
}

# A tools\*.sh script in Git's bash, from the repo root, output in the log.
function Sh($what, $script) { Run $what @($Bash, '-c', "cd '$($Root -replace '\\', '/')' && $script") }

# ---------------------------------------------------------------- the CD
Step 2 "Copying I386 from your Windows XP CD into work\iso"
$I386 = 'work\iso\I386'
function Is-Cd([string]$p) {
  if (-not $p) { return $false }
  if (Test-Path -LiteralPath $p -PathType Container) { return (Test-Path (Join-Path $p 'I386\NTDLL.DLL')) }
  return ((Test-Path -LiteralPath $p -PathType Leaf) -and $p -match '\.iso$')
}
if ((Done "$I386\HIVEDEF.INF") -and (Test-Path "$I386\NTDLL.DLL")) {
  Say "  Already in work\iso (skipping)."
} else {
  $Iso = $Iso.Trim('"', ' ')
  if (-not (Is-Cd $Iso)) {   # an image next to Setup.cmd
    $Iso = @(Get-ChildItem -Path $Root -Filter *.iso -File -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.FullName })[0]
    if ($Iso) { Say "  Found $Iso" }
  }
  if (-not (Is-Cd $Iso) -and $Yes) { Fail "no Windows XP CD image given. Give it with -Iso (an .iso, or a folder or drive holding I386)." }
  while (-not (Is-Cd $Iso)) {
    $Iso = (Read-Host "  Paste the path of your Windows XP CD image (an .iso file, or a drive or folder holding I386)").Trim('"', ' ')
    if (-not (Is-Cd $Iso)) { Say "  That is not an .iso file or a folder with I386\NTDLL.DLL in it." 'Yellow' }
  }
  if (Test-Path -LiteralPath $Iso -PathType Container) {
    Say "  Copying $Iso\I386 (about 500 MB)..."
    $code = Exec @('robocopy', (Join-Path $Iso 'I386'), (Join-Path $Root $I386), '/E', '/NFL', '/NDL', '/NJH', '/NP')
    if ($code -ge 8) { Fail "copying I386 failed (robocopy exit code $code)." }
  } else {
    Run "Extracting I386 (about 500 MB)" @($SevenZip, 'x', '-y', '-owork\iso', $Iso, 'I386\*')
  }
}
# Windows XP SP3 (5.1.2600.5512): the build every XP answer was read off
$ver = (& py -3 -c "import pefile;v=pefile.PE(r'$I386\NTDLL.DLL').VS_FIXEDFILEINFO[0];print('%d.%d.%d.%d'%(v.FileVersionMS>>16,v.FileVersionMS&0xffff,v.FileVersionLS>>16,v.FileVersionLS&0xffff))" 2>$null)
if (-not $ver) { Fail "work\iso\I386\NTDLL.DLL is not readable: delete work\iso and run Setup.cmd again." }
if (-not ($ver -match '^5\.1\.2600\.(\d+)$')) { Fail "this is not Windows XP (5.1.2600): its ntdll is $ver. Delete work\iso and give a Windows XP SP3 CD." }
if ([int]$Matches[1] -ne 5512) { Say "  ntdll $ver is not SP3's (5.1.2600.5512): the build may not work. An SP3 CD is what it was made on." 'Yellow' }
else { Say "  Windows XP $ver (SP3)" }

# ---------------------------------------------------------------- expand and rebase
Step 3 "Expanding and rebasing the files it needs (work\sys, work\rebased-shell)"
New-Item -ItemType Directory -Force work\names | Out-Null
# win32k's service names for Windows XP SP3 (j00ru's public tables; the numbers are the guest's own)
if ($Force -or -not (Test-Path 'work\names\win32k-per-system.json')) {
  Say "  Downloading win32k's service names (github.com/j00ru/windows-syscalls, 1 MB)..."
  try { Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/j00ru/windows-syscalls/master/x86/json/win32k-per-system.json' -OutFile 'work\names\win32k-per-system.json' }
  catch { Fail "downloading the win32k names failed: $($_.Exception.Message)" }
}
if ($Force -or -not (Test-Path 'work\names\win32k.txt')) {
  $names = & py -3 tools\w32k_names.py 'Windows XP' SP3
  if ($LASTEXITCODE -ne 0 -or -not $names) { Fail "tools\w32k_names.py failed." }
  Set-Content -Path 'work\names\win32k.txt' -Value $names -Encoding ASCII
}
# every file from the CD and its base (tools\fetch_xp.sh: a rerun keeps what is there)
Sh "Expanding and rebasing (tools/fetch_xp.sh)" 'sh tools/fetch_xp.sh'

# ---------------------------------------------------------------- lift and build
Step 4 "Lifting and building explorer (about an hour)"
if (Done 'build\ntexplorer_explorer.dll') { Say "  Already done (skipping)." }
else { Sh "Lifting and building (work\lift_ntexplorer.log, work\build_ntexplorer_parts.log)" 'sh tools/lift_explorer.sh' }

Step 5 "Lifting and building winmine, notepad and calc (about 40 minutes)"
$todo = @(@('winmine', 'notepad', 'calc') | Where-Object { $Force -or -not (Test-Path "build\nt$_.exe") })
if (-not $todo) { Say "  Already done (skipping)." }
foreach ($a in $todo) { Sh "$a (work\lift_nt$a.log)" "sh tools/lift_accessories.sh $a" }

# ---------------------------------------------------------------- the box
# Explorer's registry box (HKCU\Software\pcrecomp\xp\explorer: XP's COM classes and an App Path
# for each lifted runner) and its private profile in work\profile, the guest's C:\.
Step 6 "Explorer's registry box and profile (work\profile)"
Run "Windows XP's COM classes" @('py', '-3', 'tools\reginst.py', 'xp\explorer', 'work\rebased-shell', 'browseui', 'shell32', 'shdocvw', 'comctl32', 'mydocs')
Sh "The profile" "py -3 tools/profile.py 'xp\explorer' 'work/profile/C/Documents and Settings' 'C:\Documents and Settings' >/dev/null && mkdir -p work/profile/C/TEMP"

# ---------------------------------------------------------------- the launcher
Step 7 "Making the shortcut"
$lnk = Join-Path $Root 'Windows XP (recomp).cmd'
# tools/run_explorer.sh's environment (the profile, the file box, muted), in a window of its own
Set-Content -Path $lnk -Encoding ASCII -Value @(
  '@echo off',
  'rem Windows XP''s own explorer, recompiled, on an 800x600 screen of its own (W2K_SCREEN to change it).',
  'rem The guest sees only work\profile (its C:); the log is work\explorer.log. Close this window to quit.',
  'cd /d "%~dp0"',
  'set "B=%~dp0work\profile"',
  'set "P=%B%\C\Documents and Settings"',
  'if not defined W2K_SCREEN set W2K_SCREEN=800x600',
  'set PCRECOMP_MUTE=1',
  'set PCRECOMP_GUEST_PATH=C:\WINDOWS\system32',
  'set "PCRECOMP_FILEBOX=%B%"',
  'set "ProgramFiles=%B%\C\Program Files"',
  'set "CommonProgramFiles=%B%\C\Program Files\Common Files"',
  'set ProgramW6432=',
  'set CommonProgramW6432=',
  'set "USERPROFILE=%P%\user"',
  'set "ALLUSERSPROFILE=%P%\all"',
  'set "ProgramData=%P%\all"',
  'set "PUBLIC=%P%\all"',
  'set "APPDATA=%P%\user\Application Data"',
  'set "LOCALAPPDATA=%P%\user\Local Settings\Application Data"',
  'set HOMEDRIVE=',
  'set HOMEPATH=',
  'set "TEMP=%B%\C\TEMP"',
  'set "TMP=%B%\C\TEMP"',
  'title Windows XP (recomp)',
  'echo Windows XP is running in its own window. Close it, or this window, to quit.',
  'build\ntexplorer.exe --mute %* 2> work\explorer.log')
Say "  $lnk"

Write-Host ""
Say "Done. Double-click 'Windows XP (recomp).cmd' to start Windows XP's explorer." 'Green'
Pause-End
