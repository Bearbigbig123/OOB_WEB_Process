@echo off
echo Starting OOB & Tool Matching Analysis System...
echo.

REM 檢查是否已安裝必要套件
echo Checking dependencies...
pip install -r requirements.txt
echo.

REM 啟動 FastAPI 後台服務 (在背景執行)
echo Starting FastAPI backend server...
start /b "FastAPI Backend" uvicorn main:app --host localhost --port 8000 --reload
echo FastAPI backend started on http://localhost:8000
echo.

REM 等待後台服務啟動
echo Waiting for backend to start...
timeout /t 5 /nobreak > nul

REM 啟動 Streamlit 前端
echo Starting Streamlit frontend...
echo Frontend will be available at http://localhost:8501
echo.
streamlit run streamlit_app.py --server.port 8501

pause