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
        assert "BIG" in tags.get("mmu_standard", "") and "SNI 6502.3:2010" in tags.get("mmu_standard", ""), f"Unexpected mmu_standard tag: {tags.get('mmu_standard')}"

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


def test_nearest_neighbor_hole_infilling(tmp_path):
    """
    Verify hydrostatic hole-infilling rules:
    1. Shallow enclosed micro-void <= hole_mmu_px where Zs > DEM (depth_phys > 0) IS bridged.
    2. Elevated dry mound <= hole_mmu_px where DEM > Zs (depth_phys <= 0) REMAINS STRICTLY DRY!
    3. Large dry island > hole_mmu_px REMAINS STRICTLY DRY!
    """
    shape = (40, 40)
    dem = np.full(shape, 5.0, dtype=np.float32)
    raw_depth = np.full(shape, 1.5, dtype=np.float32)  # Flooded domain with Zs = 6.5m

    # 1. Shallow enclosed 3x3 void (9 px <= hole_mmu=25) STILL below Zs=6.5m (DEM=6.48m -> depth_phys=0.02m > 0)
    dem[18:21, 18:21] = 6.48
    raw_depth[18:21, 18:21] = 0.0

    # 2. Small elevated dry mound (3x3 = 9 px <= hole_mmu=25) ABOVE Zs=6.5m (DEM=8.5m > Zs=6.5m -> MUST STAY DRY!)
    dem[28:31, 28:31] = 8.5
    raw_depth[28:31, 28:31] = 0.0

    # 3. Large dry island (12x12 = 144 px > hole_mmu=25)
    dem[2:14, 2:14] = 10.0
    raw_depth[2:14, 2:14] = 0.0

    dem_path = tmp_path / "dem_holes.tif"
    depth_path = tmp_path / "flood_depth_holes.tif"

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": np.nan,
        "width": 40,
        "height": 40,
        "count": 1,
        "crs": "EPSG:32747",
        "transform": rasterio.transform.from_bounds(0, 0, 400, 400, 40, 40),
    }

    with rasterio.open(dem_path, "w", **profile) as dst:
        dst.write(dem, 1)

    with rasterio.open(depth_path, "w", **profile) as dst:
        dst.write(raw_depth, 1)

    refine_flood_hazard_raster(
        depth_tif=str(depth_path),
        dep_path=dem_path,
        hmin=0.05,
        island_mmu_px=10,
        hole_mmu_px=25,
        bridge_radius=1,
        smooth_sigma=0.5,
        rivers_gpkg=None,
    )

    with rasterio.open(depth_path) as dst:
        refined = dst.read(1)

    # 1. Shallow submerged void (DEM < Zs) is bridged with physical minimum depth >= hmin
    hole_depths = refined[18:21, 18:21]
    assert np.all(np.isfinite(hole_depths)), "Shallow submerged void (DEM < Zs) was not bridged!"
    assert np.all(hole_depths >= 0.05), "Bridged void depth below hmin!"

    # 2. Small elevated dry mound (DEM > Zs) MUST remain dry (never drown dry high ground!)
    mound_depths = refined[28:31, 28:31]
    assert np.all(np.isnan(mound_depths)), "Elevated dry mound (DEM > Zs) was erroneously drowned!"

    # 3. Large dry island MUST remain completely dry (NaN)
    island_depths = refined[4:12, 4:12]
    assert np.all(np.isnan(island_depths)), "Large dry island was erroneously infilled!"


def test_resolution_independent_hectare_mmu_on_20m_grid(tmp_path):
    """Verify hole_mmu_ha=1.0 automatically converts to 25 pixels on a 20m grid (not 100 px = 4 ha!)."""
    shape = (30, 30)
    dem = np.full(shape, 5.0, dtype=np.float32)
    raw_depth = np.full(shape, 1.5, dtype=np.float32)
    # Enclosed 4x4 submerged void (16 px * 400 m2 = 0.64 ha <= 1.0 ha -> filled)
    dem[10:14, 10:14] = 6.48
    raw_depth[10:14, 10:14] = 0.0

    dem_path = tmp_path / "dem_20m.tif"
    depth_path = tmp_path / "depth_20m.tif"
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": np.nan,
        "width": 30,
        "height": 30,
        "count": 1,
        "crs": "EPSG:32747",
        "transform": rasterio.transform.from_bounds(0, 0, 600, 600, 30, 30),  # 20m x 20m pixels
    }
    with rasterio.open(dem_path, "w", **profile) as dst:
        dst.write(dem, 1)
    with rasterio.open(depth_path, "w", **profile) as dst:
        dst.write(raw_depth, 1)

    refine_flood_hazard_raster(
        depth_tif=str(depth_path),
        dep_path=dem_path,
        hmin=0.05,
        hole_mmu_ha=1.0,
        island_mmu_ha=0.5,
        bridge_radius=0,
        smooth_sigma=0.0,
        rivers_gpkg=None,
    )

    with rasterio.open(depth_path) as dst:
        tags = dst.tags()
        assert tags.get("hole_mmu_px") == "25", f"Expected 25 px for 1.0 ha @ 20m, got {tags.get('hole_mmu_px')}"
        assert tags.get("island_mmu_px") == "12", f"Expected 12 px for 0.5 ha @ 20m, got {tags.get('island_mmu_px')}"
        assert "(1.00 ha" in tags.get("mmu_standard", "")


def test_30x30m_minimum_hole_and_scattered_pixel_floor(tmp_path):
    """
    Verify the 30m x 30m (0.09 ha = 9 px @ 10m) post-hydrostatic cleanup floor:
    1. Sub-DEM pinhole (2x2 = 4 px < 9 px) IS filled even if DEM spikes slightly.
    2. Scattered wet speck (2x2 = 4 px < 9 px) IS pruned to dry (NaN).
    3. Real elevated dry feature (3x3 = 9 px >= 30m x 30m) REMAINS STRICTLY DRY.
    """
    shape = (40, 40)
    dem = np.full(shape, 5.0, dtype=np.float32)
    raw_depth = np.zeros(shape, dtype=np.float32)

    # Flooded left half (cols 0..24) with Zs = 6.5m
    raw_depth[:, :25] = 1.5

    # 1. Tiny 2x2 sub-DEM pinhole (4 px < 9 px) inside flooded zone with elevated spike DEM = 7.0m
    dem[10:12, 10:12] = 7.0
    raw_depth[10:12, 10:12] = 0.0

    # 2. Real 3x3 elevated dry mound (9 px == 30m x 30m) inside flooded zone with DEM = 8.0m
    dem[22:25, 10:13] = 8.0
    raw_depth[22:25, 10:13] = 0.0

    # 3. Tiny 2x2 scattered wet speck (4 px < 9 px) isolated in dry right half
    raw_depth[15:17, 32:34] = 0.8

    dem_path = tmp_path / "dem_30m_floor.tif"
    depth_path = tmp_path / "depth_30m_floor.tif"
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": np.nan,
        "width": 40,
        "height": 40,
        "count": 1,
        "crs": "EPSG:32747",
        "transform": rasterio.transform.from_bounds(0, 0, 400, 400, 40, 40),
    }
    with rasterio.open(dem_path, "w", **profile) as dst:
        dst.write(dem, 1)
    with rasterio.open(depth_path, "w", **profile) as dst:
        dst.write(raw_depth, 1)

    refine_flood_hazard_raster(
        depth_tif=str(depth_path),
        dep_path=dem_path,
        hmin=0.05,
        island_mmu_ha=0.09,
        min_hole_ha=0.09,
        hole_mmu_ha=1.0,
        bridge_radius=0,
        smooth_sigma=0.0,
        rivers_gpkg=None,
    )

    with rasterio.open(depth_path) as dst:
        out = dst.read(1)

    assert np.all(np.isfinite(out[10:12, 10:12])), "Sub-30x30m pinhole (4 px) should be filled!"
    assert np.all(np.isnan(out[22:25, 10:13])), "30x30m elevated dry mound (9 px) must remain strictly dry!"
    assert np.all(np.isnan(out[15:17, 32:34])), "Sub-30x30m scattered wet speck (4 px) must be pruned!"


