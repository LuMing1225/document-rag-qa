@echo off
chcp 65001 >nul
echo ============================================
echo  启动 Milvus 向量数据库
echo  端口: 19530 (gRPC), 9091 (metrics)
echo ============================================

:: 切换到 scripts 目录
cd /d "%~dp0"

:: Step 1: 检查 Milvus 是否已运行
echo [1/3] 检查 Milvus 是否已运行...
docker ps --filter "name=milvus-standalone" --format "{{.Names}}" | findstr "milvus-standalone" >nul
if errorlevel 1 (
    echo   Milvus 未运行，正在启动 Docker Compose...
    docker compose up -d
    if errorlevel 1 (
        echo   [错误] docker compose up -d 失败，请检查 Docker 是否运行
        pause
        exit /b 1
    )
) else (
    echo   Milvus 已在运行
)

:: Step 2: 等待 Milvus 就绪（循环检查端口 19530）
echo [2/3] 等待 Milvus 就绪（端口 19530）...
set /a retry_count = 0
:wait_loop
timeout /t 3 /nobreak >nul
powershell -Command "Test-NetConnection -ComputerName localhost -Port 19530 -InformationLevel Quiet" 2>nul | findstr "True" >nul
if not errorlevel 1 (
    echo   Milvus 端口 19530 已就绪！
    goto :milvus_ready
)
set /a retry_count += 1
if %retry_count% geq 30 (
    echo   [警告] 等待 Milvus 就绪超时（90秒），请手动检查 Docker 容器状态
    docker ps
    pause
    exit /b 1
)
echo   等待中... 第 %retry_count% 次检查
goto :wait_loop

:milvus_ready
:: Step 3: 打印 Milvus 状态
echo [3/3] Milvus 状态:
docker ps --filter "name=milvus" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo ============================================
echo  Milvus 已就绪！
echo  gRPC 地址: localhost:19530
echo  管理界面: http://localhost:9091
echo ============================================
echo.
