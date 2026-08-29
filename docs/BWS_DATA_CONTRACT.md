# Data Specification & Engineering Contract: BWS Hydraulic Datasets
### Standardized Specifications for Integrating Balai Wilayah Sungai (BWS) Infrastructure & Gauge Data into HydroMT-SFINCS

**Target Models:** Standalone HydroMT-SFINCS  
**Target Coordinate Reference System (CRS):** `EPSG:32747` (UTM Zone 47S in meters) or `EPSG:4326` (WGS84)  
**Default Storage Location:** `data_raw/bws/`  

---

## 1. Overview & Data Architecture

To upgrade the baseline flood model into a high-precision hydraulic model reflecting actual flood defenses and field observations, three optional dataset layers can be compiled from **Balai Wilayah Sungai (BWS) Sumatera V**:

```
data_raw/bws/
│
├── tanggul_sungai.gpkg       <- 1. Flood Defense Structures / Levees (Thin Dikes)
├── pos_awlr.gpkg             <- 2. Automatic Water Level Recording (AWLR) Observation Gauges
└── debit_inflow.csv          <- 3. Upstream Inflow Discharge / Reservoir Releases
```

---

## 2. Dataset Specifications & Data Contracts

### 📋 Dataset 1: Flood Protection Levees & Embankments (`BWS_LEVEES_GPKG`)
* **Typical Source:** BWS River Infrastructure Inventory (Inventarisasi Tanggul / Tebing Sungai).
* **Expected File Path:** `data_raw/bws/tanggul_sungai.gpkg` (or `.shp`).
* **Geometry Type:** `LineString` or `MultiLineString` (Must trace along river banks or flood protection walls).
* **SFINCS Ingestion Method:** `sf.setup_structures(structures="...", stype="weir", par1=0.6)`
* **Physical Function:** Blocks or restricts overland water spilling until water surface level exceeds the crest elevation ($z_{crest}$).

#### Attribute Table Requirements:
| Field / Column Name | Data Type | Required? | Unit | Description & Example |
| :--- | :--- | :--- | :--- | :--- |
| `name` or `nama` | `String` | Optional | - | Name of the levee (e.g. `Tanggul Batang Anai Kiri`) |
| `z_crest` or `elev` | `Float` | **Required** | $\text{m}$ (MSL) | Top crest elevation of the levee above Mean Sea Level. |
| `par1` | `Float` | Optional | - | Weir discharge coefficient (Default: `0.6`) |
| `stype` | `String` | Optional | - | Structure type: `"weir"`, `"gate"`, or `"dam"` (Default: `"weir"`) |

> [!IMPORTANT]
> - **Elevation Datum:** Ensure `z_crest` is referenced to the same vertical datum as FABDEM (EGM2008 / MSL in meters).
> - **Geometry Quality:** Lines must not have zero-length segments or duplicate overlapping coordinates.

---

### 📋 Dataset 2: AWLR Water Level & Discharge Gauges (`BWS_GAUGES_GPKG`)
* **Typical Source:** BWS Hydro-meteorological Stations (Pos Duga Air / AWLR / ARR).
* **Expected File Path:** `data_raw/bws/pos_awlr.gpkg` (or `.shp`).
* **Geometry Type:** `Point` (Location of the telemetry gauge / sensor).
* **SFINCS Ingestion Method:** `sf.setup_observation_points(locations="...")`
* **Physical Function:** SFINCS will record high-frequency output hydrographs (water level $z_s(t)$ and depth $h(t)$) at these specific coordinates, allowing direct model calibration against observed flood events.

#### Attribute Table Requirements:
| Field / Column Name | Data Type | Required? | Unit | Description & Example |
| :--- | :--- | :--- | :--- | :--- |
| `name` or `pos_id` | `String` | **Required** | - | Unique ID or station name (e.g. `AWLR_Btg_Kuranji_Padang`) |
| `sungai` | `String` | Optional | - | Name of the river (e.g. `Batang Kuranji`) |
| `x` / `y` | `Float` | Derived | $\text{m}$ or $\text{deg}$ | Spatial point coordinates located inside the river channel. |

> [!TIP]
> **Snapping Warning:** Ensure the point geometry is placed directly inside the main river channel grid cell. If an AWLR station coordinate is placed on dry high ground beside the river, SFINCS will output 0m water depth.

---

### 📋 Dataset 3: Upstream Measured Discharge / Inflow Hydrographs (`BWS_INFLOW_HYDROGRAPHS`)
* **Typical Source:** Hourly hydrograph records from upstream dams, weirs, or discharge measurements (Bendung / Pintu Air).
* **Expected File Path:** `data_raw/bws/debit_inflow.csv` + paired coordinate point file `data_raw/bws/pos_inflow.gpkg`.
* **Geometry Type:** Tabular Time Series (`.csv`) linked to `Point` locations.
* **SFINCS Ingestion Method:** `sf.setup_discharge_forcing_from_points(locations="...", timeseries="...")`
* **Physical Function:** Injects time-varying water volume ($Q$ in $\text{m}^3/\text{s}$) into river headwaters or downstream of reservoirs.

#### Table Format Requirements (`debit_inflow.csv`):
* **Row 1:** Column headers matching the `name` column in the observation/inflow points layer.
* **Column 1:** Datetime index in ISO format (`YYYY-MM-DD HH:MM:SS`).
* **Remaining Columns:** River discharge values in cubic meters per second ($\text{m}^3/\text{s}$).

#### Example CSV Structure:
```csv
time,INFLOW_BATANG_ANAI,INFLOW_BATANG_KURANJI
2026-08-25 00:00:00,45.2,12.8
2026-08-25 01:00:00,88.5,24.3
2026-08-25 02:00:00,165.0,75.4
2026-08-25 03:00:00,240.2,110.0
2026-08-25 04:00:00,180.5,85.2
2026-08-25 05:00:00,95.0,35.1
```

---

## 3. Step-by-Step QA/QC Checklist When Data Arrives from BWS

Before setting paths in [`01_sfincs_flood_hazard_run.ipynb`](../01_sfincs_flood_hazard_run.ipynb), run this quick check:

1. [ ] **CRS Check:** Vector layers reprojected to `EPSG:32747` (UTM 47S).
2. [ ] **Levee Elevation:** Check that `z_crest` values are greater than surrounding DEM ground elevation (e.g. if ground is 12m, levee crest should be $\approx 14\text{ m}$, not relative $+2\text{ m}$).
3. [ ] **Point Locations:** Verify in QGIS that all AWLR gauge points snap directly onto the `rivers.gpkg` river line.
4. [ ] **CSV Timestamp:** Timestamps match the start time and duration of the rainfall event simulated.
