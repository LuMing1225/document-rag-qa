@echo off
chcp 65001 >nul
echo ============================================
echo  启动前端服务 (端口 8523)
echo ============================================

call conda activate pdfqa
if errorlevel 1 (
    echo [错误] 无法激活conda环境 pdfqa
    pause
    exit /b 1
)

cd /d E:\shixunXM\工单4\03-长文本版面分析RAG检索系统

echo 正在启动Streamlit前端...
echo 前端地址: http://localhost:8523
echo 按Ctrl+C停止服务
echo.

streamlit run frontend/app.py --server.port 8523

pause
