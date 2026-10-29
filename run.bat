@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if errorlevel 1 exit /b 1

if not exist "python\python.exe" goto install
"python\python.exe" -c "import streamlit, openai, openpyxl, xlrd; from importlib.metadata import version; assert tuple(map(int, version('streamlit').split('.')[:2])) >= (1, 49)" >nul 2>nul
if errorlevel 1 goto install
goto launch

:install
echo 首次运行或运行环境不完整，正在初始化...
call setup.bat --from-launcher
if errorlevel 1 goto failed

:launch
if not exist "config.py" (
    copy /y "config_template.py" "config.py" >nul
    if errorlevel 1 goto failed
)
echo.
echo 正在启动 Xbench 误报筛查工具，请保留此窗口。
echo 浏览器打开后，可在「参数设置」中填写 API Key。
echo.
"python\python.exe" -m streamlit run ui/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
if errorlevel 1 goto failed
popd
exit /b 0

:failed
echo.
echo 启动失败，请查看上方错误信息。可重新运行 setup.bat 修复环境。
pause
popd
exit /b 1
