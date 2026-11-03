"""
_env.py
=======
Centralized environment and path configuration for the Sumbar Flood Hazard Pipeline.
Ensures consistent PROJ, GDAL, and binary search path resolution across all scripts,
modules, and test suites.
"""

import os
import sys
from pathlib import Path
import pyproj
import rasterio

# Workspace root directory
ROOT_DIR = Path(__file__).resolve().parent.parent

# Set up PROJ and GDAL paths from active virtual environment (rasterio package)
try:
    rasterio_pkg = Path(rasterio.__file__).parent
    proj_dir = (rasterio_pkg / "proj_data").resolve()
    gdal_dir = (rasterio_pkg / "gdal_data").resolve()
except Exception:
    proj_dir = Path("nonexistent")
    gdal_dir = Path("nonexistent")

if proj_dir.exists():
    os.environ["PROJ_DATA"] = str(proj_dir)
    os.environ["PROJ_LIB"] = str(proj_dir)
    try:
        pyproj.datadir.set_data_dir(str(proj_dir))
    except Exception:
        pass

if gdal_dir.exists():
    os.environ["GDAL_DATA"] = str(gdal_dir)

# Register project bin directory for Windows DLL isolation (SFINCS solver & OpenMP)
if sys.platform == "win32":
    bin_path = (ROOT_DIR / "bin").resolve()
    if bin_path.exists():
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(bin_path))
            except Exception:
                pass
        if str(bin_path) not in os.environ.get("PATH", ""):
            os.environ["PATH"] = str(bin_path) + os.pathsep + os.environ.get("PATH", "")


def get_proj_env() -> dict:
    """Returns a dictionary of PROJ/GDAL environment variables for subprocess execution."""
    env = os.environ.copy()
    if proj_dir.exists():
        env["PROJ_DATA"] = str(proj_dir)
        env["PROJ_LIB"] = str(proj_dir)
    if gdal_dir.exists():
        env["GDAL_DATA"] = str(gdal_dir)
    return env
