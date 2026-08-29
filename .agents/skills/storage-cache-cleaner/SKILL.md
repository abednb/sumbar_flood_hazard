---
name: storage-cache-cleaner
description: Audits and cleans residual geospatial caches, temporary GDAL/Rasterio/Dask dump files, uv cache, and Python bytecode to free up C: partition drive space after geospatial processing.
---

# Storage and Geospatial Cache Cleaner Skill

Use this skill whenever:
- Heavy geospatial processing has completed (e.g. raster clipping, DEM conditioning, HydroMT builds, SFINCS runs).
- The user requests to clean up temporary files, free up disk space on the `C:` drive, or purge caches.
- Disk usage on `C:\` is high.

---

## 1. Quick PowerShell Execution

Execute the workspace storage cleaner script using `uv`:

```powershell
# Perform audit and cleanup
uv run python scripts/clean_storage.py

# Perform dry-run audit without deleting
uv run python scripts/clean_storage.py --dry-run
```

---

## 2. Additional Cache Purge Commands

### A. uv Package Manager Cache
`uv` maintains its own wheel and download cache in `C:\Users\<user>\AppData\Local\uv\cache`. To perform a deep purge via the official `uv` CLI:

```powershell
uv cache clean
```

### B. Python Package Cache Pruning
To remove old build artifacts and unused packages without breaking the pinned environment:

```powershell
uv cache prune
```

---

## 3. What Gets Cleaned vs. What Is Protected

| Location | Cleaned Items | Protected Items (Never Deleted) |
| :--- | :--- | :--- |
| **`C:\Users\...\AppData\Local\Temp\`** | `tmp*.tif`, `gdal*`, `rasterio*`, `dask*`, `*.nc`, `*.parquet`, `*.gpkg` temp dumps | Non-geospatial Windows system files |
| **`C:\Users\...\AppData\Local\uv\cache\`** | Downloaded wheel archives & staging builds | Pinned virtual environment (`.venv/`) |
| **Workspace Root (`fhm_master`)** | `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.ipynb_checkpoints` | Case inputs, configuration templates, raw/interim datasets, models, outputs |

---

## 4. Verification Check

After cleaning, check available space on the `C:` drive:

```powershell
Get-PSDrive C | Select-Object Name, @{Name="FreeGB";Expression={[math]::round($_.Free/1GB,2)}}, @{Name="UsedGB";Expression={[math]::round($_.Used/1GB,2)}}
```
