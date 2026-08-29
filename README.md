# Sumatera Barat Flood Hazard Pipeline — Standalone HydroMT-SFINCS

High-resolution 2D hydrodynamic flood hazard modeling pipeline for 14 clustered watershed basins (DAS clusters) across Sumatera Barat, generating flood depth, flood extent, BNPB hazard classifications, and flood propagation animations for 6 return periods (2, 5, 10, 25, 50, and 100 years).

---

## 🎯 Modeling Approach: Standalone HydroMT-SFINCS

This project utilizes **Deltares SFINCS** (*Super-Fast INundation of CoastS and riverS*) in **Standalone Direct Rainfall-on-Grid Mode**:
* **Subgrid Topography**: Downscaled to 10 m FABDEM elevation with 40 m flux routing cells.
* **Direct Rain Forcing**: 24-hour design storm hyetographs applied directly over active basin cells.
* **Calibrated Soil Infiltration**: 2D physical matrix coupling Ministry of Agriculture (*Kementerian Pertanian*) Soil Texture with BIG RBI Land Cover ($q_{\text{inf}} \in [0.05, 3.50]\text{ mm/hr}$).
* **Manning Roughness**: Distributed surface roughness mapped from BIG RBI Land Cover classes.
* **River Flow Routing**: Integrated with BIG RBI river channels (`rivers.gpkg`).
* **Hazard Post-Processing**: Automated downscaling, Continuous Flood Hazard Index (FHI), and official Perka BNPB No. 2 Tahun 2012 hazard classification (Rendah, Sedang, Tinggi).

---

## 📂 Repository Structure

```text
sumbar_flood_hazard/
├── .agents/                          # Custom AI modeling skills & workflows
├── configs/                          # Model build configuration YAML
│   └── sfincs_standalone_build.yml
├── docs/                             # Engineering documentation & guides
│   ├── WINDOWS_INSTALLATION_GUIDE.md # Setup guide for local Windows environments
│   ├── PIPELINE.md                   # Full technical architecture & hydrodynamics reference
│   ├── TUTORIAL.md                   # Step-by-step modeling guide
│   └── BWS_DATA_CONTRACT.md          # Technical specifications for BWS hydraulic structures
├── lookup_tables/                    # Physical parameter lookup matrices
│   ├── manning_lookup.csv            # Land cover -> Manning's n
│   └── soil_infiltration_lookup.csv  # Soil texture x Land cover -> Infiltration (mm/hr)
├── notebook/
│   ├── master/                       # Core master batch modeling workflows
│   │   ├── 00_data_preparation.ipynb
│   │   ├── 01_sfincs_flood_hazard_run.ipynb
│   │   └── 02_sfincs_flood_hazard_run_opt.ipynb
│   └── sumbar2026/                   # Individual cluster notebooks (DAS_101 to DAS_114)
│       ├── Flood_Hazard_DAS101_RP100.ipynb
│       ├── Flood_Hazard_DAS102_RP100.ipynb
│       ├── Flood_Hazard_DAS103_RP100.ipynb
│       └── Flood_Hazard_DAS103_RP100_opt.ipynb
├── scripts/                          # Python modeling engine & utilities
│   ├── sfincs_standalone_pipeline.py
│   ├── perka_bnpb_classification.py
│   ├── generate_soil_infiltration_raster.py
│   └── ...
├── tools/                            # Spatial optimization & GIS helper tools
│   ├── tools_das_cluster_optimization.ipynb
│   ├── tools_generate_hillshade.ipynb
│   └── tools_vector_clip_reproject_gpkg.ipynb
├── data_catalog_sfincs.yml           # HydroMT v1.x data catalog index
├── Field Survey.qgz                  # QGIS validation & field survey project
├── .gitignore
└── README.md
```

---

## ☁️ Data Storage & Cloud-Native Execution

* **Code & Notebooks**: Maintained in this GitHub repository.
* **Large Spatial Datasets (Google Drive)**: Multi-gigabyte rasters (FABDEM DEM, hillshades, NetCDF rainfall, and simulation outputs) should be placed in your Google Drive or shared cloud storage under `sumbar_flood_hazard/data/`.

---

## ⚡ Quickstart

### Windows (Local)
See the complete 6-step setup in [`docs/WINDOWS_INSTALLATION_GUIDE.md`](docs/WINDOWS_INSTALLATION_GUIDE.md).

```powershell
# 1. Install dependencies via uv
uv venv env-sfincs --python 3.11
.\env-sfincs\Scripts\activate
uv pip install hydromt hydromt_sfincs geopandas rasterio rioxarray netcdf4 ipykernel matplotlib
python -m ipykernel install --user --name hydromt-sfincs --display-name "HydroMT-SFINCS"
```

### Google Colab (Cloud)
```python
# 1. Install uv & dependencies in seconds
!pip install -q uv
!uv pip install --system hydromt hydromt_sfincs geopandas rasterio rioxarray netcdf4 matplotlib

# 2. Mount Google Drive for heavy data & outputs
from google.colab import drive
drive.mount('/content/drive')
```
