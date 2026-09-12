@echo off
rem Copyright 2026 ReSerendipity
rem
rem Licensed under the Apache License, Version 2.0 (the "License");
rem you may not use this file except in compliance with the License.
rem You may obtain a copy of the License at
rem
rem     http://www.apache.org/licenses/LICENSE-2.0
rem
rem Unless required by applicable law or agreed to in writing, software
rem distributed under the License is distributed on an "AS IS" BASIS,
rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
rem See the License for the specific language governing permissions and
rem limitations under the License.

chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ========================================
echo   RTX_VSR-lite - NVIDIA RTX 视频超分
echo ========================================
echo.

if not exist venv (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo 创建虚拟环境失败，请确认已安装 Python 3.10+ 并加入 PATH。
        goto :end
    )
)

echo [2/3] 激活环境并安装依赖...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo [3/3] 环境自检...
echo.

REM nvvfx 不在 PyPI 上，需从 NVIDIA VSR SDK 单独获取，详见 README。
python -c "import rtx_vsr; print('rtx_vsr %s 导入正常' % rtx_vsr.__version__)"
python -c "from rtx_vsr import is_sdk_present; print('nvvfx 已就位' if is_sdk_present() else '[警告] 未检测到 nvvfx，请阅读 README 的「安装 nvvfx」一节后再使用')"

echo.
echo 用法示例:
echo   python main.py -i input.mp4 -o output.mp4 --scale 2x --quality ultra
echo   python main.py -i input.mp4 -o output.mp4 -W 1920 -H 1080 -q high
echo   python main.py -i .\videos -o .\upscaled --quality high
echo   python main.py -i input.mp4 -o output.mp4 --scale 2x --dry-run
echo.
:end
echo 按任意键退出...
pause >nul
endlocal
