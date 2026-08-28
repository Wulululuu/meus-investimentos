# Cria (ou atualiza) um atalho de verdade ("Meus Investimentos.lnk") na
# Area de Trabalho, apontando pro pythonw.exe + run_app.py, com o icone
# do app. Rodar isso (em vez de fixar o .bat na barra de tarefas) resolve
# dois problemas do Windows:
# 1. .bat fixado na barra de tarefas mostra o icone generico de arquivo,
#    nao o icone do app.
# 2. Fixar o processo pythonw.exe direto (sem passar por um atalho .lnk)
#    faz o Windows perder os argumentos — ao clicar, ele tenta abrir o
#    "run_app.py" com o programa padrao de arquivos .py (normalmente um
#    editor de texto), em vez de executar o app.
$ErrorActionPreference = "Stop"
$pasta = Split-Path -Parent $PSScriptRoot

$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pythonw) { $pythonw = (Get-Command pythonw.exe -ErrorAction Stop).Source }

$atalhoPath = "$env:USERPROFILE\Desktop\Meus Investimentos.lnk"
$icone = Join-Path $pasta "icone_app.ico"

$WshShell = New-Object -ComObject WScript.Shell
$atalho = $WshShell.CreateShortcut($atalhoPath)
$atalho.TargetPath = $pythonw
$atalho.Arguments = "`"$pasta\run_app.py`""
$atalho.WorkingDirectory = $pasta
if (Test-Path $icone) { $atalho.IconLocation = $icone }
$atalho.Save()

Write-Host "Atalho criado em: $atalhoPath" -ForegroundColor Green
Write-Host "Agora e' so clicar com o botao direito nele e escolher 'Fixar na barra de tarefas'." -ForegroundColor Cyan
