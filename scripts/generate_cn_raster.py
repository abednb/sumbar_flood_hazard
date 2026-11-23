"""
generate_cn_raster.py
=====================
Generates 100 m USDA-NRCS SCS Curve Number (CN) GeoTIFFs (AMC-II average and AMC-III saturated)
by intersecting Kementerian Pertanian Soil Texture (Hydrologic Soil Group A–D) with
BIG RBI Land Cover (via canonical 15-class lookup_tables/national_rbi_lookup.csv).

Used by SFINCS v2.4.0+ modern CNB infiltration (`smaxfile` + `sefffile` + `ksfile` in meters),
avoiding the broken legacy `scsfile` (`cna`) binary path in SFINCS v2.4.0 Galibier.

Supports automatic Indonesian UTM CRS detection (`--crs auto`) so it works across any Kabupaten
from Aceh (EPSG:32646) to Papua (EPSG:32754).
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
from rasterio.warp import reproject, Resampling, transform_bounds

script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))
import _env  # noqa: F401
from geo_utils import classify_rbi_canonical, cn2_to_cn3, resolve_target_crs

# Kementan soil texture -> USDA-NRCS Hydrologic Soil Group (HSG A–D)
TEXTURE_TO_HSG = {
    "kasar": "A",
    "agak kasar": "B",
    "sedang": "B",
    "agak halus": "C",
    "halus": "D",
    "matang": "D",
    "agak matang": "D",
    "mentah": "D",
}


def generate_cn_rasters(
    soil_gpkg: str = "data_raw/soil/TeksturTanah_Kementan.gpkg",
    lc_raster: str = "data/landcover_rbi.tif",
    manning_lookup_csv: str = "lookup_tables/manning_lookup.csv",
    national_lookup_csv: str = "lookup_tables/national_rbi_lookup.csv",
    ref_dem: str = "data_raw/fabdem/FABDEM30m_Sumbar.tif",
    out_cn_amc2: str = "data/cn_amc2_100m.tif",
    out_cn_amc3: str = "data/cn_amc3_100m.tif",
    resolution: float = 100.0,
    target_crs: str = "auto",
) -> tuple[Path, Path]:
    """
    Synthesizes 100 m USDA-NRCS Curve Number GeoTIFFs (AMC-II and AMC-III) from Kementan soil
    texture polygons and the harmonized BIG RBI integer land-cover raster.
    """
    t0 = time.time()
    dem_path = Path(ref_dem).resolve()
    lc_path = Path(lc_raster).resolve()
    soil_path = Path(soil_gpkg).resolve()
    out_2 = Path(out_cn_amc2).resolve()
    out_3 = Path(out_cn_amc3).resolve()
    out_2.parent.mkdir(parents=True, exist_ok=True)
    out_3.parent.mkdir(parents=True, exist_ok=True)

    resolved_crs = resolve_target_crs(target_crs, dem_path if dem_path.exists() else lc_path)

    # 1. Target grid aligned to reference DEM (or landcover raster if DEM omitted)
    ref_src_path = dem_path if dem_path.exists() else lc_path
    with rasterio.open(ref_src_path) as ref:
        if str(ref.crs) != resolved_crs:
            left, bottom, right, top = transform_bounds(ref.crs, resolved_crs, *ref.bounds)
        else:
            left, bottom, right, top = ref.bounds
    minx = np.floor(left / resolution) * resolution
    miny = np.floor(bottom / resolution) * resolution
    maxx = np.ceil(right / resolution) * resolution
    maxy = np.ceil(top / resolution) * resolution
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)
    transform = rasterio.transform.from_bounds(minx, miny, maxx, maxy, width, height)

    print(f"=== Generating USDA-NRCS SCS Curve Number Rasters ({resolution:.0f} m, {resolved_crs}) ===")
    print(f"Grid: {width} x {height} cells")

    # 2. Rasterize Kementan Soil Texture -> HSG (1=A, 2=B, 3=C, 4=D)
    soil_gdf = gpd.read_file(soil_path)
    if str(soil_gdf.crs) != resolved_crs:
        soil_gdf = soil_gdf.to_crs(resolved_crs)
    tex_col = next((c for c in ["K_Tekstur", "k_tekstur", "TEKSTUR", "tekstur"] if c in soil_gdf.columns), None)
    if tex_col is None:
        raise KeyError(f"No texture column found in {soil_path}. Available: {list(soil_gdf.columns)}")

    hsg_map = {"A": 1, "B": 2, "C": 3, "D": 4}
    soil_gdf["hsg_int"] = (
        soil_gdf[tex_col].fillna("").astype(str).str.strip().str.lower()
        .map(TEXTURE_TO_HSG).fillna("C").map(hsg_map).astype("uint8")
    )
    hsg_grid = rasterize(
        ((g, v) for g, v in zip(soil_gdf.geometry, soil_gdf["hsg_int"]) if g is not None and not g.is_empty),
        out_shape=(height, width),
        transform=transform,
        fill=3,  # Default HSG C
        dtype="uint8",
    )

    # 3. Resample landcover raster to target 100 m grid using modal class
    lc_grid = np.zeros((height, width), dtype="uint8")
    with rasterio.open(lc_path) as lc_src:
        reproject(
            source=rasterio.band(lc_src, 1),
            destination=lc_grid,
            src_transform=lc_src.transform,
            src_crs=lc_src.crs,
            dst_transform=transform,
            dst_crs=resolved_crs,
            resampling=Resampling.mode,
        )

    # 4. Build (lc_id, hsg_int) -> CN_II table via canonical national_rbi_lookup.csv
    nat_df = pd.read_csv(national_lookup_csv)
    nat_by_name = {
        str(r["canonical_class"]).strip(): {
            1: float(r["cn_hsg_a"]),
            2: float(r["cn_hsg_b"]),
            3: float(r["cn_hsg_c"]),
            4: float(r["cn_hsg_d"]),
        }
        for _, r in nat_df.iterrows()
    }
    nat_by_id = {int(r["class_id"]): str(r["canonical_class"]).strip() for _, r in nat_df.iterrows()}

    id_to_canon = {0: "nodata_unclassified"}
    if Path(manning_lookup_csv).exists():
        mlookup = pd.read_csv(manning_lookup_csv)
        id_col = "rbi_id" if "rbi_id" in mlookup.columns else "class_id"
        name_col = "rbi_class_name" if "rbi_class_name" in mlookup.columns else "canonical_class"
        for _, row in mlookup.iterrows():
            cid = int(row[id_col])
            cname = str(row[name_col])
            id_to_canon[cid] = cname if cname in nat_by_name else classify_rbi_canonical(cname)
    else:
        id_to_canon.update(nat_by_id)

    cn2_grid = np.full((height, width), 82.0, dtype=np.float32)
    for lc_id, canon in id_to_canon.items():
        lc_m = (lc_grid == lc_id)
        if not np.any(lc_m):
            continue
        cn_dict = nat_by_name.get(canon, nat_by_name["nodata_unclassified"])
        for h_int in (1, 2, 3, 4):
            m = lc_m & (hsg_grid == h_int)
            if np.any(m):
                cn2_grid[m] = cn_dict[h_int]

    cn3_grid = cn2_to_cn3(cn2_grid).astype(np.float32)

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": -9999.0,
        "width": width,
        "height": height,
        "count": 1,
        "crs": resolved_crs,
        "transform": transform,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "compress": "lzw",
        "BIGTIFF": "YES",
    }

    with rasterio.open(out_2, "w", **profile) as dst:
        dst.write(cn2_grid, 1)
        dst.set_band_description(1, "USDA-NRCS SCS Curve Number (AMC-II Average)")
    with rasterio.open(out_3, "w", **profile) as dst:
        dst.write(cn3_grid, 1)
        dst.set_band_description(1, "USDA-NRCS SCS Curve Number (AMC-III Saturated)")

    print(
        f"[OK] Generated CN rasters in {time.time() - t0:.1f}s:\n"
        f"     AMC-II : {out_2} (min={cn2_grid.min():.1f}, mean={cn2_grid.mean():.1f}, max={cn2_grid.max():.1f})\n"
        f"     AMC-III: {out_3} (min={cn3_grid.min():.1f}, mean={cn3_grid.mean():.1f}, max={cn3_grid.max():.1f})"
    )
    return out_2, out_3


def main():
    parser = argparse.ArgumentParser(description="Generate USDA-NRCS SCS Curve Number (AMC-II & AMC-III) rasters.")
    parser.add_argument("--soil", default="data_raw/soil/TeksturTanah_Kementan.gpkg", help="Kementan soil texture GPKG")
    parser.add_argument("--lc", default="data/landcover_rbi.tif", help="Harmonized BIG RBI landcover GeoTIFF")
    parser.add_argument("--manning-lookup", default="lookup_tables/manning_lookup.csv", help="RBI integer ID lookup CSV")
    parser.add_argument("--national-lookup", default="lookup_tables/national_rbi_lookup.csv", help="Canonical 15-class national lookup CSV")
    parser.add_argument("--dem", default="data_raw/fabdem/FABDEM30m_Sumbar.tif", help="Reference DEM for grid bounds & Auto-UTM")
    parser.add_argument("--out-amc2", default="data/cn_amc2_100m.tif", help="Output AMC-II Curve Number GeoTIFF")
    parser.add_argument("--out-amc3", default="data/cn_amc3_100m.tif", help="Output AMC-III Curve Number GeoTIFF")
    parser.add_argument("--res", type=float, default=100.0, help="Grid resolution in meters (default: 100m)")
    parser.add_argument("--crs", default="auto", help="Target CRS or 'auto' for Indonesian Auto-UTM (default: auto)")
    args = parser.parse_args()

    generate_cn_rasters(
        soil_gpkg=args.soil,
        lc_raster=args.lc,
        manning_lookup_csv=args.manning_lookup,
        national_lookup_csv=args.national_lookup,
        ref_dem=args.dem,
        out_cn_amc2=args.out_amc2,
        out_cn_amc3=args.out_amc3,
        resolution=args.res,
        target_crs=args.crs,
    )


if __name__ == "__main__":
    main()
