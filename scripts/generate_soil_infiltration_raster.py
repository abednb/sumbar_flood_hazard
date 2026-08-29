import os
import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from rasterio.features import rasterize
import pyproj

proj_dir = os.path.abspath(r".\env-sfincs\Lib\site-packages\rasterio\proj_data")
gdal_dir = os.path.abspath(r".\env-sfincs\Lib\site-packages\rasterio\gdal_data")
if os.path.exists(proj_dir):
    os.environ["PROJ_DATA"] = proj_dir
    os.environ["PROJ_LIB"] = proj_dir
    pyproj.datadir.set_data_dir(proj_dir)
if os.path.exists(gdal_dir):
    os.environ["GDAL_DATA"] = gdal_dir

TARGET_CRS = "EPSG:32747"
out_tif = "data/soil_infiltration_100m.tif"
Path("data").mkdir(exist_ok=True, parents=True)

print("=== Generating Harmonized Soil Infiltration Capacity Raster ===")

# 1. Load Grid Extent from Reference DEM or DAS Clusters
with rasterio.open("data/fabdem_reprojected.tif") as ref_dem:
    bounds = ref_dem.bounds
    res = 100.0  # 100m resolution
    # Snap bounds to 100m increments
    minx = np.floor(bounds.left / res) * res
    miny = np.floor(bounds.bottom / res) * res
    maxx = np.ceil(bounds.right / res) * res
    maxy = np.ceil(bounds.top / res) * res
    
    width = int((maxx - minx) / res)
    height = int((maxy - miny) / res)
    transform = rasterio.transform.from_bounds(minx, miny, maxx, maxy, width, height)

print(f"Target Grid: {width} x {height} cells @ 100m, CRS = {TARGET_CRS}")

# 2. Load Lookup Table
lookup_df = pd.read_csv("lookup_tables/soil_infiltration_lookup.csv", comment="#")

# Build dictionary: (soil_texture, lc_category) -> infiltration_rate
rate_map = {}
for _, row in lookup_df.iterrows():
    s_tex = str(row["soil_texture"]).strip().lower()
    lc_cat = str(row["landcover_category"]).strip().lower()
    rate_map[(s_tex, lc_cat)] = float(row["infiltration_rate_mm_hr"])

# 3. Load & Reproject Kementan Soil Texture
print("Loading TeksturTanah_Kementan.gpkg...")
soil_gdf = gpd.read_file("data_raw/soil/TeksturTanah_Kementan.gpkg")
if str(soil_gdf.crs) != TARGET_CRS:
    soil_gdf = soil_gdf.to_crs(TARGET_CRS)

# Clean soil texture labels
soil_gdf["clean_texture"] = soil_gdf["K_Tekstur"].fillna("Default").astype(str).str.strip().str.lower()
soil_gdf.loc[soil_gdf["clean_texture"] == "-", "clean_texture"] = "default"

# Assign texture ID
texture_classes = sorted(soil_gdf["clean_texture"].unique().tolist())
texture_to_id = {tex: i + 1 for i, tex in enumerate(texture_classes)}
id_to_texture = {i + 1: tex for i, tex in enumerate(texture_classes)}
soil_gdf["texture_id"] = soil_gdf["clean_texture"].map(texture_to_id)

print("Rasterizing Soil Texture...")
soil_shapes = ((geom, val) for geom, val in zip(soil_gdf.geometry, soil_gdf["texture_id"]) if geom is not None and not geom.is_empty)
soil_raster = rasterize(soil_shapes, out_shape=(height, width), transform=transform, fill=0, dtype="uint8")

# 4. Load & Reproject RBI Land Cover
print("Loading RBI Landcover...")
lc_gdf = gpd.read_file("data_raw/rbi/landcover.gpkg", layer="lc_sumbar_lok26")
if str(lc_gdf.crs) != TARGET_CRS:
    lc_gdf = lc_gdf.to_crs(TARGET_CRS)

# Map RBI REMARK into simplified land cover categories
def categorize_rbi(remark):
    r = str(remark).lower()
    if "sawah" in r:
        return "sawah"
    elif "permukiman" in r or "gedung" in r or "bangunan" in r or "pelabuhan" in r or "bandara" in r:
        return "permukiman"
    elif "kebun" in r or "perkebunan" in r:
        return "perkebunan"
    elif "tegalan" in r or "ladang" in r:
        return "tegalan/ladang"
    elif "hutan" in r:
        return "hutan"
    elif "semak" in r or "belukar" in r or "rumput" in r:
        return "semak belukar"
    elif "danau" in r or "sungai" in r or "waduk" in r or "rawa" in r or "air" in r:
        return "badan air"
    else:
        return "default"

lc_gdf["lc_cat"] = lc_gdf["REMARK"].apply(categorize_rbi)
lc_classes = ["default", "sawah", "permukiman", "perkebunan", "tegalan/ladang", "hutan", "semak belukar", "badan air"]
lc_to_id = {lc: i + 1 for i, lc in enumerate(lc_classes)}
id_to_lc = {i + 1: lc for i, lc in enumerate(lc_classes)}
lc_gdf["lc_id"] = lc_gdf["lc_cat"].map(lc_to_id)

print("Rasterizing RBI Landcover...")
lc_shapes = ((geom, val) for geom, val in zip(lc_gdf.geometry, lc_gdf["lc_id"]) if geom is not None and not geom.is_empty)
lc_raster = rasterize(lc_shapes, out_shape=(height, width), transform=transform, fill=0, dtype="uint8")

# 5. Synthesize Combined Infiltration Grid (float32, mm/hr)
print("Synthesizing Infiltration Rates Matrix...")
infilt_grid = np.full((height, width), 0.50, dtype=np.float32)  # default 0.50 mm/hr

# Map vectorized combinations
for tex_id, tex_name in id_to_texture.items():
    for lc_id, lc_name in id_to_lc.items():
        # Lookup rate with multiple fallbacks
        rate = rate_map.get((tex_name, lc_name))
        if rate is None:
            rate = rate_map.get((tex_name, "default"))
        if rate is None:
            rate = rate_map.get(("default", lc_name))
        if rate is None:
            rate = 0.50
        
        mask = (soil_raster == tex_id) & (lc_raster == lc_id)
        infilt_grid[mask] = rate

# Also handle areas where soil is known but lc is unclassified (0)
for tex_id, tex_name in id_to_texture.items():
    rate = rate_map.get((tex_name, "default"), 0.50)
    mask = (soil_raster == tex_id) & (lc_raster == 0)
    infilt_grid[mask] = rate

# Handle areas where lc is known but soil is unclassified (0)
for lc_id, lc_name in id_to_lc.items():
    rate = rate_map.get(("default", lc_name), 0.50)
    mask = (soil_raster == 0) & (lc_raster == lc_id)
    infilt_grid[mask] = rate

# 6. Write GeoTIFF
profile = {
    "driver": "GTiff",
    "dtype": "float32",
    "nodata": -9999.0,
    "width": width,
    "height": height,
    "count": 1,
    "crs": TARGET_CRS,
    "transform": transform,
    "tiled": True,
    "blockxsize": 512,
    "blockysize": 512,
    "compress": "lzw",
    "BIGTIFF": "YES",
}

with rasterio.open(out_tif, "w", **profile) as dst:
    dst.write(infilt_grid, 1)

print(f"Generated {out_tif} successfully!")
print(f"Statistics: Min={infilt_grid.min():.3f}, Mean={infilt_grid.mean():.3f}, Max={infilt_grid.max():.3f} mm/hr")
