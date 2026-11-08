"""
test_refinement.py
==================
Unit tests for refine_flood_hazard_raster (Issue C3).
Tests:
1. Size-limited hole filling:
   - Small pit (area <= hole_mmu_px) enclosed by water IS filled.
   - Large island / hill (area > hole_mmu_px) enclosed by water REMAINS DRY.
2. Topographic depth reconstruction:
   - Cells with Zs < DEM are NEVER wet (no artificial hmin forcing).
"""

import numpy as np
import pytest
import rasterio
from scripts.sfincs_standalone_pipeline import refine_flood_hazard_raster


def test_size_limited_hole_filling_and_depth_reconstruction(tmp_path):
    # Create synthetic 50 x 50 test grid
    # Flood surface elevation: Zs = 10.0m
    # Background floodplain elevation: DEM = 8.0m -> raw depth = 2.0m (flooded)
    # Small enclosed dry pit: 2x2 = 4 pixels (< hole_mmu_px=25) at DEM = 8.0m, raw depth = 0 (dry)
    # Large enclosed dry hill: 10x10 = 100 pixels (> hole_mmu_px=25) at DEM = 15.0m (higher than Zs=10.0m!)
    shape = (50, 50)
    dem = np.full(shape, 8.0, dtype=np.float32)
    raw_depth = np.full(shape, 2.0, dtype=np.float32)

    # 1. Place small dry pit (4 pixels) inside flooded domain
    dem[10:12, 10:12] = 8.0
    raw_depth[10:12, 10:12] = 0.0

    # 2. Place large dry hill (100 pixels) inside flooded domain (mountain top above water level)
    dem[25:35, 25:35] = 15.0  # DEM 15m > Zs 10m
    raw_depth[25:35, 25:35] = 0.0

    # Save to temporary GeoTIFFs
    dem_path = tmp_path / "synthetic_dem.tif"
    depth_path = tmp_path / "flood_depth_10m.tif"

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": np.nan,
        "width": 50,
        "height": 50,
        "count": 1,
        "crs": "EPSG:32747",
        "transform": rasterio.transform.from_bounds(0, 0, 500, 500, 50, 50),
    }

    with rasterio.open(dem_path, "w", **profile) as dst:
        dst.write(dem, 1)

    with rasterio.open(depth_path, "w", **profile) as dst:
        dst.write(raw_depth, 1)

    # Execute refinement
    hole_mmu = 25  # Small pit (4 px) <= 25, Large hill (100 px) > 25
    refine_flood_hazard_raster(
        depth_tif=str(depth_path),
        dep_path=dem_path,
        hmin=0.05,
        island_mmu_px=10,
        hole_mmu_px=hole_mmu,
        bridge_radius=0,
        smooth_sigma=0.0,
        cosmetic=False,
    )

    # Verify preserved raw depth exists (Issue M7)
    raw_saved = tmp_path / "flood_depth_10m_raw.tif"
    assert raw_saved.exists(), "Raw depth raster was not preserved!"

    # Read refined depth and metadata tags
    with rasterio.open(depth_path) as dst:
        refined_depth = dst.read(1)
        tags = dst.tags()
        assert tags.get("mmu_scale") == "1:50000", f"Unexpected mmu_scale tag: {tags.get('mmu_scale')}"
        assert "Perka BIG" in tags.get("mmu_standard", ""), f"Unexpected mmu_standard tag: {tags.get('mmu_standard')}"

    # Assertion 1: Small dry pit (4 pixels) was filled
    pit_depths = refined_depth[10:12, 10:12]
    assert np.all(np.isfinite(pit_depths)), "Small dry pit was not filled!"
    assert np.all(pit_depths >= 0.05), "Small dry pit depth below hmin!"

    # Assertion 2: Large dry hill (100 pixels) MUST REMAIN DRY (Issue C3)
    hill_depths = refined_depth[25:35, 25:35]
    assert np.all(np.isnan(hill_depths)), "Large enclosed hill was erroneously flooded! Hole filling failed."

    # Assertion 3: Background floodplain remains flooded
    assert np.all(np.isfinite(refined_depth[2:5, 2:5]))


def test_morphological_bridging_across_embankment(tmp_path):
    """Verify that morphological closing bridges narrow road embankments/culverts."""
    shape = (30, 30)
    dem = np.full(shape, 5.0, dtype=np.float32)
    raw_depth = np.full(shape, 1.0, dtype=np.float32)
    raw_depth[:, 14:16] = 0.0  # 2-pixel wide dry road cut (20m @ 10m grid)

    dem_path = tmp_path / "dem_bridge.tif"
    depth_path = tmp_path / "flood_depth_bridge.tif"

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": np.nan,
        "width": 30,
        "height": 30,
        "count": 1,
        "crs": "EPSG:32747",
        "transform": rasterio.transform.from_bounds(0, 0, 300, 300, 30, 30),
    }

    with rasterio.open(dem_path, "w", **profile) as dst:
        dst.write(dem, 1)

    with rasterio.open(depth_path, "w", **profile) as dst:
        dst.write(raw_depth, 1)

    # Refine with bridge_radius=3 (30m closing kernel) and smooth_sigma=1.0
    refine_flood_hazard_raster(
        depth_tif=str(depth_path),
        dep_path=dem_path,
        hmin=0.05,
        island_mmu_px=10,
        hole_mmu_px=10,
        bridge_radius=3,
        smooth_sigma=1.0,
    )

    with rasterio.open(depth_path) as dst:
        bridged_depth = dst.read(1)

    # The interior 2-pixel road cut (rows 5 to 25) should now be bridged and flooded
    road_cut_depths = bridged_depth[5:25, 14:16]
    assert np.all(np.isfinite(road_cut_depths)), "Interior road embankment was not bridged by morphological closing!"
    assert np.all(road_cut_depths >= 0.05), "Bridged road cut depth below hmin!"

