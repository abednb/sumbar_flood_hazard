---
name: hydromt-sfincs
description: Official HydroMT 0.10.1 and SFINCS 2.4.0 standalone direct rainfall-on-grid 2D flood hazard modeling workflow skill with subgrid hypsometry, Kementan soil infiltration, river burning, and Perka BNPB classification.
---

# HydroMT-SFINCS Standalone 2D Flood Hazard Modeling Skill

This skill provides reproducible, high-performance workflows for configuring, building, executing, and post-processing **Deltares SFINCS** (Super-Fast INundation of CoastS and riverS, v2.4.0 Galibier Release) standalone direct rainfall-on-grid models using **HydroMT 0.10.1** and **hydromt-sfincs 1.2.2** under Windows PowerShell and `uv`.

---

## 1. Environment & Python Execution

Always execute scripts and notebooks inside the pinned workspace environment using `.\.venv\Scripts\python.exe` or `uv run`:

```powershell
# Verify HydroMT and SFINCS plugin
.\.venv\Scripts\python.exe -c "import hydromt, hydromt_sfincs; print(f'HydroMT: {hydromt.__version__}, SFINCS: {hydromt_sfincs.__version__}')"
```

Environment variables for GDAL/PROJ and the native SFINCS solver are managed centrally by `scripts/_env.py`:
- `PROJ_DATA`: `.\.venv\Lib\site-packages\rasterio\proj_data`
- `GDAL_DATA`: `.\.venv\Lib\site-packages\rasterio\gdal_data`
- `SFINCS_PATH`: `bin/sfincs.exe` (OpenMP 64-bit solver)

---

## 2. End-to-End Pipeline Workflow

### Step 1: Spatial Data Preparation & Chipping
Extract the watershed boundary, DEM window chip, conditioned river centerlines with hydraulic geometry, and the local data catalog:

```python
from scripts.sfincs_standalone_pipeline import build_sfincs_standalone

# Builds the base SFINCS model domain for a cluster (e.g. DAS_101)
model_root = build_sfincs_standalone(
    das_id="DAS_101",
    output_dir="models_sfincs_standalone",
    config_fn="configs/sfincs_standalone_build.yml",
    data_catalog_fn="data_catalog_sfincs.yml",
    das_clusters_gpkg="data/das_clusters/sumbar_das_cluster.gpkg",
    force_overwrite=True,
)
```

**Underlying Physics & QA Gates**:
- **Subgrid Hypsometry**: 40 m computational flux mesh with 10 m subgrid elevation tables derived from FABDEM (30 m native, bilinearly resampled to 10 m).
- **Manning Roughness**: Integer-coded BIG RBI land cover (`data/landcover_rbi.tif`) with lookup table `lookup_tables/manning_lookup.csv` (Chow 1959 / Arcement & Schneider 1989).
- **River Burning**: River centerlines burned into subgrid hypsometry (`datasets_riv`) with hydraulic geometry (`rivwth`, `rivdph`, `manning=0.030`).
- **Boundary Conditioning**: Waterlevel boundary cells (`msk=2`) at sea level ($z \le 0$), and outflow boundary cells (`msk=3`) at inland catchment outlets.
- **Build-Time QA**: Verifies non-uniform roughness (`std > 0`) and boundary existence (`count(msk=2) + count(msk=3) > 0`).

---

### Step 2: Extended Recession Direct Rainfall Forcing
Apply 24-hour design storm hyetographs padded with explicit zero-intensity recession timesteps (total duration 72 hours):

```python
from scripts.sfincs_standalone_pipeline import prepare_sfincs_direct_rain_forcing

prepare_sfincs_direct_rain_forcing(
    das_id="DAS_101",
    return_periods=["rp100"],
    base_model_dir="models_sfincs_standalone",
    rainfall_dir="data/rainfall",
    storm_hours=24,
    recession_hours=48,
    tref="20240101 000000",
    tstart="20240101 000000",
)
```

**Quality Controls**:
- Rainfall CRS detected from NetCDF coordinates (EPSG:4326).
- Bounding box checked to cover the active model domain.
- Active cells checked for NaN (raises error if missing) and zero total.
- Explicit zeros padded up to `tstop` (72 h) to prevent constant-tail rain holding.
- Forcing volume conservation check: domain-mean padded rainfall matches design depth within $\pm 1\%$.
- `dtmaxout` configured to 72 h so peak water levels (`zsmax`) encompass both storm peak and downstream floodplain recession.

---

### Step 3: Hydrodynamic Simulation Solver
Execute the native Windows 64-bit SFINCS executable with live progress tracking:

```python
from scripts.sfincs_standalone_pipeline import run_sfincs_model

run_sfincs_model(
    das_id="DAS_101",
    rp="rp100",
    base_model_dir="models_sfincs_standalone",
    sfincs_exe="bin/sfincs.exe",
)
```

---

### Step 4: Downscaling, Depth Reconstruction & BNPB Classification
Downscale water surface elevations ($z_s$) to the 10 m topography, reconstruct physical depth ($z_s - z_{\text{DEM}}$), and classify according to Perka BNPB No. 02/2012:

```python
from scripts.sfincs_standalone_pipeline import postprocess_sfincs_hazard

postprocess_sfincs_hazard(
    das_id="DAS_101",
    rp="rp100",
    base_model_dir="models_sfincs_standalone",
    output_maps_dir="outputs_standalone",
    hmin=0.05,
    hole_mmu_px=50,
    island_mmu_px=50,
    cosmetic=False,
    classification_method="depth",
    low_thresh=0.76,
    high_thresh=1.50,
)
```

**Hazard Tiers (Perka BNPB No. 02/2012)**:
- **Class 0 (Dry / Unflooded)**: $h < 0.05\text{ m}$
- **Class 1 (Rendah / Low Hazard)**: $0.05\text{ m} \le h < 0.76\text{ m}$
- **Class 2 (Sedang / Medium Hazard)**: $0.76\text{ m} \le h \le 1.50\text{ m}$
- **Class 3 (Tinggi / High Hazard)**: $h > 1.50\text{ m}$

**Artifact Outputs**:
- `outputs_standalone/<DAS>/<rp>/flood_depth_10m_raw.tif`: Direct downscaled depth before filtering.
- `outputs_standalone/<DAS>/<rp>/flood_depth_10m.tif`: Physically reconstructed flood depth (wet only if $z_s - z_{\text{DEM}} \ge h_{\text{min}}$).
- `outputs_standalone/<DAS>/<rp>/hazard_class_perka2012.tif`: 3-class BNPB disaster hazard level.
- `outputs_standalone/<DAS>/<rp>/flood_hazard_index.tif`: Continuous Fuzzy Large Flood Hazard Index ($0.0 - 1.0$).
- `outputs_standalone/<DAS>/<rp>/qa_report.json`: QA check outputs (roughness, boundaries, peak timing, volume balance).
- `outputs_standalone/<DAS>/<rp>/survey_validation.json`: QField ground truth contingency and RMSE metrics.

---

### Step 5: Flood Wave Propagation Animation
Render a dynamic multi-layer satellite GIF showing 72-hour propagation:

```python
from scripts.sfincs_standalone_pipeline import create_sfincs_flood_animation

create_sfincs_flood_animation(
    das_id="DAS_101",
    rp="rp100",
    base_model_dir="models_sfincs_standalone",
    output_maps_dir="outputs_standalone",
    fps=2,
    hmin=0.05,
    vmax=3.0,
)
```

---

## 3. Future Work / Hydro-Meteorological Coupling
Coupling 1D distributed hydrological rainfall-runoff models (e.g. Deltares Wflow.jl) to provide boundary hydrographs for major transboundary river inflows into SFINCS can be configured via `setup_river_inflow` and `bws_inflow_hydrographs` when streamflow records become available.
