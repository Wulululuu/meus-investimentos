# Instala (se precisar) e abre o "Meus Investimentos" - roda sozinho, sem
# precisar de nenhum passo manual. Baixa sempre a versao mais recente dos
# arquivos do app direto do GitHub.
$ErrorActionPreference = "Stop"
$pasta = $PSScriptRoot
Set-Location $pasta

Write-Host "=== Instalando Meus Investimentos ===" -ForegroundColor Cyan

# 1. Verifica/instala o Python
$temPython = Get-Command python -ErrorAction SilentlyContinue
if (-not $temPython) {
    Write-Host "Python nao encontrado - baixando instalador oficial..." -ForegroundColor Yellow
    $installer = "$env:TEMP\python-installer.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" -OutFile $installer
    Write-Host "Instalando Python (1-2 minutos, aguarde)..." -ForegroundColor Yellow
    Start-Process -FilePath $installer -ArgumentList "/passive InstallAllUsers=0 PrependPath=1 Include_launcher=0" -Wait
    Remove-Item $installer -ErrorAction SilentlyContinue

    # atualiza o PATH desta sessao, sem precisar reabrir o terminal
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$env:Path;$userPath"
    Write-Host "Python instalado." -ForegroundColor Green
} else {
    Write-Host "Python ja estava instalado." -ForegroundColor Green
}

# 2. Instala a biblioteca da janela do app
Write-Host "Instalando dependencia (pywebview)..." -ForegroundColor Yellow
python -m pip install --quiet --disable-pip-version-check pywebview

# 3. Baixa sempre a versao mais recente dos arquivos do app
$base = "https://raw.githubusercontent.com/Wulululuu/meus-investimentos/main/pacote-para-amigo"
Write-Host "Baixando o app..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "$base/run_app.py" -OutFile "$pasta\run_app.py"
Invoke-WebRequest -Uri "$base/carregar_config.py" -OutFile "$pasta\carregar_config.py"
Invoke-WebRequest -Uri "$base/icone_app.ico" -OutFile "$pasta\icone_app.ico"
if (-not (Test-Path "$pasta\config.env")) {
    "APP_URL=https://meus-investimentos-a3yv.onrender.com" | Out-File -FilePath "$pasta\config.env" -Encoding utf8
}

# 4. Cria um atalho de verdade na Area de Trabalho, com o icone do app -
# assim da pra fixar na barra de tarefas corretamente (um .bat fixado
# perde o icone e os argumentos, e abre o run_app.py num editor de texto
# em vez de rodar o app)
$pythonwPath = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pythonwPath) { $pythonwPath = (Get-Command pythonw.exe).Source }
$atalhoPath = "$env:USERPROFILE\Desktop\Meus Investimentos.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$atalho = $WshShell.CreateShortcut($atalhoPath)
$atalho.TargetPath = $pythonwPath
$atalho.Arguments = "`"$pasta\run_app.py`""
$atalho.WorkingDirectory = $pasta
if (Test-Path "$pasta\icone_app.ico") { $atalho.IconLocation = "$pasta\icone_app.ico" }
$atalho.Save()

# 5. Abre o app agora
Write-Host "Abrindo o app..." -ForegroundColor Green
Start-Process pythonw.exe -ArgumentList "run_app.py" -WorkingDirectory $pasta

Write-Host ""
Write-Host "Pronto! Um atalho 'Meus Investimentos' foi criado na sua Area de Trabalho." -ForegroundColor Cyan
Write-Host "Da proxima vez, e' so dar duplo clique nele (ou clicar com o botao direito e escolher 'Fixar na barra de tarefas')." -ForegroundColor Cyan
