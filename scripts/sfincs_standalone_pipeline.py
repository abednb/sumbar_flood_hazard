"""
Universal Standalone SFINCS Automated Pipeline for Flood Hazard Modeling
========================================================================
Supports any regional watershed cluster (e.g., Sumbar, Java, Kalimantan, global)
with dynamic CRS, flexible cluster identifier matching, and automated data chipping.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, Union
import geopandas as gpd
import rasterio
import rasterio.windows
import rasterio.warp
import xarray as xr
import numpy as np
import pyproj
import hydromt
from hydromt_sfincs import SfincsModel, utils

# Ensure script directory is always in sys.path
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from perka_bnpb_classification import classify_perka_bnpb

# Fix PROJ and GDAL paths dynamically for Windows virtual environment
site_packages = Path(sys.prefix) / "Lib" / "site-packages"
proj_dir = (site_packages / "rasterio" / "proj_data").resolve()
gdal_dir = (site_packages / "rasterio" / "gdal_data").resolve()

if proj_dir.exists():
    os.environ["PROJ_DATA"] = str(proj_dir)
    os.environ["PROJ_LIB"] = str(proj_dir)
    pyproj.datadir.set_data_dir(str(proj_dir))
if gdal_dir.exists():
    os.environ["GDAL_DATA"] = str(gdal_dir)


def normalize_cluster_id(raw_val) -> str:
    """Universal normalizer for cluster identifiers across any project or region."""
    if raw_val is None:
        return ""
    val_str = str(raw_val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    return val_str


def find_cluster_geometry(das_gdf: gpd.GeoDataFrame, target_id: str) -> Tuple[gpd.GeoDataFrame, str]:
    """
    Finds the cluster row matching target_id with high flexibility:
    Matches 'DAS_201', '201', 'DAS201', 'DAS_305', '407', 'Citarum_Hilir', etc.
    Returns: (matching_gdf, resolved_das_id)
    """
    if das_gdf.empty:
        raise ValueError("The provided cluster GeoDataFrame is empty.")

    # Detect all possible candidate identifier columns
    priority_cols = [
        "ID_Cluster", "id_cluster", "das_id", "DAS_ID", "Cluster_ID", "cluster_id",
        "ID", "id", "Name", "NAME", "name", "KODE_DAS", "kode_das", "Cluster", "cluster"
    ]
    cand_cols = [c for c in priority_cols if c in das_gdf.columns]
    if not cand_cols:
        cand_cols = [das_gdf.columns[0]]  # Fallback to first column

    def strip_das_prefix(s) -> str:
        t = str(s).strip()
        for prefix in ["DAS_", "DAS", "das_", "das", "Das_", "Das"]:
            if t.startswith(prefix):
                return t[len(prefix):].strip()
        return t

    target_str = str(target_id).strip()
    target_core = strip_das_prefix(target_str)
    target_alphanum = "".join(filter(str.isalnum, target_str)).lower()
    target_core_alphanum = "".join(filter(str.isalnum, target_core)).lower()

    for col in cand_cols:
        col_series = das_gdf[col].apply(normalize_cluster_id)
        
        # 1. Exact string match
        match = das_gdf[col_series == target_str]
        if not match.empty:
            return match, target_str
            
        # 2. Match with 'DAS_' prefix added to column
        match = das_gdf[col_series.apply(lambda x: f"DAS_{x}") == target_str]
        if not match.empty:
            return match, target_str

        # 3. Match with 'DAS_' prefix added to query
        match = das_gdf[col_series == f"DAS_{target_str}"]
        if not match.empty:
            return match, target_str
            
        # 4. Match stripped core values (e.g. '201' matches 'DAS201' or 'DAS_201')
        col_core = col_series.apply(strip_das_prefix)
        match = das_gdf[col_core == target_core]
        if not match.empty:
            return match, target_str
                
        # 5. Case-insensitive alphanumeric match on core string
        col_core_alphanum = col_core.apply(lambda x: "".join(filter(str.isalnum, str(x))).lower())
        match = das_gdf[col_core_alphanum == target_core_alphanum]
        if not match.empty:
            return match, target_str

        # 6. Case-insensitive alphanumeric match on full string
        col_alphanum = col_series.apply(lambda x: "".join(filter(str.isalnum, str(x))).lower())
        match = das_gdf[col_alphanum == target_alphanum]
        if not match.empty:
            return match, target_str

    # If no match found, list available IDs to guide the user
    sample_ids = [normalize_cluster_id(x) for x in das_gdf[cand_cols[0]].head(10)]
    raise ValueError(
        f"Cluster '{target_id}' was not found in dataset.\n"
        f"Available candidate IDs in column '{cand_cols[0]}': {sample_ids}..."
    )


def find_elevation_dem_path() -> Path:
    """Dynamically finds the elevation DEM raster in data/ directory."""
    candidates = [
        Path("data/fabdem_reprojected.tif"),
        Path("data/dem_reprojected.tif"),
        Path("data/dem.tif"),
        Path("data/elevation.tif"),
        Path("data/fabdem.tif"),
    ]
    for cand in candidates:
        if cand.exists():
            return cand
            
    # Search for any large TIFF in data/
    data_dir = Path("data")
    if data_dir.exists():
        for p in data_dir.glob("*.tif"):
            p_name = p.name.lower()
            if "hillshade" not in p_name and "landcover" not in p_name and "soil" not in p_name and "depth" not in p_name and "hazard" not in p_name:
                return p
                
    return Path("data/fabdem_reprojected.tif")


def prepare_cluster_clipped_rasters(
    das_id: str,
    das_geom: gpd.GeoDataFrame,
    source_dem: Optional[Path] = None,
    buffer_meters: float = 2000.0,
) -> str:
    """
    Extracts a local windowed chip of the large DEM for the specific cluster.
    Prevents massive in-memory memory allocation errors (OOM) and builds a universal data catalog.
    """
    root_dir = Path(".").resolve()
    chip_dir = (root_dir / "data" / "das_clusters" / "chips" / das_id).resolve()
    chip_dir.mkdir(parents=True, exist_ok=True)
    
    if source_dem is None or not source_dem.exists():
        source_dem = find_elevation_dem_path()
        
    if not source_dem.exists():
        raise FileNotFoundError(f"Elevation DEM raster not found at {source_dem}.")

    minx, miny, maxx, maxy = das_geom.total_bounds
    bbox = (minx - buffer_meters, miny - buffer_meters, maxx + buffer_meters, maxy + buffer_meters)
    
    # 1. Clip Elevation DEM
    dem_chip_path = chip_dir / "dem_chip.tif"
    if not dem_chip_path.exists():
        with rasterio.open(source_dem) as src:
            win = rasterio.windows.from_bounds(*bbox, transform=src.transform)
            data = src.read(window=win)
            win_transform = src.window_transform(win)
            profile = src.profile.copy()
            profile.update({
                "height": data.shape[1],
                "width": data.shape[2],
                "transform": win_transform,
                "compress": "lzw",
                "tiled": True,
            })
            with rasterio.open(dem_chip_path, "w", **profile) as dst:
                dst.write(data)
                
    # 2. Extract Active CRS
    active_crs = das_geom.crs
    crs_val = active_crs.to_epsg() if active_crs and active_crs.to_epsg() else (active_crs.srs if active_crs else 32747)

    # 3. Write universal data catalog for this DAS using absolute paths
    das_catalog_path = chip_dir / "catalog.yml"
    abs_dem_path = dem_chip_path.as_posix()
    abs_root = root_dir.as_posix()
    
    catalog_content = f"""# Universal HydroMT-SFINCS Data Catalog for {das_id}
# Compatible with both generic aliases and regional dataset keys

# --- Elevation DEM ---
fabdem_sumbar:
  path: {abs_dem_path}
  data_type: RasterDataset
  driver: raster
  crs: {crs_val}

elevation_dem:
  path: {abs_dem_path}
  data_type: RasterDataset
  driver: raster
  crs: {crs_val}

# --- Hydrography / River Network ---
rbi_river_sumbar:
  path: {abs_root}/data/rivers.gpkg
  data_type: GeoDataFrame
  driver: vector
  crs: {crs_val}

rivers:
  path: {abs_root}/data/rivers.gpkg
  data_type: GeoDataFrame
  driver: vector
  crs: {crs_val}

# --- Land Cover & Roughness ---
rbi_landcover_sumbar:
  path: {abs_root}/data/landcover_100m.tif
  data_type: RasterDataset
  driver: raster
  crs: {crs_val}

landcover:
  path: {abs_root}/data/landcover_100m.tif
  data_type: RasterDataset
  driver: raster
  crs: {crs_val}

# --- Soil Infiltration Capacity (Ksat) ---
soil_infiltration_sumbar:
  path: {abs_root}/data/soil_infiltration_100m.tif
  data_type: RasterDataset
  driver: raster
  crs: {crs_val}

soil_infiltration:
  path: {abs_root}/data/soil_infiltration_100m.tif
  data_type: RasterDataset
  driver: raster
  crs: {crs_val}

# --- Gridded Design Rainfall Events ---
rainfall_rp2:
  path: {abs_root}/data/rainfall/rainfall_rp2_hourly.nc
  data_type: RasterDataset
  driver: netcdf
  crs: {crs_val}

rainfall_rp5:
  path: {abs_root}/data/rainfall/rainfall_rp5_hourly.nc
  data_type: RasterDataset
  driver: netcdf
  crs: {crs_val}

rainfall_rp10:
  path: {abs_root}/data/rainfall/rainfall_rp10_hourly.nc
  data_type: RasterDataset
  driver: netcdf
  crs: {crs_val}

rainfall_rp25:
  path: {abs_root}/data/rainfall/rainfall_rp25_hourly.nc
  data_type: RasterDataset
  driver: netcdf
  crs: {crs_val}

rainfall_rp50:
  path: {abs_root}/data/rainfall/rainfall_rp50_hourly.nc
  data_type: RasterDataset
  driver: netcdf
  crs: {crs_val}

rainfall_rp100:
  path: {abs_root}/data/rainfall/rainfall_rp100_hourly.nc
  data_type: RasterDataset
  driver: netcdf
  crs: {crs_val}
"""
    with open(das_catalog_path, "w", encoding="utf-8") as f:
        f.write(catalog_content)
        
    return str(das_catalog_path)


def build_sfincs_standalone(
    das_id: str,
    output_dir: str = "models_sfincs_standalone",
    config_fn: str = "configs/sfincs_standalone_build.yml",
    data_catalog_fn: str = "data_catalog_sfincs.yml",
    das_clusters_gpkg: str = "data/das_clusters.gpkg",
    admin_boundary_gpkg: Optional[str] = None,
    force_overwrite: bool = True,
    bws_structures_gpkg: Optional[str] = None,
    bws_gauges_gpkg: Optional[str] = None,
) -> str:
    """
    Builds the base SFINCS model domain for any specific watershed cluster.
    Works universally for any region or dataset naming scheme.
    """
    model_root = Path(output_dir) / das_id
    model_root.parent.mkdir(parents=True, exist_ok=True)
    
    # 1. Flexible Cluster Boundary Search
    if not os.path.exists(das_clusters_gpkg):
        # Fallback search in modified_das_cluster
        cand = Path("data/modified_das_cluster/smaller_das_cluster.gpkg")
        if cand.exists():
            das_clusters_gpkg = str(cand)
            
    das_gdf = gpd.read_file(das_clusters_gpkg)
    das_geom, resolved_id = find_cluster_geometry(das_gdf, das_id)
    das_geom = das_geom.copy()
    
    # 2. Optional Administrative Boundary Clipping (Prevents transboundary OOM)
    admin_candidates = [
        admin_boundary_gpkg,
        "data/boundary_kabkot.gpkg",
        "data/admin_boundary.gpkg",
        "data/boundary_regional.gpkg",
    ]
    resolved_admin = None
    for cand in admin_candidates:
        if cand and os.path.exists(cand):
            resolved_admin = cand
            break
            
    if resolved_admin:
        try:
            admin_gdf = gpd.read_file(resolved_admin).to_crs(das_geom.crs)
            admin_buffered = admin_gdf.geometry.union_all().buffer(2000.0) if hasattr(admin_gdf.geometry, "union_all") else admin_gdf.geometry.unary_union.buffer(2000.0)
            clipped_geom = das_geom.intersection(admin_buffered)
            if not clipped_geom.empty and not clipped_geom.is_empty.all():
                das_geom["geometry"] = clipped_geom
        except Exception as e:
            print(f"[{das_id}] Note: Regional boundary clipping skipped: {e}")
    
    temp_das_dir = Path("data/das_clusters/individual")
    temp_das_dir.mkdir(parents=True, exist_ok=True)
    temp_das_path = temp_das_dir / f"{das_id}.gpkg"
    das_geom.to_file(temp_das_path, driver="GPKG")
    
    # 3. Window-clip DEM to avoid monolithic array allocation
    print(f"[{das_id}] Preparing optimized spatial data chip...")
    catalog_to_use = prepare_cluster_clipped_rasters(das_id, das_geom)
    
    # 4. Build SFINCS model using HydroMT CLI
    hydromt_exe = Path(sys.executable).parent / "hydromt.exe"
    if not hydromt_exe.exists():
        hydromt_exe = Path("env-sfincs/Scripts/hydromt.exe")
    if not hydromt_exe.exists():
        hydromt_exe = "hydromt"
        
    region_arg = f'{{"geom": "{temp_das_path.as_posix()}"}}'
    cmd = [
        str(hydromt_exe), "build", "sfincs",
        str(model_root),
        "-r", region_arg,
        "-i", config_fn,
        "-d", catalog_to_use,
        "-vv"
    ]
    if force_overwrite:
        cmd.append("--fo")
        
    print(f"[{das_id}] Building standalone SFINCS base model at {model_root}...")
    env = os.environ.copy()
    env["PROJ_DATA"] = str(proj_dir)
    env["PROJ_LIB"] = str(proj_dir)
    env["GDAL_DATA"] = str(gdal_dir)
    subprocess.run(cmd, check=True, env=env)
    
    # 5. Optional Infrastructure / Gauges Placeholders
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
        
    print(f"[{das_id}] Base model build completed successfully.")
    return str(model_root)


def prepare_sfincs_direct_rain_forcing(
    das_id: str,
    return_periods: List[str] = ["rp2", "rp5", "rp10", "rp25", "rp50", "rp100"],
    base_model_dir: str = "models_sfincs_standalone",
    rainfall_dir: str = "data/rainfall",
    data_catalog_fn: Optional[str] = None,
    bws_inflow_hydrographs: Optional[str] = None,
):
    """
    Applies direct rainfall NetCDF forcing for each return period design storm.
    Dynamically projects precipitation to the model's native coordinate reference system.
    """
    base_root = Path(base_model_dir) / das_id
    if not base_root.exists():
        raise FileNotFoundError(f"Base model {base_root} not found. Run build_sfincs_standalone first.")

    for rp in return_periods:
        case_dir = Path(base_model_dir) / f"{das_id}_{rp}"
        print(f"[{das_id}][{rp}] Generating direct rainfall model configuration at {case_dir}...")
        
        # Load base model into memory
        sf = SfincsModel(root=str(base_root), mode="r")
        sf.read()
        
        # Align simulation time bounds to 24h design storm event
        sf.set_config("tref", "20240101 000000")
        sf.set_config("tstart", "20240101 000000")
        sf.set_config("tstop", "20240101 230000")
        
        # Load rainfall dataset
        nc_candidates = [
            Path(rainfall_dir) / f"rainfall_{rp}_hourly.nc",
            Path(rainfall_dir) / f"rainfall_{rp}.nc",
            Path(rainfall_dir) / f"{rp}.nc",
        ]
        nc_path = None
        for cand in nc_candidates:
            if cand.exists():
                nc_path = cand
                break
                
        if not nc_path:
            raise FileNotFoundError(f"Rainfall NetCDF for {rp} not found in {rainfall_dir}.")
            
        ds = xr.open_dataset(nc_path)
        var_name = "precip" if "precip" in ds.data_vars else list(ds.data_vars.keys())[0]
        precip_da = ds[var_name]
        
        # Ensure correct dimension ordering
        dims = list(precip_da.dims)
        if "time" in dims and "lat" in dims and "lon" in dims:
            precip_da = precip_da.transpose("time", "lat", "lon")
            precip_da.raster.set_crs(4326)
        elif "time" in dims and "y" in dims and "x" in dims:
            precip_da = precip_da.transpose("time", "y", "x")

        time_interval = 3600.0
        dtwnd = sf.config.get("dtwnd", 1800)
        if dtwnd > time_interval:
            sf.set_config("dtwnd", time_interval)

        # Reproject from geographic/native to SFINCS model grid CRS
        precip_out = precip_da.raster.reproject(
            dst_crs=sf.crs, method="nearest_index"
        ).fillna(0)
        precip_out = precip_out.rename("precip_2d")
        y_dim, x_dim = precip_out.raster.dims
        precip_out = precip_out.rename({y_dim: "y", x_dim: "x"})
        
        sf.set_forcing(precip_out, name="precip_2d")
        
        # Optional: Upstream discharge forcing
        if bws_inflow_hydrographs and os.path.exists(bws_inflow_hydrographs):
            print(f"[{das_id}][{rp}] Applying upstream discharge forcing...")
            
        # Write to case directory
        sf.set_root(str(case_dir), mode="w+")
        sf.write()
        print(f"[{das_id}][{rp}] Ready for simulation at {case_dir}.")


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
        str(Path("env-sfincs/Scripts/sfincs.exe").resolve()),
        "sfincs.exe",
    ]
    resolved_exe = None
    for cand in candidates:
        if cand and (os.path.exists(cand) or shutil.which(cand) is not None):
            resolved_exe = cand
            break

    log_path = model_dir / "sfincs_run.log"
    print(f"[{das_id}][{rp}] Running SFINCS hydrodynamic engine (Logging to {log_path})...")
    
    # Remove stale or locked results file from previous attempts
    map_nc = model_dir / "sfincs_map.nc"
    if map_nc.exists():
        try:
            os.remove(map_nc)
        except OSError:
            pass

    if resolved_exe:
        cmd = [resolved_exe]
    else:
        abs_path = os.path.abspath(str(model_dir))
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{abs_path}:/data",
            "deltares/sfincs-cpu:latest"
        ]

    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            cmd,
            cwd=str(model_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
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
            raise subprocess.CalledProcessError(proc.returncode, cmd)
            
    print(f"[{das_id}][{rp}] Simulation finished successfully.")


def _clip_and_mask_raster(
    raster_path: str,
    geom_mask: gpd.GeoDataFrame,
    lake_gpkg: Optional[str] = "data/lake.gpkg",
):
    """
    Clips a raster precisely to the cluster polygon boundary and masks out permanent lake water bodies.
    """
    import rasterio.mask
    with rasterio.open(raster_path) as src:
        # 1. Clip to Cluster Boundary
        if geom_mask.crs != src.crs:
            geom_mask = geom_mask.to_crs(src.crs)
        shapes = [geom for geom in geom_mask.geometry if geom.is_valid]
        
        out_image, out_transform = rasterio.mask.mask(src, shapes, crop=False)
        out_meta = src.meta.copy()

        # 2. Mask out Lake Water Bodies if lake layer exists
        if lake_gpkg and os.path.exists(lake_gpkg):
            try:
                lake_gdf = gpd.read_file(lake_gpkg)
                if not lake_gdf.empty:
                    if lake_gdf.crs != src.crs:
                        lake_gdf = lake_gdf.to_crs(src.crs)
                    
                    union_das = geom_mask.geometry.union_all() if hasattr(geom_mask.geometry, 'union_all') else geom_mask.geometry.unary_union
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


def postprocess_sfincs_hazard(
    das_id: str,
    rp: str,
    base_model_dir: str = "models_sfincs_standalone",
    output_maps_dir: str = "outputs_standalone",
    das_clusters_gpkg: str = "data/das_clusters.gpkg",
    lake_gpkg: str = "data/lake.gpkg",
    hmin: float = 0.05,
):
    """
    Downscales SFINCS water levels to high-resolution topography,
    clips strictly to cluster boundary, masks out permanent lake bodies,
    and computes Fuzzy Large BNPB hazard classifications.
    """
    model_dir = Path(base_model_dir) / f"{das_id}_{rp}"
    map_nc = model_dir / "sfincs_map.nc"
    if not map_nc.exists():
        raise FileNotFoundError(f"Results file {map_nc} not found.")

    sf = SfincsModel(str(model_dir), mode="r")
    sf.read_results()
    
    zsmax = sf.results["zsmax"].max(dim="timemax")
    
    # Subgrid high-resolution topography
    dep_subgrid_path = model_dir / "subgrid" / "dep_subgrid.tif"
    if not dep_subgrid_path.exists():
        dep_subgrid_path = Path(base_model_dir) / das_id / "subgrid" / "dep_subgrid.tif"
    if not dep_subgrid_path.exists():
        raise FileNotFoundError(f"Subgrid topography not found at {dep_subgrid_path}")
        
    dep = hydromt.open_raster(str(dep_subgrid_path.resolve()))
    
    out_dir = Path(output_maps_dir) / das_id / rp
    out_dir.mkdir(parents=True, exist_ok=True)
    depth_tif = str(out_dir / "flood_depth_10m.tif")
    hazard_tif = str(out_dir / "hazard_class_perka2012.tif")
    fhi_tif = str(out_dir / "flood_hazard_index.tif")
    
    print(f"[{das_id}][{rp}] Downscaling flood depths to high-resolution DEM grid...")
    utils.downscale_floodmap(
        zsmax=zsmax,
        dep=dep,
        hmin=hmin,
        floodmap_fn=depth_tif,
    )
    
    # Load cluster polygon for precise boundary masking
    if not os.path.exists(das_clusters_gpkg):
        cand = Path("data/modified_das_cluster/smaller_das_cluster.gpkg")
        if cand.exists():
            das_clusters_gpkg = str(cand)
            
    if os.path.exists(das_clusters_gpkg):
        das_gdf = gpd.read_file(das_clusters_gpkg)
        das_geom, _ = find_cluster_geometry(das_gdf, das_id)
        if not das_geom.empty:
            print(f"[{das_id}][{rp}] Clipping depth map to catchment boundary...")
            _clip_and_mask_raster(depth_tif, das_geom, lake_gpkg=lake_gpkg)
    
    print(f"[{das_id}][{rp}] Computing Fuzzy Large Flood Hazard Index & BNPB Classification...")
    classify_perka_bnpb(
        depth_raster=depth_tif,
        out_path=hazard_tif,
        out_fhi_path=fhi_tif,
        hmin=hmin,
        midpoint=1.125,
        spread=1.75,
        low_fhi_thresh=0.333,
        high_fhi_thresh=0.666,
    )
    print(f"[{das_id}][{rp}] Complete. Hazard Level saved: {hazard_tif}")
    print(f"[{das_id}][{rp}] Complete. Hazard Index saved: {fhi_tif}")


def create_sfincs_flood_animation(
    das_id: str,
    rp: str,
    base_model_dir: str = "models_sfincs_standalone",
    output_maps_dir: str = "outputs_standalone",
    das_clusters_gpkg: str = "data/das_clusters.gpkg",
    kecamatan_gpkg: str = "data/boundary_kecamatan.gpkg",
    kabkot_gpkg: str = "data/boundary_kabkot.gpkg",
    lake_gpkg: str = "data/lake.gpkg",
    fps: int = 2,
    hmin: float = 0.05,
    vmax: float = 3.0,
):
    """
    Renders an animated dynamic GIF showing 24-hour flood wave propagation.
    Dynamically adjusts to any regional coordinate system and gracefully handles missing optional boundary layers.
    """
    import io
    import imageio.v2 as imageio
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from rasterio.features import rasterize
    import contextily as cx

    model_dir = Path(base_model_dir) / f"{das_id}_{rp}"
    map_nc = model_dir / "sfincs_map.nc"
    if not map_nc.exists():
        raise FileNotFoundError(f"Results file {map_nc} not found at {map_nc}")

    out_dir = Path(output_maps_dir) / das_id / rp
    out_dir.mkdir(parents=True, exist_ok=True)
    anim_gif_path = out_dir / "flood_propagation_24h.gif"

    print(f"[{das_id}][{rp}] Generating 24-hour flood propagation animation...")

    # 1. Load SFINCS simulation results
    with xr.open_dataset(map_nc) as ds:
        zb = ds["zb"].values
        zs_all = ds["zs"]
        time_steps = len(zs_all.time)
        time_vals = [str(t)[:19].replace("T", " ") for t in zs_all.time.values]
        zs_values = zs_all.values

        x_min, x_max = float(ds.corner_x.min()), float(ds.corner_x.max())
        y_min, y_max = float(ds.corner_y.min()), float(ds.corner_y.max())
        grid_shape = zb.shape

    # 2. Prepare Cluster Vector
    if not os.path.exists(das_clusters_gpkg):
        cand = Path("data/modified_das_cluster/smaller_das_cluster.gpkg")
        if cand.exists():
            das_clusters_gpkg = str(cand)

    das_gdf = gpd.read_file(das_clusters_gpkg)
    das_poly_native, _ = find_cluster_geometry(das_gdf, das_id)

    transform = rasterio.transform.from_bounds(x_min, y_min, x_max, y_max, grid_shape[1], grid_shape[0])
    shapes_das = [geom for geom in das_poly_native.geometry if geom.is_valid]
    das_mask_north_up = rasterize(shapes_das, out_shape=grid_shape, transform=transform, fill=0, default_value=1)

    # 3. Prepare Lake Mask
    if lake_gpkg and os.path.exists(lake_gpkg):
        try:
            lake_gdf = gpd.read_file(lake_gpkg).to_crs(das_poly_native.crs)
            union_das_native = das_poly_native.geometry.union_all() if hasattr(das_poly_native.geometry, 'union_all') else das_poly_native.geometry.unary_union
            lake_sub = lake_gdf[lake_gdf.intersects(union_das_native)]
            if not lake_sub.empty:
                lake_shapes = [geom for geom in lake_sub.geometry if geom.is_valid]
                lake_mask_north_up = rasterize(lake_shapes, out_shape=grid_shape, transform=transform, fill=0, default_value=1)
            else:
                lake_mask_north_up = np.zeros(grid_shape, dtype=np.uint8)
        except Exception:
            lake_mask_north_up = np.zeros(grid_shape, dtype=np.uint8)
    else:
        lake_mask_north_up = np.zeros(grid_shape, dtype=np.uint8)

    final_cell_mask = (das_mask_north_up == 1) & (lake_mask_north_up == 0)

    # 4. Prepare Vector Layers in Web Mercator (EPSG:3857) for Basemap
    das_poly_3857 = das_poly_native.to_crs("EPSG:3857")
    bounds_3857 = das_poly_3857.total_bounds
    union_3857 = das_poly_3857.geometry.union_all() if hasattr(das_poly_3857.geometry, 'union_all') else das_poly_3857.geometry.unary_union

    pad_x = (bounds_3857[2] - bounds_3857[0]) * 0.04
    pad_y = (bounds_3857[3] - bounds_3857[1]) * 0.04
    xlim_view = [bounds_3857[0] - pad_x, bounds_3857[2] + pad_x]
    ylim_view = [bounds_3857[1] - pad_y, bounds_3857[3] + pad_y]

    kec_intersect = None
    if kecamatan_gpkg and os.path.exists(kecamatan_gpkg):
        try:
            kec_gdf = gpd.read_file(kecamatan_gpkg).to_crs("EPSG:3857")
            kec_intersect = kec_gdf[kec_gdf.intersects(union_3857)].copy()
        except Exception:
            pass

    kab_intersect = None
    if kabkot_gpkg and os.path.exists(kabkot_gpkg):
        try:
            kab_gdf = gpd.read_file(kabkot_gpkg).to_crs("EPSG:3857")
            kab_intersect = kab_gdf[kab_gdf.intersects(union_3857)].copy()
        except Exception:
            pass

    frames = []
    norm = Normalize(vmin=hmin, vmax=vmax)
    cmap = plt.get_cmap("Blues")

    # Render frames
    for t_idx in range(time_steps):
        h_2d = np.maximum(zs_values[t_idx, :, :] - zb, 0.0)
        h_2d_masked = np.where(final_cell_mask, h_2d, np.nan)
        h_2d_masked[h_2d_masked < hmin] = np.nan

        # Reproject depth slice to EPSG:3857 for contextily basemap
        h_3857 = np.zeros(grid_shape, dtype=np.float32)
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

        fig, ax = plt.subplots(figsize=(10, 10), dpi=120)
        ax.set_xlim(xlim_view)
        ax.set_ylim(ylim_view)

        # 1. Basemap
        try:
            cx.add_basemap(ax, crs="EPSG:3857", source=cx.providers.Esri.WorldImagery, alpha=0.9, attribution=False)
        except Exception:
            pass

        # 2. Administrative Boundaries
        if kec_intersect is not None and not kec_intersect.empty:
            kec_intersect.plot(ax=ax, facecolor="none", edgecolor="white", linewidth=0.8, alpha=0.7)
            name_col = next((c for c in ["WADMKC", "NAMOBJ", "KECAMATAN", "NAME_3", "Name"] if c in kec_intersect.columns), None)
            if name_col:
                for _, row in kec_intersect.iterrows():
                    rep = row.geometry.representative_point()
                    if xlim_view[0] <= rep.x <= xlim_view[1] and ylim_view[0] <= rep.y <= ylim_view[1]:
                        ax.annotate(str(row[name_col]), xy=(rep.x, rep.y), xytext=(0, 0), textcoords="offset points",
                                    fontsize=6.5, color="white", weight="normal", ha="center", va="center")

        if kab_intersect is not None and not kab_intersect.empty:
            kab_intersect.plot(ax=ax, facecolor="none", edgecolor="#FFFF00", linewidth=1.2, alpha=0.85)
            kab_col = next((c for c in ["WADMKK", "NAMOBJ", "KABUPATEN", "NAME_2", "Name"] if c in kab_intersect.columns), None)
            if kab_col:
                for _, row in kab_intersect.iterrows():
                    rep = row.geometry.representative_point()
                    if xlim_view[0] <= rep.x <= xlim_view[1] and ylim_view[0] <= rep.y <= ylim_view[1]:
                        ax.annotate(str(row[kab_col]), xy=(rep.x, rep.y), xytext=(0, 0), textcoords="offset points",
                                    fontsize=8.5, color="#FFFF00", weight="bold", ha="center", va="center")

        # 3. Cluster Boundary
        das_poly_3857.plot(ax=ax, facecolor="none", edgecolor="#00FF00", linestyle="--", linewidth=1.4, alpha=0.9)

        # 4. Water Level Slice
        if not np.all(np.isnan(dest_h)):
            ax.imshow(
                dest_h,
                extent=[bounds_extent_3857[0], bounds_extent_3857[1], bounds_extent_3857[2], bounds_extent_3857[3]],
                cmap=cmap,
                norm=norm,
                alpha=0.8,
                origin="upper",
                zorder=5
            )

        ax.set_title(f"SFINCS 2D Flood Wave Propagation: {das_id} ({rp.upper()})\nTime: {time_vals[t_idx]} UTC (+{t_idx:02d}h)",
                     fontsize=11, fontweight="bold", pad=8)
        ax.set_axis_off()
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        buf.seek(0)
        frames.append(imageio.imread(buf))
        plt.close(fig)

    imageio.mimsave(str(anim_gif_path), frames, fps=fps, loop=0)
    print(f"[{das_id}][{rp}] Animation compiled: {anim_gif_path}")
    return str(anim_gif_path)
