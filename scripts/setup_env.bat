@echo off
chcp 65001 >nul
echo ============================================
echo  环境初始化脚本
echo ============================================

:: Step 1: 检查conda环境pdfqa
echo [1/4] 检查conda环境 pdfqa...
call conda env list | findstr /I "pdfqa" >nul
if errorlevel 1 (
    echo   conda环境pdfqa不存在，正在创建...
    call conda create -n pdfqa python=3.10 -y
    if errorlevel 1 (
        echo [错误] 创建conda环境失败
        pause
        exit /b 1
    )
) else (
    echo   conda环境pdfqa已存在
)

:: Step 2: 激活环境并安装依赖
echo [2/4] 激活conda环境并安装Python依赖...
call conda activate pdfqa
cd /d E:\shixunXM\工单4\03-长文本版面分析RAG检索系统

pip install -r requirements.txt
if errorlevel 1 (
    echo [警告] 部分依赖安装失败，请手动检查
) else (
    echo   Python依赖安装完成
)

:: Step 3: 检查Ollama
echo [3/4] 检查Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
    echo   [提示] 未检测到Ollama，请从 https://ollama.com/download 下载安装
) else (
    echo   Ollama已安装
)

:: Step 4: 检查Ollama模型
echo [4/4] 检查Ollama模型...
ollama list 2>nul | findstr /I "bge-m3" >nul
if errorlevel 1 (
    echo   缺少模型 bge-m3，正在下载...
    ollama pull bge-m3:latest
) else (
    echo   bge-m3:latest 已存在
)

ollama list 2>nul | findstr /I "qwen3:8b" >nul
if errorlevel 1 (
    echo   缺少模型 qwen3:8b，正在下载...
    ollama pull qwen3:8b
) else (
    echo   qwen3:8b 已存在
)

echo.
echo ============================================
echo  环境初始化完成！
echo  下一步: 运行 scripts\start_all.bat 启动服务
echo ============================================
pause
