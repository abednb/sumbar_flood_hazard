import nbformat
from pathlib import Path

# 1. Update 01_sfincs_flood_hazard_run.ipynb
nb01_path = Path('notebook/master/01_sfincs_flood_hazard_run.ipynb')
if nb01_path.exists():
    with open(nb01_path, 'r', encoding='utf-8') as f:
        nb01 = nbformat.read(f, as_version=4)

    for cell in nb01.cells:
        if cell.cell_type == 'code':
            if 'SELECTED_CLUSTERS = ' in cell.source and 'OUTPUT_MODELS_DIR' in cell.source:
                cell.source = """# ==============================================================================
# 1. SET YOUR TARGET DAS CLUSTERS AND RETURN PERIODS HERE
# ==============================================================================

# Target cluster ID(s). Supports ANY identifier format from ANY study region!
# Examples: ["DAS_102"], ["DAS201"], ["305"], ["407"], ["Citarum_Hilir"]
SELECTED_CLUSTERS = ["DAS_102"]

# Choose Return Periods: "rp2", "rp5", "rp10", "rp25", "rp50", "rp100"
SELECTED_RPS = ["rp100"]

# ==============================================================================
# 2. BOUNDARY & REGIONAL CONFIGURATION
# ==============================================================================
# Path to your watershed cluster boundary layer (GeoPackage)
DAS_CLUSTERS_GPKG = "data/das_clusters.gpkg"

# Optional Infrastructure / Survey data (Leave as None for baseline)
BWS_LEVEES_GPKG = None        # e.g., "data_raw/bws/tanggul_sungai.gpkg"
BWS_GAUGES_GPKG = None        # e.g., "data_raw/bws/pos_awlr.gpkg"
BWS_INFLOW_HYDROGRAPHS = None # e.g., "data_raw/bws/debit_inflow.csv"

# ==============================================================================
# 3. OUTPUT & CONFIG DIRECTORIES
# ==============================================================================
OUTPUT_MODELS_DIR = "models_sfincs_standalone"
OUTPUT_MAPS_DIR = "outputs_standalone"
CONFIG_FILE = "configs/sfincs_standalone_build.yml"
DATA_CATALOG_FILE = "data_catalog_sfincs.yml"

print(f"🎯 Active Target Clusters : {SELECTED_CLUSTERS}")
print(f"🎯 Active Return Periods  : {SELECTED_RPS}")
print(f"🗺️ Boundary Layer Source  : {DAS_CLUSTERS_GPKG}")
print(f"📂 Models Directory       : {OUTPUT_MODELS_DIR}")
print(f"🗺️ Hazard Maps Directory   : {OUTPUT_MAPS_DIR}")
"""
            elif 'build_sfincs_standalone(' in cell.source:
                cell.source = """for das_id in SELECTED_CLUSTERS:
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
"""

    with open(nb01_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb01, f)
    print("Updated 01_sfincs_flood_hazard_run.ipynb")

# 2. Update 02_sfincs_flood_hazard_run_opt.ipynb
nb02_path = Path('notebook/master/02_sfincs_flood_hazard_run_opt.ipynb')
if nb02_path.exists():
    with open(nb02_path, 'r', encoding='utf-8') as f:
        nb02 = nbformat.read(f, as_version=4)

    for cell in nb02.cells:
        if cell.cell_type == 'code':
            if 'SELECTED_CLUSTERS = ' in cell.source and 'OUTPUT_MODELS_DIR' in cell.source:
                cell.source = """# ==============================================================================
# 1. SET YOUR TARGET DAS CLUSTERS AND RETURN PERIODS HERE
# ==============================================================================

# Target large clusters: ["DAS_103", "DAS_107", "DAS_110", "DAS_113"] or any cluster ID
# Examples: ["DAS_103"], ["DAS201"], ["305"], ["407"], ["Citarum_Hilir"]
SELECTED_CLUSTERS = ["DAS_103"]

# Choose Return Periods: "rp2", "rp5", "rp10", "rp25", "rp50", "rp100"
SELECTED_RPS = ["rp100"]

# ==============================================================================
# 2. BOUNDARY DATASET & PATH CONFIGURATIONS
# ==============================================================================
# Uses the optimized smaller DAS cluster boundary (< 10,000 km2)
DAS_CLUSTERS_GPKG = "data/modified_das_cluster/smaller_das_cluster.gpkg"

# Optional Infrastructure / Surveys (Leave as None for baseline)
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
"""

    with open(nb02_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb02, f)
    print("Updated 02_sfincs_flood_hazard_run_opt.ipynb")

print("All master notebooks updated successfully!")
