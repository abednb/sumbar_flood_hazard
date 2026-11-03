"""
generate_soil_infiltration_raster.py
====================================
Generates the spatially distributed soil infiltration capacity raster (data/soil_infiltration_100m.tif)
by coupling Kementerian Pertanian Soil Texture (data_raw/soil/TeksturTanah_Kementan.gpkg)
with BIG RBI Land Cover (data_raw/rbi/landcover.gpkg, layer lc_sumbar_lok26) through the
empirical infiltration lookup matrix (lookup_tables/soil_infiltration_lookup.csv).

Units: mm/hr
Underlying scheme: Conservative constant-loss assumption (10-100x lower than textbook saturated
hydraulic conductivity Ksat to prevent continuous sponge drainage during continuous design hyetographs).
"""

import argparse
import sys
import time
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize

# Import centralized environment
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))
import _env

TARGET_CRS = "EPSG:32747"


def categorize_rbi(remark: str) -> str:
    """Categorizes granular RBI land cover strings into standardized matrix categories."""
    r = str(remark).lower()
    if "sawah" in r:
        return "sawah"
    elif any(k in r for k in ["permukiman", "gedung", "bangunan", "pelabuhan", "bandara", "kantor", "rumah sakit", "sekolah"]):
        return "permukiman"
    elif "kebun" in r or "perkebunan" in r:
        return "perkebunan"
    elif "tegalan" in r or "ladang" in r or "tagalan" in r:
        return "tegalan/ladang"
    elif "hutan" in r:
        return "hutan"
    elif any(k in r for k in ["semak", "belukar", "rumput", "padang"]):
        return "semak belukar"
    elif any(k in r for k in ["danau", "sungai", "waduk", "rawa", "air", "kolam", "empang", "tambak", "laut"]):
        return "badan air"
    else:
        return "default"


def generate_soil_infiltration_raster(
    soil_gpkg: str = "data_raw/soil/TeksturTanah_Kementan.gpkg",
    rbi_gpkg: str = "data_raw/rbi/landcover.gpkg",
    rbi_layer: str = "lc_sumbar_lok26",
    lookup_csv: str = "lookup_tables/soil_infiltration_lookup.csv",
    ref_dem: str = "data/fabdem_reprojected.tif",
    out_tif: str = "data/soil_infiltration_100m.tif",
    resolution: float = 100.0,
    default_rate: float = 0.50,
) -> Path:
    """
    Synthesizes the harmonized 2D infiltration grid.
    """
    t_start = time.time()
    out_path = Path(out_tif).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"=== Generating Harmonized Soil Infiltration Capacity Raster ({resolution}m) ===")

    # 1. Target Grid Extent from Reference DEM
    with rasterio.open(ref_dem) as ref:
        bounds = ref.bounds
        minx = np.floor(bounds.left / resolution) * resolution
        miny = np.floor(bounds.bottom / resolution) * resolution
        maxx = np.ceil(bounds.right / resolution) * resolution
        maxy = np.ceil(bounds.top / resolution) * resolution
        width = int((maxx - minx) / resolution)
        height = int((maxy - miny) / resolution)
        transform = rasterio.transform.from_bounds(minx, miny, maxx, maxy, width, height)

    print(f"Target Grid: {width} x {height} cells @ {resolution}m, CRS = {TARGET_CRS}")

    # 2. Load Lookup Matrix
    lookup_df = pd.read_csv(lookup_csv, comment="#")
    rate_map = {}
    for _, row in lookup_df.iterrows():
        s_tex = str(row["soil_texture"]).strip().lower()
        lc_cat = str(row["landcover_category"]).strip().lower()
        rate_map[(s_tex, lc_cat)] = float(row["infiltration_rate_mm_hr"])

    # 3. Load & Reproject Kementan Soil Texture
    print(f"Loading soil texture from {soil_gpkg}...")
    soil_gdf = gpd.read_file(soil_gpkg)
    if str(soil_gdf.crs) != TARGET_CRS:
        soil_gdf = soil_gdf.to_crs(TARGET_CRS)

    soil_gdf["clean_texture"] = soil_gdf["K_Tekstur"].fillna("Default").astype(str).str.strip().str.lower()
    soil_gdf.loc[soil_gdf["clean_texture"] == "-", "clean_texture"] = "default"

    texture_classes = sorted(soil_gdf["clean_texture"].unique().tolist())
    texture_to_id = {tex: i + 1 for i, tex in enumerate(texture_classes)}
    id_to_texture = {i + 1: tex for i, tex in enumerate(texture_classes)}
    soil_gdf["texture_id"] = soil_gdf["clean_texture"].map(texture_to_id)

    print("Rasterizing Soil Texture...")
    soil_shapes = ((geom, val) for geom, val in zip(soil_gdf.geometry, soil_gdf["texture_id"]) if geom is not None and not geom.is_empty)
    soil_raster = rasterize(soil_shapes, out_shape=(height, width), transform=transform, fill=0, dtype="uint8")

    # 4. Load & Reproject RBI Land Cover
    print(f"Loading RBI landcover layer '{rbi_layer}' from {rbi_gpkg}...")
    lc_gdf = gpd.read_file(rbi_gpkg, layer=rbi_layer)
    if str(lc_gdf.crs) != TARGET_CRS:
        lc_gdf = lc_gdf.to_crs(TARGET_CRS)

    lc_gdf["lc_cat"] = lc_gdf["REMARK"].apply(categorize_rbi)
    lc_classes = ["default", "sawah", "permukiman", "perkebunan", "tegalan/ladang", "hutan", "semak belukar", "badan air"]
    lc_to_id = {lc: i + 1 for i, lc in enumerate(lc_classes)}
    id_to_lc = {i + 1: lc for i, lc in enumerate(lc_classes)}
    lc_gdf["lc_id"] = lc_gdf["lc_cat"].map(lc_to_id)

    print("Rasterizing RBI Landcover...")
    lc_shapes = ((geom, val) for geom, val in zip(lc_gdf.geometry, lc_gdf["lc_id"]) if geom is not None and not geom.is_empty)
    lc_raster = rasterize(lc_shapes, out_shape=(height, width), transform=transform, fill=0, dtype="uint8")

    # 5. Synthesize Combined Infiltration Grid (float32, mm/hr)
    print("Synthesizing infiltration rate matrix...")
    infilt_grid = np.full((height, width), default_rate, dtype=np.float32)

    for tex_id, tex_name in id_to_texture.items():
        for lc_id, lc_name in id_to_lc.items():
            rate = rate_map.get((tex_name, lc_name))
            if rate is None:
                rate = rate_map.get((tex_name, "default"))
            if rate is None:
                rate = rate_map.get(("default", lc_name))
            if rate is None:
                rate = default_rate

            mask = (soil_raster == tex_id) & (lc_raster == lc_id)
            infilt_grid[mask] = rate

    for tex_id, tex_name in id_to_texture.items():
        rate = rate_map.get((tex_name, "default"), default_rate)
        mask = (soil_raster == tex_id) & (lc_raster == 0)
        infilt_grid[mask] = rate

    for lc_id, lc_name in id_to_lc.items():
        rate = rate_map.get(("default", lc_name), default_rate)
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

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(infilt_grid, 1)
        dst.set_band_description(1, "Conservative Soil Infiltration Rate (mm/hr)")

    print(f"[OK] Generated {out_path} in {time.time() - t_start:.1f}s")
    print(f"Statistics: Min={infilt_grid.min():.3f}, Mean={infilt_grid.mean():.3f}, Max={infilt_grid.max():.3f} mm/hr")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generate harmonized soil infiltration raster from Kementan x RBI matrix.")
    parser.add_argument("--soil", default="data_raw/soil/TeksturTanah_Kementan.gpkg", help="Path to Kementan soil GPKG")
    parser.add_argument("--rbi", default="data_raw/rbi/landcover.gpkg", help="Path to RBI landcover GPKG")
    parser.add_argument("--layer", default="lc_sumbar_lok26", help="Layer name in RBI GPKG")
    parser.add_argument("--lookup", default="lookup_tables/soil_infiltration_lookup.csv", help="Path to infiltration lookup CSV")
    parser.add_argument("--dem", default="data/fabdem_reprojected.tif", help="Reference DEM")
    parser.add_argument("--out", default="data/soil_infiltration_100m.tif", help="Output GeoTIFF path")
    parser.add_argument("--res", type=float, default=100.0, help="Resolution in meters (default 100m)")
    args = parser.parse_args()

    generate_soil_infiltration_raster(
        soil_gpkg=args.soil,
        rbi_gpkg=args.rbi,
        rbi_layer=args.layer,
        lookup_csv=args.lookup,
        ref_dem=args.dem,
        out_tif=args.out,
        resolution=args.res,
    )


if __name__ == "__main__":
    main()
