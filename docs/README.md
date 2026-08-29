# Sumatera Barat Flood Hazard Pipeline — Standalone HydroMT-SFINCS

High-resolution 2D hydrodynamic flood hazard modeling pipeline for 13 clustered watersheds (DAS clusters) across Sumatera Barat, generating flood depth, flood extent, BNPB hazard classifications, and propagation animations for 6 return periods (2, 5, 10, 25, 50, and 100 years).

---

## 🎯 Modeling Approach: Standalone HydroMT-SFINCS

This project utilizes **Deltares SFINCS** (*Super-Fast INundation of CoastS and riverS*) in **Standalone Direct Rainfall-on-Grid Mode**:
* **Subgrid Topography**: Downscaled to 10 m FABDEM elevation with 40 m flux routing cells.
* **Direct Rain Forcing**: 24-hour design storm hyetographs applied directly over all active basin cells.
* **Calibrated Soil Infiltration**: 2D physical matrix coupling official Ministry of Agriculture (*Kementerian Pertanian*) Soil Texture with BIG RBI Land Cover ($q_{\text{inf}} \in [0.05, 3.50]\text{ mm/hr}$).
* **Manning Roughness**: Distributed surface roughness mapped from BIG RBI Land Cover classes.
* **River Flow Routing**: Integrated with BIG RBI river channels (`rivers.gpkg`).
* **Hazard Post-Processing**: Automated downscaling, Continuous Flood Hazard Index (FHI), and official Perka BNPB No. 2 Tahun 2012 hazard classification (Rendah, Sedang, Tinggi).
* **Visualization**: 5-layer animated satellite GIFs and interactive Folium maps.

---

## 📂 Repository Structure

```
sumbar_flood_hazard/
├── bin/                              # Native Windows 64-bit SFINCS v2.4.0 Galibier Release & DLLs
├── configs/                          # Model build configuration YAML
│   └── sfincs_standalone_build.yml
├── data/                             # Processed spatial layers (FABDEM, rivers, landcover, soil)
│   ├── soil_infiltration_100m.tif    # 100m Kementan soil infiltration raster
│   ├── landcover_100m.tif            # 100m RBI land cover raster
│   ├── rivers.gpkg                   # RBI river network (EPSG:32747)
│   ├── das_clusters.gpkg             # 13 clustered watershed polygons
│   └── rainfall/                     # 24h design storm NetCDFs (RP2 to RP100)
├── data_raw/                         # Original raw data archives
├── docs/                             # Engineering documentation and data contracts
│   ├── PIPELINE.md                   # Full technical architecture & hydrodynamics reference
│   └── BWS_DATA_CONTRACT.md          # Specifications for BWS structures and AWLR gauges
├── lookup_tables/                    # Physical parameter lookup matrices
│   ├── manning_lookup.csv            # Land cover -> Manning's n
│   └── soil_infiltration_lookup.csv  # Soil texture x Land cover -> Infiltration (mm/hr)
├── models_sfincs_standalone/         # Built SFINCS model instances per DAS and return period
├── outputs_standalone/               # Final flood hazard maps, FHI rasters, and animations
├── qc_reports/                       # QA/QC logs and validation summaries
├── scripts/                          # Core Python modeling engine
│   ├── sfincs_standalone_pipeline.py # End-to-end automation pipeline
│   ├── perka_bnpb_classification.py  # BNPB hazard classification logic
│   └── generate_soil_infiltration_raster.py # Infiltration raster synthesis
├── 00_data_preparation.ipynb        # Stage 0: Data preparation & QA/QC
├── 01_sfincs_flood_hazard_run.ipynb  # Master batch execution notebook (13 DAS x 6 RP)
├── Flood_Hazard_DAS101_RP100.ipynb   # Single-DAS prototype notebook (DAS_101, RP100)
├── Flood_Hazard_DAS102_RP100.ipynb   # Single-DAS prototype notebook (DAS_102, RP100)
├── data_catalog_sfincs.yml           # HydroMT v1.x data catalog
└── docs/                             # Engineering documentation
    ├── README.md                     # Project overview
    ├── TUTORIAL.md                   # Step-by-step tutorial guide
    ├── WINDOWS_INSTALLATION_GUIDE.md # 6-Step setup guide for team members
    ├── PIPELINE.md                   # Full technical architecture & hydrodynamics reference
    └── BWS_DATA_CONTRACT.md          # Specifications for BWS structures and AWLR gauges
```

---

## ⚡ Quick Start

### 1. Environment Setup
Create and activate the dedicated HydroMT-SFINCS environment:
```powershell
powershell -ExecutionPolicy Bypass -File .\env\setup_env.ps1
```

### 2. Run the Workflow
1. **Data Prep**: Run [`00_data_preparation.ipynb`](../00_data_preparation.ipynb) to reproject FABDEM, synthesize Manning roughness, and generate the Kementan soil infiltration raster.
2. **Prototype Simulation**: Open [`Flood_Hazard_DAS101_RP100.ipynb`](../Flood_Hazard_DAS101_RP100.ipynb) (or [`Flood_Hazard_DAS102_RP100.ipynb`](../Flood_Hazard_DAS102_RP100.ipynb)) to run Steps 1 through 6 for a single basin cluster.
3. **Batch Production**: Open [`01_sfincs_flood_hazard_run.ipynb`](../01_sfincs_flood_hazard_run.ipynb) to execute the entire matrix (13 DAS clusters $\times$ 6 Return Periods).

---

## 📖 Key Documentation
* [`TUTORIAL.md`](TUTORIAL.md) — Step-by-step practical guide.
* [`WINDOWS_INSTALLATION_GUIDE.md`](WINDOWS_INSTALLATION_GUIDE.md) — Zero-to-hero Windows installation guide for team members.
* [`PIPELINE.md`](PIPELINE.md) — Full hydrodynamic theory, subgrid derivation, and equations.
* [`BWS_DATA_CONTRACT.md`](BWS_DATA_CONTRACT.md) — Integration guide for BWS levees, dikes, and AWLR telemetry stations.
