# Gera a pasta portatil dist\NotepadCarrossel e confere o executavel.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    python -m venv (Join-Path $Root ".venv")
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Root "requirements.txt")
& $Python -m pytest
if ($LASTEXITCODE -ne 0) { throw "Os testes falharam." }

$DistBuild = Join-Path $Root "build\pyi-dist"
$WorkBuild = Join-Path $Root "build\pyi-work"
if (Test-Path $DistBuild) { Remove-Item $DistBuild -Recurse -Force }
& $Python -m PyInstaller --noconfirm --clean (Join-Path $Root "packaging\NotepadCarrossel.spec") --distpath $DistBuild --workpath $WorkBuild
if ($LASTEXITCODE -ne 0) { throw "O PyInstaller falhou." }

$Portable = Join-Path $Root "dist\NotepadCarrossel"
if (Test-Path $Portable) { Remove-Item $Portable -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $Portable "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Portable "backup") | Out-Null
Copy-Item (Join-Path $DistBuild "NotepadCarrossel.exe") (Join-Path $Portable "NotepadCarrossel.exe") -Force
Copy-Item (Join-Path $Root "packaging\README.txt") (Join-Path $Portable "README.txt") -Force

$Exe = Join-Path $Portable "NotepadCarrossel.exe"
$env:PATH = "C:\Windows\System32"
$env:PYTHONPATH = ""
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue

Write-Host "Abrindo a interface empacotada..."
& $Exe --smoke-gui
if ($LASTEXITCODE -ne 0) { throw "A interface empacotada nao abriu." }
$Smoke = Join-Path $Portable "data\smoke-result.txt"
if (-not (Test-Path $Smoke)) { throw "A interface nao gravou o resultado." }

Write-Host "Conferindo persistencia no executavel..."
& $Exe --self-test
if ($LASTEXITCODE -ne 0) { throw "O autoteste do executavel falhou." }
$Result = Get-Content (Join-Path $Portable "data\selftest-result.txt") -Raw
if ($Result -notlike "SELFTEST_OK*") { throw $Result }

$Accent = Join-Path $Root "dist\area de trabalho\Notepad Carrossel"
New-Item -ItemType Directory -Force -Path $Accent | Out-Null
& $Exe --self-test --root $Accent
if ($LASTEXITCODE -ne 0) { throw "O autoteste em caminho com espaco falhou." }

Write-Host "Pasta portatil pronta: $Portable"
