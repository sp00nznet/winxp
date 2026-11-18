@echo off
rem tools\devmgr_stub.cmd OUTDIR: src\stub\devmgr.c as OUTDIR\devmgr.dll (x86, no CRT, no imports, base 0x21C00000)
setlocal
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -products * -property installationPath`) do set "VS=%%i"
call "%VS%\VC\Auxiliary\Build\vcvarsall.bat" amd64_x86 >nul || exit /b 1
cd /d "%~dp0..\src\stub" || exit /b 1
cl /nologo /O1 /GS- /c devmgr.c /Fo"%~1\devmgr.obj" || exit /b 1
link /nologo /DLL /NOENTRY /NODEFAULTLIB /BASE:0x21C00000 /FIXED:NO /DEF:devmgr.def /OUT:"%~1\devmgr.dll" "%~1\devmgr.obj" || exit /b 1
