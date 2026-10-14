@echo off
chcp 65001 >nul
echo ============================================
echo  一键启动全部服务（Milvus 版）
echo  Milvus: 19530  后端: 8563  前端: 8523
echo ============================================

:: Step 1: 启动 Milvus 向量数据库
echo [1/6] 启动 Milvus 向量数据库...
call "%~dp0start_milvus.bat"
if errorlevel 1 (
    echo   [错误] Milvus 启动失败，无法继续
    pause
    exit /b 1
)

:: Step 2: 检查Ollama是否运行
echo [2/6] 检查Ollama服务...
tasklist /FI "IMAGENAME eq ollama.exe" | find /I "ollama.exe" >nul
if errorlevel 1 (
    echo   Ollama未运行，正在启动...
    start "" "C:\Users\luming\AppData\Local\Programs\Ollama\ollama app.exe"
    timeout /t 5 /nobreak >nul
) else (
    echo   Ollama已在运行
)

:: Step 3: 启动后端（新窗口）
echo [3/6] 启动后端服务（新窗口，rag_layout 环境）...
start "RAG-Backend" cmd /k "cd /d E:\shixunXM\工单4\03-长文本版面分析RAG检索系统 && call conda activate rag_layout && uvicorn backend.main:app --host 0.0.0.0 --port 8563"

:: Step 4: 等待后端就绪
echo [4/6] 等待后端就绪...
timeout /t 10 /nobreak >nul

:: 检查后端是否响应
curl -s http://localhost:8563/docs >nul 2>&1
if errorlevel 1 (
    echo   后端还在启动中，再等待8秒...
    timeout /t 8 /nobreak >nul
    curl -s http://localhost:8563/docs >nul 2>&1
    if errorlevel 1 (
        echo   [警告] 后端仍未就绪，请手动检查后端窗口日志
    ) else (
        echo   后端已就绪
    )
) else (
    echo   后端已就绪
)

:: Step 5: 启动前端（新窗口）
echo [5/6] 启动前端服务（新窗口，rag_layout 环境）...
start "RAG-Frontend" cmd /k "cd /d E:\shixunXM\工单4\03-长文本版面分析RAG检索系统 && call conda activate rag_layout && streamlit run frontend/app.py --server.port 8523"

:: Step 6: 打开浏览器
echo [6/6] 打开浏览器...
timeout /t 3 /nobreak >nul
start http://localhost:8523

echo.
echo ============================================
echo  全部服务已启动！
echo  Milvus:     localhost:19530
echo  后端API:    http://localhost:8563/docs
echo  前端界面:   http://localhost:8523
echo ============================================
echo.
echo  关闭对应的命令行窗口即可停止服务。
pause
