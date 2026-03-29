# Windows 작업 스케줄러 등록 — 매일 KST 08:00 Discord 자동 발송
# 실행: powershell -ExecutionPolicy Bypass -File register_task.ps1

$taskName   = "BTC_Discord_Daily_Report"
$batFile    = "c:\Users\user\미주 BTC 뉴스 통합분석\run_discord_report.bat"
$triggerTime = "08:00"   # KST (시스템 시간이 KST로 설정된 경우)

# 기존 작업 삭제 후 재등록
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batFile`""
$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -WakeToRun

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "매일 KST 08:00 AI 종합분석 → Discord 자동 발송" `
    -RunLevel Highest

Write-Host ""
Write-Host "✅ 작업 스케줄러 등록 완료!" -ForegroundColor Green
Write-Host "   작업 이름 : $taskName"
Write-Host "   실행 시간 : 매일 $triggerTime (KST)"
Write-Host "   로그 파일 : c:\Users\user\미주 BTC 뉴스 통합분석\scheduler.log"
Write-Host ""
Write-Host "즉시 테스트 실행:" -ForegroundColor Yellow
Write-Host "   Start-ScheduledTask -TaskName '$taskName'"
