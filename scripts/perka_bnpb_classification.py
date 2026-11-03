"""
perka_bnpb_classification.py
============================
Authoritative disaster hazard classification module according to:
    Peraturan Kepala Badan Nasional Penanggulangan Bencana No. 02 Tahun 2012
    (Pedoman Umum Pengkajian Risiko Bencana), Lampiran Bab III: Pengkajian Bahaya Banjir.
    BNPB, Jakarta (2012).

Hazard Level Thresholds (Physical Depth):
    - Class 0: Unflooded / Dry (h < hmin, default 0.05m)
    - Class 1: Rendah (Low Hazard)    -> hmin <= h < 0.76m
    - Class 2: Sedang (Medium Hazard) -> 0.76m <= h <= 1.50m
    - Class 3: Tinggi (High Hazard)   -> h > 1.50m

Supported Methods:
    - "depth": Direct physical inundation depth interval classification (Recommended standard).
    - "fuzzy": Continuous sigmoidal Fuzzy Large membership function (Flood Hazard Index: 0.0 to 1.0)
               with analytical threshold derivation matching the physical depth boundaries:
               thr = 1.0 / (1.0 + (depth_thresh / midpoint) ** (-spread))
"""

from pathlib import Path
from typing import Literal, Optional, Tuple, Union
import numpy as np
import rasterio

# ==============================================================================
# AUTHORITATIVE CARTOGRAPHIC COLOR PALETTE
# ==============================================================================
# Official Cartographic standards for Indonesian disaster hazard mapping:
#   - Rendah (Low Hazard)    : #34A853 / rgb(52, 168, 83)   (Green)
#   - Sedang (Medium Hazard) : #FBBC05 / rgb(251, 188, 5)   (Amber / Yellow)
#   - Tinggi (High Hazard)   : #EA4335 / rgb(234, 67, 53)  (Red)
#
# Continuous Flood Hazard Index (FHI 0.0 to 1.0) gradual color interpolation:
#   Rendah (#34A853) -> Sedang (#FBBC05) -> Tinggi (#EA4335)
# ==============================================================================

PERKA_COLOR_HEX = {
    "Rendah": "#34A853",
    "Sedang": "#FBBC05",
    "Tinggi": "#EA4335",
}

PERKA_COLOR_RGB = {
    "Rendah": (52, 168, 83),
    "Sedang": (251, 188, 5),
    "Tinggi": (234, 67, 53),
}

# Embedded GeoTIFF 8-bit RGBA Colormap (GDAL / QGIS / ArcGIS compliant)
PERKA_COLORMAP_RGBA = {
    0: (0, 0, 0, 0),        # Dry / Unflooded / NoData (Transparent)
    1: (52, 168, 83, 255),   # Rendah (#34A853)
    2: (251, 188, 5, 255),  # Sedang (#FBBC05)
    3: (234, 67, 53, 255),  # Tinggi (#EA4335)
}
PERKA_COLOR_RGBA = PERKA_COLORMAP_RGBA


def get_perka_discrete_cmap():
    """
    Returns a matplotlib ListedColormap for discrete Perka BNPB hazard classes:
    1: Rendah (#34A853), 2: Sedang (#FBBC05), 3: Tinggi (#EA4335).
    """
    from matplotlib.colors import ListedColormap
    return ListedColormap(
        [PERKA_COLOR_HEX["Rendah"], PERKA_COLOR_HEX["Sedang"], PERKA_COLOR_HEX["Tinggi"]],
        name="perka_bnpb_discrete",
    )


def get_fhi_continuous_cmap():
    """
    Returns a matplotlib LinearSegmentedColormap for continuous Flood Hazard Index (0.0 to 1.0):
    Gradual color ramp across Rendah (#34A853) -> Sedang (#FBBC05) -> Tinggi (#EA4335).
    """
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list(
        "fhi_continuous_ramp",
        [PERKA_COLOR_HEX["Rendah"], PERKA_COLOR_HEX["Sedang"], PERKA_COLOR_HEX["Tinggi"]],
    )


def write_perka_hazard_qml(out_qml_path: Union[str, Path]) -> str:
    """
    Writes a standalone QGIS Layer Style file (.qml) for discrete Perka BNPB hazard classes.
    Automatically loaded by QGIS when placed alongside hazard_class_perka2012.tif.
    """
    qml_content = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.0" styleCategories="AllStyleCategories">
  <pipe>
    <rasterrenderer type="paletted" opacity="1" band="1">
      <colorPalette>
        <paletteEntry value="0" color="#000000" alpha="0" label="Kering / Nodata"/>
        <paletteEntry value="1" color="{PERKA_COLOR_HEX['Rendah']}" alpha="255" label="Rendah (h &lt; 0.76 m)"/>
        <paletteEntry value="2" color="{PERKA_COLOR_HEX['Sedang']}" alpha="255" label="Sedang (0.76 - 1.50 m)"/>
        <paletteEntry value="3" color="{PERKA_COLOR_HEX['Tinggi']}" alpha="255" label="Tinggi (h &gt; 1.50 m)"/>
      </colorPalette>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0"/>
    <huesaturation colorizeGreen="128" colorizeOn="0" saturation="0" grayscaleMode="0" colorizeRed="255" colorizeBlue="128" colorizeStrength="100"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
"""
    p = Path(out_qml_path)
    p.write_text(qml_content, encoding="utf-8")
    return str(p)


def write_fhi_continuous_qml(out_qml_path: Union[str, Path]) -> str:
    """
    Writes a standalone QGIS Layer Style file (.qml) for continuous Flood Hazard Index (0.0 to 1.0).
    Automatically loaded by QGIS when placed alongside flood_hazard_index.tif.
    """
    qml_content = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.0" styleCategories="AllStyleCategories">
  <pipe>
    <rasterrenderer type="singlebandpseudocolor" opacity="1" band="1" classificationMin="0" classificationMax="1">
      <rastershader>
        <colorrampshader colorRampType="INTERPOLATED" clip="0" classificationMode="1">
          <item value="0.0" color="{PERKA_COLOR_HEX['Rendah']}" alpha="255" label="0.0 (Rendah)"/>
          <item value="0.5" color="{PERKA_COLOR_HEX['Sedang']}" alpha="255" label="0.5 (Sedang)"/>
          <item value="1.0" color="{PERKA_COLOR_HEX['Tinggi']}" alpha="255" label="1.0 (Tinggi)"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0"/>
    <huesaturation colorizeGreen="128" colorizeOn="0" saturation="0" grayscaleMode="0" colorizeRed="255" colorizeBlue="128" colorizeStrength="100"/>
    <rasterresampler maxOversampling="2"/>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
"""
    p = Path(out_qml_path)
    p.write_text(qml_content, encoding="utf-8")
    return str(p)


def compute_fuzzy_large_membership(
    depth: np.ndarray,
    midpoint: float = 1.125,
    spread: float = 1.75,
) -> np.ndarray:
    """
    Computes ArcGIS-equivalent Fuzzy Large membership (Flood Hazard Index / FHI: 0.0 - 1.0).

    Formula:
        mu(x) = 1.0 / (1.0 + (x / midpoint) ** (-spread))
    """
    fhi = np.zeros_like(depth, dtype=np.float32)
    positive_mask = depth > 0.0

    with np.errstate(divide="ignore", invalid="ignore"):
        fhi[positive_mask] = 1.0 / (1.0 + (depth[positive_mask] / midpoint) ** (-spread))

    return np.clip(fhi, 0.0, 1.0)


def depth_to_fuzzy_threshold(
    depth_val: float,
    midpoint: float = 1.125,
    spread: float = 1.75,
) -> float:
    """
    Analytically derives the exact FHI threshold corresponding to a given physical depth.
    """
    if depth_val <= 0:
        return 0.0
    return float(1.0 / (1.0 + (depth_val / midpoint) ** (-spread)))


def classify_depth_array(
    depth: np.ndarray,
    hmin: float = 0.05,
    low_thresh: float = 0.76,
    high_thresh: float = 1.50,
    method: Literal["depth", "fuzzy"] = "depth",
    midpoint: float = 1.125,
    spread: float = 1.75,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Classifies a numpy array of flood depths into BNPB Perka 2/2012 hazard classes (0, 1, 2, 3)
    and computes the continuous Flood Hazard Index (0.0 to 1.0).

    Returns
    -------
    hazard_class : np.ndarray (uint8)
    fhi : np.ndarray (float32)
    """
    valid_mask = np.isfinite(depth) & (depth >= hmin)
    fhi = np.zeros_like(depth, dtype=np.float32)
    fhi[valid_mask] = compute_fuzzy_large_membership(
        depth[valid_mask], midpoint=midpoint, spread=spread
    )

    hazard_class = np.zeros_like(depth, dtype=np.uint8)

    if method == "depth":
        hazard_class[valid_mask & (depth < low_thresh)] = 1
        hazard_class[valid_mask & (depth >= low_thresh) & (depth <= high_thresh)] = 2
        hazard_class[valid_mask & (depth > high_thresh)] = 3
    elif method == "fuzzy":
        fhi_low = depth_to_fuzzy_threshold(low_thresh, midpoint, spread)
        fhi_high = depth_to_fuzzy_threshold(high_thresh, midpoint, spread)
        hazard_class[valid_mask & (fhi < fhi_low)] = 1
        hazard_class[valid_mask & (fhi >= fhi_low) & (fhi <= fhi_high)] = 2
        hazard_class[valid_mask & (fhi > fhi_high)] = 3
    else:
        raise ValueError(f"Unknown classification method '{method}'. Choose 'depth' or 'fuzzy'.")

    return hazard_class, fhi


def classify_perka_bnpb(
    depth_raster: Union[str, Path],
    out_path: Union[str, Path],
    out_fhi_path: Optional[Union[str, Path]] = None,
    hmin: float = 0.05,
    low_thresh: float = 0.76,
    high_thresh: float = 1.50,
    method: Literal["depth", "fuzzy"] = "depth",
    midpoint: float = 1.125,
    spread: float = 1.75,
) -> Tuple[str, Optional[str]]:
    """
    Classifies a water depth GeoTIFF into BNPB Perka 2/2012 hazard levels and writes
    the classified hazard raster and continuous Flood Hazard Index raster.

    Parameters
    ----------
    depth_raster : str or Path
        Path to the input water depth GeoTIFF (units: meters).
    out_path : str or Path
        Path to output classified hazard GeoTIFF (Class 1: Low, 2: Medium, 3: High).
    out_fhi_path : str or Path, optional
        Path to output continuous Flood Hazard Index GeoTIFF (0.0 to 1.0).
    hmin : float
        Minimum inundation depth threshold (m), default 0.05m.
    low_thresh : float
        Upper boundary of Low Hazard / lower boundary of Medium Hazard (m), default 0.76m.
    high_thresh : float
        Upper boundary of Medium Hazard / lower boundary of High Hazard (m), default 1.50m.
    method : {"depth", "fuzzy"}
        Classification method (default: "depth").
    midpoint : float
        Fuzzy Large midpoint parameter (default: 1.125).
    spread : float
        Fuzzy Large spread parameter (default: 1.75).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_fhi_path:
        out_fhi_path = Path(out_fhi_path)
        out_fhi_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(depth_raster) as src:
        depth = src.read(1)
        profile = src.profile.copy()
        nodata_val = src.nodata

    # Treat nodata and non-finite as NaN
    if nodata_val is not None:
        depth = np.where(depth == nodata_val, np.nan, depth)
    depth = np.where(~np.isfinite(depth), np.nan, depth)

    # Classify
    hazard_class, fhi = classify_depth_array(
        depth=depth,
        hmin=hmin,
        low_thresh=low_thresh,
        high_thresh=high_thresh,
        method=method,
        midpoint=midpoint,
        spread=spread,
    )

    # 1. Write Classified Hazard GeoTIFF (uint8)
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
        # Embed authoritative 8-bit RGBA color table (Rendah: #34A853, Sedang: #FBBC05, Tinggi: #EA4335)
        dst.write_colormap(1, PERKA_COLORMAP_RGBA)
        dst.set_band_description(1, f"BNPB Perka 2/2012 Flood Hazard Level (1:Low, 2:Medium, 3:High) [{method} method]")
        dst.update_tags(
            standard="Perka BNPB No. 02/2012",
            method=method,
            hmin=str(hmin),
            low_thresh=str(low_thresh),
            high_thresh=str(high_thresh),
            midpoint=str(midpoint),
            spread=str(spread),
            color_rendah=PERKA_COLOR_HEX["Rendah"],
            color_sedang=PERKA_COLOR_HEX["Sedang"],
            color_tinggi=PERKA_COLOR_HEX["Tinggi"],
        )

    # Write companion QGIS layer style (.qml)
    qml_hazard_path = out_path.with_suffix(".qml")
    write_perka_hazard_qml(qml_hazard_path)
    print(f"[OK] Classified BNPB hazard map ({method} mode) written to: {out_path}")
    print(f"[OK] QGIS layer style written to: {qml_hazard_path}")

    # 2. Write Continuous Flood Hazard Index GeoTIFF (float32, 0.0 - 1.0)
    out_fhi_str = None
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
        fhi_masked = np.where(depth >= hmin, fhi, np.nan).astype(np.float32)
        with rasterio.open(out_fhi_path, "w", **profile_fhi) as dst_fhi:
            dst_fhi.write(fhi_masked, 1)
            dst_fhi.set_band_description(1, "Fuzzy Large Flood Hazard Index (0.0 to 1.0)")
            dst_fhi.update_tags(
                standard="Perka BNPB No. 02/2012 Fuzzy Large",
                midpoint=str(midpoint),
                spread=str(spread),
                color_ramp="Rendah(#34A853)->Sedang(#FBBC05)->Tinggi(#EA4335)",
            )
        # Write companion QGIS continuous color ramp style (.qml)
        qml_fhi_path = out_fhi_path.with_suffix(".qml")
        write_fhi_continuous_qml(qml_fhi_path)
        print(f"[OK] Continuous Flood Hazard Index written to: {out_fhi_path}")
        print(f"[OK] QGIS continuous layer style written to: {qml_fhi_path}")
        out_fhi_str = str(out_fhi_path)

    return str(out_path), out_fhi_str
