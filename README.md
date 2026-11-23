# Sumatera Barat Flood Hazard Mapping

Regional-scale 2D hydrodynamic flood hazard modeling pipeline for **17 clustered watershed basins** (`DAS_101`–`DAS_114`, with Mentawai disaggregated into `DAS_108_A`–`D`) across Sumatera Barat, generating flood depth, flood extent, Perka BNPB No. 02/2012 hazard classifications, continuous Flood Hazard Index (FHI), automated QA reports, and flood wave propagation animations for 6 return periods (`RP2`, `RP5`, `RP10`, `RP25`, `RP50`, and `RP100`).

---

## Modeling Approach: HydroMT-SFINCS National v2.0 Standard (Deltares)

This repository implements a **National Indonesian *Kabupaten*-Ready Standalone Direct Rainfall-on-Grid 2D Hydrodynamic Pipeline** using **Deltares SFINCS** (*Super-Fast INundation of CoastS*, v2.4.0 Galibier Release) via **HydroMT `0.10.1`** and **`hydromt-sfincs 1.2.2`**:

* **Indonesian Auto-UTM Portability**: Automatic WGS 84 UTM zone detection across all Indonesian zones (`EPSG:32646–32654` North / `EPSG:32746–32754` South via `scripts/geo_utils.py`) and canonical 15-class BIG RBI parameterization (`lookup_tables/national_rbi_lookup.csv`).
* **Strict Active Watershed Masking**: Computational cells are strictly masked to the hydrological catchment polygon (`mask: das_region`, `reset_mask: true`) so open ocean and adjacent basins remain inactive (`msk=0`), cutting active cell counts by 40%–70% and enabling proper inland outflow boundaries (`msk=3`).
* **Subgrid Topography & On-the-Fly DEM Chipping**: Defaults to the **80 m flux mesh / 10 m subgrid V3 standard** (`configs/sfincs_standalone_build_80m_fast.yml`, `nr_subgrid_pixels: 8`, ~13× faster solver with `F1 = 0.91`, `r = 0.95` vs. `40 m`), with **40 m flux mesh / 10 m subgrid** (`configs/sfincs_standalone_build.yml`, `nr_subgrid_pixels: 4`) available for high-priority urban basins. Per-DAS elevation chips are extracted and bilinearly reprojected on-the-fly via GDAL `WarpedVRT` directly from native **30 m bare-earth FABDEM** (`data_raw/fabdem/FABDEM30m_Sumbar.tif`).
* **Dynamic-Recession Direct Rainfall Forcing**: 24-hour design storm hyetographs padded with explicit zero-intensity recession hours scaled dynamically by catchment area (`24 h` for `< 500 km²`, `36 h` for `500–1,500 km²`, `48 h` for `> 1,500 km²`), optional WMO/USWB Areal Reduction Factor (`apply_arf=False` by default), automated volume conservation ($\pm 1\%$), and numerical tuning (`alpha=0.65`, `huthresh=0.02`, `viscosity=0`).
* **Modern USDA-NRCS Curve Number Infiltration (`CNB`)**: Uses SFINCS `v2.4.0+` Curve Number with Recovery (`smaxfile`, `sefffile`, `ksfile` in meters) derived from **Kementan Soil HSG × BIG RBI Land Cover** (`scripts/generate_cn_raster.py`, `AMC-II` 25% pre-filled for `RP2–RP10` and `AMC-III` 50% pre-filled for `RP25–RP100`), avoiding the broken legacy `scsfile` binary path in SFINCS `v2.4.0`.
* **Distributed Manning Roughness**: Spatially distributed surface friction derived from 30 m integer-coded BIG RBI Land Cover (`data/landcover_rbi.tif` + `lookup_tables/manning_lookup.csv`) following Chow (1959) and Arcement & Schneider (1989).
* **Silted/Aggraded River Channel Burning**: Mapped RBI stream centerlines enhanced with BIG RBI polygon river widths (`data/rivers_ar.gpkg`) burned into subgrid hypsometry (`datasets_riv`) using calibrated silted Indonesian alluvial geometry ($w = 8 / 15 / 22\text{ m}$ fallback, $d = 0.35 / 0.55 / 0.80\text{ m}$, Manning $n = 0.045$).
* **Dual Boundary Conditioning & Coastal MHHW**: Coastal waterlevel boundaries (`msk=2`, $z \le 0$) forced with **Mean Higher High Water (MHHW `+0.80 m`)** tidal backwater via native `sfincs.bnd`/`sfincs.bzs`, paired with inland outflow boundaries (`msk=3`) snapped to lowest-elevation catchment outlets.
* **Option B (80 m V3) Natural Hydrostatic Post-Processing & BNPB Standards**: Bilinear water-surface downscaling with **hydrologically connected edge-NaN recovery and a conservative `+0.35 m` FABDEM vertical uncertainty margin** (Hawker et al., 2022 `< 0.50 m` MAE; strictly gated to connected flat floodplains `< 5°` within `≤ 120 m = 1.5 × dx`, decaying smoothly to `0 m`; use `0.25 m / 80 m / r=5` on 40 m runs), RBI river corridor protection, **4-connected `30 m × 30 m` (`0.09 ha`) pinhole & speck cleanup** (`island_mmu_ha=0.09`, `min_hole_ha=0.09`, `hole_mmu_ha=2.0`, `bridge_radius=6`), Euclidean signed-distance anti-aliasing ($\sigma = 1.2\text{ px}$), continuous Fuzzy Large FHI, Perka BNPB No. 02/2012 classification, **subgrid hypsometric volume QA** (`qa_report.json`), and outlier-screened QField survey validation (`survey_validation.json`).

> **Upstream Roadmap (v3.0 Quadtree Upgrade):** When upgrading from HydroMT `0.10.1` / `hydromt-sfincs 1.2.2` / SFINCS `v2.4.0` to **HydroMT `v1.4+` / `hydromt-sfincs v2.0+` / SFINCS `v2.5.0 Hautacam`**, replace the regular `40 m` mesh with native **Quadtree adaptive refinement** (`20–40 m` along rivers/floodplains + `80–160 m` on steep mountains) and NetCDF `inffile` (`inftype = cnb`) to retain `40 m` lowland accuracy at `80 m` solver speed across all 514 Indonesian *Kabupaten/Kota*.

---

## Repository Structure

```text
sumbar_flood_hazard/
├── .agents/                                  # Workspace AI skills & environment rules
├── configs/                                  # HydroMT-SFINCS model build configurations
│   ├── sfincs_standalone_build.yml           # Standard 40 m flux mesh / 10 m subgrid (silted rivers)
│   └── sfincs_standalone_build_80m_fast.yml  # High-speed 80 m flux mesh / 10 m subgrid
├── docs/                                     # Technical documentation & guides
│   ├── README.md                             # Documentation index
│   ├── WINDOWS_INSTALLATION_GUIDE.md         # Local Windows setup guide (uv sync)
│   ├── PIPELINE.md                           # Hydrodynamic formulation & architecture
│   ├── TUTORIAL.md                           # Step-by-step execution guide
│   ├── BWS_DATA_CONTRACT.md                  # Specifications for BWS levees/gauges/inflows
│   └── REMEDIATION_REPORT.md                 # Historical engineering audit log
├── env/                                      # Environment provisioning scripts
│   ├── requirements.txt
│   └── setup_env.ps1
├── lookup_tables/                            # Physical parameter lookup matrices
│   ├── national_rbi_lookup.csv               # Canonical 15-class Indonesian BIG RBI Manning & CN table
│   ├── manning_lookup.csv                    # RBI integer class -> Manning's n
│   └── soil_infiltration_lookup.csv          # Kementan soil x RBI land cover -> qinf (mm/hr)
├── notebook/
│   └── master/                               # Core master workflows
│       ├── 00_data_preparation.ipynb
│       └── 01_sfincs_flood_hazard_run.ipynb
├── scripts/                                  # Core Python modeling & QA engine
│   ├── _env.py                               # Centralized PROJ/GDAL/DLL loader
│   ├── geo_utils.py                          # Indonesian Auto-UTM, dynamic recession, WMO ARF & RBI canonicalizer
│   ├── sfincs_standalone_pipeline.py         # End-to-end build, CNB/MHHW force, run & Option B post-process engine
│   ├── perka_bnpb_classification.py          # Perka BNPB No. 02/2012 classifier & QML generator
│   ├── qa_checks.py                          # Roughness, mask, depth peak-timing & subgrid hypsometric volume QA
│   ├── validate_against_survey.py            # Outlier-screened QField ground-truth validation
│   ├── generate_landcover_raster.py          # BIG RBI vector -> 30 m integer raster + Manning CSV (Auto-UTM)
│   ├── generate_cn_raster.py                 # Kementan HSG x RBI -> 100 m USDA-NRCS CN (AMC-II & AMC-III)
│   ├── generate_soil_infiltration_raster.py  # Kementan x RBI -> 100 m constant-loss fallback raster (Auto-UTM)
│   ├── clean_storage.py                      # Safe workspace & geospatial cache cleaner
│   └── ...
├── tests/                                    # Automated pytest unit test suite (55 tests)
├── tools/                                    # GIS helper notebooks (clustering, hillshade, clipping)
├── data_catalog_sfincs.yml                   # HydroMT 0.10.1 / hydromt_sfincs 1.2.2 data catalog
├── Field Survey.qgz                          # QGIS/QField validation project
├── pyproject.toml                            # Pinned uv project specification
├── uv.lock                                   # Locked reproducible dependency tree
└── README.md
```

---

## Data Storage & Execution

* **Code, Configs, Tests & Master Notebooks**: Version-controlled in Git.
* **Spatial Datasets (Local / Shared Drive)**: Heavy spatial inputs (native 30 m `FABDEM30m_Sumbar.tif`, RBI vectors, Kementan soil polygons, NetCDF rainfall, and SFINCS outputs) are excluded via `.gitignore` and stored locally under `data_raw/`, `data/`, `models_sfincs_standalone/`, and `outputs/`.

---

## Quickstart

### Windows (Local — Recommended)
See the step-by-step setup in [`docs/WINDOWS_INSTALLATION_GUIDE.md`](docs/WINDOWS_INSTALLATION_GUIDE.md).

```powershell
# 1. Provision unified virtual environment (.venv) from pyproject.toml + uv.lock
uv sync --extra dev

# 2. Register Jupyter kernel
.\.venv\Scripts\python.exe -m ipykernel install --user --name hydromt-sfincs --display-name "HydroMT-SFINCS"

# 3. Verify installation & run unit tests
.\.venv\Scripts\python.exe -m pytest
```

### Google Colab (Cloud)
```python
# 1. Install pinned versions compatible with this repository
!pip install -q uv
!uv pip install --system hydromt==0.10.1 hydromt-sfincs==1.2.2 geopandas rasterio rioxarray netcdf4 matplotlib

# 2. Mount Google Drive for spatial data & outputs
from google.colab import drive
drive.mount('/content/drive')
```

---

## Scientifically Grounded Parameter Matrix (Tier 1 & Tier 2)

All model parameters are partitioned into **Tier 1 (Upstream Physics & Hydrodynamic Build)** and **Tier 2 (Downstream Post-Processing & Cartography)**:

| Parameter | Tier | Current Pipeline Value | Units / Scale | Physical / Cartographic Role | Authoritative Scientific Reference & Regulatory Standard |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **Curve Number Infiltration (`CNB`)** | Tier 1 | `smaxfile`/`sefffile`/`ksfile` (`AMC-II` 25% sat for RP2–10; `AMC-III` 50% sat for RP25–100) | $\text{meters}$ ($100\text{ m}$ CN grid) | Physically bounded USDA-NRCS Curve Number loss from Kementan Soil HSG × BIG RBI Land Cover (`generate_cn_raster.py`). | **USDA-NRCS NEH Part 630** (2004); **Arsyad (2010)**; **BBSDLP** |
| **Bankfull River Depth (`rivdph`)** | Tier 1 | `0.55` fallback (Trunk: `0.80`; Secondary: `0.55`; Headwater: `0.35`) | $\text{meters}$ | Silted/aggraded Indonesian channel depth preventing artificial trench water trapping. | **Leopold & Maddock (1953)**; **Suripin (2004)** |
| **Bankfull River Width (`rivwth`)** | Tier 1 | `15.0` fallback (Trunk: `22.0`; Secondary: `15.0`; Headwater: `8.0`; enhanced via `rivers_ar.gpkg`) | $\text{meters}$ | Defines burned subgrid channel cross-sectional width from RBI polygons + centerlines. | **Leopold & Maddock (1953)** |
| **River Channel Manning ($n$)** | Tier 1 | `0.045` | $\text{s/m}^{1/3}$ | Aggraded/vegetated Indonesian alluvial river channel resistance. | **SNI 2830:2008**; **KP-03 (2013)**; **Chow (1959)** |
| **Coastal Tailwater (`coastal_mhhw_m`)** | Tier 1 | `+0.80` (`sfincs.bnd` / `sfincs.bzs` on coastal `msk=2` cells) | $\text{meters}$ above MSL | Represents Mean Higher High Water (MHHW) spring-tide backwater at coastal river mouths. | **Leijnse et al. (2021)** |
| **Floodplain Manning ($n$)** | Tier 1 | Settlement: `0.120`; Shrub: `0.070`; Forest: `0.120`; Paddy: `0.040` | $\text{s/m}^{1/3}$ | Spatially distributed surface friction from BIG RBI Land Cover (`lookup_tables/manning_lookup.csv` & `national_rbi_lookup.csv`). | **Chow (1959)**; **Arcement & Schneider (1989)** |
| **Solver Numerics (`alpha`, `huthresh`, `viscosity`)** | Tier 1 | `alpha=0.65`, `huthresh=0.02 m`, `viscosity=0`, dynamic recession (`24–48 h`) | — | Stabilizes CFL time-stepping, speeds up solver, and guarantees full hydrograph recession. | **Leijnse et al. (2021)** (Deltares SFINCS) |
| **Minimum Inundation Cutoff ($h_{\text{min}}$)** | Tier 2 | `0.05` | $\text{meters}$ ($5\text{ cm}$) | Physical wet-dry threshold separating nuisance sheet runoff from hazard inundation. | **Leijnse et al. (2021)**; **Perka BNPB No. 02/2012** |
| **Natural Floodplain Margin (80 m V3)** | Tier 2 | `freeboard_m=0.35`, `max_ext_dist_m=120.0`, `max_ext_slope_deg=5.0` *(40 m preset: `0.25 / 80.0`)* | $\text{m}$, $\text{m}$, $\text{deg}$ | Hydrologically connected bilinear edge-NaN recovery (`1.5 × dx`) + decaying FABDEM vertical uncertainty margin on flat plains (`< 5°`); steep hills stay dry. | **Hawker et al. (2022)** (*ERL* FABDEM MAE ~0.50 m) |
| **4-Connected Feature Floor (`island_mmu_ha` / `min_hole_ha`)** | Tier 2 | `0.09` (`30 m × 30 m` = `9 px` @ 10 m, 1 native FABDEM pixel) | $\text{hectares}$ | 4-connected cleanup eliminating all sub-DEM pinholes and scattered specks `< 30×30 m`. | **Peraturan BIG No. 18/2021**; **SNI 6502.3:2010** |
| **Hole MMU (`hole_mmu_ha`)** | Tier 2 | `2.00` (auto-scaled to pixels: `200 px` @ 10 m) | $\text{hectares}$ | Bridges enclosed flat voids **strictly where $z_s + \Delta z > z_{\text{DEM}}$**; elevated dry hills remain dry. | **SNI 6502.3:2010**; **Perka BNPB No. 02/2012** |
| **Morphological Closing (`bridge_radius`)** | Tier 2 | `6` (`60 m` @ 10 m grid; `5` on 40 m preset) | pixels | Bridges coarse-DEM road/bund gaps strictly where hydrostatically submerged. | **Soille (2003)** (mathematical morphology) |
| **Boundary Anti-Aliasing (`smooth_sigma`)** | Tier 2 | `1.2` | pixels | Eliminates raster staircase artifacts using Euclidean signed distance fields. | **Borgefors (1986)**; **Soille (2003)** |
| **Fuzzy Large Hazard Index ($x_0, s$)** | Tier 2 | Midpoint: `1.125`, Spread: `1.75` | $\text{meters}$ | Maps physical depth into a continuous flood hazard index ($FHI \in [0, 1]$). | **Klir & Yuan (1995)**; **Perka BNPB No. 02/2012** |

---

## Bibliography & Regulatory Framework

Every reference below is verified and directly underpins a specific numerical, physical, cartographic, or statutory component implemented in this repository:

### 1. 2D Hydrodynamic Modeling, Subgrid Numerics & Bare-Earth DEM
* **Leijnse, T., van Ormondt, M., Nederhoff, K., & van Dongeren, A. (2021).** *Modeling compound flooding in coastal systems using a computationally efficient reduced-physics solver: Including fluvial, pluvial, tidal, wind- and wave-driven processes.* **Coastal Engineering**, 163, 103796. [https://doi.org/10.1016/j.coastaleng.2020.103796](https://doi.org/10.1016/j.coastaleng.2020.103796) — *(Foundational formulation of Deltares SFINCS governing equations, subgrid tables, and compound flood routing).*
* **Eilander, D., Boisgontier, H., Bouaziz, L. J. E., Buitink, J., Couasnon, A., Dalmijn, B., Hegnauer, M., de Jong, T., Loos, S., Marth, I., & van Verseveld, W. (2023).** *HydroMT: Automated and reproducible model building and analysis.* **Journal of Open Source Software**, 8(83), 4897. [https://doi.org/10.21105/joss.04897](https://doi.org/10.21105/joss.04897) — *(Automated HydroMT model builder and data catalog framework).*
* **Eilander, D., Couasnon, A., Leijnse, T., Ikeuchi, H., Yamazaki, D., Muis, S., Dullaart, J., Haag, A., Winsemius, H. C., & Ward, P. J. (2023).** *A globally applicable framework for compound flood hazard modeling.* **Natural Hazards and Earth System Sciences**, 23(2), 823–846. [https://doi.org/10.5194/nhess-23-823-2023](https://doi.org/10.5194/nhess-23-823-2023) — *(HydroMT-SFINCS automated regional flood hazard workflow).*
* **Volp, N. D., van Prooijen, B. C., & Stelling, G. S. (2013).** *A finite volume approach for shallow water flow accounting for high-resolution bathymetry and roughness data.* **Water Resources Research**, 49(7), 4126–4135. [https://doi.org/10.1002/wrcr.20315](https://doi.org/10.1002/wrcr.20315) — *(Mathematical basis of 2D subgrid elevation-volume and roughness integration).*
* **Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C., & Neal, J. (2022).** *A 30m global map of elevation with forests and buildings removed.* **Environmental Research Letters**, 17(2), 024016. [https://doi.org/10.1088/1748-9326/ac4d4f](https://doi.org/10.1088/1748-9326/ac4d4f) — *(Bare-earth FABDEM 30 m elevation source dataset used in this pipeline).*
* **Saksena, S., & Merwade, V. (2015).** *Incorporating the effect of DEM resolution and accuracy for improved flood inundation mapping.* **Journal of Hydrology**, 530, 180–194. [https://doi.org/10.1016/j.jhydrol.2015.09.069](https://doi.org/10.1016/j.jhydrol.2015.09.069) — *(Sensitivity of 2D flood inundation mapping to DEM spatial resolution).*

### 2. Fluvial Hydraulics, Channel Geometry & Surface Roughness
* **Leopold, L. B., & Maddock, T. (1953).** *The Hydraulic Geometry of Stream Channels and Some Physiographic Implications.* **U.S. Geological Survey Professional Paper 252**, Washington, D.C. [https://doi.org/10.3133/pp252](https://doi.org/10.3133/pp252) — *(Empirical basis for scaling bankfull width and depth for subgrid river burning).*
* **Chow, V. T. (1959).** *Open-Channel Hydraulics.* McGraw-Hill, New York — *(Reference Manning's roughness $n$ coefficients for channels and floodplains).*
* **Arcement, G. J., & Schneider, V. R. (1989).** *Guide for Selecting Manning's Roughness Coefficients for Natural Channels and Flood Plains.* **U.S. Geological Survey Water-Supply Paper 2339**, Reston, VA. [https://doi.org/10.3133/wsp2339](https://doi.org/10.3133/wsp2339) — *(Composite floodplain and vegetated roughness parameterization).*
* **Suripin. (2004).** *Sistem Drainase Perkotaan yang Berkelanjutan.* ANDI Offset, Yogyakarta — *(Indonesian urban drainage and channel conveyance reference).*
* **Standar Nasional Indonesia (SNI) 2830:2008.** *Tata cara perhitungan tinggi muka air sungai dengan cara pias berdasarkan rumus Manning.* Badan Standardisasi Nasional (BSN), Jakarta.
* **Direktorat Jenderal Sumber Daya Air. (2013).** *Kriteria Perencanaan Bagian Saluran (KP-03).* Standar Perencanaan Irigasi, Kementerian Pekerjaan Umum dan Perumahan Rakyat, Jakarta.

### 3. Tropical Soil Infiltration & Antecedent Moisture (AMC-III)
* **USDA Natural Resources Conservation Service. (2004).** *National Engineering Handbook (NEH), Part 630: Hydrology, Chapter 10: Estimation of Direct Runoff from Storm Rainfall.* USDA-NRCS, Washington, D.C. — *(Hydrologic Soil Groups A–D and Antecedent Moisture Condition III definition).*
* **Arsyad, S. (2010).** *Konservasi Tanah dan Air* (Edisi Kedua). IPB Press, Bogor — *(Indonesian tropical soil infiltration capacity reference).*
* **Triatmodjo, B. (2008).** *Hidrologi Terapan.* Beta Offset, Yogyakarta — *(Indonesian watershed hydrology and rainfall-runoff loss reference).*
* **Balai Besar Penelitian dan Pengembangan Sumberdaya Lahan Pertanian (BBSDLP), Kementerian Pertanian.** *Peta Tekstur Tanah Skala 1:50.000 Provinsi Sumatera Barat.* Kementerian Pertanian Republik Indonesia — *(Authoritative soil texture input layer).*

### 4. Post-Processing Morphology, Cartography & Indonesian Statutory Standards
* **Soille, P. (2003).** *Morphological Image Analysis: Principles and Applications* (2nd ed.). Springer-Verlag, Berlin, Heidelberg. [https://doi.org/10.1007/978-3-662-05088-0](https://doi.org/10.1007/978-3-662-05088-0) — *(Circular morphological closing and connected-component MMU filtering).*
* **Borgefors, G. (1986).** *Distance transformations in digital images.* **Computer Vision, Graphics, and Image Processing**, 34(3), 344–371. [https://doi.org/10.1016/S0734-189X(86)80047-0](https://doi.org/10.1016/S0734-189X(86)80047-0) — *(Euclidean Distance Transform used for signed-distance boundary anti-aliasing).*
* **Klir, G. J., & Yuan, B. (1995).** *Fuzzy Sets and Fuzzy Logic: Theory and Applications.* Prentice Hall, Upper Saddle River, NJ — *(Fuzzy Large membership formulation for continuous FHI scaling).*
* **Peraturan Kepala BNPB No. 02 Tahun 2012.** *Pedoman Umum Pengkajian Risiko Bencana.* Badan Nasional Penanggulangan Bencana (BNPB), Jakarta — *(Statutory 3-tier flood hazard depth classification: Rendah, Sedang, Tinggi).*
* **Standar Nasional Indonesia (SNI) 6502.3:2010.** *Spesifikasi penyajian peta rupabumi – Bagian 3: Skala 1:50.000.* Badan Standardisasi Nasional (BSN), Jakarta — *(1:50,000 cartographic presentation standard).*
* **Peraturan Badan Informasi Geospasial (BIG) No. 18 Tahun 2021.** *Tata Cara Penyelenggaraan Informasi Geospasial.* Badan Informasi Geospasial, Cibinong — *(Supersedes Perka BIG No. 1 Tahun 2020).*
* **Undang-Undang Republik Indonesia No. 24 Tahun 2007** *(tentang Penanggulangan Bencana)* & **Undang-Undang Republik Indonesia No. 4 Tahun 2011** *(tentang Informasi Geospasial)*.
