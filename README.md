# Sumatera Barat Flood Hazard Pipeline

High-resolution 2D hydrodynamic flood hazard modeling pipeline for 14 clustered watershed basins (DAS clusters) across Sumatera Barat, generating flood depth, flood extent, BNPB hazard classifications, and flood propagation animations for 6 return periods (2, 5, 10, 25, 50, and 100 years).

---

## Modeling Approach: HydroMT-SFINCS by Deltares

This project utilizes **Deltares SFINCS** (*Super-Fast INundation of CoastS and riverS*, v2.4.0 Galibier Release) via **HydroMT 0.10.1** and **hydromt-sfincs 1.2.2** in **Standalone Direct Rainfall-on-Grid Mode**:
* **Subgrid Topography**: 40 m computational flux mesh coupled with 10 m subgrid hypsometry derived from FABDEM (30 m native, bilinearly resampled to 10 m).
* **Extended Direct Rain Forcing**: 24-hour design storm hyetographs padded with 48 hours of zero-intensity recession forcing (72-hour total simulation duration) to capture peak propagation and catchment drainage.
* **Conservative Soil Infiltration**: 2D physical matrix coupling Ministry of Agriculture (*Kementerian Pertanian*) Soil Texture with BIG RBI Land Cover under a conservative constant-loss assumption ($q_{\text{inf}} \in [0.00, 3.50]\text{ mm/hr}$), with optional SCS Curve Number parameterization.
* **Distributed Manning Roughness**: Spatially distributed friction derived from integer-coded BIG RBI Land Cover (`data/landcover_rbi.tif`) following Chow (1959) and Arcement & Schneider (1989).
* **River Channel Bathymetry**: River centerlines burned directly into subgrid hypsometry (`datasets_riv`) parameterized by regional hydraulic geometry power laws ($w = a \cdot A^b, d = c \cdot A^d$, Manning $n = 0.030$).
* **Dual Boundary Conditioning**: Coastal sea-level waterlevel boundary ($z \le 0$) and designated outflow boundaries (`btype: outflow`, `msk=3`) at inland catchment outlets.
* **Physical Hazard Post-Processing**: Automated downscaling, physically grounded depth reconstruction ($z_s - z_{\text{DEM}}$), continuous Flood Hazard Index (FHI), and official Perka BNPB No. 2 Tahun 2012 hazard classification (Rendah, Sedang, Tinggi) with QField survey validation.

---

## Repository Structure

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
│       ├── ...
│       ├── Flood_Hazard_DASXXX_RPXXX.ipynb
├── scripts/                          # Python modeling engine & utilities
│   ├── sfincs_standalone_pipeline.py
│   ├── perka_bnpb_classification.py
│   ├── generate_soil_infiltration_raster.py
│   └── ...
├── tools/                            # Spatial optimization & GIS helper tools
│   ├── tools_das_cluster_optimization.ipynb
│   ├── tools_generate_hillshade.ipynb
│   └── tools_vector_clip_reproject_gpkg.ipynb
├── data_catalog_sfincs.yml           # HydroMT 0.10.1 / hydromt_sfincs 1.2.2 data catalog index
├── Field Survey.qgz                  # QGIS validation & field survey project
├── .gitignore
└── README.md
```

---

## Data Storage & Cloud-Native Execution

* **Code & Notebooks**: Maintained in this GitHub repository.
* **Large Spatial Datasets (Google Drive)**: Multi-gigabyte rasters (FABDEM DEM, hillshades, NetCDF rainfall, and simulation outputs) should be placed in your Google Drive or shared cloud storage under `sumbar_flood_hazard/data/`.

---

## Quickstart

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

---

## Bibliography & Regulatory Framework

This flood hazard modeling pipeline couples peer-reviewed hydrodynamic science with statutory disaster management standards and Indonesian water resources regulations:

### 1. Scientific Literature & Hydrodynamic Modeling

* **Deltares SFINCS (2D Hydrodynamics & Subgrid Modeling)**:
  * Leijnse, T., van Ormondt, M., Nederhoff, K., & van Dongeren, A. (2021). *Coupling of a subgrid technique with a compound flood model for coastal inundation*. **Coastal Engineering**, 163, 103797. [https://doi.org/10.1016/j.coastaleng.2020.103797](https://doi.org/10.1016/j.coastaleng.2020.103797)
  * Sadana, T., Aerts, J. C. J. H., Eilander, D., Merz, B., de Moel, H., Busker, T., Bril, V., & de Bruijn, J. (2025). *Validation of the Open-Source Hydrodynamic Model SFINCS on Historical River Floods at the Global Scale*. **EGUsphere** [Preprint]. [https://doi.org/10.5194/egusphere-2025-4387](https://doi.org/10.5194/egusphere-2025-4387)
  * Eilander, D., Couasnon, A., Leijnse, T., Ikeuchi, H., Yamazaki, D., Muis, S., Dullaart, J., Haag, A., Winsemius, H. C., & Ward, P. J. (2023). *A globally applicable framework for compound flood hazard modeling*. **Natural Hazards and Earth System Sciences**, 23(2), 823–846. [https://doi.org/10.5194/nhess-23-823-2023](https://doi.org/10.5194/nhess-23-823-2023)

* **HydroMT Automated Modeling Framework**:
  * Eilander, D., van Verseveld, W., Stam, J., Winsemius, H., & Deltares HydroMT Contributors. (2023). *HydroMT: Hydro and Earth system Model Tools*. Deltares. [https://deltares.github.io/hydromt/](https://deltares.github.io/hydromt/)

* **High-Resolution Digital Elevation Model (FABDEM)**:
  * Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., & Sampson, C. (2022). *A 30 m globally unified Copernicus DEM-derived digital elevation model removing trees and buildings: FABDEM*. **Geophysical Research Letters**, 49(17), e2022GL099236. [https://doi.org/10.1029/2022GL099236](https://doi.org/10.1029/2022GL099236)

* **Open-Channel Hydraulics & Manning's Roughness**:
  * Chow, V. T. (1959). *Open-Channel Hydraulics*. McGraw-Hill, New York.
  * Arcement, G. J., & Schneider, V. R. (1989). *Guide for Selecting Manning's Roughness Coefficients for Natural Channels and Flood Plains*. **U.S. Geological Survey Water-Supply Paper 2339**, Reston, VA. [https://doi.org/10.3133/wsp2339](https://doi.org/10.3133/wsp2339)

* **Soil Infiltration & Hydrology**:
  * Green, W. H., & Ampt, G. A. (1911). *Studies on Soil Physics: Part I. Flow of Air and Water through Soils*. **The Journal of Agricultural Science**, 4(1), 1–24. [https://doi.org/10.1017/S0021859600001440](https://doi.org/10.1017/S0021859600001440)
  * USDA Natural Resources Conservation Service. (1986). *Urban Hydrology for Small Watersheds*. **Technical Release 55 (TR-55)**, Second Edition, Washington, D.C.

---

### 2. Official Indonesian Regulations & Technical Guidelines

* **Disaster Management & Hazard Assessment (BNPB)**:
  * **Peraturan Kepala BNPB (Perka BNPB) No. 02 Tahun 2012**: *Pedoman Umum Pengkajian Risiko Bencana*. Badan Nasional Penanggulangan Bencana, Jakarta. *(Defines national flood depth hazard classifications: Rendah < 0.75 m, Sedang 0.75–1.50 m, and Tinggi > 1.50 m, along with spatial fuzzy index logic).*
  * **Undang-Undang Republik Indonesia No. 24 Tahun 2007**: *tentang Penanggulangan Bencana*. Lembaran Negara Republik Indonesia Tahun 2007 No. 66.

* **National Standards (Badan Standardisasi Nasional - BSN)**:
  * **SNI 2415:2016**: *Tata cara perhitungan debit banjir rencana*. Badan Standardisasi Nasional. *(National guideline for hydrological statistical distributions: Gumbel, Log Pearson Type III, and design flood hydrographs).*
  * **SNI 7746:2012**: *Tata cara perhitungan debit andalan sungai dengan kurva durasi debit*. Badan Standardisasi Nasional.

* **Geospatial & Thematic Data Standards (BIG & Kementan)**:
  * **Undang-Undang No. 4 Tahun 2011**: *tentang Informasi Geospasial*. Lembaran Negara Republik Indonesia Tahun 2011 No. 49.
  * **Peraturan Badan Informasi Geospasial (BIG) No. 1 Tahun 2020**: *tentang Standar Pengumpulan dan Spesifikasi Teknis Data Geospasial Dasar*. *(Specifies technical standards for Peta Rupa Bumi Indonesia / RBI thematic base layers).*
  * **Balai Besar Penelitian dan Pengembangan Sumberdaya Lahan Pertanian (BBSDLP), Kementerian Pertanian**: *Peta Tekstur Tanah Skala 1:50.000 Provinsi Sumatera Barat*. Kementerian Pertanian Republik Indonesia.

