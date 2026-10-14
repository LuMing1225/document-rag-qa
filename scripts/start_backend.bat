@echo off
chcp 65001 >nul
echo ============================================
echo  启动后端服务 (端口 8563)
echo ============================================

call conda activate pdfqa
if errorlevel 1 (
    echo [错误] 无法激活conda环境 pdfqa
    pause
    exit /b 1
)

cd /d E:\shixunXM\工单4\03-长文本版面分析RAG检索系统

echo 正在启动FastAPI后端...
echo 后端地址: http://localhost:8563
echo 按Ctrl+C停止服务
echo.

uvicorn backend.main:app --host 0.0.0.0 --port 8563

pause
