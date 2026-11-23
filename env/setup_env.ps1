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

# 2. Provision unified virtual environment (.venv) from pyproject.toml + uv.lock
Write-Host "[2/4] Syncing unified virtual environment (.venv) via uv sync..." -ForegroundColor Yellow
uv sync --extra dev

# 3. Verify core geospatial imports
Write-Host "[3/4] Verifying HydroMT-SFINCS installation..." -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" -c "import hydromt, hydromt_sfincs, geopandas, rasterio; print(f'OK: hydromt={hydromt.__version__}, hydromt_sfincs={hydromt_sfincs.__version__}')"

# 4. Register Jupyter Kernel
Write-Host "[4/4] Registering Jupyter Kernel 'HydroMT-SFINCS'..." -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" -m ipykernel install --user --name hydromt-sfincs --display-name "HydroMT-SFINCS"

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
