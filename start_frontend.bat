@echo off
chcp 65001 >nul
REM ============================================================
REM  启动 长文本版面分析RAG检索系统 前端 (Streamlit, 端口 8523)
REM  后端 API 地址: http://localhost:8563
REM ============================================================

REM 切换到本脚本所在目录
cd /d %~dp0

echo ============================================
echo  正在启动 Streamlit 前端 (端口 8523)...
echo  后端 API: http://localhost:8563
echo ============================================

conda run -n pdfqa streamlit run frontend/app.py --server.port 8523 --server.headless true

pause
