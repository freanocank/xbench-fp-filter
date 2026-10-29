@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if errorlevel 1 exit /b 1
echo ============================================
echo   Xbench FP Filter - 初始化设置
echo ============================================
echo.

REM Download the embedded runtime only when it is missing.
if not exist "python\python.exe" (
    echo [1/3] 下载 Python 运行环境，需要网络连接...
    powershell -NoProfile -Command "$ErrorActionPreference = 'Stop'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'python_embed.zip' -UseBasicParsing"
    if errorlevel 1 goto failed
    powershell -NoProfile -Command "$ErrorActionPreference = 'Stop'; Expand-Archive -LiteralPath 'python_embed.zip' -DestinationPath 'python' -Force"
    if errorlevel 1 goto failed
    del "python_embed.zip"
) else (
    echo [1/3] Python 运行环境已就绪。
)

REM The embedded runtime uses python*._pth, not *.pth.
powershell -NoProfile -Command "$ErrorActionPreference = 'Stop'; Get-ChildItem 'python\python*._pth' | ForEach-Object { (Get-Content -LiteralPath $_.FullName) -replace '^#import site','import site' | Set-Content -LiteralPath $_.FullName -Encoding Ascii }"
if errorlevel 1 goto failed

"python\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 (
    echo 安装 pip...
    powershell -NoProfile -Command "$ErrorActionPreference = 'Stop'; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get_pip.py' -UseBasicParsing"
    if errorlevel 1 goto failed
    "python\python.exe" get_pip.py --quiet --no-warn-script-location
    if errorlevel 1 goto failed
    del "get_pip.py"
)

echo.
echo [2/3] 安装依赖包，首次运行可能需要几分钟...
"python\python.exe" -m pip install -r requirements.txt --quiet --no-warn-script-location
if errorlevel 1 goto failed

echo.
echo [3/3] 检查配置文件...
if not exist "config.py" (
    copy /y "config_template.py" "config.py" >nul
    if errorlevel 1 goto failed
    echo 默认配置已生成，可在页面中填写 API Key。
) else (
    echo 配置文件已存在。
)

echo.
echo 设置完成！双击 run.bat 启动工具。
if /i not "%~1"=="--from-launcher" pause
popd
exit /b 0

:failed
echo.
echo 安装失败，请查看上方错误信息，检查网络后重新运行 setup.bat。
if /i not "%~1"=="--from-launcher" pause
popd
exit /b 1
