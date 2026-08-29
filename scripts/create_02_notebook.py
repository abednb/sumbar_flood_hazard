import os
import sys
from pathlib import Path
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.metadata = {
    'kernelspec': {
        'display_name': 'Python 3 (env-sfincs)',
        'language': 'python',
        'name': 'python3'
    },
    'language_info': {
        'name': 'python',
        'version': '3.11.9'
    }
}

cells = []

# Cell 1: Title
cells.append(nbf.v4.new_markdown_cell("""# Standalone HydroMT-SFINCS Direct Pipeline (Optimized Smaller DAS Clusters)
Kernel: **HydroMT-SFINCS** (`env-sfincs`)

This notebook runs the automated **HydroMT-SFINCS 2D flood hazard modeling workflow** specifically configured for the **Optimized Smaller DAS Clusters** (`data/modified_das_cluster/smaller_das_cluster.gpkg`):
1. **Targeted for Large / Transboundary Basins**: Pre-configured to run `DAS_103` (Lima Puluh Kota), `DAS_107` (Payakumbuh / Solok / Tanah Datar), `DAS_110` (Pasaman), and `DAS_113` (Solok Selatan), as well as any other cluster in West Sumatra.
2. **Boundary Source**: Uses `data/modified_das_cluster/smaller_das_cluster.gpkg` (all clusters $< 10,000\\text{ km}^2$, perfectly covering 100% of target Kabupaten territory without RAM OOM errors).
3. **40m 2D Computational Grid + 10m FABDEM Subgrid**: High numerical speed combined with 10m micro-topography fidelity.
4. **Direct Rainfall-on-Grid (SCS Design Storms RP2 to RP100)** applied across the active sub-basin.
5. **Post-Processing & BNPB Classification**: 10m downscaling, Continuous Fuzzy Large Flood Hazard Index (0-1), and Perka BNPB No. 2/2012 hazard mapping.
"""))

# Cell 2: Markdown - User Configuration Panel
cells.append(nbf.v4.new_markdown_cell("""---
## 📌 USER CONFIGURATION CONTROL PANEL (Modify Here Only)

> **GUIDELINE FOR USERS & TEAM MEMBERS:**  
> Adjust your target cluster(s) and return period(s) in the cell below. All downstream steps will automatically execute for the specified selections using the optimized boundary layer.
>
> ### Common Scenarios:
> * **Run Single Large Cluster (e.g. DAS_103, RP100):**
>   ```python
>   SELECTED_CLUSTERS = ["DAS_103"]
>   SELECTED_RPS = ["rp100"]
>   ```
> * **Batch Run All 4 Large Transboundary Clusters (RP100):**
>   ```python
>   SELECTED_CLUSTERS = ["DAS_103", "DAS_107", "DAS_110", "DAS_113"]
>   SELECTED_RPS = ["rp100"]
>   ```
> * **Run Full Return Period Suite for a Cluster (RP2 to RP100):**
>   ```python
>   SELECTED_CLUSTERS = ["DAS_103"]
>   SELECTED_RPS = ["rp2", "rp5", "rp10", "rp25", "rp50", "rp100"]
>   ```
"""))

# Cell 3: Code - User Configuration
cells.append(nbf.v4.new_code_cell("""# ==============================================================================
# 1. SET YOUR TARGET DAS CLUSTERS AND RETURN PERIODS HERE
# ==============================================================================

# Target large clusters: ["DAS_103", "DAS_107", "DAS_110", "DAS_113"] or any cluster ID
SELECTED_CLUSTERS = ["DAS_103"]

# Choose Return Periods: "rp2", "rp5", "rp10", "rp25", "rp50", "rp100"
SELECTED_RPS = ["rp100"]

# ==============================================================================
# 2. BOUNDARY DATASET & PATH CONFIGURATIONS
# ==============================================================================
# Uses the optimized smaller DAS cluster boundary (< 10,000 km2)
DAS_CLUSTERS_GPKG = "data/modified_das_cluster/smaller_das_cluster.gpkg"

# Optional BWS Infrastructure / Surveys (Leave as None for baseline)
BWS_LEVEES_GPKG = None        # e.g., "data_raw/bws/tanggul_sungai.gpkg"
BWS_GAUGES_GPKG = None        # e.g., "data_raw/bws/pos_awlr.gpkg"
BWS_INFLOW_HYDROGRAPHS = None # e.g., "data_raw/bws/debit_inflow.csv"

# Output and Config Directories
OUTPUT_MODELS_DIR = "models_sfincs_standalone"
OUTPUT_MAPS_DIR = "outputs_standalone"
CONFIG_FILE = "configs/sfincs_standalone_build.yml"
DATA_CATALOG_FILE = "data_catalog_sfincs.yml"

print(f"🎯 Target Clusters     : {SELECTED_CLUSTERS}")
print(f"🎯 Target Return Periods: {SELECTED_RPS}")
print(f"🗺️ Boundary Source GPKG : {DAS_CLUSTERS_GPKG}")
print(f"📂 Models Directory     : {OUTPUT_MODELS_DIR}")
print(f"📂 Maps Output Directory : {OUTPUT_MAPS_DIR}")
"""))

# Cell 4: Markdown - Step 1
cells.append(nbf.v4.new_markdown_cell("""---
## 1. Environment & Pipeline Initialization

Initializes Python paths, dynamic PROJ/GDAL projections paths, and loads all modular pipeline routines from `scripts/sfincs_standalone_pipeline.py`.
"""))

# Cell 5: Code - Environment Setup
cells.append(nbf.v4.new_code_cell("""import sys
import os
from pathlib import Path
import pyproj

# Add local scripts directory to sys.path
if "scripts" not in sys.path:
    sys.path.insert(0, "scripts")

# Fix PROJ and GDAL paths dynamically for Windows active environment
site_packages = Path(sys.prefix) / "Lib" / "site-packages"
proj_dir = (site_packages / "rasterio" / "proj_data").resolve()
gdal_dir = (site_packages / "rasterio" / "gdal_data").resolve()
if proj_dir.exists():
    os.environ["PROJ_DATA"] = str(proj_dir)
    os.environ["PROJ_LIB"] = str(proj_dir)
    pyproj.datadir.set_data_dir(str(proj_dir))
if gdal_dir.exists():
    os.environ["GDAL_DATA"] = str(gdal_dir)

import sfincs_standalone_pipeline
import importlib
importlib.reload(sfincs_standalone_pipeline)
from sfincs_standalone_pipeline import (
    build_sfincs_standalone,
    prepare_sfincs_direct_rain_forcing,
    run_sfincs_model,
    postprocess_sfincs_hazard,
    create_sfincs_flood_animation,
)

print("✓ Environment initialized and Standalone SFINCS pipeline loaded successfully!")
"""))

# Cell 6: Markdown - Step 2
cells.append(nbf.v4.new_markdown_cell("""---
## 2. Step 1 — Build Base SFINCS Mesh (40m Grid + 10m Subgrid)

Constructs the 2D computational domain from `smaller_das_cluster.gpkg`, extracts 10m subgrid tables from FABDEM, samples surface roughness from RBI Land Cover, and applies authoritative soil infiltration capacity (`soil_infiltration_sumbar`).
"""))

# Cell 7: Code - Build Base Mesh
cells.append(nbf.v4.new_code_cell("""for das_id in SELECTED_CLUSTERS:
    print(f"\\n==================== [{das_id}] BUILDING BASE SFINCS MESH ====================")
    build_sfincs_standalone(
        das_id=das_id,
        output_dir=OUTPUT_MODELS_DIR,
        config_fn=CONFIG_FILE,
        data_catalog_fn=DATA_CATALOG_FILE,
        das_clusters_gpkg=DAS_CLUSTERS_GPKG,
        bws_structures_gpkg=BWS_LEVEES_GPKG,
        bws_gauges_gpkg=BWS_GAUGES_GPKG,
        force_overwrite=True,
    )
"""))

# Cell 8: Markdown - Step 3
cells.append(nbf.v4.new_markdown_cell("""---
## 3. Step 2 — Apply Direct Rainfall-on-Grid Forcing

Applies the hourly gridded NetCDF precipitation arrays (`rainfall_<rp>.nc`) across all 2D computational cells of the optimized domain.
"""))

# Cell 9: Code - Rainfall Forcing
cells.append(nbf.v4.new_code_cell("""for das_id in SELECTED_CLUSTERS:
    print(f"\\n==================== [{das_id}] PREPARING FORCINGS FOR {SELECTED_RPS} ====================")
    prepare_sfincs_direct_rain_forcing(
        das_id=das_id,
        return_periods=SELECTED_RPS,
        base_model_dir=OUTPUT_MODELS_DIR,
        data_catalog_fn=DATA_CATALOG_FILE,
        bws_inflow_hydrographs=BWS_INFLOW_HYDROGRAPHS,
    )
"""))

# Cell 10: Markdown - Step 4
cells.append(nbf.v4.new_markdown_cell("""---
## 4. Step 3 — Run SFINCS Hydrodynamic Simulation Engine

Executes the 2D hydrodynamic solver (automatic detection of native Windows `sfincs.exe` or `deltares/sfincs-cpu` Docker).
"""))

# Cell 11: Code - Run SFINCS
cells.append(nbf.v4.new_code_cell("""for das_id in SELECTED_CLUSTERS:
    for rp in SELECTED_RPS:
        print(f"\\n==================== [{das_id}][{rp}] EXECUTING HYDRODYNAMIC SIMULATION ====================")
        run_sfincs_model(
            das_id=das_id,
            rp=rp,
            base_model_dir=OUTPUT_MODELS_DIR,
        )
"""))

# Cell 12: Markdown - Step 5
cells.append(nbf.v4.new_markdown_cell("""---
## 5. Step 4 — Downscale Depth to 10m, Compute Fuzzy Large Index & BNPB Classification

Downscales SFINCS water levels to high-resolution FABDEM (10m), calculates the **Flood Hazard Index (0-1)** via **Fuzzy Large Membership** (Midpoint: `1.125`, Spread: `1.75`), and classifies into **BNPB Perka No. 2/2012** hazard levels (`Low <= 0.333`, `Medium 0.333 - 0.666`, `High > 0.666`).
"""))

# Cell 13: Code - Post-processing
cells.append(nbf.v4.new_code_cell("""for das_id in SELECTED_CLUSTERS:
    for rp in SELECTED_RPS:
        print(f"\\n==================== [{das_id}][{rp}] POST-PROCESSING & BNPB CLASSIFICATION ====================")
        postprocess_sfincs_hazard(
            das_id=das_id,
            rp=rp,
            base_model_dir=OUTPUT_MODELS_DIR,
            output_maps_dir=OUTPUT_MAPS_DIR,
            hmin=0.05,
        )
"""))

# Cell 14: Markdown - Step 6
cells.append(nbf.v4.new_markdown_cell("""---
## 6. Step 5 — Quick GIS Visualization & QA/QC (3-Panel Map)

Renders the 10m flood inundation depth raster, continuous Fuzzy Large Flood Hazard Index (0-1), and Perka BNPB hazard classification for visual verification.
"""))

# Cell 15: Code - Visualization
cells.append(nbf.v4.new_code_cell("""import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import rasterio
import numpy as np
from pathlib import Path

# Select which completed run to inspect
PLOT_DAS = SELECTED_CLUSTERS[0]
PLOT_RP = SELECTED_RPS[0]

depth_path = Path(OUTPUT_MAPS_DIR) / PLOT_DAS / PLOT_RP / "flood_depth_10m.tif"
fhi_path = Path(OUTPUT_MAPS_DIR) / PLOT_DAS / PLOT_RP / "flood_hazard_index.tif"
hazard_path = Path(OUTPUT_MAPS_DIR) / PLOT_DAS / PLOT_RP / "hazard_class_perka2012.tif"

if depth_path.exists():
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(22, 7), dpi=150)
    
    # 1. Flood Inundation Depth Map (10m FABDEM Downscaled)
    with rasterio.open(depth_path) as src_d:
        depth_data = src_d.read(1)
        depth_masked = np.where(depth_data < 0.05, np.nan, depth_data)
        im1 = ax1.imshow(depth_masked, cmap="Blues", vmin=0, vmax=3.0)
        plt.colorbar(im1, ax=ax1, label="Inundation Depth (m)", fraction=0.046, pad=0.04)
        ax1.set_title(f"[{PLOT_DAS}][{PLOT_RP}] 10m SFINCS Flood Depth", fontsize=11, fontweight="bold")
        ax1.axis("off")
        
    # 2. Continuous Flood Hazard Index (Fuzzy Large: 0 to 1)
    if fhi_path.exists():
        with rasterio.open(fhi_path) as src_f:
            fhi_data = src_f.read(1)
            im2 = ax2.imshow(fhi_data, cmap="YlOrRd", vmin=0.0, vmax=1.0)
            plt.colorbar(im2, ax=ax2, label="Hazard Index (0 - 1)", fraction=0.046, pad=0.04)
            ax2.set_title(f"[{PLOT_DAS}][{PLOT_RP}] Fuzzy Large Hazard Index\\n(Midpoint: 1.125, Spread: 1.75)", fontsize=11, fontweight="bold")
            ax2.axis("off")
            
    # 3. Perka BNPB No. 2/2012 Hazard Classification Map (Low, Medium, High)
    if hazard_path.exists():
        with rasterio.open(hazard_path) as src_h:
            hazard_data = src_h.read(1)
            hazard_masked = np.where(hazard_data == 0, np.nan, hazard_data)
            cmap_bnpb = ListedColormap(["#FFFF00", "#FFA500", "#FF0000"])  # Rendah (Yellow), Sedang (Orange), Tinggi (Red)
            norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5], cmap_bnpb.N)
            im3 = ax3.imshow(hazard_masked, cmap=cmap_bnpb, norm=norm)
            cbar = plt.colorbar(im3, ax=ax3, ticks=[1, 2, 3], fraction=0.046, pad=0.04)
            cbar.ax.set_yticklabels(["Rendah (FHI <= 0.333)", "Sedang (0.333 - 0.666)", "Tinggi (FHI > 0.666)"])
            ax3.set_title(f"[{PLOT_DAS}][{PLOT_RP}] BNPB Hazard Level\\n(Perka BNPB No. 2/2012)", fontsize=11, fontweight="bold")
            ax3.axis("off")
            
    plt.suptitle(f"SFINCS Flood Hazard Assessment: {PLOT_DAS} ({PLOT_RP.upper()})\\nUsing Optimized Smaller DAS Cluster Boundary", fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout()
    plt.show()
else:
    print(f"Output not found yet: {depth_path}. Please execute Steps 1-4 first.")
"""))

# Cell 16: Markdown - Step 7
cells.append(nbf.v4.new_markdown_cell("""---
## 7. Step 6 — 24-Hour Flood Wave Propagation Animation

Extracts dynamic hourly water level slices ($t=1\\text{h}, 2\\text{h}, \\dots, 24\\text{h}$) from `sfincs_map.nc`, overlays transient flood depths over the terrain elevation model, and compiles a high-resolution looping animated GIF (`flood_propagation_24h.gif`).
"""))

# Cell 17: Code - Animation Generation
cells.append(nbf.v4.new_code_cell("""from IPython.display import Image, display

for das_id in SELECTED_CLUSTERS:
    for rp in SELECTED_RPS:
        print(f"\\n==================== [{das_id}][{rp}] GENERATING FLOOD PROPAGATION ANIMATION ====================")
        anim_path = create_sfincs_flood_animation(
            das_id=das_id,
            rp=rp,
            base_model_dir=OUTPUT_MODELS_DIR,
            output_maps_dir=OUTPUT_MAPS_DIR,
            das_clusters_gpkg=DAS_CLUSTERS_GPKG,
            kecamatan_gpkg="data/boundary_kecamatan.gpkg",
            kabkot_gpkg="data/boundary_kabkot.gpkg",
            lake_gpkg="data/lake.gpkg",
            fps=2,
            hmin=0.05,
            vmax=3.0,
        )
        display(Image(filename=anim_path))
"""))

nb.cells = cells
notebook_path = Path("02_sfincs_flood_hazard_run.ipynb")
with open(notebook_path, "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print(f"Successfully created: {notebook_path.resolve()}")
