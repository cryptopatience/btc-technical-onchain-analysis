@echo off
cd /d "c:\Users\user\미주 BTC 뉴스 통합분석"
"C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe" discord_scheduler.py --now >> "c:\Users\user\미주 BTC 뉴스 통합분석\scheduler.log" 2>&1
