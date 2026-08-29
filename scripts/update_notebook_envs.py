import json
import sys
from pathlib import Path

target_notebooks = [
    "01_sfincs_flood_hazard_run.ipynb",
    "Flood_Hazard_DAS101_RP100.ipynb",
    "Flood_Hazard_DAS102_RP100.ipynb",
    "Flood_Hazard_DAS103_RP100.ipynb",
    "tools_vector_clip_reproject_gpkg.ipynb"
]

new_lines = [
    "# Fix PROJ and GDAL paths dynamically for active Python environment\n",
    "site_packages = Path(sys.prefix) / 'Lib' / 'site-packages'\n",
    "proj_dir = (site_packages / 'rasterio' / 'proj_data').resolve()\n",
    "gdal_dir = (site_packages / 'rasterio' / 'gdal_data').resolve()\n",
    "if proj_dir.exists():\n",
    "    os.environ['PROJ_DATA'] = str(proj_dir)\n",
    "    os.environ['PROJ_LIB'] = str(proj_dir)\n",
    "    pyproj.datadir.set_data_dir(str(proj_dir))\n",
    "if gdal_dir.exists():\n",
    "    os.environ['GDAL_DATA'] = str(gdal_dir)\n",
]

for nb_name in target_notebooks:
    p = Path(nb_name)
    if not p.exists():
        continue
    with open(p, "r", encoding="utf-8") as f:
        nb = json.load(f)
    
    modified = False
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            src = cell.get("source", [])
            joined = "".join(src)
            if "proj_data" in joined or "env-sfincs" in joined:
                new_src = []
                skip = False
                for line in src:
                    if "Fix PROJ and GDAL" in line or "proj_dir = os.path.abspath" in line:
                        skip = True
                        new_src.extend(new_lines)
                    elif skip and ("import sfincs_standalone_pipeline" in line or "importlib" in line or "print(" in line or "import geopandas" in line):
                        skip = False
                        new_src.append(line)
                    elif not skip:
                        new_src.append(line)
                cell["source"] = new_src
                modified = True
                
    if modified:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1)
        print(f"Successfully updated {nb_name}")
