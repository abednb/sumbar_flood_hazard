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

**Underlying Physics & QA Gates (National v2.0 Standard)**:
- **Indonesian Auto-UTM**: Automatic UTM zone detection (`EPSG:32646–32754` via `scripts/geo_utils.py`).
- **Active Watershed Mask**: Strictly bounded to `das_region` (`setup_mask_active: mask: das_region, reset_mask: true`) so outside-basin and ocean cells remain inactive (`msk=0`) and inland outlets receive `msk=3`.
- **Subgrid Hypsometry**: 40 m (or 80 m fast mode) computational flux mesh with 10 m subgrid elevation tables derived from native 30 m FABDEM via on-the-fly `WarpedVRT`.
- **Manning Roughness**: Integer-coded BIG RBI land cover (`data/landcover_rbi.tif`) with `lookup_tables/manning_lookup.csv` & canonical 15-class `lookup_tables/national_rbi_lookup.csv`.
- **Silted River Burning**: River centerlines enhanced with BIG RBI polygon river widths (`data/rivers_ar.gpkg`) burned into subgrid hypsometry (`rivwth: 8/15/22 m`, `rivdph: 0.35/0.55/0.80 m`, `manning=0.045`).
- **CNB Infiltration**: SFINCS `v2.4.0+` Curve Number with Recovery (`smaxfile`/`sefffile`/`ksfile` in meters from `data/cn_amc2_100m.tif` & `data/cn_amc3_100m.tif`; NEVER use legacy `scsfile` in `v2.4.0`!).
- **Boundary Conditioning**: Coastal waterlevel boundaries (`msk=2`) forced with MHHW (`+0.80 m`) via native `sfincs.bnd`/`sfincs.bzs`, and inland outflow boundaries (`msk=3`) snapped to lowest-elevation catchment outlets.
- **Build-Time & Subgrid QA**: Verifies non-uniform roughness, masked domain, boundary presence, depth peak timing, and exact subgrid hypsometric storage volume (`sfincs_subgrid.nc`).

---

### Step 2: Extended Recession Direct Rainfall Forcing
Apply 24-hour design storm hyetographs padded with explicit zero-intensity recession timesteps (default 48 hours = 24 h storm + 24 h recession; extend to 72 h for large basins):

```python
from scripts.sfincs_standalone_pipeline import prepare_sfincs_direct_rain_forcing

prepare_sfincs_direct_rain_forcing(
    das_id="DAS_101",
    return_periods=["rp100"],
    base_model_dir="models_sfincs_standalone",
    rainfall_dir="data/rainfall",
    storm_hours=24,
    recession_hours=None,       # Auto-scales by basin area (24h / 36h / 48h)
    infiltration_mode="cnb",    # USDA-NRCS smax/seff/ks (never legacy scsfile in v2.4.0)
    coastal_mhhw_m=0.80,        # Coastal MHHW tidal backwater on msk=2 cells
    alpha=0.65,
    huthresh=0.02,
    viscosity=0,
    tref="20240101 000000",
    tstart="20240101 000000",
)
```

**Quality Controls**:
- Rainfall CRS detected from NetCDF coordinates (EPSG:4326).
- Bounding box checked to cover the active model domain.
- Active cells checked for NaN (raises error if missing) and zero total.
- Explicit zeros padded up to `tstop` to prevent constant-tail rain holding.
- Forcing volume conservation check: domain-mean padded rainfall matches design depth within $\pm 1\%$.
- `dtmaxout` configured to full simulation length so peak water levels (`zsmax`) encompass both storm peak and downstream floodplain recession.

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

### Step 4: Option B Natural Hydrostatic Downscaling & BNPB Classification
Downscale water surface elevations ($z_s$) to 10 m topography, apply **Option B Hydrostatically Connected Natural Floodplain Margin (`+0.25 m` FABDEM uncertainty margin strictly gated to connected flat `< 5°` plains within `≤ 80 m`)** + **4-connected `30 m × 30 m` (`0.09 ha`) pinhole/speck floor**, and classify according to Perka BNPB No. 02/2012:

```python
from scripts.sfincs_standalone_pipeline import postprocess_sfincs_hazard

postprocess_sfincs_hazard(
    das_id="DAS_101",
    rp="rp100",
    base_model_dir="models_sfincs_standalone",
    output_maps_dir="outputs",
    hmin=0.05,
    freeboard_m=0.25,
    max_ext_dist_m=80.0,
    max_ext_slope_deg=5.0,
    hole_mmu_ha=2.0,
    island_mmu_ha=0.09,
    min_hole_ha=0.09,
    bridge_radius=5,
    smooth_sigma=1.2,
    cosmetic=False,
    classification_method="depth",
)
```

**Hazard Tiers (Perka BNPB No. 02/2012)**:
- **Class 0 (Dry / Unflooded)**: $h < 0.05\text{ m}$
- **Class 1 (Rendah / Low Hazard)**: $0.05\text{ m} \le h < 0.76\text{ m}$
- **Class 2 (Sedang / Medium Hazard)**: $0.76\text{ m} \le h \le 1.50\text{ m}$
- **Class 3 (Tinggi / High Hazard)**: $h > 1.50\text{ m}$

**Artifact Outputs**:
- `outputs/<DAS>/<rp>/<DAS_TAG>_<RP_TAG>_Flood_Depth_raw.tif`: Direct downscaled depth before filtering.
- `outputs/<DAS>/<rp>/<DAS_TAG>_<RP_TAG>_Flood_Depth.tif`: Hydrostatically reconstructed flood depth (wet only where $z_s > z_{\text{DEM}}$).
- `outputs/<DAS>/<rp>/<DAS_TAG>_<RP_TAG>_FloodHazard_Classes.tif`: 3-class BNPB disaster hazard level (with companion `.qml`).
- `outputs/<DAS>/<rp>/<DAS_TAG>_<RP_TAG>_FloodHazard_Index.tif`: Continuous Fuzzy Large Flood Hazard Index ($0.0 - 1.0$, with companion `.qml`).
- `outputs/<DAS>/<rp>/qa_report.json`: QA check outputs (roughness, active mask & boundaries, depth-based peak timing, storage volume balance).
- `outputs/<DAS>/<rp>/survey_validation.json`: QField ground truth contingency and outlier-filtered RMSE metrics.

---

### Step 5: Flood Wave Propagation Animation
Render a dynamic multi-layer satellite GIF showing 72-hour propagation:

```python
from scripts.sfincs_standalone_pipeline import create_sfincs_flood_animation

create_sfincs_flood_animation(
    das_id="DAS_101",
    rp="rp100",
    base_model_dir="models_sfincs_standalone",
    output_maps_dir="outputs",
    fps=2,
    hmin=0.05,
    vmax=3.0,
)
```

---

## 3. Future Work / Hydro-Meteorological Coupling
Coupling 1D distributed hydrological rainfall-runoff models (e.g. Deltares Wflow.jl) to provide boundary hydrographs for major transboundary river inflows into SFINCS can be configured via `setup_river_inflow` and `bws_inflow_hydrographs` when streamflow records become available.
