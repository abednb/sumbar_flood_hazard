---
name: hydromt-wflow-sfincs
description: Official HydroMT v1.x and uv workflow skill for building, updating, and running Standalone SFINCS 2D flood hazard models with subgrid tables, Kementan soil infiltration, and Perka BNPB classification.
---

# HydroMT-SFINCS Standalone Modeling Skill (CLI & Python)

This skill provides reproducible, high-performance workflows for building, configuring, and executing **Deltares SFINCS** (Super-Fast INundation of CoastS and riverS) standalone direct rainfall-on-grid models using **HydroMT-SFINCS** and native Windows OpenMP multi-threading.

---

## 1. Environment & CLI Verification

Always execute scripts and notebooks inside the workspace environment:

```powershell
.\env-sfincs\Scripts\activate
python -c "import hydromt_sfincs; print('HydroMT-SFINCS is active!')"
```

---

## 2. Model Architecture & Data Flow

```text
[Data Catalog (data_catalog_sfincs.yml)]
   ├── 10m FABDEM Elevation (fabdem_sumbar)
   ├── 100m RBI Land Cover (rbi_landcover_sumbar)
   ├── 100m Kementan Soil Infiltration (soil_infiltration_sumbar)
   ├── River Vector Channels (rbi_river_sumbar)
   └── 24h Design Rainfall NetCDFs (rainfall_sumbar_rp100)
           │
           ▼
[HydroMT-SFINCS Build: configs/sfincs_standalone_build.yml]
   ├── Subgrid Elevation & Bathymetry Tables (10m subgrid / 40m flux)
   ├── Distributed Manning's n (lookup_tables/manning_lookup.csv)
   └── Spatially-Distributed Soil Infiltration (qinf binary grid)
           │
           ▼
[Direct Rain Forcing: setup_precip_forcing_from_grid]
   └── 24-Hour Cumulative/Hourly Rainfall Grid
           │
           ▼ (Solver Run: bin/sfincs.exe / OpenMP 4 threads)
   [2D Hydrodynamic Output (sfincs_map.nc)]
           │
           ▼ (Downscale to 10m & Classify)
   [BNPB Hazard Map (outputs_standalone/<das_id>/<rp>/hazard_class_perka2012.tif)]
```

---

## 3. Standard Standalone SFINCS Workflow


### Step 1: Initialize Case Directory & Data Contract
```powershell
# Create a controlled case directory structure
uv run fhm init-case --case-id <CASE_ID>

# Validate required vector layers, DEM, and rainfall contracts
uv run fhm validate-inputs --case-id <CASE_ID>
```

### Step 2: Prepare Design Rainfall Forcing
Convert annual maximum daily rainfall into a time-disaggregated hyetograph (e.g. SCS-Type II or Alternating Block Method):
```powershell
uv run fhm prepare-rainfall --case-id <CASE_ID> --return-period <RP>
```
*Note: Available return periods: 2, 5, 10, 25, 50, 100 years.*

### Step 3: Build & Configure Wflow Model with HydroMT CLI
HydroMT v1.x uses the `build` sub-command with an INI configuration template and the data catalog:

```powershell
# Build Wflow model structure from catchment boundaries and DEM
uv run hydromt build wflow_sbm models/wflow/<CASE_ID> `
  -i cases/<CASE_ID>/configs/wflow_build.yml `
  -d configs/data_catalog.yml `
  -v
```

### Step 4: Run Wflow.jl Hydrological Solver
Execute Wflow simulation to generate river discharge time-series:
```powershell
julia --project=. -e "using Wflow; Wflow.run(\"models/wflow/<CASE_ID>/wflow_sbm.toml\")"
```

### Step 5: Build & Configure SFINCS Inundation Model with HydroMT CLI
Build the 2D hydrodynamic overland flow domain and couple river inflow boundary points:

```powershell
# Build SFINCS model domain, elevation subgrid, roughness, and boundary conditions
uv run hydromt build sfincs models/sfincs/<CASE_ID>_<RP>yr `
  -i configs/sfincs/build.template.yml `
  -d configs/data_catalog.yml `
  -r "{'bbox': [<xmin>, <ymin>, <xmax>, <ymax>]}" `
  -v
```

To update an existing SFINCS setup with Wflow discharge hydrographs:
```powershell
uv run hydromt update sfincs models/sfincs/<CASE_ID>_<RP>yr `
  -i configs/sfincs/sfincs_update_forcing.ini `
  -d configs/data_catalog.yml `
  -v
```

### Step 6: Run SFINCS Hydrodynamic Solver
```powershell
# Run SFINCS binary on Windows
& "$env:SFINCS_PATH" -d models/sfincs/<CASE_ID>_<RP>yr
```

### Step 7: Post-Processing & BNPB Hazard Classification
Extract maximum flood depth ($h_{max}$) and classify according to Perka BNPB No. 2 Tahun 2012:

```powershell
uv run fhm classify-depth `
  --depth models/sfincs/<CASE_ID>_<RP>yr/sfincs_hmax.tif `
  --output outputs/maps/<CASE_ID>/hazard_<RP>yr.tif
```

---

## 4. HydroMT INI Template Conventions

### `configs/wflow/wflow_build.ini` Key Sections
- `[setup_basemaps]`: Hydrography, flow directions (`flwdir`), catchment delineation from conditioned DEM.
- `[setup_rivers]`: River network mapping, bankfull discharge estimation.
- `[setup_landuse]`: Manning roughness $N$ and canopy interception parameters.
- `[setup_soil]`: Soil thickness, saturated hydraulic conductivity ($K_{sat}$), and porosity from HYSOGs/soil maps.

### `configs/sfincs/sfincs_build.ini` Key Sections
- `[setup_grid]`: Computational 2D regular grid definition (resolution, CRS).
- `[setup_subgrid]`: High-resolution DEM integration for subgrid bathymetry/storage.
- `[setup_manning_roughness]`: Spatially distributed friction derived from land use.
- `[setup_discharge_bnd]`: Fluvial inflow injection points from upstream hydrographs.
- `[setup_precip]`: Pluvial rainfall grid/forcing array.

---

## 5. Scientific Quality Gates & Troubleshooting

- **DEM Conditioning**: A raw 10 m DEM is not routing-ready. Ensure river burning, sink filling, and bridge removal are verified in pre-processing.
- **CRS Consistency**: Ensure all vector and raster sources match the local projected coordinate system (e.g. UTM Zone 47S / EPSG:32747) to avoid spatial distortion in cell dimensions.
- **Water Balance & Volume QA**: Check that total inflow volume matches runoff generated before validating inundation extent.
- **Windows File Paths**: Use forward slashes (`/`) or quoted paths in configuration files to prevent escape sequence issues in PowerShell.
