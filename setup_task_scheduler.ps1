# Registra uma Tarefa Agendada do Windows que roda a atualizacao diaria
# de cotacoes e proventos, de segunda a sexta, as 19:00 (apos o fechamento da B3).
# Execute este script uma unica vez (clique com o botao direito > Executar com PowerShell,
# ou rode `powershell -ExecutionPolicy Bypass -File setup_task_scheduler.ps1`).

$ErrorActionPreference = "Stop"

$pastaApp = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"

$acao = New-ScheduledTaskAction -Execute $python -Argument "update_daily.py" -WorkingDirectory $pastaApp
$gatilho = New-ScheduledTaskTrigger -Daily -At 19:00
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask -TaskName "MeusInvestimentos-AtualizacaoDiaria" `
    -Action $acao -Trigger $gatilho -Settings $config `
    -Description "Atualiza cotacoes e proventos do app Meus Investimentos apos o fechamento da B3" `
    -Force

Write-Host "Tarefa agendada criada: 'MeusInvestimentos-AtualizacaoDiaria' (todo dia as 19:00)." -ForegroundColor Green
Write-Host "Para verificar: abra o 'Agendador de Tarefas' do Windows e procure por esse nome." -ForegroundColor Green
