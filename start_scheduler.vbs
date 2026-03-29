Set WShell = CreateObject("WScript.Shell")
WShell.CurrentDirectory = "c:\Users\user\미주 BTC 뉴스 통합분석"
WShell.Run """C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe"" discord_scheduler.py", 0, False
