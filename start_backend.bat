@echo off
REM ============================================================
REM  母婴护理 RAG 检索系统后端启动脚本
REM  端口: 8563
REM  运行环境: conda 的 pdfqa 环境
REM ============================================================
chcp 65001 >nul
cd /d "E:\shixunXM\工单4\03-长文本版面分析RAG检索系统"

REM 激活 pdfqa 环境（若已在 Anaconda Prompt 中可直接运行）
call conda activate pdfqa

echo ============================================================
echo  启动母婴护理 RAG 后端，端口 8563 ...
echo  依赖 Ollama: bge-m3:latest / qwen3:8b (localhost:11434)
echo ============================================================

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8563

pause
