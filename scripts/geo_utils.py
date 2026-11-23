"""
geo_utils.py
============
National Indonesian Geospatial Utilities for HydroMT-SFINCS Flood Hazard Standardization (v2.0).

Provides:
- Dynamic Auto-UTM EPSG detection across all Indonesian zones (46N–54N / 46S–54S; EPSG:32646–32754)
- Dynamic hydrograph recession scaling by catchment area (prevents late-peaking waves on large basins)
- Optional USWB/WMO 24-hour Areal Reduction Factor (ARF) for large catchments (> 100 km²)
- Canonical BIG RBI land-cover classification to 15 national classes (Manning's n & USDA-NRCS CN)
"""

from pathlib import Path
from typing import Optional, Tuple, Union
import geopandas as gpd
import numpy as np
import pyproj
import rasterio
from rasterio.warp import transform_bounds


def infer_utm_epsg_from_lonlat(lon: float, lat: float) -> int:
    """
    Computes the standard WGS 84 UTM EPSG code from geographic longitude and latitude.
    Covers all Indonesian zones:
      - Northern Hemisphere (lat >= 0): EPSG:32646 (Aceh/Sumut) .. EPSG:32654 (Papua/Maluku Utara)
      - Southern Hemisphere (lat <  0): EPSG:32746 (Sumbar/Bengkulu) .. EPSG:32754 (Papua Selatan)
    """
    zone = int(np.floor((float(lon) + 180.0) / 6.0)) + 1
    zone = max(1, min(60, zone))
    return (32600 + zone) if float(lat) >= 0.0 else (32700 + zone)


def infer_utm_crs_from_file(path: Union[str, Path]) -> str:
    """
    Infers the optimal WGS 84 UTM CRS ('EPSG:326XX' or 'EPSG:327XX') from the centroid of any
    raster (.tif/.vrt) or vector (.gpkg/.shp/.geojson/.parquet) geospatial file.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Cannot infer UTM CRS; file not found: {p}")

    if p.suffix.lower() in {".tif", ".tiff", ".vrt"}:
        with rasterio.open(p) as src:
            if src.crs is None:
                raise ValueError(f"Raster has no CRS metadata: {p}")
            minlon, minlat, maxlon, maxlat = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
            lon = 0.5 * (minlon + maxlon)
            lat = 0.5 * (minlat + maxlat)
    else:
        gdf = gpd.read_file(p)
        if gdf.empty or gdf.crs is None:
            raise ValueError(f"Vector dataset is empty or missing CRS: {p}")
        gdf_4326 = gdf.to_crs("EPSG:4326")
        minlon, minlat, maxlon, maxlat = gdf_4326.total_bounds
        lon = 0.5 * (minlon + maxlon)
        lat = 0.5 * (minlat + maxlat)

    return f"EPSG:{infer_utm_epsg_from_lonlat(lon, lat)}"


def resolve_target_crs(target_crs: Optional[str], reference_path: Union[str, Path]) -> str:
    """
    Resolves 'auto' or None to the appropriate WGS 84 UTM CRS for `reference_path`.
    If an explicit CRS string (e.g., 'EPSG:32747') is provided, validates and returns it.
    """
    if target_crs is None or str(target_crs).strip().lower() in {"", "auto", "utm"}:
        return infer_utm_crs_from_file(reference_path)
    crs_obj = pyproj.CRS.from_user_input(target_crs)
    epsg = crs_obj.to_epsg()
    return f"EPSG:{epsg}" if epsg else crs_obj.to_wkt()


def get_dynamic_recession_hours(area_km2: float, min_hours: int = 24) -> int:
    """
    Scales post-storm recession duration to watershed area so flood waves fully drain
    and pass peak-timing QA (<= 1% late-peaking cells) across both small coastal and large inland basins:
      - <  500 km² : 24 h (48 h total with 24 h storm)
      - 500–1500 km²: 36 h (60 h total)
      - > 1500 km² : 48 h (72 h total)
    """
    if area_km2 >= 1500.0:
        rec = 48
    elif area_km2 >= 500.0:
        rec = 36
    else:
        rec = 24
    return max(int(min_hours), rec)


def compute_wmo_arf(area_km2: float, duration_hr: float = 24.0) -> float:
    """
    Computes the Leclerc & Schaake (1972) analytical approximation of the USWB / WMO
    Areal Reduction Factor (ARF) for converting point design rainfall into catchment-average rainfall:
      ARF = 1 - exp(-1.1 * t^0.25) + exp(-1.1 * t^0.25 - 0.01 * A_mi2)
    Returns 1.0 for small catchments (< 25 km²) and clips conservatively to [0.75, 1.00].
    """
    if area_km2 < 25.0:
        return 1.0
    area_mi2 = float(area_km2) * 0.386102159
    c = 1.1 * (float(duration_hr) ** 0.25)
    arf = 1.0 - np.exp(-c) + np.exp(-c - 0.01 * area_mi2)
    return float(np.clip(arf, 0.75, 1.0))


def classify_rbi_canonical(remark: str) -> str:
    """
    Maps any Indonesian BIG RBI `REMARK` string (provincial or national) into one of
    15 canonical national land-cover categories used for Manning roughness & USDA-NRCS CN.
    """
    r = str(remark).strip().lower()
    if "sawah" in r:
        return "paddy_sawah"
    if any(k in r for k in ["laut", "pesisir"]):
        return "sea"
    if any(k in r for k in ["danau", "situ", "waduk", "sungai", "saluran", "kolam", "empang", "tambak", "gosong", "badan air"]):
        return "inland_water"
    if any(k in r for k in ["bakau", "mangrove"]):
        return "mangrove"
    if any(k in r for k in ["hutan rawa", "gambut"]):
        return "peat_swamp_forest"
    if "rawa" in r:
        return "marsh_swamp"
    if any(k in r for k in ["landas pacu", "taxiway", "apron", "dermaga", "jalan", "tol"]):
        return "paved_transport"
    if any(k in r for k in [
        "permukiman", "gedung", "bangunan", "industri", "kantor", "rumah sakit", "puskesmas",
        "pendidikan", "sekolah", "masjid", "gereja", "vihara", "pura", "saranaibadah",
        "bandara", "pelabuhan", "terminal", "stadion", "arenaolahraga", "spbu", "pompa",
        "pusat ", "lembaga", "instalasi", "panti", "gardu", "pembangkit", "pengolahan", "menara"
    ]):
        return "built_up_urban"
    if "sawah" in r:
        return "paddy_sawah"
    if any(k in r for k in ["hutan rakyat", "tanaman campur"]):
        return "agroforest_mixed"
    if "hutan" in r:
        return "dense_forest"
    if any(k in r for k in ["perkebunan", "kebun"]):
        return "plantation"
    if any(k in r for k in ["tegalan", "ladang", "tagalan", "budidaya lainnya"]):
        return "dryland_cropland"
    if any(k in r for k in ["semak", "belukar", "non budidaya"]):
        return "shrubland"
    if any(k in r for k in ["rumput", "lapangan", "makam", "pemakaman", "pariwisata"]):
        return "grassland_open"
    if any(k in r for k in ["tanah kosong", "pasir", "pertambangan", "batu", "gundul"]):
        return "bare_sand_mining"
    return "dryland_cropland"


def cn2_to_cn3(cn2: np.ndarray) -> np.ndarray:
    """Standard USDA-NRCS NEH Part 630 AMC-II -> AMC-III (saturated wet) Curve Number conversion."""
    return np.clip((23.0 * cn2) / (10.0 + 0.13 * cn2), 1.0, 100.0)


def cn2_to_cn1(cn2: np.ndarray) -> np.ndarray:
    """Standard USDA-NRCS NEH Part 630 AMC-II -> AMC-I (dry) Curve Number conversion."""
    return np.clip((4.2 * cn2) / (10.0 - 0.058 * cn2), 1.0, 100.0)
