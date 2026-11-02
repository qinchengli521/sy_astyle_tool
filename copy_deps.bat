@echo off
chcp 65001 >nul
rem ============================================================
rem 复制运行依赖到打包输出目录
rem 从代码仓库根目录复制 .astylerc 与 astyle\astyle.exe
rem 到 dist\AstyleTool\（PyInstaller 目录模式产物）。
rem 用法：先按 docs\打包说明.md 打包，再双击或命令行运行本脚本。
rem ============================================================
setlocal

set "DIST=%~dp0dist\AstyleTool"

if not exist "%DIST%\AstyleTool.exe" (
    echo [错误] 未找到 "%DIST%\AstyleTool.exe"
    echo 请先按 docs\打包说明.md 第 2 节执行 PyInstaller 打包。
    exit /b 1
)

if not exist "%~dp0.astylerc" (
    echo [错误] 未找到 "%~dp0.astylerc"
    exit /b 1
)
if not exist "%~dp0astyle\astyle.exe" (
    echo [错误] 未找到 "%~dp0astyle\astyle.exe"
    exit /b 1
)

copy /y "%~dp0.astylerc" "%DIST%\" >nul
if errorlevel 1 (
    echo [错误] 复制 .astylerc 失败。
    exit /b 1
)

if not exist "%DIST%\astyle" mkdir "%DIST%\astyle"
copy /y "%~dp0astyle\astyle.exe" "%DIST%\astyle\" >nul
if errorlevel 1 (
    echo [错误] 复制 astyle.exe 失败。
    exit /b 1
)

echo [完成] 依赖已复制到 "%DIST%"
echo 发布目录内容：
dir /b "%DIST%"
endlocal
