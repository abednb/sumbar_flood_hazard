"""
test_perka_bnpb_classification.py
=================================
Unit tests for Perka BNPB No. 02/2012 classification in both 'depth' and 'fuzzy' modes.
Verifies exact class threshold boundaries:
- Low:    hmin <= h < 0.76m
- Medium: 0.76m <= h <= 1.50m
- High:   h > 1.50m
"""

import numpy as np
import pytest
from scripts.perka_bnpb_classification import (
    classify_depth_array,
    compute_fuzzy_large_membership,
    depth_to_fuzzy_threshold,
)


def test_perka_depth_mode_thresholds():
    test_depths = np.array([0.02, 0.05, 0.50, 0.74, 0.76, 0.80, 1.49, 1.50, 1.51, 1.60, 3.00], dtype=np.float32)
    classes, fhi = classify_depth_array(
        depth=test_depths,
        hmin=0.05,
        low_thresh=0.76,
        high_thresh=1.50,
        method="depth",
    )

    expected = np.array([0, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3], dtype=np.uint8)
    np.testing.assert_array_equal(classes, expected)


def test_perka_fuzzy_mode_thresholds():
    # Acceptance criteria from prompt:
    # h = 0.74 -> 1, 0.80 -> 2, 1.49 -> 2, 1.51 -> 3, and 1.60 -> 3 in both modes
    test_depths = np.array([0.02, 0.05, 0.50, 0.74, 0.76, 0.80, 1.49, 1.50, 1.51, 1.60, 3.00], dtype=np.float32)
    classes, fhi = classify_depth_array(
        depth=test_depths,
        hmin=0.05,
        low_thresh=0.76,
        high_thresh=1.50,
        method="fuzzy",
        midpoint=1.125,
        spread=1.75,
    )

    expected = np.array([0, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3], dtype=np.uint8)
    np.testing.assert_array_equal(classes, expected)


def test_analytical_fuzzy_monotonicity():
    midpoint = 1.125
    spread = 1.75
    fhi_low = depth_to_fuzzy_threshold(0.76, midpoint, spread)
    fhi_high = depth_to_fuzzy_threshold(1.50, midpoint, spread)

    assert 0.30 < fhi_low < 0.40
    assert 0.60 < fhi_high < 0.70
    assert fhi_low < fhi_high


def test_nan_and_negative_depth_handling():
    test_depths = np.array([np.nan, -0.5, 0.0, np.inf, 0.8], dtype=np.float32)
    classes, fhi = classify_depth_array(test_depths, hmin=0.05, method="depth")

    assert classes[0] == 0  # nan
    assert classes[1] == 0  # negative
    assert classes[2] == 0  # zero
    assert classes[3] == 0  # inf
    assert classes[4] == 2  # 0.8m -> Medium hazard


def test_cartographic_color_definitions():
    from scripts.perka_bnpb_classification import (
        PERKA_COLOR_HEX,
        PERKA_COLOR_RGBA,
        PERKA_COLOR_RGB,
        get_perka_discrete_cmap,
        get_fhi_continuous_cmap,
    )
    # Check exact hex codes requested by user:
    # Tinggi: #EA4335 rgb(234, 67, 53)
    # Sedang: #FBBC05 rgb(251, 188, 5)
    # Rendah: #34A853 rgb(52, 168, 83)
    assert PERKA_COLOR_HEX["Tinggi"].upper() == "#EA4335"
    assert PERKA_COLOR_HEX["Sedang"].upper() == "#FBBC05"
    assert PERKA_COLOR_HEX["Rendah"].upper() == "#34A853"

    assert PERKA_COLOR_RGB["Tinggi"] == (234, 67, 53)
    assert PERKA_COLOR_RGB["Sedang"] == (251, 188, 5)
    assert PERKA_COLOR_RGB["Rendah"] == (52, 168, 83)

    assert PERKA_COLOR_RGBA[0] == (0, 0, 0, 0)
    assert PERKA_COLOR_RGBA[1] == (52, 168, 83, 255)
    assert PERKA_COLOR_RGBA[2] == (251, 188, 5, 255)
    assert PERKA_COLOR_RGBA[3] == (234, 67, 53, 255)

    # Test colormap constructors
    discrete_cmap = get_perka_discrete_cmap()
    assert discrete_cmap.N == 3

    continuous_cmap = get_fhi_continuous_cmap()
    # Check continuous ramp endpoints and midpoint
    c_start = continuous_cmap(0.0)
    c_mid = continuous_cmap(0.5)
    c_end = continuous_cmap(1.0)
    # Green at 0.0
    assert round(c_start[0] * 255) == 52
    assert round(c_start[1] * 255) == 168
    assert round(c_start[2] * 255) == 83
    # Red at 1.0
    assert round(c_end[0] * 255) == 234
    assert round(c_end[1] * 255) == 67
    assert round(c_end[2] * 255) == 53


def test_classify_and_style_generation(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    from scripts.perka_bnpb_classification import classify_perka_bnpb

    depth_data = np.array([[0.0, 0.5], [1.0, 2.0]], dtype=np.float32)
    depth_file = tmp_path / "test_depth.tif"
    hazard_file = tmp_path / "hazard_class_perka2012.tif"
    fhi_file = tmp_path / "flood_hazard_index.tif"

    profile = {
        "driver": "GTiff",
        "height": 2,
        "width": 2,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:32747",
        "transform": from_origin(100, 200, 10, 10),
        "nodata": -9999.0,
    }
    with rasterio.open(depth_file, "w", **profile) as dst:
        dst.write(depth_data, 1)

    out_haz, out_fhi = classify_perka_bnpb(
        depth_raster=depth_file,
        out_path=hazard_file,
        out_fhi_path=fhi_file,
        hmin=0.05,
    )

    # Verify embedded GeoTIFF colormap
    with rasterio.open(out_haz) as src:
        colormap = src.colormap(1)
        assert colormap[1] == (52, 168, 83, 255)   # Rendah
        assert colormap[2] == (251, 188, 5, 255)  # Sedang
        assert colormap[3] == (234, 67, 53, 255)  # Tinggi
        assert colormap[0] == (0, 0, 0, 0)        # Nodata

    # Verify companion QGIS .qml style files were generated
    qml_hazard = hazard_file.with_suffix(".qml")
    qml_fhi = fhi_file.with_suffix(".qml")
    assert qml_hazard.exists()
    assert qml_fhi.exists()
    assert "#34A853" in qml_hazard.read_text(encoding="utf-8")
    assert "#EA4335" in qml_fhi.read_text(encoding="utf-8")
