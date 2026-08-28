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
if (-not (Test-Path "$pasta\config.env")) {
    "APP_URL=https://meus-investimentos-a3yv.onrender.com" | Out-File -FilePath "$pasta\config.env" -Encoding utf8
}

# 4. Cria um atalho pra abrir rapido nas proximas vezes
$atalho = "$pasta\Abrir Meus Investimentos.bat"
if (-not (Test-Path $atalho)) {
    $conteudoAtalho = "@echo off`r`ncd /d `"%~dp0`"`r`nstart `"`" pythonw.exe run_app.py`r`n"
    [System.IO.File]::WriteAllText($atalho, $conteudoAtalho, [System.Text.Encoding]::ASCII)
}

# 5. Abre o app agora
Write-Host "Abrindo o app..." -ForegroundColor Green
Start-Process pythonw.exe -ArgumentList "run_app.py" -WorkingDirectory $pasta

Write-Host ""
Write-Host "Pronto! Da proxima vez, e' so dar duplo clique em 'Abrir Meus Investimentos.bat' nesta pasta." -ForegroundColor Cyan
