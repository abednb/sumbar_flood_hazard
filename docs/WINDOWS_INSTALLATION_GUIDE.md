# Windows Setup & Installation Guide (Beginner-Friendly)
## Quick 6-Step Setup for Team Members to Run Standalone HydroMT-SFINCS on Windows

This guide provides the simplest, foolproof workflow for team members to run the **Sumatera Barat 2D Flood Hazard Model** on their Windows PCs without needing Git, Conda, or administrator privileges.

---

## ⚡ The 6-Step Quick Workflow (No Git Required)

```mermaid
graph LR
    S1[1. Install VS Code] --> S2[2. Copy Repo Folder]
    S2 --> S3[3. Open Folder in VS Code]
    S3 --> S4[4. Run Setup Script in Terminal]
    S4 --> S5[5. Select Kernel in Notebook]
    S5 --> S6[6. Run Notebook Cells]
```

### 1️⃣ Step 1: Install Visual Studio Code
* Download and install **VS Code** from [https://code.visualstudio.com/](https://code.visualstudio.com/).
* Open VS Code, go to the Extensions tab (`Ctrl + Shift + X`), search and install:
  * **Python** (by Microsoft)
  * **Jupyter** (by Microsoft)

### 2️⃣ Step 2: Copy the Project Folder to Local PC
* Copy the `sumbar_flood_hazard` folder (via flash drive, shared network drive, or zip) onto your local PC:
  * Example: `D:\Project\sumbar_flood_hazard` or `C:\Project\sumbar_flood_hazard`.

### 3️⃣ Step 3: Open the Folder in VS Code
* In VS Code: Click **File** $\rightarrow$ **Open Folder...** $\rightarrow$ Select `D:\Project\sumbar_flood_hazard`.

### 4️⃣ Step 4: Run the Automated Setup Script in VS Code Terminal
* Open the built-in terminal in VS Code (`Ctrl + ` ` ` or **Terminal** $\rightarrow$ **New Terminal**).
* Copy and paste this single command:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\env\setup_env.ps1
  ```
  *(This automatically installs `uv`, provisions isolated **Python 3.12**, installs all geospatial packages in under 60 seconds, and registers the Jupyter kernel).*

### 5️⃣ Step 5: Open Notebook and Select the Dedicated Kernel
* Open the master batch notebook in [`notebook/master/01_sfincs_flood_hazard_run.ipynb`](../notebook/master/01_sfincs_flood_hazard_run.ipynb).
* In the top-right corner of the notebook editor, click **Select Kernel**:
  * Choose **Python Environments...** $\rightarrow$ select **`.venv`** (`.\.venv\Scripts\python.exe`).
  * *(Or select **Jupyter Kernel...** $\rightarrow$ **`HydroMT-SFINCS`**)*.

> [!IMPORTANT]
> **Avoid the "No module named pyproj" error**: When VS Code opens a notebook for the first time, it often defaults to your computer's global Windows Python. Always ensure the top-right kernel button displays **`.venv`** or **`HydroMT-SFINCS`** before executing cells.

### 6️⃣ Step 6: Configure Your Assigned Watershed & Run!
* In **Cell 1 (User Configuration Control Panel)**, set your assigned watershed ID and return period:
  ```python
  SELECTED_CLUSTERS = ["DAS_104"]  # Change to your assigned DAS ID (e.g., DAS_101 to DAS_114)
  SELECTED_RPS = ["rp100"]         # "rp2", "rp5", "rp10", "rp25", "rp50", "rp100"
  ```
* Run **Cell 2 (Environment & Data Verification)**:
  * Confirms PROJ/GDAL path bindings and loads `sfincs_standalone_pipeline`.
* Run remaining cells sequentially or click **Run All**!

---

## 📦 Stack & Dependency Specifications

The pipeline is standardized on **Python 3.12** managed via **`astral-sh/uv`** for lightning-fast, reproducible virtual environments without conda bloat:

| Category | Component / Library | Version Specification | Purpose in Pipeline |
| :--- | :--- | :--- | :--- |
| **Runtime** | Python | `3.12.x` (64-bit) | Core execution runtime |
| **Package Engine** | `uv` | Latest | High-performance venv and wheel manager |
| **Hydrodynamic Engine** | SFINCS Native Binary | `2.4.0-galibier-release` | 2D overland flow & subgrid solver |
| **Model Builder** | `hydromt` | `==0.10.1` | HydroMT core framework |
| **Model Plugin** | `hydromt-sfincs` | `==1.2.2` | SFINCS grid & subgrid table generator |
| **Vector Engine** | `geopandas` | `>=1.0.0` (1.1.x) | Watershed & administrative boundaries |
| **Raster Engine** | `rasterio` | `>=1.4.0` (1.5.x) | GeoTIFF I/O & downscaling |
| **Projections / CRS** | `pyproj` | `>=3.7.0` (3.7.x) | Dynamic PROJ coordinate transformations |
| **Data Array Engine** | `xarray` / `rioxarray` | `>=2024.1.0` / `>=0.18.0` | Gridded NetCDF rainfall & geospatial cubes |
| **Unstructured Mesh** | `xugrid` | `>=0.14.0` | HydroMT spatial mesh operations |
| **Flow Routing** | `pyflwdir` | `>=0.5.10` | Stream network & flow direction extraction |
| **Visualization** | `matplotlib` / `folium` | `>=3.9.0` / `>=0.17.0` | 3-panel QA maps & interactive web maps |
| **Animation** | `pillow` / `imageio` | `>=10.0.0` | 24-hour flood propagation animated GIF |

---

## 🛠️ Manual Setup (Step-by-Step PowerShell)

If you prefer executing commands manually instead of running `setup_env.ps1`:

```powershell
# 1. Install astral-sh/uv package manager
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Refresh PATH in current terminal session
$env:Path += ";$HOME\.local\bin;$HOME\.cargo\bin"

# 2. Provision unified virtual environment (.venv) from pyproject.toml + uv.lock
uv sync --extra dev

# 3. Register the Jupyter Kernel for VS Code
.\.venv\Scripts\python.exe -m ipykernel install --user --name hydromt-sfincs --display-name "HydroMT-SFINCS"
```

---

## 🔍 Step 4 — Verify Native SFINCS Solver & DLLs

Verify that the native 64-bit SFINCS hydrodynamic executable runs properly:

```powershell
.\bin\sfincs.exe
```

**Expected Output:**
```text
 ******************************************************************************
 *                                                                            *
 * SFINCS: Super-Fast INundation of CoastS and riverS                         *
 *                                                                            *
 * Deltares, The Netherlands                                                  *
 * Version 2.4.0-galibier-release                                             *
 ******************************************************************************
```
*(If the banner appears, your Intel Fortran runtime, OpenMP, HDF5, and NetCDF DLLs in `bin/` are fully operational!)*

---

## 🚀 Step 5 — Notebook Cell Execution Workflow

When running [`notebook/master/01_sfincs_flood_hazard_run.ipynb`](../notebook/master/01_sfincs_flood_hazard_run.ipynb), execute cells in numerical order:

* **Cell 1 — User Configuration Control Panel**:
  Configure target clusters and return periods (e.g., `SELECTED_CLUSTERS = ["DAS_104"]`, `SELECTED_RPS = ["rp100"]`).
* **Cell 2 — Environment & Data Verification**:
  Dynamically binds PROJ/GDAL paths from the active virtual environment and imports `sfincs_standalone_pipeline`.
* **Cell 3 (Step 1) — Build SFINCS Base Grids**:
  Extracts a masked **`80 m` V3 default** (or optional `40 m`) computational domain, derives 10 m subgrid tables on-the-fly from native 30 m FABDEM, burns silted rivers enhanced with `rivers_ar.gpkg`, and applies distributed Manning roughness from BIG RBI Land Cover.
* **Cell 4 (Step 2) — Apply Direct Rainfall, CNB & Coastal MHHW Forcing**:
  Binds 24-hour design storm hyetographs (`rainfall_<rp>.nc`) with dynamic zero-rain recession (`24–48 h`), applies USDA-NRCS `CNB` Curve Number infiltration (`smaxfile`/`sefffile`/`ksfile`), and sets `+0.80 m` coastal MHHW tidal backwater on coastal domains.
* **Cell 5 (Step 3) — Run SFINCS Hydrodynamic Simulation Engine**:
  Executes the 2D solver with an interactive terminal progress bar (automatically selecting native `bin/sfincs.exe` or Docker fallback).
* **Cell 6 (Step 4) — Option B Post-Processing, Subgrid QA & BNPB Classification**:
  Downscales water surface elevation to 10 m, applies the **`80 m V3` Option B `+0.35 m` FABDEM flat-floodplain margin** (`< 5°`, `≤ 120 m`, `bridge_radius=6`) and **4-connected `30 m × 30 m` floor**, computes continuous **Flood Hazard Index (0 to 1)** and **Perka BNPB No. 02/2012** classes, and runs automated subgrid hypsometric QA + QField validation.
* **Cell 7 (Step 5) — Quick GIS Visualization & QA/QC**:
  Renders a publication-ready 3-panel verification figure (10m Flood Depth, Continuous FHI, and BNPB 3-Class Map).
* **Cell 8 (Step 6) — Flood Wave Propagation Animation**:
  Compiles dynamic hourly flood wave propagation into an animated looping GIF (`DASXXX_RPYYY_Flood_Animation.gif`).

---

## 📁 Output Artifacts Inspection

Once the notebook finishes, all results are saved in `outputs/{das_id}/{rp}/`:

```
outputs/DAS_104/rp100/
├── DAS104_RP100_Flood_Depth.tif          <- Hydrostatically refined maximum inundation depth (m)
├── DAS104_RP100_Flood_Depth_raw.tif      <- Raw unrefined downscaled simulation depth (m)
├── DAS104_RP100_FloodHazard_Index.tif    <- Continuous Fuzzy Large Flood Hazard Index (0.0 to 1.0) + .qml
├── DAS104_RP100_FloodHazard_Classes.tif  <- Perka BNPB No. 02/2012 Classes (1: Rendah, 2: Sedang, 3: Tinggi) + .qml
├── qa_report.json                        <- Automated roughness, mask/boundary, peak timing & volume QA
└── survey_validation.json                <- Outlier-screened validation against QField observations
```

Open these GeoTIFFs in **QGIS** to inspect inundation boundaries and prepare thematic hazard cartography.

---

## ⚠️ Troubleshooting & FAQ

| Problem | Cause | Solution |
| :--- | :--- | :--- |
| **`No module named pyproj`** or **`ModuleNotFoundError`** | VS Code notebook connected to the global Windows Python instead of the virtual environment. | Click **Select Kernel** in top-right $\rightarrow$ **Python Environments...** $\rightarrow$ choose **`.venv`** (or **Jupyter Kernel...** $\rightarrow$ **`HydroMT-SFINCS`**). |
| **`Running scripts is disabled on this system`** | Windows PowerShell execution policy restriction. | Run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| **`HydroMT-SFINCS kernel not visible in VS Code`** | VS Code cached previous Python kernels. | Press `Ctrl + Shift + P` $\rightarrow$ select `Developer: Reload Window`. |
| **`sfincs.exe exited with code 3221225781`** | Missing Microsoft Visual C++ 2015–2022 runtime or Intel Fortran DLLs. | Install [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe) and verify all 9 DLLs remain inside `bin/`. |
| **`PermissionError: [WinError 5] Access is denied` on `sfincs.exe`** | Windows 11 SmartScreen / Mark-of-the-Web (MOTW) blocking network-copied binary. | Run in PowerShell: `Get-ChildItem -Path .\bin -Recurse \| Unblock-File` (or re-run `.\env\setup_env.ps1`). |
| **`ImportError: DLL load failed while importing _gdal`** | PROJ or GDAL library path conflict. | Ensure you are executing from `.venv` (`HydroMT-SFINCS`) and Cell 2 of the notebook was run. |
| **`Out of Memory / RAM spikes during mesh build`** | High-resolution FABDEM raster tiling during 10m subgrid extraction. | Ensure at least 8 GB of free RAM; close unnecessary browser tabs or background applications. |
