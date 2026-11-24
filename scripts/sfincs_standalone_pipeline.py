"""
Universal Standalone SFINCS Automated Pipeline for Flood Hazard Modeling
========================================================================
Supports any regional watershed cluster (e.g., Sumbar, Java, Kalimantan, global)
with dynamic CRS, flexible cluster identifier matching, automated data chipping,
subgrid river burning, rigorous boundary conditioning, and Perka BNPB No. 2/2012 classification.
"""

import gc
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import rasterio
import rasterio.mask
import rasterio.warp
import rasterio.windows
import xarray as xr
from scipy import ndimage
import hydromt
from hydromt_sfincs import SfincsModel, utils

# Ensure script directory and environment helper are loaded
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))
import _env
from geo_utils import compute_wmo_arf, get_dynamic_recession_hours
from perka_bnpb_classification import classify_perka_bnpb
from qa_checks import check_roughness, check_boundaries, check_peak_timing, volume_balance, run_all_qa
from validate_against_survey import validate_flood_map


def _release_hydromt_log_handlers(target_dir: Optional[Union[str, Path]] = None) -> int:
    """
    Closes and removes leaked HydroMT logging.FileHandler instances (especially on Windows).
    HydroMT's Model.set_root() attaches a FileHandler to hydromt.log on a module-level logger
    and never closes it automatically; in long-lived Jupyter kernels this triggers
    WinError 32 when a subsequent `hydromt build --fo` subprocess tries to unlink hydromt.log.
    """
    target_resolved = Path(target_dir).resolve() if target_dir is not None else None
    closed = 0
    loggers = [logging.getLogger()]
    for lg in list(logging.root.manager.loggerDict.values()):
        if isinstance(lg, logging.Logger):
            loggers.append(lg)

    for lg in loggers:
        for handler in list(lg.handlers):
            if not isinstance(handler, logging.FileHandler):
                continue
            fname = getattr(handler, "baseFilename", "")
            if not fname:
                continue
            fpath = Path(fname)
            should_close = fpath.name.lower() == "hydromt.log"
            if should_close and target_resolved is not None:
                try:
                    fpath.resolve().relative_to(target_resolved)
                except ValueError:
                    should_close = False
            if should_close:
                try:
                    handler.flush()
                except Exception:
                    pass
                try:
                    handler.close()
                except Exception:
                    pass
                lg.removeHandler(handler)
                closed += 1
    if closed:
        gc.collect()
    return closed


def normalize_cluster_id(raw_val) -> str:
    """Universal normalizer for cluster identifiers across any project or region."""
    if raw_val is None:
        return ""
    val_str = str(raw_val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    return val_str


def find_cluster_geometry(
    das_gdf: gpd.GeoDataFrame,
    target_id: str,
    id_column: str = "ID_Cluster",
) -> Tuple[gpd.GeoDataFrame, str]:
    """
    Finds the cluster row matching target_id with strict unambiguous validation.
    Normalizes 'DAS_101' ≡ '101' ≡ 'DAS101'.
    Raises ValueError if more than one row matches, or if no match is found.
    """
    if das_gdf.empty:
        raise ValueError("The provided cluster GeoDataFrame is empty.")

    target_str = str(target_id).strip()

    def strip_das_prefix(s) -> str:
        t = str(s).strip()
        for prefix in ["DAS_", "DAS", "das_", "das", "Das_", "Das"]:
            if t.startswith(prefix):
                return t[len(prefix):].strip()
        return t

    target_core = strip_das_prefix(target_str)
    target_alphanum = "".join(filter(str.isalnum, target_str)).lower()
    target_core_alphanum = "".join(filter(str.isalnum, target_core)).lower()

    # Prioritize user-specified id_column, followed by known candidate columns
    priority_cols = [id_column, "ID_Cluster", "id_cluster", "das_id", "DAS_ID", "Cluster_ID", "cluster_id", "KODE_DAS"]
    cand_cols = []
    for c in priority_cols:
        if c in das_gdf.columns and c not in cand_cols:
            cand_cols.append(c)

    if not cand_cols:
        raise KeyError(f"Identifier column '{id_column}' not found in GeoDataFrame. Available columns: {list(das_gdf.columns)}")

    for col in cand_cols:
        col_series = das_gdf[col].apply(normalize_cluster_id)

        # Match criteria in order of specificity
        # 1. Exact string match
        mask = col_series == target_str
        # 2. Match with 'DAS_' prefix variations
        if not mask.any():
            mask = col_series.apply(lambda x: f"DAS_{x}") == target_str
        if not mask.any():
            mask = col_series == f"DAS_{target_str}"
        # 3. Match stripped core values
        if not mask.any():
            mask = col_series.apply(strip_das_prefix) == target_core
        # 4. Alphanumeric match
        if not mask.any():
            col_core_alphanum = col_series.apply(lambda x: "".join(filter(str.isalnum, strip_das_prefix(x))).lower())
            mask = col_core_alphanum == target_core_alphanum

        match_count = int(mask.sum())
        if match_count == 1:
            matched_val = col_series[mask].iloc[0]
            print(f"[OK] Unambiguously matched cluster '{target_id}' in column '{col}' -> '{matched_val}'")
            return das_gdf[mask].copy(), target_str
        elif match_count > 1:
            matched_vals = col_series[mask].tolist()
            raise ValueError(
                f"Ambiguous match: Found {match_count} rows matching '{target_id}' in column '{col}': {matched_vals}. "
                f"Please specify an exact unique identifier."
            )

    sample_ids = [normalize_cluster_id(x) for x in das_gdf[cand_cols[0]].head(10)]
    raise ValueError(
        f"Cluster '{target_id}' was not found in dataset.\n"
        f"Searched candidate columns {cand_cols}.\n"
        f"Available sample IDs in column '{cand_cols[0]}': {sample_ids}..."
    )


def find_elevation_dem_path(explicit_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Finds the elevation DEM raster unambiguously (supports both projected DEMs and native 30m FABDEM).
    Rejects loose glob fallbacks (Issue M5).
    """
    if explicit_path:
        p = Path(explicit_path).resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Explicitly specified DEM not found at: {p}")

    candidates = [
        Path("data/fabdem_30m.tif"),
        Path("data_raw/fabdem/FABDEM30m_Sumbar.tif"),
        Path("data/fabdem_reprojected.tif"),
        Path("data/dem_reprojected.tif"),
        Path("data/dem.tif"),
    ]
    for cand in candidates:
        if cand.exists():
            return cand.resolve()

    raise FileNotFoundError(
        f"Elevation DEM raster could not be resolved.\n"
        f"Checked standard locations: {[str(c) for c in candidates]}.\n"
        f"Please provide an explicit path."
    )


def compute_river_hydraulic_geometry(
    rivers_gdf: gpd.GeoDataFrame,
    river_polygons_gpkg: Optional[Union[str, Path]] = "data/rivers_ar.gpkg",
    silted_profile: bool = True,
) -> gpd.GeoDataFrame:
    """
    Assigns hydraulic geometry parameters (rivwth, rivdph, manning) to river centerlines
    using Indonesian aggraded/silted channel geometry (default v2.0 standard) and optional
    BIG RBI river polygon widths (rivers_ar.gpkg) when available (Issue H2).
    """
    gdf = rivers_gdf.copy()
    num_rivers = len(gdf)
    if num_rivers == 0:
        return gdf

    # Base estimates from channel class / naming
    has_name = gdf["NAMOBJ"].notna() if "NAMOBJ" in gdf.columns else np.zeros(num_rivers, dtype=bool)
    is_double_line = (gdf["REMARK"] == "Sungai") if "REMARK" in gdf.columns else np.zeros(num_rivers, dtype=bool)
    length = gdf["SHAPE_Leng"].values if "SHAPE_Leng" in gdf.columns else np.full(num_rivers, 500.0)

    if silted_profile:
        # Calibrated silted/aggraded Indonesian alluvial channel profile (v2.0 national standard):
        # Prevents artificial over-carving of trenches in FABDEM while preserving realistic overbank spill.
        rivwth = np.where(is_double_line | (has_name & (length > 2000)), 22.0, np.where(has_name, 15.0, 8.0))
        rivdph = np.where(is_double_line | (has_name & (length > 2000)), 0.80, np.where(has_name, 0.55, 0.35))
        manning_n = 0.045  # Vegetated/aggraded tropical river banks (Chow 1959 / Arcement & Schneider 1989)
    else:
        # Legacy idealized clean channel profile
        rivwth = np.where(is_double_line | (has_name & (length > 2000)), 30.0, np.where(has_name, 20.0, 12.0))
        rivdph = np.where(is_double_line | (has_name & (length > 2000)), 1.20, np.where(has_name, 0.85, 0.60))
        manning_n = 0.035

    # Enhance trunk widths using mapped BIG RBI river polygons (rivers_ar.gpkg) when available
    if river_polygons_gpkg and Path(river_polygons_gpkg).exists():
        try:
            poly_bbox = tuple(gdf.total_bounds)
            ar_gdf = gpd.read_file(river_polygons_gpkg, bbox=poly_bbox)
            if not ar_gdf.empty:
                if gdf.crs is not None and ar_gdf.crs != gdf.crs:
                    ar_gdf = ar_gdf.to_crs(gdf.crs)
                # Effective hydraulic width proxy for elongated river polygons: W ~ 2 * Area / Perimeter
                perim = np.maximum(ar_gdf.geometry.length.values, 1.0)
                ar_gdf = ar_gdf.copy()
                ar_gdf["_poly_w"] = np.clip((2.0 * ar_gdf.geometry.area.values) / perim, 12.0, 250.0)
                joined = gpd.sjoin(gdf[["geometry"]], ar_gdf[["geometry", "_poly_w"]], how="left", predicate="intersects")
                max_poly_w = joined.groupby(joined.index)["_poly_w"].max()
                mapped_w = np.array([float(max_poly_w.get(idx, np.nan)) for idx in gdf.index], dtype=float)
                rivwth = np.where(np.isfinite(mapped_w), np.maximum(rivwth, mapped_w), rivwth)
        except Exception:
            pass

    gdf["rivwth"] = np.round(rivwth, 1)
    gdf["rivdph"] = np.round(rivdph, 2)
    gdf["manning"] = manning_n
    return gdf


def _detect_epsg(path: Path, fallback_epsg: int) -> int:
    """Reads the native EPSG code from a raster or vector file header, falling back safely."""
    try:
        if path.suffix.lower() in {".tif", ".tiff", ".vrt"}:
            with rasterio.open(path) as src:
                if src.crs and src.crs.to_epsg():
                    return int(src.crs.to_epsg())
        elif path.suffix.lower() in {".gpkg", ".shp", ".geojson", ".parquet"}:
            gdf_hdr = gpd.read_file(path, rows=1)
            if gdf_hdr.crs and gdf_hdr.crs.to_epsg():
                return int(gdf_hdr.crs.to_epsg())
    except Exception:
        pass
    return int(fallback_epsg)


def prepare_cluster_clipped_rasters(
    das_id: str,
    das_geom: gpd.GeoDataFrame,
    source_dem: Optional[Path] = None,
    buffer_meters: float = 2000.0,
    chip_res_m: float = 10.0,
) -> Tuple[str, Optional[Path]]:
    """
    Extracts a local windowed chip of the DEM for the specific cluster with metadata caching (Issue M6).
    Supports BOTH pre-projected DEMs AND native 30m geographic (EPSG:4326) FABDEM via on-the-fly
    WarpedVRT windowed reprojection & bilinear resampling to `chip_res_m` in the DAS projected CRS
    (eliminating multi-gigabyte pre-upsampled provincial rasters).
    Exports the DAS polygon mask ('das_region.gpkg') so setup_mask_active masks out-of-basin cells (msk=0).
    Clips and conditions river hydrography with hydraulic geometry (Issue H2).
    Generates outlet boundary polygon (Issue H3) using lowest-elevation fallback when needed.
    Builds the per-DAS catalog with native dataset CRSs (portable across all Indonesian UTM zones).

    Returns: (catalog_path, outlet_boundary_path)
    """
    from rasterio.vrt import WarpedVRT
    from rasterio.enums import Resampling

    root_dir = Path(".").resolve()
    chip_dir = (root_dir / "temp" / "chips" / das_id).resolve()
    chip_dir.mkdir(parents=True, exist_ok=True)

    if source_dem is None or not source_dem.exists():
        source_dem = find_elevation_dem_path()

    active_crs = das_geom.crs

    # Save DAS polygon for setup_mask_active (mask: das_region)
    das_region_path = chip_dir / "das_region.gpkg"
    das_geom.to_file(das_region_path, driver="GPKG")

    minx, miny, maxx, maxy = das_geom.total_bounds
    # Snap bbox to chip_res_m grid for clean alignment
    snap_minx = float(np.floor((minx - buffer_meters) / chip_res_m) * chip_res_m)
    snap_miny = float(np.floor((miny - buffer_meters) / chip_res_m) * chip_res_m)
    snap_maxx = float(np.ceil((maxx + buffer_meters) / chip_res_m) * chip_res_m)
    snap_maxy = float(np.ceil((maxy + buffer_meters) / chip_res_m) * chip_res_m)
    bbox = (snap_minx, snap_miny, snap_maxx, snap_maxy)

    # 1. DEM Chip Caching (Issue M6)
    dem_chip_path = chip_dir / "dem_chip.tif"
    meta_json_path = chip_dir / "chip_meta.json"
    source_mtime = os.path.getmtime(source_dem)
    cache_key = f"v3_vrt_{source_dem.resolve()}_{source_mtime}_{bbox}_{chip_res_m}_{active_crs.to_epsg()}"
    cache_hash = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()

    rebuild_chip = True
    if dem_chip_path.exists() and meta_json_path.exists():
        try:
            with open(meta_json_path, "r") as mf:
                meta = json.load(mf)
                if meta.get("hash") == cache_hash:
                    with rasterio.open(dem_chip_path) as chk:
                        if chk.nodata is not None and chk.nodata > 1e10:
                            rebuild_chip = True
                        else:
                            rebuild_chip = False
        except Exception:
            rebuild_chip = True

    if rebuild_chip:
        print(f"[{das_id}] Extracting {chip_res_m:.0f}m DEM chip from {source_dem.name} (CRS={active_crs.to_epsg()})...")
        with rasterio.open(source_dem) as src:
            same_crs = (src.crs == active_crs)
            same_res = same_crs and (abs(abs(src.res[0]) - chip_res_m) <= 0.5) and (abs(abs(src.res[1]) - chip_res_m) <= 0.5)

            if same_res:
                win = rasterio.windows.from_bounds(*bbox, transform=src.transform)
                data = src.read(window=win, boundless=True, fill_value=np.nan).astype(np.float32)
                win_transform = src.window_transform(win)
                dst_crs = src.crs
            else:
                # On-the-fly windowed reprojection + bilinear resampling via GDAL WarpedVRT
                dst_width = int(round((snap_maxx - snap_minx) / chip_res_m))
                dst_height = int(round((snap_maxy - snap_miny) / chip_res_m))
                win_transform = rasterio.transform.from_bounds(
                    snap_minx, snap_miny, snap_maxx, snap_maxy, dst_width, dst_height
                )
                dst_crs = active_crs
                vrt_opts = {
                    "crs": dst_crs,
                    "transform": win_transform,
                    "width": dst_width,
                    "height": dst_height,
                    "resampling": Resampling.bilinear,
                    "nodata": -9999.0,
                }
                if src.nodata is not None:
                    vrt_opts["src_nodata"] = src.nodata
                with WarpedVRT(src, **vrt_opts) as vrt:
                    data = vrt.read().astype(np.float32)

            # Distinguish border-connected ocean NoData (fill with 0.0m for coastal msk=2 edges)
            # from interior highland NoData gaps (preserve as -9999.0 so inland pits are not sunk to sea level).
            src_nodata = src.nodata
            invalid_mask = (~np.isfinite(data[0])) | (data[0] > 1e10) | (data[0] < -500.0)
            if src_nodata is not None and np.isfinite(src_nodata):
                invalid_mask |= (data[0] == src_nodata)

            if np.any(invalid_mask):
                labeled_inv, n_inv = ndimage.label(invalid_mask)
                border_inv = (
                    set(np.unique(labeled_inv[0, :]))
                    | set(np.unique(labeled_inv[-1, :]))
                    | set(np.unique(labeled_inv[:, 0]))
                    | set(np.unique(labeled_inv[:, -1]))
                )
                border_inv.discard(0)
                is_border_nodata = np.isin(labeled_inv, list(border_inv)) if border_inv else np.zeros_like(invalid_mask)
                valid_vals = data[0][~invalid_mask]
                is_coastal_tile = (valid_vals.size > 0) and (float(np.nanpercentile(valid_vals, 1)) < 5.0)
                if is_coastal_tile:
                    data[0][is_border_nodata] = 0.0
                    data[0][invalid_mask & (~is_border_nodata)] = -9999.0
                else:
                    data[0][invalid_mask] = -9999.0

            profile = {
                "driver": "GTiff",
                "dtype": "float32",
                "count": data.shape[0],
                "height": data.shape[1],
                "width": data.shape[2],
                "crs": dst_crs,
                "transform": win_transform,
                "compress": "lzw",
                "tiled": True,
                "blockxsize": 256,
                "blockysize": 256,
                "nodata": -9999.0,
            }
            with rasterio.open(dem_chip_path, "w", **profile) as dst:
                dst.write(data)

        with open(meta_json_path, "w") as mf:
            json.dump({"hash": cache_hash, "source_dem": str(source_dem), "mtime": source_mtime, "bbox": bbox, "chip_res_m": chip_res_m}, mf, indent=2)
    else:
        print(f"[{das_id}] Reusing cached DEM chip: {dem_chip_path.name}")

    # 2. Extract and Verify Native CRSs for Datasets (Dynamic across all Indonesian UTM zones)
    dem_crs_val = _detect_epsg(dem_chip_path, fallback_epsg=(active_crs.to_epsg() or 32747))
    region_crs_val = active_crs.to_epsg() or dem_crs_val

    # 3. Clip and Condition Rivers for Subgrid Burning (Issue H2)
    rivers_chip_path = chip_dir / "rivers.gpkg"
    base_rivers_path = root_dir / "data" / "rivers.gpkg"
    if base_rivers_path.exists():
        riv_gdf = gpd.read_file(base_rivers_path, bbox=bbox)
        if not riv_gdf.empty:
            riv_conditioned = compute_river_hydraulic_geometry(riv_gdf)
            riv_conditioned.to_file(rivers_chip_path, driver="GPKG")
        else:
            shutil.copy2(base_rivers_path, rivers_chip_path)
    else:
        rivers_chip_path = base_rivers_path

    # 4. Outlet Boundary Polygon (Issue H3)
    outlet_poly_path = chip_dir / "outlet_boundary.gpkg"
    outlet_src_path = root_dir / "data" / "das_clusters" / "individual" / f"{das_id}_outlet.gpkg"
    has_outlet = False

    das_poly_geom = das_geom.geometry.iloc[0]
    if outlet_src_path.exists():
        try:
            gdf_out = gpd.read_file(outlet_src_path).to_crs(active_crs)
            if not gdf_out.empty:
                pt = gdf_out.geometry.iloc[0]
                snapped_pt = das_poly_geom.boundary.interpolate(das_poly_geom.boundary.project(pt))
                outlet_buf = snapped_pt.buffer(250.0)
                outlet_gdf = gpd.GeoDataFrame([{"geometry": outlet_buf, "btype": "outflow"}], crs=active_crs)
                outlet_gdf.to_file(outlet_poly_path, driver="GPKG")
                has_outlet = True
                print(f"[{das_id}] Outflow boundary polygon generated at ({snapped_pt.x:.1f}, {snapped_pt.y:.1f})")
        except Exception as e:
            print(f"[{das_id}] Note: Failed to generate outlet from {outlet_src_path.name}: {e}")

    # Fallback: pick LOWEST-ELEVATION river-boundary intersection point (never arbitrary first point!)
    if not has_outlet and rivers_chip_path.exists():
        try:
            riv_sub = gpd.read_file(rivers_chip_path).to_crs(active_crs)
            inter = riv_sub.intersection(das_poly_geom.boundary)
            cand_pts = []
            for g in inter:
                if g is None or g.is_empty:
                    continue
                if g.geom_type == "Point":
                    cand_pts.append(g)
                elif g.geom_type == "MultiPoint":
                    cand_pts.extend(list(g.geoms))
                else:
                    cand_pts.append(g.centroid)
            if cand_pts:
                best_pt = cand_pts[0]
                best_elev = float("inf")
                with rasterio.open(dem_chip_path) as dsrc:
                    for pt_c, val in zip(cand_pts, dsrc.sample([(p.x, p.y) for p in cand_pts])):
                        z = float(val[0])
                        if np.isfinite(z) and z > -500.0 and z < best_elev:
                            best_elev = z
                            best_pt = pt_c
                outlet_buf = best_pt.buffer(250.0)
                outlet_gdf = gpd.GeoDataFrame([{"geometry": outlet_buf, "btype": "outflow"}], crs=active_crs)
                outlet_gdf.to_file(outlet_poly_path, driver="GPKG")
                has_outlet = True
                print(f"[{das_id}] Outflow boundary polygon created at lowest river outlet (z={best_elev:.1f}m)")
        except Exception as e:
            print(f"[{das_id}] Note: River boundary outlet fallback failed: {e}")

    # 5. Write Universal Per-DAS Data Catalog with Native CRSs
    das_catalog_path = chip_dir / "catalog.yml"
    abs_dem_path = dem_chip_path.as_posix()
    abs_root = root_dir.as_posix()
    abs_riv_path = rivers_chip_path.as_posix()
    abs_region_path = das_region_path.as_posix()

    lc_file = (root_dir / "data" / "landcover_rbi.tif") if (root_dir / "data" / "landcover_rbi.tif").exists() else (root_dir / "data" / "landcover_100m.tif")
    soil_file = root_dir / "data" / "soil_infiltration_100m.tif"

    riv_crs_val = _detect_epsg(rivers_chip_path, fallback_epsg=region_crs_val)
    lc_crs_val = _detect_epsg(lc_file, fallback_epsg=dem_crs_val)
    soil_crs_val = _detect_epsg(soil_file, fallback_epsg=dem_crs_val)

    catalog_content = f"""# Universal HydroMT-SFINCS Data Catalog for {das_id}
# Compatible with HydroMT 0.10.1 / hydromt_sfincs 1.2.2

# --- Active Watershed Domain Polygon (for setup_mask_active) ---
das_region:
  path: "{abs_region_path}"
  data_type: GeoDataFrame
  driver: vector
  crs: {region_crs_val}

# --- Elevation DEM ---
fabdem_sumbar:
  path: "{abs_dem_path}"
  data_type: RasterDataset
  driver: raster
  crs: {dem_crs_val}

elevation_dem:
  path: "{abs_dem_path}"
  data_type: RasterDataset
  driver: raster
  crs: {dem_crs_val}

# --- Hydrography / River Network ---
rbi_river_sumbar:
  path: "{abs_riv_path}"
  data_type: GeoDataFrame
  driver: vector
  crs: {riv_crs_val}

rivers:
  path: "{abs_riv_path}"
  data_type: GeoDataFrame
  driver: vector
  crs: {riv_crs_val}

# --- Land Cover & Roughness ---
rbi_landcover_sumbar:
  path: "{lc_file.as_posix()}"
  data_type: RasterDataset
  driver: raster
  crs: {lc_crs_val}
  nodata: 0

landcover:
  path: "{lc_file.as_posix()}"
  data_type: RasterDataset
  driver: raster
  crs: {lc_crs_val}
  nodata: 0

# --- Soil Infiltration Capacity (AMC-III qinf) ---
soil_infiltration_sumbar:
  path: "{soil_file.as_posix()}"
  data_type: RasterDataset
  driver: raster
  crs: {soil_crs_val}

soil_infiltration:
  path: "{soil_file.as_posix()}"
  data_type: RasterDataset
  driver: raster
  crs: {soil_crs_val}

# --- Gridded Design Rainfall Events (Native netCDF coordinates, no forced CRS) ---
rainfall_rp2:
  path: "{abs_root}/data/rainfall/rainfall_rp2_hourly.nc"
  data_type: RasterDataset
  driver: netcdf

rainfall_rp5:
  path: "{abs_root}/data/rainfall/rainfall_rp5_hourly.nc"
  data_type: RasterDataset
  driver: netcdf

rainfall_rp10:
  path: "{abs_root}/data/rainfall/rainfall_rp10_hourly.nc"
  data_type: RasterDataset
  driver: netcdf

rainfall_rp25:
  path: "{abs_root}/data/rainfall/rainfall_rp25_hourly.nc"
  data_type: RasterDataset
  driver: netcdf

rainfall_rp50:
  path: "{abs_root}/data/rainfall/rainfall_rp50_hourly.nc"
  data_type: RasterDataset
  driver: netcdf

rainfall_rp100:
  path: "{abs_root}/data/rainfall/rainfall_rp100_hourly.nc"
  data_type: RasterDataset
  driver: netcdf
"""
    with open(das_catalog_path, "w", encoding="utf-8") as f:
        f.write(catalog_content)

    return str(das_catalog_path), (outlet_poly_path if has_outlet else None)


def build_sfincs_standalone(
    das_id: str,
    output_dir: str = "models_sfincs_standalone",
    config_fn: str = "configs/sfincs_standalone_build_80m_fast.yml",
    data_catalog_fn: str = "data_catalog_sfincs.yml",
    das_clusters_gpkg: str = "data/das_clusters/sumbar_das_cluster.gpkg",
    admin_boundary_gpkg: Optional[str] = None,
    force_overwrite: bool = True,
    bws_structures_gpkg: Optional[str] = None,
    bws_gauges_gpkg: Optional[str] = None,
) -> str:
    """
    Builds the base SFINCS model domain for any specific watershed cluster.
    Incorporates subgrid river burning, rigorous boundary conditioning, and build-time QA.
    """
    model_root = Path(output_dir) / das_id
    model_root.parent.mkdir(parents=True, exist_ok=True)

    # 1. Flexible and strict cluster boundary search (Issue M4)
    if not os.path.exists(das_clusters_gpkg):
        cand = Path("data/das_clusters/sumbar_das_cluster.gpkg")
        if cand.exists():
            das_clusters_gpkg = str(cand)

    das_gdf = gpd.read_file(das_clusters_gpkg)
    das_geom, resolved_id = find_cluster_geometry(das_gdf, das_id, id_column="ID_Cluster")
    das_geom = das_geom.copy()

    # 2. Preserve Complete Hydrological Catchment (do NOT clip upstream headwaters at admin borders!)
    if admin_boundary_gpkg:
        print(f"[{das_id}] Preserving complete hydrological watershed for SFINCS physics (admin clipping reserved for final reporting).")

    temp_das_dir = Path("data/das_clusters/individual")
    temp_das_dir.mkdir(parents=True, exist_ok=True)
    temp_das_path = temp_das_dir / f"{das_id}.gpkg"
    das_geom.to_file(temp_das_path, driver="GPKG")

    # 3. Spatial Data Chipping & Catalog Preparation
    print(f"[{das_id}] Preparing optimized spatial data chip and catalog...")
    catalog_to_use, outlet_poly_path = prepare_cluster_clipped_rasters(das_id, das_geom)

    # 4. Build SFINCS model using HydroMT CLI
    hydromt_exe = Path(sys.executable).parent / "hydromt.exe"
    if not hydromt_exe.exists():
        hydromt_exe = Path(sys.executable).parent / "hydromt"
    if not hydromt_exe.exists():
        hydromt_exe = shutil.which("hydromt") or "hydromt"

    region_arg = f'{{"geom": "{temp_das_path.as_posix()}"}}'
    cmd = [
        sys.executable, "-m", "hydromt.cli.main", "build", "sfincs",
        str(model_root),
        "-r", region_arg,
        "-i", config_fn,
        "-d", catalog_to_use,
        "-vv"
    ]
    if force_overwrite:
        cmd.append("--fo")

    # Release any leaked HydroMT FileHandlers from earlier runs in this Python/Jupyter kernel
    # so Windows does not raise WinError 32 when `hydromt build --fo` unlinks hydromt.log.
    _release_hydromt_log_handlers(model_root)
    stale_log = model_root / "hydromt.log"
    if force_overwrite and stale_log.exists():
        try:
            stale_log.unlink()
        except PermissionError as exc:
            raise PermissionError(
                f"Cannot overwrite '{stale_log}' because another process holds a file lock on it "
                f"(common on Windows when another Jupyter kernel or editor has the model folder open). "
                f"Restart your Jupyter kernel (or close other open notebooks/QGIS layers using {model_root}) and re-run."
            ) from exc

    print(f"[{das_id}] Building standalone SFINCS base model at {model_root}...")
    env = _env.get_proj_env()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )
    for line in iter(proc.stdout.readline, ""):
        print(line, end="", flush=True)
    proc.stdout.close()
    retcode = proc.wait()
    if retcode != 0:
        raise subprocess.CalledProcessError(retcode, cmd)

    # 5. Outflow Boundary Conditioning (Issue H3)
    try:
        if outlet_poly_path and outlet_poly_path.exists():
            print(f"[{das_id}] Injecting outflow boundary cells (msk=3) at outlet...")
            sf = SfincsModel(root=str(model_root), mode="r+", data_libs=[catalog_to_use])
            sf.read()
            try:
                sf.setup_mask_bounds(
                    btype="outflow",
                    include_mask=str(outlet_poly_path),
                    reset_bounds=False,
                )
                sf.write_grid()
            except Exception as e:
                print(f"[{das_id}] Warning setting outflow boundary: {e}")

        # 6. Optional Hydraulic Structures / Gauges
        if bws_structures_gpkg and os.path.exists(bws_structures_gpkg):
            print(f"[{das_id}] Injecting hydraulic structures from {bws_structures_gpkg}...")
            sf = SfincsModel(root=str(model_root), mode="r+", data_libs=[catalog_to_use])
            sf.setup_structures(structures=bws_structures_gpkg, stype="weir", par1=0.6)
            sf.write_structures()

        if bws_gauges_gpkg and os.path.exists(bws_gauges_gpkg):
            print(f"[{das_id}] Injecting observation gauges from {bws_gauges_gpkg}...")
            sf = SfincsModel(root=str(model_root), mode="r+", data_libs=[catalog_to_use])
            sf.setup_observation_points(locations=bws_gauges_gpkg)
            sf.write_observation_points()
    finally:
        _release_hydromt_log_handlers(model_root)

    # 7. Build-Time QA Gates (Issues C1, H3)
    print(f"[{das_id}] Running build-time Quality Assurance gates...")
    check_roughness(model_root)
    check_boundaries(model_root)

    print(f"[{das_id}] Base model build completed and verified successfully.")
    return str(model_root)


def _apply_cnb_infiltration_to_case(
    case_dir: Path,
    sf: SfincsModel,
    cn_tif: Path,
    initial_sat_frac: float = 0.0,
    ks_recovery_mmhr: float = 0.0,
) -> None:
    """
    Replaces constant qinf with verified SFINCS v2.4.0+ Curve Number with Recovery (CNB) binary maps:
      - sfincs.smax : Maximum potential soil retention S_max [m] = (1000/CN - 10) * 0.0254
      - sfincs.seff : Initial effective storage capacity [m] = S_max * (1 - initial_sat_frac)
                      Default initial_sat_frac=0.0 (seff = S_max) when `cn_tif` already encodes the
                      target USDA-NRCS antecedent condition (AMC-II for RP2-RP10 or AMC-III via
                      cn2_to_cn3 for RP25-RP100), preventing double-counting of wet soil saturation
                      (USDA-NRCS NEH Part 630; SNI 2415:2016; Deltares SFINCS / EPA SWMM).
      - sfincs.ks   : Recovery hydraulic conductivity [mm/hr] (0.0 during single-event storm)

    Explicitly deletes sfincs.qinf, gis/qinf.tif, and sfincs.scs so legacy v2.4.0 scsfile bugs
    or zombie qinf files can never override CNB infiltration.
    """
    import rioxarray
    from hydromt_sfincs import workflows

    da_cn = rioxarray.open_rasterio(cn_tif, masked=True).squeeze("band", drop=True)
    da_cn = da_cn.raster.reproject_like(sf.grid, method="med")
    da_s_m = (workflows.cn_to_s(da_cn, sf.mask > 0) * 0.0254).astype(np.float32)

    if da_s_m.raster.res[1] < 0:
        da_s_m = da_s_m.raster.flipud()
    msk_da = sf.grid["msk"]
    if msk_da.raster.res[1] < 0:
        msk_da = msk_da.raster.flipud()
    mask_arr = msk_da.values

    smax_arr = np.nan_to_num(da_s_m.values, nan=0.0).astype(np.float32)
    avail_frac = float(np.clip(1.0 - initial_sat_frac, 0.0, 1.0))
    seff_arr = (smax_arr * avail_frac).astype(np.float32)
    ks_arr = np.full_like(smax_arr, float(ks_recovery_mmhr), dtype=np.float32)

    sf.reggrid.write_map(str(case_dir / "sfincs.smax"), data=smax_arr, mask=mask_arr, dtype="f4")
    sf.reggrid.write_map(str(case_dir / "sfincs.seff"), data=seff_arr, mask=mask_arr, dtype="f4")
    sf.reggrid.write_map(str(case_dir / "sfincs.ks"), data=ks_arr, mask=mask_arr, dtype="f4")

    for stale in [case_dir / "sfincs.qinf", case_dir / "gis" / "qinf.tif", case_dir / "sfincs.scs"]:
        if stale.exists():
            stale.unlink()

    drop_prefixes = ("qinffile", "qinf ", "qinf=", "scsfile", "smaxfile", "sefffile", "ksfile")
    inp_path = case_dir / "sfincs.inp"
    lines = [
        ln for ln in inp_path.read_text(encoding="utf-8").splitlines()
        if not ln.strip().lower().startswith(drop_prefixes)
    ]
    lines += [
        "smaxfile             = sfincs.smax",
        "sefffile             = sfincs.seff",
        "ksfile               = sfincs.ks",
    ]
    inp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    act_s = smax_arr[mask_arr > 0]
    print(f"  [CNB] Applied smax/seff/ks from {cn_tif.name} (Smax mean={act_s.mean():.3f}m, initial_sat={initial_sat_frac*100:.0f}%)")


def _apply_coastal_mhhw_to_case(case_dir: Path, sf: SfincsModel, mhhw_m: float = 0.80) -> int:
    """
    Writes native SFINCS sfincs.bnd and sfincs.bzs files applying a constant Mean Higher High Water
    (MHHW) coastal tailwater elevation (+mhhw_m) across all coastal waterlevel cells (msk == 2).
    Bypasses hydromt_sfincs 1.2.2 pandas-3 Index.is_integer incompatibility.
    """
    msk = sf.mask.values
    ys, xs = np.where(msk == 2)
    if len(xs) == 0:
        return 0

    step = max(1, len(xs) // 25)
    sel_y = sf.grid["y"].values[ys[::step]]
    sel_x = sf.grid["x"].values[xs[::step]]
    n_pts = len(sel_x)

    (case_dir / "sfincs.bnd").write_text(
        "\n".join(f"{float(x):.2f} {float(y):.2f}" for x, y in zip(sel_x, sel_y)) + "\n",
        encoding="utf-8",
    )
    tref = pd.to_datetime(sf.config["tref"], format="%Y%m%d %H%M%S")
    tstart = pd.to_datetime(sf.config["tstart"], format="%Y%m%d %H%M%S")
    tstop = pd.to_datetime(sf.config["tstop"], format="%Y%m%d %H%M%S")
    t0_s = float((tstart - tref).total_seconds())
    t1_s = float((tstop - tref).total_seconds())
    vals_str = " ".join([f"{float(mhhw_m):.3f}"] * n_pts)
    (case_dir / "sfincs.bzs").write_text(f"{t0_s:.1f} {vals_str}\n{t1_s:.1f} {vals_str}\n", encoding="utf-8")

    inp_path = case_dir / "sfincs.inp"
    lines = [
        ln for ln in inp_path.read_text(encoding="utf-8").splitlines()
        if not ln.strip().lower().startswith(("bndfile", "bzsfile"))
    ]
    lines += [
        "bndfile              = sfincs.bnd",
        "bzsfile              = sfincs.bzs",
    ]
    inp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  [MHHW] Applied coastal tidal backwater +{mhhw_m:.2f}m at {n_pts} boundary points (sfincs.bnd/sfincs.bzs)")
    return n_pts


def prepare_sfincs_direct_rain_forcing(
    das_id: str,
    return_periods: List[str] = ["rp2", "rp5", "rp10", "rp25", "rp50", "rp100"],
    base_model_dir: str = "models_sfincs_standalone",
    rainfall_dir: str = "data/rainfall",
    data_catalog_fn: Optional[str] = None,
    bws_inflow_hydrographs: Optional[str] = None,
    storm_hours: int = 24,
    recession_hours: Optional[int] = None,  # Auto-scales by basin area (24h <500km2, 36h 500-1500km2, 48h >1500km2)
    tref: str = "20240101 000000",
    tstart: str = "20240101 000000",
    amc_scale: float = 1.0,                 # Used only if infiltration_mode='qinf'
    infiltration_mode: str = "cnb",         # 'cnb' (USDA-NRCS smax/seff/ks, v2.0 standard) or 'qinf' (legacy constant)
    cn_amc2_tif: str = "data/cn_amc2_100m.tif",
    cn_amc3_tif: str = "data/cn_amc3_100m.tif",
    coastal_mhhw_m: Optional[float] = 0.80, # Coastal MHHW tailwater backwater [m] on msk=2 cells (None/0 disables)
    apply_arf: bool = False,                # Optional USWB/WMO Areal Reduction Factor for large basins (>100 km2)
    alpha: float = 0.65,                    # CFL factor (0.65 safe for pluvial-fluvial floods; ~30% faster than 0.50)
    huthresh: float = 0.02,                 # Minimum wet flow depth (m); avoids 1cm hillslope sheet-flow choking CFL dt
    viscosity: int = 0,                     # Disable horizontal eddy viscosity at 40-80m floodplain scale (~10-15% speedup)
    dtout: float = 3600.0,                  # Map output interval in seconds (zsmax unaffected)
):
    """
    Applies direct rainfall NetCDF forcing for each return period design storm (v2.0 National Standard).
    Features:
      - Dynamic recession duration scaled to active catchment area (24h / 36h / 48h) so large basins drain fully.
      - Explicit zero-rainfall padding up to tstop + volume conservation verification (Issue C2).
      - Native SFINCS v2.4.0+ CNB infiltration (smax/seff/ks) with return-period-aware antecedent moisture:
        AMC-II (25% pre-filled) for RP2-RP10 and AMC-III (50% pre-filled) for RP25-RP100.
      - Coastal MHHW (+0.80m) tailwater forcing via native sfincs.bnd/sfincs.bzs on coastal domains.
      - Optional USWB/WMO Areal Reduction Factor (ARF) for large watersheds (>100 km²).
    """
    base_root = Path(base_model_dir) / das_id
    if not base_root.exists():
        raise FileNotFoundError(f"Base model {base_root} not found. Run build_sfincs_standalone first.")

    # Infer active watershed area for dynamic recession duration & optional ARF
    sf_probe = SfincsModel(root=str(base_root), mode="r")
    sf_probe.read()
    dx_m = float(sf_probe.config.get("dx", 40.0))
    dy_m = float(sf_probe.config.get("dy", dx_m))
    active_area_km2 = float(np.sum(sf_probe.mask.values > 0) * dx_m * dy_m / 1e6)

    eff_recession = get_dynamic_recession_hours(active_area_km2) if recession_hours is None else int(recession_hours)
    total_hours = storm_hours + eff_recession
    tstart_dt = pd.to_datetime(tstart, format="%Y%m%d %H%M%S")
    tstop_dt = tstart_dt + pd.Timedelta(hours=total_hours)
    tstop_str = tstop_dt.strftime("%Y%m%d %H%M%S")

    print(
        f"[{das_id}] Active area={active_area_km2:.1f} km² | Timeline: tstart={tstart}, tstop={tstop_str} "
        f"(Duration: {total_hours}h = {storm_hours}h storm + {eff_recession}h recession)"
    )

    arf_factor = compute_wmo_arf(active_area_km2, duration_hr=float(storm_hours)) if apply_arf else 1.0
    if apply_arf and arf_factor < 0.999:
        print(f"[{das_id}] Applying WMO/USWB Areal Reduction Factor (ARF = {arf_factor:.3f}) for {active_area_km2:.1f} km² catchment.")

    for rp in return_periods:
        case_dir = Path(base_model_dir) / f"{das_id}_{rp}"
        print(f"[{das_id}][{rp}] Generating direct rainfall model configuration at {case_dir}...")

        sf = SfincsModel(root=str(base_root), mode="r")
        sf.read()

        # Simulation time configuration
        sf.set_config("tref", tref)
        sf.set_config("tstart", tstart)
        sf.set_config("tstop", tstop_str)

        # Output intervals & safe numerical speed tuning
        sf.set_config("dtout", float(dtout))
        sf.set_config("dtmaxout", float(total_hours * 3600))  # Ensure zsmax covers full run
        sf.set_config("dtwnd", min(float(sf.config.get("dtwnd", 1800)), 3600.0))
        sf.set_config("alpha", float(alpha))
        sf.set_config("huthresh", float(huthresh))
        sf.set_config("viscosity", int(viscosity))

        # Find rainfall dataset
        nc_candidates = [
            Path(rainfall_dir) / f"rainfall_{rp}_hourly.nc",
            Path(rainfall_dir) / f"rainfall_{rp}.nc",
            Path(rainfall_dir) / f"{rp}.nc",
        ]
        nc_path = next((cand for cand in nc_candidates if cand.exists()), None)
        if not nc_path:
            raise FileNotFoundError(f"Rainfall NetCDF for {rp} not found in {rainfall_dir}. Checked: {[str(c) for c in nc_candidates]}")

        ds = xr.open_dataset(nc_path)
        var_name = "precip" if "precip" in ds.data_vars else next(
            (v for v in ds.data_vars if "time" in ds[v].dims), list(ds.data_vars.keys())[0]
        )
        precip_da = ds[var_name]

        # Standardize coordinates & Detect CRS (Issue H4)
        dims = list(precip_da.dims)
        is_geographic = False
        if "lat" in dims and "lon" in dims:
            is_geographic = True
            precip_da = precip_da.transpose("time", "lat", "lon")
            precip_da.raster.set_crs(4326)
        elif "y" in dims and "x" in dims:
            precip_da = precip_da.transpose("time", "y", "x")
            if precip_da.raster.crs is None:
                precip_da.raster.set_crs(sf.crs)

        # Check Bounding Box Coverage (Issue H4)
        # Note: HydroMT SfincsModel.bbox is already in EPSG:4326 (lon/lat); use sf.grid.raster.bounds for projected CRS.
        if is_geographic:
            m_minlon, m_minlat, m_maxlon, m_maxlat = sf.bbox
            rain_minlon, rain_minlat, rain_maxlon, rain_maxlat = precip_da.raster.bounds
            if not (rain_minlon <= m_minlon and rain_maxlon >= m_maxlon and rain_minlat <= m_minlat and rain_maxlat >= m_maxlat):
                print(f"[WARNING] Rainfall bounding box [{rain_minlon:.2f}, {rain_minlat:.2f}, {rain_maxlon:.2f}, {rain_maxlat:.2f}] does not fully contain model domain [{m_minlon:.2f}, {m_minlat:.2f}, {m_maxlon:.2f}, {m_maxlat:.2f}]!")

        # Reproject to SFINCS computational grid
        precip_reprojected = precip_da.raster.reproject_like(sf.grid, method="nearest")

        # QA Check on active cells (Issue H4)
        active_mask = (sf.mask.values > 0)
        event_total_arr = precip_reprojected.sum(dim="time").values
        active_event_totals = event_total_arr[active_mask]
        nan_count = int(np.isnan(active_event_totals).sum())
        if nan_count > 0:
            raise ValueError(f"Rainfall contains {nan_count} NaN values within active model cells! Rainfall data is incomplete.")

        zero_rain_count = int((active_event_totals == 0.0).sum())
        zero_rain_pct = (zero_rain_count / max(len(active_event_totals), 1)) * 100.0
        if zero_rain_pct > 0.5:
            print(f"[WARNING] {zero_rain_pct:.2f}% of active catchment cells receive zero rainfall.")

        precip_clean = precip_reprojected.fillna(0.0) * arf_factor

        # Pad rainfall series with zero-intensity timesteps up to tstop (Issue C2)
        time_coords = pd.date_range(start=tstart_dt, periods=total_hours + 1, freq="1h")
        precip_padded = precip_clean.reindex(time=time_coords, fill_value=0.0)

        # Volume Conservation QA Check (Issue C2)
        design_depth_mm = float(precip_clean.sum(dim="time").mean().values)
        integrated_padded_depth_mm = float(precip_padded.sum(dim="time").mean().values)
        vol_diff_pct = abs(design_depth_mm - integrated_padded_depth_mm) / max(design_depth_mm, 1e-5) * 100.0
        if vol_diff_pct > 1.0:
            raise AssertionError(f"Forcing volume check failed: padded rainfall differs from design depth by {vol_diff_pct:.2f}% (> 1%)!")

        print(f"[{das_id}][{rp}] Forcing volume check passed: domain-mean design depth = {design_depth_mm:.1f} mm, padded = {integrated_padded_depth_mm:.1f} mm")

        precip_out = precip_padded.rename("precip_2d")
        y_dim, x_dim = precip_out.raster.dims
        precip_out = precip_out.rename({y_dim: "y", x_dim: "x"})

        sf.set_forcing(precip_out, name="precip_2d")

        if bws_inflow_hydrographs and os.path.exists(bws_inflow_hydrographs):
            print(f"[{das_id}][{rp}] Applying upstream discharge forcing...")

        # Write to case directory
        sf.set_root(str(case_dir), mode="w+")
        sf.write()

        # Infiltration scheme: modern CNB (USDA-NRCS Curve Number with recovery) vs legacy constant qinf
        # Because cn_amc2_100m.tif (RP2-RP10) and cn_amc3_100m.tif (RP25-RP100, via cn2_to_cn3) ALREADY
        # encode USDA-NRCS NEH Part 630 / SNI 2415:2016 antecedent moisture (AMC-II vs AMC-III),
        # initial_sat_frac=0.0 sets seff = S_max(AMC) exactly ONCE without double-counting saturation.
        rp_digits = "".join(ch for ch in str(rp) if ch.isdigit())
        rp_num = int(rp_digits) if rp_digits else 100
        use_amc3 = rp_num >= 25
        cn_path = Path(cn_amc3_tif if use_amc3 else cn_amc2_tif)
        if str(infiltration_mode).lower() == "cnb" and cn_path.exists():
            _apply_cnb_infiltration_to_case(case_dir, sf, cn_path, initial_sat_frac=0.0)
        else:
            if str(infiltration_mode).lower() == "cnb":
                print(f"  [NOTE] CN raster {cn_path} not found; retaining constant qinf from base model.")
            qinf_path = case_dir / "sfincs.qinf"
            if qinf_path.exists() and amc_scale is not None and amc_scale < 1.0:
                qinf_arr = np.fromfile(qinf_path, dtype=np.float32)
                qinf_amc = (qinf_arr * amc_scale).astype(np.float32)
                qinf_amc.tofile(qinf_path)
                print(f"[{das_id}][{rp}] Scaled soil infiltration to AMC-III (factor: {amc_scale:.2f}x; mean qinf: {np.mean(qinf_arr):.3f} -> {np.mean(qinf_amc):.3f} mm/hr)")

        # Coastal MHHW tailwater forcing (+0.80m default on coastal msk=2 cells)
        if coastal_mhhw_m is not None and float(coastal_mhhw_m) > 0.0:
            _apply_coastal_mhhw_to_case(case_dir, sf, mhhw_m=float(coastal_mhhw_m))

        _release_hydromt_log_handlers(case_dir)
        _release_hydromt_log_handlers(base_root)
        print(f"[{das_id}][{rp}] Case configuration ready at {case_dir}.")


def run_sfincs_model(
    das_id: str,
    rp: str,
    base_model_dir: str = "models_sfincs_standalone",
    sfincs_exe: Optional[str] = None,
):
    """
    Executes the SFINCS hydrodynamic simulation engine with live terminal progress bar.
    """
    import re
    from tqdm.auto import tqdm

    model_dir = Path(base_model_dir) / f"{das_id}_{rp}"
    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory {model_dir} not found.")

    candidates = [
        sfincs_exe,
        os.environ.get("SFINCS_PATH"),
        str(Path("bin/sfincs.exe").resolve()),
        str(Path("bin/sfincs").resolve()),
        str(Path("env-sfincs/Scripts/sfincs.exe").resolve()),
        "sfincs.exe",
        "sfincs",
    ]
    resolved_exe = next((cand for cand in candidates if cand and (os.path.exists(cand) or shutil.which(cand) is not None)), None)

    log_path = model_dir / "sfincs_run.log"
    print(f"[{das_id}][{rp}] Running SFINCS hydrodynamic engine (Logging to {log_path})...")

    # Remove stale results file
    map_nc = model_dir / "sfincs_map.nc"
    if map_nc.exists():
        try:
            os.remove(map_nc)
        except OSError:
            pass

    if resolved_exe:
        cmd = [resolved_exe]
    elif shutil.which("udocker"):
        abs_path = os.path.abspath(str(model_dir))
        cmd = ["udocker", "--allow-root", "run", "--rm", "-v", f"{abs_path}:/data", "deltares/sfincs-cpu:latest"]
    elif shutil.which("docker"):
        abs_path = os.path.abspath(str(model_dir))
        cmd = ["docker", "run", "--rm", "-v", f"{abs_path}:/data", "deltares/sfincs-cpu:latest"]
    else:
        raise FileNotFoundError("No SFINCS simulation solver found! Please place sfincs.exe inside 'bin/sfincs.exe'.")

    env = _env.get_proj_env()
    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            cmd,
            cwd=str(model_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=env,
        )

        pbar = tqdm(
            total=100,
            desc=f"[{das_id}][{rp}] SFINCS Simulation",
            unit="%",
            bar_format="{l_bar}{bar}| {n:.0f}% [{elapsed}<{remaining}, {rate_fmt}]"
        )

        last_pct = 0
        pct_regex = re.compile(r"(\d+)\s*%\s*complete")

        for line in iter(proc.stdout.readline, ""):
            log_file.write(line)
            log_file.flush()

            match = pct_regex.search(line)
            if match:
                current_pct = int(match.group(1))
                if current_pct > last_pct:
                    pbar.update(current_pct - last_pct)
                    last_pct = current_pct

        proc.stdout.close()
        proc.wait()

        if last_pct < 100 and proc.returncode == 0:
            pbar.update(100 - last_pct)
        pbar.close()

        if proc.returncode != 0:
            err_snippet = ""
            if log_path.exists():
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as lf:
                        lines = lf.readlines()
                        err_snippet = "".join(lines[-35:])
                except Exception:
                    pass
            print(f"\n❌ SFINCS Simulation Failed for [{das_id}][{rp}] (Exit Code {proc.returncode})!\n"
                  f"--- Tail of sfincs_run.log ---\n{err_snippet}\n"
                  f"--------------------------------", file=sys.stderr)
            raise subprocess.CalledProcessError(proc.returncode, cmd, output=err_snippet)

    print(f"[{das_id}][{rp}] Simulation finished successfully.")


def _clip_and_mask_raster(
    raster_path: str,
    geom_mask: gpd.GeoDataFrame,
    lake_gpkg: Optional[str] = "data/lake.gpkg",
):
    """
    Clips a raster precisely to the cluster polygon boundary and masks out permanent lake water bodies.
    """
    with rasterio.open(raster_path) as src:
        if geom_mask.crs != src.crs:
            geom_mask = geom_mask.to_crs(src.crs)
        shapes = [geom for geom in geom_mask.geometry if geom.is_valid]

        existing_tags = src.tags()
        out_image, out_transform = rasterio.mask.mask(src, shapes, crop=False)
        out_meta = src.meta.copy()

        if lake_gpkg and os.path.exists(lake_gpkg):
            try:
                lake_gdf = gpd.read_file(lake_gpkg)
                if not lake_gdf.empty:
                    if lake_gdf.crs != src.crs:
                        lake_gdf = lake_gdf.to_crs(src.crs)

                    union_das = geom_mask.geometry.union_all() if hasattr(geom_mask.geometry, "union_all") else geom_mask.geometry.unary_union
                    lake_sub = lake_gdf[lake_gdf.intersects(union_das)]

                    if not lake_sub.empty:
                        lake_shapes = [geom for geom in lake_sub.geometry if geom.is_valid]
                        from rasterio.io import MemoryFile
                        mem_meta = out_meta.copy()
                        mem_meta.update({"height": out_image.shape[1], "width": out_image.shape[2], "transform": out_transform})
                        with MemoryFile() as memfile:
                            with memfile.open(**mem_meta) as mem_dst:
                                mem_dst.write(out_image)
                            with memfile.open() as mem_src:
                                out_image, out_transform = rasterio.mask.mask(mem_src, lake_shapes, invert=True, crop=False)
            except Exception as e:
                print(f"Note: Lake masking skipped: {e}")

        out_meta.pop("blockxsize", None)
        out_meta.pop("blockysize", None)
        out_meta.pop("tiled", None)
        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
            "compress": "lzw"
        })

    with rasterio.open(raster_path, "w", **out_meta) as dst:
        dst.write(out_image)
        if existing_tags:
            dst.update_tags(**existing_tags)



def refine_flood_hazard_raster(
    depth_tif: str,
    dep_path: Union[str, Path],
    hmin: float = 0.15,
    island_mmu_px: Optional[int] = None,   # Optional pixel override; defaults to island_mmu_ha (0.09 ha = 30m x 30m)
    hole_mmu_px: Optional[int] = None,     # Optional pixel override; defaults to hole_mmu_ha (1.0 ha)
    island_mmu_ha: float = 0.09,           # Resolution-independent 30m x 30m (0.09 ha) minimum flood patch size
    hole_mmu_ha: float = 1.0,              # Resolution-independent 1.0 ha hydrostatic enclosed void limit
    min_hole_ha: float = 0.09,             # Resolution-independent 30m x 30m (0.09 ha = 1 FABDEM pixel) sub-DEM pinhole fill
    bridge_radius: int = 3,    # Circular morphological closing radius (px) across narrow road cuts & bunds
    smooth_sigma: float = 1.0, # Boundary anti-aliasing sigma (px)
    h_connect: float = 0.15,   # 0.15m core depth threshold for hydraulic connectivity bridging (aligned with hmin)
    freeboard_m: float = 0.0,  # Strict deterministic default = 0.0m (no invented water; use only for explicit DEM uncertainty sensitivity envelopes)
    max_ext_dist_m: float = 0.0,      # Max outward WSE bilinear edge-NaN recovery distance [m] (default 80.0m = 1x dx in postprocess)
    max_ext_slope_deg: float = 5.0,   # Slope ceiling [deg] if optional uncertainty freeboard sensitivity is enabled
    depth_offset: float = 0.0,
    depth_scale: float = 1.0,
    cosmetic: bool = False,
    out_display_tif: Optional[str] = None,
    max_slope_deg: Optional[float] = 8.0, # Prunes narrow hillslope sheet noise (>= 8 deg, Van Zuidam 1985) outside RBI rivers
    rivers_gpkg: Optional[str] = "data/rivers.gpkg",
) -> None:
    """
    Refines raw downscaled flood depth rasters while strictly respecting hydrostatics (Zs - DEM >= hmin)
    and enforcing a 4-connected 30m x 30m (0.09 ha, native FABDEM pixel footprint) minimum feature floor.

    When `max_ext_dist_m > 0` with `freeboard_m = 0.0` (Strict Scientific Standard: `max_ext_dist_m <= 1.0 * dx`),
    purely recovers bilinear edge-NaN dropouts where the simulated water surface strictly exceeds terrain
    by at least `hmin` (default 0.15m / 15 cm), without adding synthetic water elevation or volume.
    """
    depth_p = Path(depth_tif)
    # 1. Preserve raw depth raster (Issue M7)
    raw_depth_path = depth_p.parent / f"{depth_p.stem}_raw{depth_p.suffix}"
    if not raw_depth_path.exists():
        shutil.copy2(depth_p, raw_depth_path)
    if depth_p.name == "flood_depth_10m.tif":
        legacy_raw = depth_p.parent / "flood_depth_10m_raw.tif"
        if not legacy_raw.exists():
            shutil.copy2(depth_p, legacy_raw)

    with rasterio.open(depth_tif) as src_d:
        raw_depth = src_d.read(1)
        profile = src_d.profile.copy()
        nodata_d = src_d.nodata
        raster_bounds = src_d.bounds
        raster_crs = src_d.crs

    # Convert resolution-independent hectare MMU targets to pixel counts when pixel overrides are not given
    px_w = abs(float(profile["transform"][0]))
    px_h = abs(float(profile["transform"][4]))
    px_area_m2 = max(px_w * px_h, 1.0)
    if hole_mmu_px is None:
        hole_mmu_px = int(round((hole_mmu_ha * 10000.0) / px_area_m2)) if hole_mmu_ha > 0 else 0
    if island_mmu_px is None:
        island_mmu_px = int(round((island_mmu_ha * 10000.0) / px_area_m2)) if island_mmu_ha > 0 else 0
    min_hole_px = int(round((min_hole_ha * 10000.0) / px_area_m2)) if min_hole_ha > 0 else 0

    with rasterio.open(str(dep_path)) as src_dem:
        dem_nodata = src_dem.nodata
        if src_dem.shape == raw_depth.shape:
            dem = src_dem.read(1)
        else:
            dem = np.zeros_like(raw_depth, dtype=np.float32)
            rasterio.warp.reproject(
                source=rasterio.band(src_dem, 1),
                destination=dem,
                src_transform=src_dem.transform,
                src_crs=src_dem.crs,
                dst_transform=profile["transform"],
                dst_crs=profile["crs"],
                resampling=rasterio.warp.Resampling.bilinear,
            )

    # Clean DEM nodata and non-finite values (Issues M1, C3)
    if dem_nodata is not None:
        dem = np.where(dem == dem_nodata, np.nan, dem)
    dem = np.where((dem > 3.0e38) | (~np.isfinite(dem)), np.nan, dem)

    # Slope calculation for steep unchannelized hillslope noise pruning
    if max_slope_deg is not None and max_slope_deg > 0:
        res_x = abs(profile["transform"][0])
        res_y = abs(profile["transform"][4])
        gy, gx = np.gradient(dem, res_y, res_x)
        slope_deg = np.degrees(np.arctan(np.sqrt(gx**2 + gy**2)))
    else:
        slope_deg = None

    # Valid mask for raw wet cells
    valid_mask = np.isfinite(raw_depth)
    if nodata_d is not None and np.isfinite(nodata_d):
        valid_mask &= (raw_depth != nodata_d)
    raw_wet_mask = valid_mask & (raw_depth >= hmin) & np.isfinite(dem)

    # Prune narrow unchannelized hillslope runoff ribbons (width <= 30m, slope >= max_slope_deg)
    # while ALWAYS protecting mapped RBI river corridors (flash-flood / banjir bandang channels)
    if slope_deg is not None:
        river_corridor_mask = np.zeros_like(raw_wet_mask, dtype=bool)
        if rivers_gpkg and os.path.exists(rivers_gpkg):
            try:
                from rasterio.features import rasterize
                riv_gdf = gpd.read_file(rivers_gpkg, bbox=tuple(raster_bounds))
                if not riv_gdf.empty:
                    if str(riv_gdf.crs) != str(raster_crs):
                        riv_gdf = riv_gdf.to_crs(raster_crs)
                    riv_bufs = riv_gdf.geometry.buffer(30.0)
                    river_corridor_mask = rasterize(
                        [(g, 1) for g in riv_bufs if g is not None and not g.is_empty],
                        out_shape=raw_wet_mask.shape,
                        transform=profile["transform"],
                        fill=0,
                        dtype="uint8",
                    ).astype(bool)
            except Exception:
                pass
        dist_wet = ndimage.distance_transform_edt(raw_wet_mask)
        steep_gully = raw_wet_mask & (slope_deg >= max_slope_deg) & (dist_wet <= 1.5) & (~river_corridor_mask)
        raw_wet_mask = raw_wet_mask & (~steep_gully)

    # 0b. Optional Hydrostatically Connected Natural Floodplain Margin (Option B v2.0 Standard)
    # Recovers bilinear 40m/80m edge-NaN strips where DEM < Zs and adds a conservative, distance-decaying
    # FABDEM vertical uncertainty margin (+freeboard_m) strictly gated to connected flat floodplains.
    struct_8 = np.ones((3, 3), dtype=bool)
    ext_depth_field = None
    core_wet_mask = raw_wet_mask.copy()
    if max_ext_dist_m is not None and max_ext_dist_m > 0.0 and np.any(raw_wet_mask):
        eff_slope = slope_deg
        if eff_slope is None:
            gy, gx = np.gradient(dem, px_h, px_w)
            eff_slope = np.degrees(np.arctan(np.sqrt(gx**2 + gy**2)))
        zs_core = np.where(raw_wet_mask & np.isfinite(dem), raw_depth + dem, np.nan)
        dist_to_wet_px, ind_ext = ndimage.distance_transform_edt(
            np.isnan(zs_core), return_distances=True, return_indices=True
        )
        zs_smooth = ndimage.gaussian_filter(zs_core[tuple(ind_ext)], sigma=2.0)
        dist_to_wet_m = dist_to_wet_px * max(px_w, px_h)

        decay = np.clip(1.0 - (dist_to_wet_m / max(float(max_ext_dist_m), 1.0)), 0.0, 1.0)
        eff_freeboard = np.where(eff_slope < float(max_ext_slope_deg), max(float(freeboard_m), 0.0) * decay, 0.0)
        ext_depth_field = (zs_smooth + eff_freeboard) - dem

        slope_strict_lim = float(max_slope_deg) if (max_slope_deg is not None and max_slope_deg > 0) else 8.0
        allow_ext = (
            np.isfinite(dem)
            & (dist_to_wet_m <= float(max_ext_dist_m))
            & (
                (((zs_smooth - dem) >= hmin) & (eff_slope < slope_strict_lim))
                | ((ext_depth_field >= hmin) & (eff_slope < float(max_ext_slope_deg)))
            )
        )
        potential = raw_wet_mask | allow_ext
        lbl_pot, n_pot = ndimage.label(potential, structure=struct_8)
        if n_pot > 0:
            core_labels = np.unique(lbl_pot[raw_wet_mask])
            core_labels = core_labels[core_labels > 0]
            seed_wet_mask = np.isin(lbl_pot, core_labels)
        else:
            seed_wet_mask = raw_wet_mask.copy()
    else:
        seed_wet_mask = raw_wet_mask.copy()

    # 1. Hydraulic Connectivity Filtering & Morphological Closing
    if bridge_radius > 0:
        if h_connect > hmin and ext_depth_field is None:
            labeled_raw, num_features = ndimage.label(seed_wet_mask, structure=struct_8)
            if num_features > 0:
                max_depth_per_patch = ndimage.maximum(
                    np.nan_to_num(raw_depth, nan=0.0), labeled_raw, range(1, num_features + 1)
                )
                lookup_max = np.concatenate([[0.0], max_depth_per_patch])
                patch_max = lookup_max[labeled_raw]
                bridging_seed_mask = seed_wet_mask & (patch_max >= h_connect)
            else:
                bridging_seed_mask = seed_wet_mask.copy()
        else:
            bridging_seed_mask = seed_wet_mask.copy()

        y, x = np.ogrid[-bridge_radius:bridge_radius + 1, -bridge_radius:bridge_radius + 1]
        kernel = (x ** 2 + y ** 2) <= bridge_radius ** 2
        closed_mask = ndimage.binary_closing(bridging_seed_mask, structure=kernel)
        closed_mask |= seed_wet_mask
    else:
        closed_mask = seed_wet_mask.copy()

    # 2. Size-Limited Enclosed Hole Detection (<= hole_mmu_px, not touching raster border)
    if hole_mmu_px > 0:
        dry_mask = ~closed_mask
        labeled_dry, num_features = ndimage.label(dry_mask, structure=struct_8)

        border_labels = set(np.unique(labeled_dry[0, :])) | \
                        set(np.unique(labeled_dry[-1, :])) | \
                        set(np.unique(labeled_dry[:, 0])) | \
                        set(np.unique(labeled_dry[:, -1]))
        border_labels.discard(0)

        dry_sizes = ndimage.sum(dry_mask, labeled_dry, range(1, num_features + 1))
        dry_sizes_lookup = np.concatenate([[0], dry_sizes])
        patch_sizes = dry_sizes_lookup[labeled_dry]

        is_border_patch = np.isin(labeled_dry, list(border_labels))
        small_enclosed_holes = (patch_sizes <= hole_mmu_px) & (~is_border_patch) & (labeled_dry > 0)
        filled_mask = closed_mask | small_enclosed_holes
    else:
        filled_mask = closed_mask.copy()

    # 3. Boundary Anti-Aliasing (Signed distance transform)
    if smooth_sigma > 0:
        dist_in = ndimage.distance_transform_edt(filled_mask)
        dist_out = ndimage.distance_transform_edt(~filled_mask)
        signed_dist = dist_in - dist_out
        smooth_dist = ndimage.gaussian_filter(signed_dist, sigma=smooth_sigma)
        smooth_mask = smooth_dist >= 0.0
    else:
        smooth_mask = filled_mask.copy()

    # 4. Foreground MMU Sieve (Prune isolated noise patches < island_mmu_px)
    if island_mmu_px > 0:
        labeled_wet, num_wet = ndimage.label(smooth_mask, structure=struct_8)
        wet_sizes = ndimage.sum(smooth_mask, labeled_wet, range(1, num_wet + 1))
        wet_sizes_lookup = np.concatenate([[0], wet_sizes])
        wet_patch_sizes = wet_sizes_lookup[labeled_wet]
        candidate_mask = smooth_mask & (wet_patch_sizes >= island_mmu_px)
    else:
        candidate_mask = smooth_mask

    # 5. Strictly Hydrostatic Topographic Depth Reconstruction (Zs - DEM >= hmin)
    # Cells where terrain is ABOVE the interpolated water level, or where reconstructed depth is
    # below hmin (default 0.15m / 15 cm minimum flood hazard threshold), remain STRICTLY DRY (NaN)
    # so shallow pixel noise is never artificially inflated up to hmin!
    if ext_depth_field is not None:
        depth_phys = ext_depth_field
        # Keep true simulated core depth on raw_wet_mask; smooth tapered depth_ext on connected fringe >= hmin
        physically_submerged = np.isfinite(depth_phys) & (depth_phys >= hmin)
        final_mask = candidate_mask & np.isfinite(dem) & (core_wet_mask | physically_submerged)
        depth_reconstructed = np.where(
            core_wet_mask & final_mask,
            raw_depth,
            np.where(final_mask, depth_phys, np.nan),
        ).astype(np.float32)
    else:
        zs = np.where(raw_wet_mask & np.isfinite(dem), raw_depth + dem, np.nan)
        nan_mask = np.isnan(zs)
        if np.any(~nan_mask):
            ind = ndimage.distance_transform_edt(nan_mask, return_distances=False, return_indices=True)
            zs_infilled = zs[tuple(ind)]
            depth_phys = zs_infilled - dem
        else:
            depth_phys = np.full_like(dem, np.nan)

        physically_submerged = np.isfinite(depth_phys) & (depth_phys >= hmin)
        final_mask = candidate_mask & np.isfinite(dem) & (raw_wet_mask | physically_submerged)
        depth_reconstructed = np.where(final_mask, depth_phys, np.nan).astype(np.float32)

    if smooth_sigma > 0:
        depth_raw_recon = np.where(final_mask, depth_reconstructed, 0.0)
        weight = final_mask.astype(float)
        smooth_w = ndimage.gaussian_filter(weight, sigma=smooth_sigma)
        smooth_d = ndimage.gaussian_filter(depth_raw_recon, sigma=smooth_sigma)
        with np.errstate(divide="ignore", invalid="ignore"):
            norm_depth = np.where(final_mask, smooth_d / np.maximum(smooth_w, 1e-5), np.nan).astype(np.float32)
    else:
        norm_depth = depth_reconstructed

    # Calibration scaling (default 1.0 / 0.0; discouraged except for explicit sensitivity experiments)
    calibrated_depth = norm_depth * depth_scale + depth_offset
    # Strictly remove any pixel below minimum flood disaster depth hmin (never clamp < hmin upward!)
    final_depth = np.where(
        final_mask & np.isfinite(calibrated_depth) & (calibrated_depth >= hmin),
        calibrated_depth,
        np.nan,
    ).astype(np.float32)

    # 6. Post-Hydrostatic Sub-DEM Pinhole & Scattered Speckle Cleanup (minimum feature floor: 30m x 30m = 0.09 ha)
    # Step 5 terrain intersection can punch tiny sub-pixel pinholes (< 30m x 30m, smaller than 1 native FABDEM pixel)
    # and detach tiny scattered wet fragments along edges. Using 4-connectivity (rook neighbors) eliminates both
    # isolated specks and thin diagonal single-pixel bridges/pinholes cleanly in QGIS without drowning >= 30x30m hills!
    struct_4 = ndimage.generate_binary_structure(2, 1)
    if min_hole_px > 1:
        wet_now = np.isfinite(final_depth) & (final_depth >= hmin)
        dry_now = ~wet_now
        lbl_dry, n_dry = ndimage.label(dry_now, structure=struct_4)
        if n_dry > 0:
            b_lbls = (
                set(np.unique(lbl_dry[0, :]))
                | set(np.unique(lbl_dry[-1, :]))
                | set(np.unique(lbl_dry[:, 0]))
                | set(np.unique(lbl_dry[:, -1]))
            )
            b_lbls.discard(0)
            d_sizes = ndimage.sum(dry_now, lbl_dry, range(1, n_dry + 1))
            d_lookup = np.concatenate([[0], d_sizes])
            # Fill strictly sub-sensor pinholes (< min_hole_px, e.g., < 9 px = < 30m x 30m);
            # features >= 30m x 30m remain strictly dry if DEM >= Zs!
            sub_dem_pinholes = (
                (d_lookup[lbl_dry] < min_hole_px)
                & (~np.isin(lbl_dry, list(b_lbls)))
                & (lbl_dry > 0)
            )
            if np.any(sub_dem_pinholes) and np.any(wet_now):
                ind_nn = ndimage.distance_transform_edt(~wet_now, return_distances=False, return_indices=True)
                final_depth = np.where(sub_dem_pinholes, final_depth[tuple(ind_nn)], final_depth).astype(np.float32)

    if island_mmu_px > 0:
        wet_now = np.isfinite(final_depth) & (final_depth >= hmin)
        lbl_wet, n_wet = ndimage.label(wet_now, structure=struct_4)
        if n_wet > 0:
            w_sizes = ndimage.sum(wet_now, lbl_wet, range(1, n_wet + 1))
            w_lookup = np.concatenate([[0], w_sizes])
            keep_wet = wet_now & (w_lookup[lbl_wet] >= island_mmu_px)
            final_depth = np.where(keep_wet, final_depth, np.nan).astype(np.float32)

    # 7. Write Output GeoTIFF (and optional display raster if cosmetic=True)
    profile.update(dtype=rasterio.float32, count=1, nodata=np.nan, compress="lzw")
    res_m = abs(profile["transform"][0])
    hole_mmu_ha_eff = round((hole_mmu_px * (res_m ** 2)) / 10000.0, 2)
    min_hole_ha_eff = round((min_hole_px * (res_m ** 2)) / 10000.0, 2)

    target_write_path = depth_tif
    with rasterio.open(target_write_path, "w", **profile) as dst:
        dst.write(final_depth, 1)
        desc = "Refined Physical Flood Depth 10m (Hydrostatically Constrained & 30x30m MMU Filtered)"
        dst.set_band_description(1, desc)
        dst.update_tags(
            hmin=str(hmin),
            hole_mmu_px=str(hole_mmu_px),
            island_mmu_px=str(island_mmu_px),
            min_hole_px=str(min_hole_px),
            mmu_scale="1:50000",
            mmu_standard=f"1:50,000 cartographic legibility 2x2mm ({hole_mmu_ha_eff:.2f} ha) & 30m FABDEM floor ({min_hole_ha_eff:.2f} ha); SNI 6502.3:2010 / Peraturan BIG No. 18/2021 sliver cleanup",
            bridge_radius=str(bridge_radius),
            smooth_sigma=str(smooth_sigma),
            h_connect=str(h_connect),
            freeboard_m=str(freeboard_m),
            max_ext_dist_m=str(max_ext_dist_m),
            max_ext_slope_deg=str(max_ext_slope_deg),
            max_slope_deg=str(max_slope_deg),
            cosmetic=str(cosmetic),
            depth_scale=str(depth_scale),
            depth_offset=str(depth_offset),
        )

    if cosmetic and out_display_tif and str(out_display_tif) != str(depth_tif):
        shutil.copy2(depth_tif, out_display_tif)

    print(f"[OK] Refined physical depth written to: {target_write_path} (bridge_radius={bridge_radius}, smooth_sigma={smooth_sigma}, min_feature_px={min_hole_px}/{island_mmu_px}, hole_mmu_px={hole_mmu_px} [{hole_mmu_ha_eff:.2f} ha])")


def format_output_cluster_id(das_id: str) -> str:
    """Format cluster ID for file naming: 'DAS_101' -> 'DAS101', 'DAS_108_A' -> 'DAS108_A'."""
    clean = str(das_id).strip()
    if clean.upper().startswith("DAS_"):
        return "DAS" + clean[4:]
    elif clean.upper().startswith("DAS"):
        return clean.upper()
    return f"DAS{clean}"


def format_output_rp(rp: str) -> str:
    """Format return period for file naming: 'rp100' -> 'RP100', '100' -> 'RP100'."""
    clean = str(rp).strip()
    if clean.lower().startswith("rp"):
        return f"RP{clean[2:]}"
    return f"RP{clean}"


def postprocess_sfincs_hazard(
    das_id: str,
    rp: str,
    base_model_dir: str = "models_sfincs_standalone",
    output_maps_dir: str = "outputs",
    das_clusters_gpkg: str = "data/das_clusters/sumbar_das_cluster.gpkg",
    lake_gpkg: str = "data/lake.gpkg",
    hmin: float = 0.15,                    # 15 cm minimum flood hazard depth (Wing et al., 2018; Sampson et al., 2015; Bates et al., 2021)
    reproj_method: str = "bilinear",       # Continuous bilinear water level interpolation (removes stair-step ridges)
    island_mmu_px: Optional[int] = None,   # Optional pixel override; defaults to island_mmu_ha (0.09 ha = 30m x 30m)
    hole_mmu_px: Optional[int] = None,     # Optional pixel override; defaults to hole_mmu_ha (1.0 ha)
    island_mmu_ha: float = 0.09,           # Native 30m x 30m (0.09 ha = 1 FABDEM pixel) minimum flood patch floor (Hawker et al., 2022)
    hole_mmu_ha: float = 1.0,              # 1.0 ha (2mm x 2mm @ 1:50,000 legibility) hydrostatic enclosed void limit
    min_hole_ha: float = 0.09,             # Native 30m x 30m (0.09 ha) sub-DEM pinhole fill
    bridge_radius: int = 3,                # 3 px (30m) circular morphological closing matching Indonesian road/embankment widths (10-30m)
    smooth_sigma: float = 1.0,             # 1.0 px Euclidean signed-distance boundary anti-aliasing (Borgefors, 1986)
    h_connect: float = 0.15,               # 0.15m core depth threshold for hydraulic connectivity bridging (aligned with hmin)
    freeboard_m: float = 0.0,              # Strict deterministic default = 0.0m (no synthetic water elevation added!)
    max_ext_dist_m: float = 80.0,          # 80m (1.0 x dx) pure bilinear edge-NaN recovery strictly where Zs - DEM >= hmin (40m on 40m grid)
    max_ext_slope_deg: float = 5.0,        # Slope ceiling [deg] if optional DEM uncertainty freeboard sensitivity is enabled
    max_slope_deg: Optional[float] = 8.0,  # Prunes narrow hillslope sheet noise (>= 8 deg, Van Zuidam 1985; RBI rivers always protected)
    depth_offset: float = 0.0,
    depth_scale: float = 1.0,
    cosmetic: bool = False,
    classification_method: str = "depth",
    low_thresh: float = 0.76,
    high_thresh: float = 1.50,
    rivers_gpkg: Optional[str] = "data/rivers.gpkg",
):
    """
    Downscales SFINCS water levels to high-resolution topography,
    applies physically grounded depth reconstruction,
    clips strictly to cluster boundary, masks out permanent lake bodies,
    and classifies flood hazard according to Perka BNPB No. 2/2012.
    """
    model_dir = Path(base_model_dir) / f"{das_id}_{rp}"
    map_nc = model_dir / "sfincs_map.nc"
    if not map_nc.exists():
        raise FileNotFoundError(f"Results file {map_nc} not found.")

    sf = SfincsModel(str(model_dir), mode="r")
    sf.read_results()

    # Peak water surface elevation over full simulation
    if "timemax" in sf.results["zsmax"].dims:
        zsmax = sf.results["zsmax"].max(dim="timemax")
    else:
        zsmax = sf.results["zsmax"]

    dep_candidates = [
        model_dir / "subgrid" / "dep_subgrid.tif",
        Path(base_model_dir) / das_id / "subgrid" / "dep_subgrid.tif",
        Path("temp/chips") / das_id / "dem_chip.tif",
        find_elevation_dem_path(),
    ]
    dep_path = next((cand for cand in dep_candidates if cand and Path(cand).exists()), None)
    if not dep_path:
        raise FileNotFoundError(f"High-resolution topography not found for {das_id}.")

    print(f"[{das_id}][{rp}] Downscaling flood depths with topography: {dep_path.name} (reproj_method={reproj_method})")
    dep = hydromt.open_raster(str(dep_path.resolve()))

    das_tag = format_output_cluster_id(das_id)
    rp_tag = format_output_rp(rp)
    prefix = f"{das_tag}_{rp_tag}"

    out_dir = Path(output_maps_dir) / das_id / rp
    out_dir.mkdir(parents=True, exist_ok=True)
    depth_tif = str(out_dir / f"{prefix}_Flood_Depth.tif")
    raw_depth_tif = str(out_dir / f"{prefix}_Flood_Depth_raw.tif")
    hazard_tif = str(out_dir / f"{prefix}_FloodHazard_Classes.tif")
    fhi_tif = str(out_dir / f"{prefix}_FloodHazard_Index.tif")
    display_tif = str(out_dir / f"{prefix}_Flood_Depth_display.tif") if cosmetic else None

    # Downscale to raw depth
    utils.downscale_floodmap(
        zsmax=zsmax,
        dep=dep,
        hmin=hmin,
        reproj_method=reproj_method,
        floodmap_fn=raw_depth_tif,
    )
    shutil.copy2(raw_depth_tif, depth_tif)

    # Clip to catchment boundary
    if not os.path.exists(das_clusters_gpkg):
        cand = Path("data/das_clusters/sumbar_das_cluster.gpkg")
        if cand.exists():
            das_clusters_gpkg = str(cand)

    das_geom = None
    if os.path.exists(das_clusters_gpkg):
        das_gdf = gpd.read_file(das_clusters_gpkg)
        das_geom, _ = find_cluster_geometry(das_gdf, das_id)
        if not das_geom.empty:
            _clip_and_mask_raster(depth_tif, das_geom, lake_gpkg=lake_gpkg)

    # Refine flood depth (Option B natural hydrostatic edge recovery + 4-connected 30m x 30m noise floor)
    print(
        f"[{das_id}][{rp}] Refining flood depth raster (reproj={reproj_method}, freeboard={freeboard_m:.2f}m, "
        f"ext_dist={max_ext_dist_m:.0f}m, bridge_radius={bridge_radius}, min_hole_ha={min_hole_ha}, "
        f"island_mmu_ha={island_mmu_ha}, hole_mmu_ha={hole_mmu_ha})..."
    )
    refine_flood_hazard_raster(
        depth_tif=depth_tif,
        dep_path=dep_path,
        hmin=hmin,
        island_mmu_px=island_mmu_px,
        hole_mmu_px=hole_mmu_px,
        island_mmu_ha=island_mmu_ha,
        hole_mmu_ha=hole_mmu_ha,
        min_hole_ha=min_hole_ha,
        bridge_radius=bridge_radius,
        smooth_sigma=smooth_sigma,
        h_connect=h_connect,
        freeboard_m=freeboard_m,
        max_ext_dist_m=max_ext_dist_m,
        max_ext_slope_deg=max_ext_slope_deg,
        depth_offset=depth_offset,
        depth_scale=depth_scale,
        cosmetic=cosmetic,
        out_display_tif=display_tif,
        max_slope_deg=max_slope_deg,
        rivers_gpkg=rivers_gpkg,
    )

    if das_geom is not None and not das_geom.empty:
        _clip_and_mask_raster(depth_tif, das_geom, lake_gpkg=lake_gpkg)
        # Re-sieve any tiny detached edge slivers (< island_mmu_ha) sliced by polygon/lake clipping
        with rasterio.open(depth_tif) as src_c:
            arr_c = src_c.read(1)
            prof_c = src_c.profile.copy()
            tags_c = src_c.tags()
            px_area = max(abs(float(src_c.transform[0]) * float(src_c.transform[4])), 1.0)
        eff_island_px = island_mmu_px if island_mmu_px is not None else int(round((island_mmu_ha * 10000.0) / px_area))
        if eff_island_px > 1:
            wet_c = np.isfinite(arr_c) & (arr_c >= hmin)
            struct_4_c = ndimage.generate_binary_structure(2, 1)
            lbl_c, n_c = ndimage.label(wet_c, structure=struct_4_c)
            if n_c > 0:
                sz_c = ndimage.sum(wet_c, lbl_c, range(1, n_c + 1))
                lkp_c = np.concatenate([[0], sz_c])
                clean_c = np.where(wet_c & (lkp_c[lbl_c] >= eff_island_px), arr_c, np.nan).astype(np.float32)
                with rasterio.open(depth_tif, "w", **prof_c) as dst_c:
                    dst_c.write(clean_c, 1)
                    if tags_c:
                        dst_c.update_tags(**tags_c)

    # Classify hazard (Perka BNPB No. 02/2012)
    print(f"[{das_id}][{rp}] Classifying hazard ({classification_method} mode)...")
    classify_perka_bnpb(
        depth_raster=depth_tif,
        out_path=hazard_tif,
        out_fhi_path=fhi_tif,
        hmin=hmin,
        low_thresh=low_thresh,
        high_thresh=high_thresh,
        method=classification_method,
    )

    # Run Automated QA Gates & Survey Validation (Issues H5, C1, C2, H3)
    qa_report_path = out_dir / "qa_report.json"
    survey_val_path = out_dir / "survey_validation.json"

    print(f"[{das_id}][{rp}] Generating QA Report...")
    run_all_qa(model_dir=model_dir, out_json=qa_report_path)

    das_geom_gpkg = f"data/das_clusters/individual/{das_id}.gpkg"
    validate_flood_map(
        depth_tif=depth_tif,
        das_geom_gpkg=(das_geom_gpkg if os.path.exists(das_geom_gpkg) else das_clusters_gpkg),
        das_id=das_id,
        hmin=hmin,
        out_json=str(survey_val_path),
    )

    print(f"[{das_id}][{rp}] Hazard mapping and validation completed successfully.")


def create_sfincs_flood_animation(
    das_id: str,
    rp: str,
    base_model_dir: str = "models_sfincs_standalone",
    output_maps_dir: str = "outputs",
    das_clusters_gpkg: str = "data/das_clusters/sumbar_das_cluster.gpkg",
    kecamatan_gpkg: str = "data/boundary_kecamatan.gpkg",
    kabkot_gpkg: str = "data/boundary_kabkot.gpkg",
    lake_gpkg: str = "data/lake.gpkg",
    fps: int = 2,
    hmin: float = 0.15,
    vmax: float = 3.0,
):
    """
    Renders an animated dynamic GIF showing flood wave propagation over the simulation duration.
    """
    import io
    try:
        import imageio.v2 as imageio
        use_imageio = True
    except ImportError:
        try:
            import imageio
            use_imageio = True
        except ImportError:
            use_imageio = False
            from PIL import Image as PILImage

    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from rasterio.features import rasterize
    import contextily as cx

    model_dir = Path(base_model_dir) / f"{das_id}_{rp}"
    map_nc = model_dir / "sfincs_map.nc"
    if not map_nc.exists():
        raise FileNotFoundError(f"Results file {map_nc} not found at {map_nc}")

    sf = SfincsModel(str(model_dir), mode="r")
    sf.read_results()
    da_zs = sf.results["zs"]
    da_zb = sf.results.get("zb", None)

    time_steps = da_zs.sizes["time"]
    time_vals = [pd.to_datetime(t).strftime("%Y-%m-%d %H:%M") for t in da_zs["time"].values]

    das_tag = format_output_cluster_id(das_id)
    rp_tag = format_output_rp(rp)
    prefix = f"{das_tag}_{rp_tag}"

    out_dir = Path(output_maps_dir) / das_id / rp
    out_dir.mkdir(parents=True, exist_ok=True)
    anim_gif_path = out_dir / f"{prefix}_Flood_Animation.gif"

    print(f"[{das_id}][{rp}] Rendering {time_steps}-frame animation to {anim_gif_path}...")

    ny, nx = da_zs.shape[-2], da_zs.shape[-1]
    grid_shape = (ny, nx)
    transform = da_zs.raster.transform
    x_min, y_min, x_max, y_max = da_zs.raster.bounds

    zs_values = da_zs.values
    zb = da_zb.values if (da_zb is not None and hasattr(da_zb, "values")) else np.zeros_like(zs_values[0])

    # Cluster boundary mask
    if not os.path.exists(das_clusters_gpkg):
        cand = Path("data/das_clusters/sumbar_das_cluster.gpkg")
        if cand.exists():
            das_clusters_gpkg = str(cand)

    das_gdf = gpd.read_file(das_clusters_gpkg)
    das_poly_native, _ = find_cluster_geometry(das_gdf, das_id)

    shapes_das = [geom for geom in das_poly_native.geometry if geom.is_valid]
    das_mask = rasterize(shapes_das, out_shape=grid_shape, transform=transform, fill=0, default_value=1)

    das_poly_3857 = das_poly_native.to_crs("EPSG:3857")
    bounds_3857 = das_poly_3857.total_bounds
    pad_x = (bounds_3857[2] - bounds_3857[0]) * 0.04
    pad_y = (bounds_3857[3] - bounds_3857[1]) * 0.04
    xlim_view = [bounds_3857[0] - pad_x, bounds_3857[2] + pad_x]
    ylim_view = [bounds_3857[1] - pad_y, bounds_3857[3] + pad_y]

    frames = []
    norm = Normalize(vmin=hmin, vmax=vmax)
    cmap = plt.get_cmap("Blues")

    for t_idx in range(time_steps):
        h_2d = np.maximum(zs_values[t_idx, :, :] - zb, 0.0)
        h_2d_masked = np.where(das_mask == 1, h_2d, np.nan)
        h_2d_masked[h_2d_masked < hmin] = np.nan

        transform_3857, width_3857, height_3857 = rasterio.warp.calculate_default_transform(
            das_poly_native.crs, "EPSG:3857", grid_shape[1], grid_shape[0], x_min, y_min, x_max, y_max
        )
        dest_h = np.full((height_3857, width_3857), np.nan, dtype=np.float32)

        rasterio.warp.reproject(
            source=h_2d_masked,
            destination=dest_h,
            src_transform=transform,
            src_crs=das_poly_native.crs,
            dst_transform=transform_3857,
            dst_crs="EPSG:3857",
            resampling=rasterio.warp.Resampling.bilinear,
            src_nodata=np.nan,
            dst_nodata=np.nan
        )

        bounds_extent_3857 = [
            transform_3857[2],
            transform_3857[2] + transform_3857[0] * width_3857,
            transform_3857[5] + transform_3857[4] * height_3857,
            transform_3857[5]
        ]

        fig, ax = plt.subplots(figsize=(10, 10), dpi=100)
        ax.set_xlim(xlim_view)
        ax.set_ylim(ylim_view)

        try:
            cx.add_basemap(ax, crs="EPSG:3857", source=cx.providers.Esri.WorldImagery, alpha=0.9, attribution=False)
        except Exception:
            pass

        das_poly_3857.plot(ax=ax, facecolor="none", edgecolor="#00FF00", linestyle="--", linewidth=1.4, alpha=0.9)

        if not np.all(np.isnan(dest_h)):
            ax.imshow(
                dest_h,
                extent=bounds_extent_3857,
                cmap=cmap,
                norm=norm,
                alpha=0.8,
                origin="upper",
                zorder=5
            )

        ax.set_title(f"Simulasi Propagasi Banjir: {das_id} ({rp.upper()})\nWaktu: (+{t_idx:02d}h)",
                     fontsize=11, fontweight="bold", pad=8)
        ax.set_axis_off()
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        if use_imageio:
            frames.append(imageio.imread(buf))
        else:
            frames.append(PILImage.open(buf).copy())
        plt.close(fig)

    if use_imageio:
        imageio.mimsave(str(anim_gif_path), frames, fps=fps, loop=0)
    else:
        duration_ms = int(1000 / max(fps, 1))
        frames[0].save(
            str(anim_gif_path),
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            optimize=True,
        )
    print(f"[{das_id}][{rp}] Animation compiled: {anim_gif_path}")
    return str(anim_gif_path)
