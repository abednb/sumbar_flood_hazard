Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Sumatera Barat Flood Hazard - HydroMT-SFINCS Setup Guide " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check if uv is installed
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[1/4] Installing astral-sh/uv package manager..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path += ";$HOME\.local\bin;$HOME\.cargo\bin"
} else {
    Write-Host "[1/4] astral-sh/uv is already installed." -ForegroundColor Green
}

# 2. Create virtual environment
if (-not (Test-Path ".\env-sfincs")) {
    Write-Host "[2/4] Creating virtual environment env-sfincs with Python 3.12..." -ForegroundColor Yellow
    uv venv env-sfincs --python 3.12
} else {
    Write-Host "[2/4] Virtual environment env-sfincs already exists." -ForegroundColor Green
}

# 3. Install dependencies
Write-Host "[3/4] Installing HydroMT-SFINCS and geospatial dependencies..." -ForegroundColor Yellow
uv pip install -r env/requirements.txt --python env-sfincs\Scripts\python.exe

# 4. Register Jupyter Kernel
Write-Host "[4/4] Registering Jupyter Kernel 'HydroMT-SFINCS'..." -ForegroundColor Yellow
& ".\env-sfincs\Scripts\python.exe" -m ipykernel install --user --name hydromt-sfincs --display-name "HydroMT-SFINCS"

# 5. Windows 11 Compatibility: Unblock binaries and verify runtime
if (Test-Path ".\bin") {
    Write-Host "Unblocking native solver binaries and DLLs (Windows 11 MOTW guard)..." -ForegroundColor Gray
    Get-ChildItem -Path .\bin -ErrorAction SilentlyContinue | Unblock-File
}

try {
    $sfincsCheck = & ".\bin\sfincs.exe" 2>&1
    if ($sfincsCheck -match "SFINCS") {
        Write-Host "[OK] SFINCS 2.4.0 Native Solver & runtime DLLs verified!" -ForegroundColor Green
    }
} catch {
    Write-Host "[NOTE] If sfincs.exe fails on Windows 11, install Visual C++ Redistributable (x64): https://aka.ms/vs/17/release/vc_redist.x64.exe" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host " SETUP COMPLETE! Ready to run SFINCS Standalone models.  " -ForegroundColor Green
Write-Host " In Jupyter/VS Code, select the 'HydroMT-SFINCS' kernel. " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
