# Sumatera Barat Flood Hazard Mapping

Regional scale 2D hydrodynamic flood hazard modeling pipeline for 14 clustered watershed basins (DAS clusters) across Sumatera Barat, generating flood depth, flood extent, hazard index & classifications, and flood propagation animations for 6 return periods (2, 5, 10, 25, 50, and 100 years).

---

## Modeling Approach: HydroMT-SFINCS by Deltares

This project utilizes **Deltares SFINCS** (*Super-Fast INundation of CoastS and riverS*, v2.4.0 Galibier Release) via **HydroMT 0.10.1** and **hydromt-sfincs 1.2.2** in **Standalone Direct Rainfall-on-Grid Mode**:
* **Subgrid Topography**: 40 m computational flux mesh coupled with 10 m subgrid hypsometry derived from FABDEM (30 m native, bilinearly resampled to 10 m).
* **Extended Direct Rain Forcing**: 24-hour design storm hyetographs padded with 12–48 hours of zero-intensity recession forcing (36–72 hour simulation timeline) to capture peak propagation and catchment drainage.
* **Pre-Saturated Soil Infiltration (AMC-III)**: 2D physical matrix coupling Ministry of Agriculture (*Kementerian Pertanian*) Soil Texture with BIG RBI Land Cover under an Antecedent Moisture Condition III (AMC-III) constant-loss assumption ($q_{\text{inf}} \in [0.00, 2.60]\text{ mm/hr}$), calibrated for wet monsoon extremes (Arsyad, 2010; USDA-NRCS, 2004).
* **Distributed Manning Roughness**: Spatially distributed friction derived from integer-coded BIG RBI Land Cover (`data/landcover_rbi.tif`) following Chow (1959) and Arcement & Schneider (1989).
* **Aggraded River Bathymetry**: River centerlines burned directly into subgrid hypsometry (`datasets_riv`) parameterized by regional hydraulic geometry power laws ($w = 25.0\text{--}35.0\text{ m}, d = 1.6\text{ m}$, Manning $n = 0.035$), incorporating riverbed aggradation documented by BWS Sumatera V (2020, 2022) and SNI 2830:2008.
* **Dual Boundary Conditioning**: Coastal sea-level waterlevel boundary ($z \le 0$) and designated outflow boundaries (`btype: outflow`, `msk=3`) at inland catchment outlets.
* **Hazard Post-Processing**: Automated downscaling, physically grounded depth reconstruction ($z_s - z_{\text{DEM}}$), 1:50,000 scale Minimum Mapping Unit ($1.0\text{ ha} = 100\text{ px}$ island/hole filters; Perka BIG 1/2020 & Perka BNPB 2/2012), hydro-morphological bridging ($30\text{ m}$) across transport embankments, boundary anti-aliasing ($\sigma = 1.0\text{ px}$), continuous Fuzzy Large Flood Hazard Index (FHI), and official Perka BNPB No. 2 Tahun 2012 hazard classification (Rendah, Sedang, Tinggi) with QField survey validation.

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

## Scientifically Grounded Parameter Matrix (Tier 1 & Tier 2)

All model parameters are partitioned into **Tier 1 (Upstream Physics & Hydrodynamic Build)** and **Tier 2 (Downstream Post-Processing & Cartography)**, anchored in Indonesian statutory guidelines and peer-reviewed international scientific literature:

| Parameter | Tier | Calibrated / Adjusted Value | Units / Scale | Physical / Cartographic Role | Authoritative Scientific Reference & Regulatory Standard |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **Soil Infiltration Capacity ($q_{\text{inf}}$)** | Tier 1 | `0.00 - 2.60` (Clay: 0.18–0.45; Loam: 0.52–1.10; Sand: 1.50–2.60) | $\text{mm/hr}$ ($100\text{ m}$ grid) | Governs rainfall-runoff loss under wet monsoon storm conditions. | **USDA-NRCS NEH Part 630** (AMC-III); **Arsyad (2010)**; **BBSDLP (2014)**; **Triatmodjo (2008)** |
| **Bankfull River Depth (`rivdph`)** | Tier 1 | `1.60` (Trunk: 2.0; Secondary: 1.6; Headwater: 1.2) | $\text{meters}$ | Controls in-bank flow conveyance and threshold for overbank floodplain inundation. | **BWS Sumatera V (2020, 2022)** (aggraded riverbed); **Leopold & Maddock (1953)**; **Suripin (2004)** |
| **Bankfull River Width (`rivwth`)** | Tier 1 | `25.0` (Trunk: 35.0; Secondary: 25.0; Headwater: 15.0) | $\text{meters}$ | Defines burned river channel cross-sectional width. | **Leopold & Maddock (1953)**; **BWS Sumatera V (2020)** |
| **River Channel Manning ($n$)** | Tier 1 | `0.035` | $\text{s/m}^{1/3}$ | Dictates channel flow velocity and energy slope resistance. | **SNI 2830:2008**; **KP-03 (2013)**; **Chow (1959)** (meandering gravel/sand channel with debris) |
| **Floodplain Manning ($n$)** | Tier 1 | Settlement: `0.080`; Shrub: `0.050`; Forest: `0.120`; Paddy: `0.045` | $\text{s/m}^{1/3}$ | Spatially distributed surface friction from BIG RBI Land Cover. | **Chow (1959)**; **Arcement & Schneider (1989)**; **FEMA (2019)** (urban macro-roughness) |
| **Minimum Inundation Cutoff ($h_{\text{min}}$)** | Tier 2 | `0.05` | $\text{meters}$ ($5\text{ cm}$) | Physical wet-dry cell threshold to distinguish surface sheet flow from inundation. | **Deltares SFINCS (Leijnse et al., 2021)**; **InaRISK BNPB** |
| **Island Minimum Mapping Unit (`island_mmu_px`)** | Tier 2 | `100` | pixels ($1.0\text{ ha} = 10,000\text{ m}^2$) | Sieve filter to eliminate spurious isolated perched puddles and hillslope noise. | **Perka BIG No. 1/2020** & **SNI 19-6502.2-2010** (1:50,000 scale); **Perka BNPB No. 02/2012** |
| **Hole Minimum Mapping Unit (`hole_mmu_px`)** | Tier 2 | `100` | pixels ($1.0\text{ ha} = 10,000\text{ m}^2$) | Fills small dry voids within continuous floodplains if $z_s \ge z_{\text{DEM}} + h_{\text{min}}$. | **Perka BIG No. 1/2020** (1:50,000 scale); **Perka BNPB No. 02/2012** |
| **Morphological Closing (`bridge_radius`)** | Tier 2 | `3` | pixels ($30\text{ m}$ radius) | Bridges flow artificially severed by coarse DEM road embankments and culverts. | **Soille (2003)** (mathematical morphology); **Wood & Schmidt (2002)** (hydro-enforcement) |
| **Boundary Anti-Aliasing (`smooth_sigma`)** | Tier 2 | `1.0` | pixels ($10\text{ m}$ filter) | Eliminates raster staircase pixelation using Euclidean signed distance fields. | **Borgefors (1986)** (Euclidean Distance Transform); **Soille (2003)** |
| **Fuzzy Large Hazard Index ($x_0, s$)** | Tier 2 | Midpoint: `1.125`, Spread: `1.75` | $\text{meters}$ | Translates depth into a continuous flood hazard index ($FHI \in [0, 1]$). | **Klir & Yuan (1995)**; **Zadeh (1965)**; **Perka BNPB No. 02/2012** |

---

## Bibliography & Regulatory Framework

This flood hazard modeling pipeline couples peer-reviewed hydrodynamic science with statutory disaster management standards and Indonesian water resources regulations:

### 1. 2D Hydrodynamic Modeling & Subgrid Numerical Frameworks

* **Deltares SFINCS (Subgrid Hydrodynamics)**:
  * Leijnse, T., van Ormondt, M., Nederhoff, K., & van Dongeren, A. (2021). *Coupling of a subgrid technique with a compound flood model for coastal inundation*. **Coastal Engineering**, 163, 103797. [https://doi.org/10.1016/j.coastaleng.2020.103797](https://doi.org/10.1016/j.coastaleng.2020.103797)
  * Sadana, T., Aerts, J. C. J. H., Eilander, D., Merz, B., de Moel, H., Busker, T., Bril, V., & de Bruijn, J. (2025). *Validation of the Open-Source Hydrodynamic Model SFINCS on Historical River Floods at the Global Scale*. **EGUsphere** [Preprint]. [https://doi.org/10.5194/egusphere-2025-4387](https://doi.org/10.5194/egusphere-2025-4387)
  * Eilander, D., Couasnon, A., Leijnse, T., Ikeuchi, H., Yamazaki, D., Muis, S., Dullaart, J., Haag, A., Winsemius, H. C., & Ward, P. J. (2023). *A globally applicable framework for compound flood hazard modeling*. **Natural Hazards and Earth System Sciences**, 23(2), 823–846. [https://doi.org/10.5194/nhess-23-823-2023](https://doi.org/10.5194/nhess-23-823-2023)
* **HydroMT Automated Modeling Framework**:
  * Eilander, D., van Verseveld, W., Stam, J., Winsemius, H., & Deltares HydroMT Contributors. (2023). *HydroMT: Hydro and Earth system Model Tools*. Deltares. [https://deltares.github.io/hydromt/](https://deltares.github.io/hydromt/)
* **High-Resolution Bare-Earth Topography (FABDEM)**:
  * Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., & Sampson, C. (2022). *A 30 m globally unified Copernicus DEM-derived digital elevation model removing trees and buildings: FABDEM*. **Geophysical Research Letters**, 49(17), e2022GL099236. [https://doi.org/10.1029/2022GL099236](https://doi.org/10.1029/2022GL099236)
* **DEM & FABDEM Downscaling, Super-Resolution & Subgrid Topography (30 m to 10 m)**:
  * Zhu, Y., Burlando, P., Tan, P. Y., Geiß, C., & Fatichi, S. (2025). *Improving pluvial flood simulations with a multi-source digital elevation model super-resolution method*. **Natural Hazards and Earth System Sciences**, 25(6), 2271–2291. [https://doi.org/10.5194/nhess-25-2271-2025](https://doi.org/10.5194/nhess-25-2271-2025). *(Explicitly demonstrates deep learning super-resolution downscaling of 30 m satellite DEMs to 10 m using auxiliary optical imagery; proves that 10 m downscaled topography reduces floodwater depth MAE by 13.1% and improves inundation area Intersection-over-Union by 46% over standard interpolation).*
  * Ye, J., Shen, F., Wang, Y., & Li, M. (2024). *A DEM Image Superresolution Reconstruction Method Based on the Texture Transfer of High-Resolution Remote Sensing Images*. **IEEE Journal of Selected Topics in Applied Earth Observations and Remote Sensing**, 17, 10839–10853. [https://doi.org/10.1109/JSTARS.2024.3406240](https://doi.org/10.1109/JSTARS.2024.3406240). *(Presents a texture-transfer super-resolution approach downscaling 30 m DEMs to 10 m guided by 10 m Sentinel-2 multi-spectral bands, restoring fine terrain morphology and hydraulic breaklines).*
  * Demiray, B. Z., Sit, M., & Demir, I. (2021). *D-SRGAN: DEM Super-Resolution with Generative Adversarial Networks*. **SN Computer Science**, 2(1), 48. [https://doi.org/10.1007/s42979-020-00442-2](https://doi.org/10.1007/s42979-020-00442-2). *(Formulates GAN-based deep learning super-resolution for enhancing topography in hydrologic and hydraulic applications).*
  * Saksena, S., & Merwade, V. (2015). *Incorporating the effect of DEM resolution and accuracy for improved flood inundation mapping*. **Journal of Hydrology**, 530, 180–194. [https://doi.org/10.1016/j.jhydrol.2015.09.067](https://doi.org/10.1016/j.jhydrol.2015.09.067). *(Quantifies hydrodynamic sensitivity, flood depth variations, and boundary discrepancies across DEM resolution transitions between 10 m and 30 m).*
  * Volp, N. D., van Prooijen, B. C., & Stelling, G. S. (2013). *A finite volume approach for shallow water flow accounting for high-resolution 2D subgrid elevation variations*. **Ocean Dynamics**, 63(4), 413–426. [https://doi.org/10.1007/s10236-013-0604-0](https://doi.org/10.1007/s10236-013-0604-0). *(Foundational mathematical formulation for subgrid hypsometry, where high-resolution 10 m downscaled topography governs volume-elevation tables and flux boundaries inside coarser 2D numerical cells).*
  * Hawker, L., Bates, P., Neal, J., & Rougier, J. (2018). *Perspectives on Digital Elevation Model (DEM) Simulation for Flood Hazard Modelling*. In: Guy J-P. Schumann (ed.), *Earth Observation for Flood Risk Management: Challenges and New Opportunities*, Elsevier, pp. 65–87. [https://doi.org/10.1016/B978-0-12-814880-8.00004-9](https://doi.org/10.1016/B978-0-12-814880-8.00004-9). *(Comprehensive analysis of global DEM resolution trade-offs, spatial downscaling methodologies, and vertical error propagation across flood inundation extents).*

### 2. Fluvial Hydraulics, River Burning & Channel Aggradation

* **Downstream Hydraulic Geometry**:
  * Leopold, L. B., & Maddock, T. (1953). *The Hydraulic Geometry of Stream Channels and Some Physiographic Implications*. **U.S. Geological Survey Professional Paper 252**, Washington, D.C. [https://doi.org/10.3133/pp252](https://doi.org/10.3133/pp252). *(Establishes power-law scaling of channel bankfull width and depth across drainage basin areas).*
* **Riverbed Aggradation & Sedimentation in Sumatera Barat**:
  * Balai Wilayah Sungai (BWS) Sumatera V. (2020). *Laporan Akhir Perencanaan Teknis Pengendalian Banjir Batang Kuranji dan Batang Air Dingin Kota Padang*. Balai Wilayah Sungai Sumatera V, Direktorat Jenderal Sumber Daya Air, Kementerian Pekerjaan Umum dan Perumahan Rakyat (PUPR), Padang. *(Documents severe riverbed aggradation reducing active bankfull depth to 1.1–1.5 m in West Sumatra alluvial plains).*
  * Balai Wilayah Sungai (BWS) Sumatera V. (2022). *Penyusunan Rencana Pengelolaan Sumber Daya Air Wilayah Sungai Batang Anai - Batang Kuranji - Batang Arau*. Direktorat Jenderal Sumber Daya Air, Kementerian PUPR, Padang.
  * Suripin. (2004). *Sistem Drainase Perkotaan yang Berkelanjutan*. ANDI Offset, Yogyakarta. *(Analyzes channel conveyance degradation, sediment deposition, and urban drainage overflow in Indonesia).*
* **River Channel Manning Resistance**:
  * Standar Nasional Indonesia (SNI) 2830:2008. *Tata cara perhitungan tinggi muka air sungai dengan cara pias berdasarkan rumus Manning*. Badan Standardisasi Nasional (BSN), Jakarta. *(Standardizes Manning n = 0.030–0.040 for natural meandering gravel-bed streams with sand and woody debris).*
  * Direktorat Jenderal Sumber Daya Air. (2013). *Kriteria Perencanaan Bagian Saluran (KP-03)*. Standar Perencanaan Irigasi, Kementerian Pekerjaan Umum dan Perumahan Rakyat, Jakarta.

### 3. Tropical Soil Infiltration & Saturated Catchment Physics (AMC-III)

* **Antecedent Soil Moisture & Runoff Generation**:
  * USDA Natural Resources Conservation Service. (2004). *National Engineering Handbook (NEH), Part 630: Hydrology, Chapter 10: Estimation of Direct Runoff from Storm Rainfall*. Natural Resources Conservation Service, U.S. Department of Agriculture, Washington, D.C. *(Defines Antecedent Moisture Condition III / AMC-III: saturated catchment state following >53 mm of 5-day prior rainfall).*
  * Triatmodjo, B. (2008). *Hidrologi Terapan*. Beta Offset, Yogyakarta. *(Comprehensive reference for Indonesian watershed hydrology, infiltration capacity curves, and design flood hydrograph loss rates).*
* **Indonesian Tropical Soil Infiltration Capacity**:
  * Arsyad, S. (2010). *Konservasi Tanah dan Air* (Edisi Kedua). IPB Press, Bogor. *(Authoritative empirical final infiltration rates fc for Indonesian Inceptisols, Ultisols, and Andisols).*
  * Balai Besar Penelitian dan Pengembangan Sumberdaya Lahan Pertanian (BBSDLP) / Balittanah. (2014). *Karakteristik Fisik Tanah dan Pengelolaan Hidrologi DAS*. Badan Penelitian dan Pengembangan Pertanian, Kementerian Pertanian Republik Indonesia, Bogor.
* **Classical Steady-State Infiltration Physics**:
  * Green, W. H., & Ampt, G. A. (1911). *Studies on Soil Physics: Part I. Flow of Air and Water through Soils*. **The Journal of Agricultural Science**, 4(1), 1–24. [https://doi.org/10.1017/S0021859600001440](https://doi.org/10.1017/S0021859600001440)
  * Kohnke, H. (1968). *Soil Physics*. McGraw-Hill, New York; and Uhland, R. E., & O'Neal, A. M. (1951). *Soil permeability determinations for use in soil and water conservation*. USDA Soil Conservation Service SCS-TP-101. *(Basis for SFINCS constant-loss steady-state infiltration rates fc).*

### 4. Floodplain Roughness & Flow Resistance

* Chow, V. T. (1959). *Open-Channel Hydraulics*. McGraw-Hill, New York. *(Definitive reference for base and composite Manning's roughness coefficients across floodplain vegetation types).*
* Arcement, G. J., & Schneider, V. R. (1989). *Guide for Selecting Manning's Roughness Coefficients for Natural Channels and Flood Plains*. **U.S. Geological Survey Water-Supply Paper 2339**, Reston, VA. [https://doi.org/10.3133/wsp2339](https://doi.org/10.3133/wsp2339)
* Federal Emergency Management Agency (FEMA). (2019). *Guidance for Flood Risk Analysis and Mapping: Hydraulic Numerical Models*. Federal Insurance and Mitigation Administration, Washington, D.C. *(Justifies elevated macro-roughness n = 0.080–0.100 for dense urban settlements and obstructed floodplain corridors).*

### 5. Cartographic Filtering, Mathematical Morphology & Anti-Aliasing

* **Statutory Minimum Mapping Unit (MMU / Satuan Pemetaan Terkecil)**:
  * Peraturan Badan Informasi Geospasial (BIG) No. 1 Tahun 2020. *Standar Pengumpulan dan Spesifikasi Teknis Data Geospasial Dasar untuk Peta Rupa Bumi Indonesia*. Badan Informasi Geospasial, Cibinong. *(Mandates minimum legible polygon area of 4 mm x 4 mm on paper = 16 mm², equivalent to 1.0–4.0 ha at 1:50,000 scale).*
  * Standar Nasional Indonesia (SNI) 19-6502.2-2010. *Spesifikasi penyajian peta rupa bumi - Bagian 2: Skala 1:50.000*. Badan Standardisasi Nasional (BSN), Jakarta.
* **Mathematical Morphology & Hydro-Enforcement**:
  * Soille, P. (2003). *Morphological Image Analysis: Principles and Applications* (2nd ed.). Springer-Verlag, Berlin, Heidelberg. [https://doi.org/10.1007/978-3-662-05088-0](https://doi.org/10.1007/978-3-662-05088-0). *(Formulation of circular binary closing kernels and size-limited morphological hole filling).*
  * Wood, N. J., & Schmidt, J. (2002). *Drainage network extraction from digital elevation models: the effect of resolution and hydro-enforcement across infrastructure barriers*. **Hydrological Processes**, 16(11), 2263–2279. [https://doi.org/10.1002/hyp.1098](https://doi.org/10.1002/hyp.1098). *(Techniques for bridging infrastructure cuts like road embankments and culverts).*
  * Borgefors, G. (1986). *Distance transformations in digital images*. **Computer Vision, Graphics, and Image Processing**, 34(3), 344–371. [https://doi.org/10.1016/S0734-189X(86)80047-0](https://doi.org/10.1016/S0734-189X(86)80047-0). *(Exact Euclidean Distance Transform for signed distance fields and continuous boundary anti-aliasing).*

### 6. Statutory Disaster Risk & Hazard Classification

* **National Disaster Management Authority (BNPB)**:
  * Peraturan Kepala BNPB (Perka BNPB) No. 02 Tahun 2012. *Pedoman Umum Pengkajian Risiko Bencana*. Badan Nasional Penanggulangan Bencana, Jakarta. *(Mandates 3-tier flood hazard depth thresholds: Rendah < 0.75 m, Sedang 0.75–1.50 m, Tinggi > 1.50 m, and 1.0 ha assessment grid unit for Kabupaten/Kota level in Sumatera).*
  * Undang-Undang Republik Indonesia No. 24 Tahun 2007. *tentang Penanggulangan Bencana*. Lembaran Negara Republik Indonesia Tahun 2007 No. 66.
* **Design Flood Hydrology Standards**:
  * Standar Nasional Indonesia (SNI) 2415:2016. *Tata cara perhitungan debit banjir rencana*. Badan Standardisasi Nasional (BSN), Jakarta. *(Guidelines for statistical distributions: Gumbel, Log Pearson Type III, and rainfall temporal distribution).*
  * Standar Nasional Indonesia (SNI) 7746:2012. *Tata cara perhitungan debit andalan sungai dengan kurva durasi debit*. Badan Standardisasi Nasional (BSN), Jakarta.
* **Continuous Fuzzy Hazard Scaling**:
  * Klir, G. J., & Yuan, B. (1995). *Fuzzy Sets and Fuzzy Logic: Theory and Applications*. Prentice Hall, Upper Saddle River, NJ. *(Fuzzy Large membership function f(x) = [1 + (x/x0)^(-s)]^(-1) applied to continuous flood depth vulnerability indexation).*
  * Zadeh, L. A. (1965). *Fuzzy sets*. **Information and Control**, 8(3), 338–353. [https://doi.org/10.1016/S0019-9958(65)90241-X](https://doi.org/10.1016/S0019-9958(65)90241-X).
* **Indonesian Geospatial Data Governance**:
  * Undang-Undang Republik Indonesia No. 4 Tahun 2011. *tentang Informasi Geospasial*. Lembaran Negara Republik Indonesia Tahun 2011 No. 49.
  * Balai Besar Penelitian dan Pengembangan Sumberdaya Lahan Pertanian (BBSDLP), Kementerian Pertanian. *Peta Tekstur Tanah Skala 1:50.000 Provinsi Sumatera Barat*. Kementerian Pertanian Republik Indonesia.


