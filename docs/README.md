# Sumatera Barat Flood Hazard Pipeline — Documentation Index

> **Language / Bahasa:** English | [**Baca Dokumentasi dalam Bahasa Indonesia (`docs/id/`)**](id/README.md)

Welcome to the technical documentation hub for the **Sumatera Barat 2D Hydrodynamic Flood Hazard Modeling Pipeline** powered by **Deltares SFINCS** (*Super-Fast INundation of CoastS*, v2.4.0 Galibier Release) and **HydroMT-SFINCS `1.2.2`** (`.venv` via `uv`).

This directory contains technical guides, data specifications, and engineering references for **17 clustered watershed basins** (`DAS_101` to `DAS_114`, with Mentawai disaggregated into `DAS_108_A`–`D`) across Sumatera Barat for 6 return periods (`RP2`, `RP5`, `RP10`, `RP25`, `RP50`, and `RP100`).

---

## 📚 Document Index & Navigation

| Document | Primary Audience | Purpose & Contents |
| :--- | :--- | :--- |
| [**`WINDOWS_INSTALLATION_GUIDE.md`**](WINDOWS_INSTALLATION_GUIDE.md) | Beginners, Local Team Members, GIS Analysts | **6-step setup guide** to provision the unified `.venv` (`uv sync --extra dev`), register the `HydroMT-SFINCS` Jupyter kernel, unblock Windows 11 binaries, and run simulations without Conda. |
| [**`TUTORIAL.md`**](TUTORIAL.md) | Geospatial Modelers, Hydrologists | **Step-by-step modeling tutorial** covering prepared datasets, single-cluster prototyping (40 m standard or 80 m fast mode), master batch execution, QA gates, and storage cleanup. |
| [**`PIPELINE.md`**](PIPELINE.md) | Scientists, Hydraulic Engineers, Reviewers | **Mathematical formulation and hydrodynamic reference**: Shallow water equations, active masking, subgrid hypsometry, AMC-III soil infiltration, hydrostatic MMU post-processing, and Perka BNPB No. 02/2012 classification. |
| [**`BWS_DATA_SPECIFICATIONS.md`**](BWS_DATA_SPECIFICATIONS.md) | BWS Sumatera V, PUPR, Field Surveyors | **Standardized BWS data specifications & requirements** defining geometry and attribute schemas for integrating flood levees (`tanggul_sungai.gpkg`), AWLR gauges (`pos_awlr.gpkg`), and inflow hydrographs. |
| [**`REMEDIATION_REPORT.md`**](REMEDIATION_REPORT.md) | Technical Auditors, Senior Modelers | **Archival Engineering Audit Log** documenting historical physics, numerical, and geospatial fixes with unit test evidence. |

---

## 🎯 Modeling Summary: National Indonesian v2.0 Standalone Standard

* **Hydrodynamic Solver**: Native Windows 64-bit SFINCS v2.4.0 Galibier Release (`bin/sfincs.exe`) with safe numerical tuning (`alpha=0.65`, `huthresh=0.02`, `viscosity=0`) and **Auto-UTM** support across all Indonesian zones (`EPSG:32646–32754`).
* **Spatial Discretization**: Strictly masked active watershed domain (`mask: das_region`, `msk=0` outside DAS) supporting **40 m flux / 10 m subgrid** (`configs/sfincs_standalone_build.yml`) or **80 m flux / 10 m subgrid** (`configs/sfincs_standalone_build_80m_fast.yml`) chipped on-the-fly via `WarpedVRT` from native 30 m FABDEM.
* **Rainfall & Coastal Forcing**: 24-hour design storms padded with dynamic zero-intensity recession hours (`24/36/48 h` scaled to basin area) plus **Coastal MHHW (`+0.80 m`)** tidal backwater via native `sfincs.bnd`/`sfincs.bzs`.
* **Infiltration (`CNB`)**: Modern USDA-NRCS Curve Number with Recovery (`smaxfile`/`sefffile`/`ksfile` in meters) from **Kementan Soil HSG × Canonical BIG RBI Land Cover** (single-counted `AMC-II` for `RP2–RP10` and `AMC-III` via `cn2_to_cn3` for `RP25–RP100` with `initial_sat_frac=0.0`; **USDA-NRCS NEH Part 630** & **SNI 2415:2016**), with pre-calibrated constant `qinf` retained as fallback.
* **Channel Conveyance (Pre-Field Baseline)**: River centerlines enhanced with BIG RBI river polygons (`data/rivers_ar.gpkg`; fallback $w = 8/15/22\text{ m}, d = 0.35/0.55/0.80\text{ m}$ pending BWS cross-section surveys, Manning $n = 0.045$).
* **Strict Hydrostatic Post-Processing (15 cm Floor), Subgrid QA & BNPB Standards**: Minimum flood hazard cutoff **`hmin = 0.15 m` (15 cm)** strictly applied across Depth, FHI, and Classes (Wing et al., 2018; Sampson et al., 2015; Bates et al., 2021), pure bilinear edge-NaN recovery (`freeboard_m=0.0`, `max_ext_dist_m=80.0 m = 1.0 × dx`; zero synthetic water inflation), road/bund bridging (`bridge_radius=3` / `30 m`), 4-connected **`30 m × 30 m` (`0.09 ha`)** native FABDEM feature floor, `1.0 ha` hydrostatic void limit (`2 mm × 2 mm` @ 1:50,000; $\sigma = 1.0\text{ px}$; **SNI 6502.3:2010** & **Peraturan BIG No. 18/2021**), exact **subgrid hypsometric volume QA**, **Perka BNPB No. 02/2012** depth classification, and continuous Fuzzy Large FHI surrogate.

---

For quick setup instructions, proceed directly to [**`WINDOWS_INSTALLATION_GUIDE.md`**](WINDOWS_INSTALLATION_GUIDE.md).
