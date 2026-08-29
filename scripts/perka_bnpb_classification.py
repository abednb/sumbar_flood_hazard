"""
perka_bnpb_classification.py

Standard classification module for flood depth rasters according to
Perka BNPB No. 2 Tahun 2012 (Pedoman Umum Pengkajian Risiko Bencana) using
ArcGIS-equivalent Fuzzy Large Membership and Raster Calculator logic.

1. Fuzzy Large Membership (Flood Hazard Index / FHI: 0 to 1):
   - Type     : "Large" (Left-asymmetric continuous sigmoidal curve)
   - Midpoint : 1.125
   - Spread   : 1.75
   - Formula  : FHI = 1.0 / (1.0 + (Depth / Midpoint) ** (-Spread))
   
2. Hazard Classification Level (Low, Medium, High):
   - Formula  : Con(FHI <= 0.333, 1, Con(FHI > 0.666, 3, 2))
   - Class 0  : Dry / Unflooded (< hmin = 0.05m or nodata)
   - Class 1  : Low Hazard (Rendah)    -> FHI <= 0.333
   - Class 2  : Medium Hazard (Sedang) -> 0.333 < FHI <= 0.666
   - Class 3  : High Hazard (Tinggi)   -> FHI > 0.666
"""

import os
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
import rasterio


def compute_fuzzy_large_membership(
    depth: np.ndarray,
    midpoint: float = 1.125,
    spread: float = 1.75,
) -> np.ndarray:
    """
    Computes ArcGIS-equivalent Fuzzy Large membership (Flood Hazard Index: 0.0 - 1.0).
    
    Formula:
        mu(x) = 1.0 / (1.0 + (x / midpoint) ** (-spread))
    """
    fhi = np.zeros_like(depth, dtype=np.float32)
    positive_mask = depth > 0.0
    
    with np.errstate(divide="ignore", invalid="ignore"):
        fhi[positive_mask] = 1.0 / (1.0 + (depth[positive_mask] / midpoint) ** (-spread))
        
    fhi = np.clip(fhi, 0.0, 1.0)
    return fhi


def classify_perka_bnpb(
    depth_raster: str,
    out_path: str,
    out_fhi_path: Optional[str] = None,
    hmin: float = 0.05,
    midpoint: float = 1.125,
    spread: float = 1.75,
    low_fhi_thresh: float = 0.333,
    high_fhi_thresh: float = 0.666,
) -> Tuple[str, Optional[str]]:
    """
    Transforms water depth into Flood Hazard Index (Fuzzy Large) and classifies into
    BNPB Perka 2/2012 hazard levels (1: Low, 2: Medium, 3: High).

    Parameters
    ----------
    depth_raster : str
        Path to the input water depth GeoTIFF (units: meters).
    out_path : str
        Path to the output classified hazard GeoTIFF (Class 1, 2, 3).
    out_fhi_path : str, optional
        Path to the continuous Flood Hazard Index GeoTIFF (0.0 to 1.0).
    hmin : float, optional
        Minimum inundation depth threshold (default 0.05m).
    midpoint : float, optional
        Fuzzy Large midpoint parameter (default 1.125).
    spread : float, optional
        Fuzzy Large spread parameter (default 1.75).
    low_fhi_thresh : float, optional
        Upper FHI threshold for Low Hazard class (default 0.333).
    high_fhi_thresh : float, optional
        Lower FHI threshold for High Hazard class (default 0.666).
    """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    if out_fhi_path:
        Path(out_fhi_path).parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(depth_raster) as src:
        depth = src.read(1)
        profile = src.profile.copy()
        nodata_val = src.nodata

    # Valid mask for flooded area
    valid_mask = ~np.isnan(depth)
    if nodata_val is not None:
        valid_mask &= depth != nodata_val
    flooded_mask = valid_mask & (depth >= hmin)

    # 1. Compute Fuzzy Large Membership (Flood Hazard Index: 0 - 1)
    fhi = np.zeros(depth.shape, dtype=np.float32)
    fhi[flooded_mask] = compute_fuzzy_large_membership(
        depth[flooded_mask], midpoint=midpoint, spread=spread
    )

    # 2. Raster Calculator Classification: Con(FHI <= 0.333, 1, Con(FHI > 0.666, 3, 2))
    hazard_class = np.zeros(depth.shape, dtype=np.uint8)
    hazard_class[flooded_mask & (fhi <= low_fhi_thresh)] = 1
    hazard_class[flooded_mask & (fhi > low_fhi_thresh) & (fhi <= high_fhi_thresh)] = 2
    hazard_class[flooded_mask & (fhi > high_fhi_thresh)] = 3

    # 3. Write Classified Hazard GeoTIFF (uint8)
    profile_class = profile.copy()
    profile_class.pop("blockxsize", None)
    profile_class.pop("blockysize", None)
    profile_class.pop("tiled", None)
    profile_class.update(
        dtype=rasterio.uint8,
        count=1,
        nodata=0,
        compress="lzw",
    )
    with rasterio.open(out_path, "w", **profile_class) as dst:
        dst.write(hazard_class, 1)
        dst.set_band_description(1, "BNPB Perka 2/2012 Flood Hazard Level (1:Low, 2:Medium, 3:High)")

    print(f"[OK] Classified BNPB hazard map written to: {out_path}")

    # 4. Write Continuous Flood Hazard Index GeoTIFF (float32, 0.0 - 1.0) if path provided
    if out_fhi_path:
        profile_fhi = profile.copy()
        profile_fhi.pop("blockxsize", None)
        profile_fhi.pop("blockysize", None)
        profile_fhi.pop("tiled", None)
        profile_fhi.update(
            dtype=rasterio.float32,
            count=1,
            nodata=np.nan,
            compress="lzw",
        )
        fhi_masked = np.where(flooded_mask, fhi, np.nan).astype(np.float32)
        with rasterio.open(out_fhi_path, "w", **profile_fhi) as dst_fhi:
            dst_fhi.write(fhi_masked, 1)
            dst_fhi.set_band_description(1, "Fuzzy Large Flood Hazard Index (0.0 to 1.0)")
        print(f"[OK] Continuous Flood Hazard Index written to: {out_fhi_path}")

    return out_path, out_fhi_path
