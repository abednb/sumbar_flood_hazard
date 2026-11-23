"""
test_national_v2.py
===================
Unit tests for Phase 3 National Indonesian Kabupaten v2.0 Standardization:
1. Auto-UTM EPSG detection across the entire Indonesian archipelago (46N-54N / 46S-54S)
2. Dynamic hydrograph recession scaling & WMO/USWB Areal Reduction Factor (ARF)
3. Canonical 15-class Indonesian BIG RBI land-cover mapping & USDA-NRCS CN conversions
4. Option B Hydrostatically Connected Natural Floodplain Margin (+0.25m FABDEM uncertainty)
5. Subgrid hypsometric storage volume QA (sfincs_subgrid.nc z_level/z_volmax)
"""

import numpy as np
import pandas as pd
import pytest
import rasterio
import xarray as xr

from scripts.geo_utils import (
    classify_rbi_canonical,
    cn2_to_cn1,
    cn2_to_cn3,
    compute_wmo_arf,
    get_dynamic_recession_hours,
    infer_utm_epsg_from_lonlat,
)
from scripts.qa_checks import volume_balance
from scripts.sfincs_standalone_pipeline import refine_flood_hazard_raster


@pytest.mark.parametrize(
    "city,lon,lat,expected_epsg",
    [
        ("Banda Aceh", 95.32, 5.55, 32646),
        ("Medan", 98.67, 3.59, 32647),
        ("Padang (Sumbar)", 100.35, -0.95, 32747),
        ("Jakarta", 106.85, -6.21, 32748),
        ("Surabaya", 112.75, -7.25, 32749),
        ("Makassar", 119.43, -5.14, 32750),
        ("Manado", 124.84, 1.48, 32651),
        ("Jayapura", 140.72, -2.54, 32754),
    ],
)
def test_indonesia_auto_utm_epsg(city, lon, lat, expected_epsg):
    assert infer_utm_epsg_from_lonlat(lon, lat) == expected_epsg, f"Wrong UTM EPSG for {city}"


def test_dynamic_recession_and_wmo_arf():
    assert get_dynamic_recession_hours(350.0) == 24
    assert get_dynamic_recession_hours(968.0) == 36
    assert get_dynamic_recession_hours(2200.0) == 48

    assert compute_wmo_arf(15.0) == 1.0
    arf_1000 = compute_wmo_arf(1000.0, duration_hr=24.0)
    assert 0.75 <= arf_1000 < 0.98


def test_canonical_rbi_and_cn_conversions():
    assert classify_rbi_canonical("Permukiman dan Tempat Kegiatan") == "built_up_urban"
    assert classify_rbi_canonical("Sawah Irigasi") == "paddy_sawah"
    assert classify_rbi_canonical("Hutan Bakau/Mangrove") == "mangrove"
    assert classify_rbi_canonical("Hutan Rimba") == "dense_forest"
    assert classify_rbi_canonical("Danau/Situ") == "inland_water"

    cn2 = np.array([50.0, 75.0, 90.0, 100.0], dtype=np.float32)
    cn3 = cn2_to_cn3(cn2)
    cn1 = cn2_to_cn1(cn2)
    assert np.all(cn3 >= cn2) and np.all(cn3 <= 100.0)
    assert np.all(cn1 <= cn2) and np.all(cn1 >= 1.0)
    assert cn3[-1] == pytest.approx(100.0)


def test_option_b_natural_floodplain_margin(tmp_path):
    """
    Verify Option B (+0.25m FABDEM margin, <= 80m, flat < 5 deg, hydrologically connected):
      1. Connected flat margin pixels (DEM = Zs + 0.10m, 20m outside wet edge) ARE recovered.
      2. Elevated dry hill (DEM = Zs + 2.0m) REMAINS strictly dry.
      3. Steep hillside (slope > 8 deg) REMAINS strictly dry.
      4. Disconnected depression beyond 80m REMAINS strictly dry.
    """
    shape = (60, 60)  # 600m x 600m at 10m resolution
    dem = np.full(shape, 5.0, dtype=np.float32)
    raw_depth = np.zeros(shape, dtype=np.float32)

    # Flooded core: cols 5..20, rows 5..55 at Zs = 6.0m (depth = 1.0m on DEM = 5.0m)
    raw_depth[5:55, 5:20] = 1.0

    # 1. Flat floodplain terrace just outside wet edge (cols 20..24, 0..40m away) at DEM = 6.10m (Zs + 0.10m)
    dem[10:25, 20:24] = 6.10

    # 2. Elevated dry hill right outside wet edge (cols 20..25, rows 30..36) at DEM = 8.0m (Zs + 2.0m -> MUST STAY DRY!)
    dem[30:36, 20:26] = 8.0

    # 3. Steep cliff right outside wet edge (cols 20..26, rows 42..50): climbs 2.5m per 10m pixel (~14 deg -> MUST STAY DRY!)
    for k in range(6):
        dem[42:50, 20 + k] = 6.05 + 2.5 * k

    # 4. Disconnected low basin far away (cols 45..55, 250m > 80m away, DEM = 4.0m -> MUST STAY DRY!)
    dem[10:25, 45:55] = 4.0

    dem_path = tmp_path / "dem_optb.tif"
    depth_path = tmp_path / "depth_optb.tif"
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": np.nan,
        "width": 60,
        "height": 60,
        "count": 1,
        "crs": "EPSG:32747",
        "transform": rasterio.transform.from_bounds(0, 0, 600, 600, 60, 60),
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
        hole_mmu_ha=2.0,
        bridge_radius=0,
        smooth_sigma=0.0,
        freeboard_m=0.25,
        max_ext_dist_m=80.0,
        max_ext_slope_deg=5.0,
        rivers_gpkg=None,
    )

    with rasterio.open(depth_path) as dst:
        out = dst.read(1)
        tags = dst.tags()
        assert tags.get("freeboard_m") == "0.25"
        assert tags.get("max_ext_dist_m") == "80.0"

    # 1. Flat terrace (+0.10m above Zs, within +0.25m * decay) recovered smoothly
    assert np.all(np.isfinite(out[12:23, 20:23])), "Connected flat floodplain terrace within +0.25m freeboard was not recovered!"
    # 2. Elevated dry hill (DEM = 8.0m) strictly dry
    assert np.all(np.isnan(out[31:35, 21:25])), "Elevated dry hill was erroneously flooded!"
    # 3. Steep cliff strictly dry
    assert np.all(np.isnan(out[43:49, 22:26])), "Steep hillside (>5 deg) was erroneously flooded!"
    # 4. Disconnected far basin (>80m away) strictly dry
    assert np.all(np.isnan(out[12:23, 46:54])), "Disconnected basin >80m away was erroneously flooded!"


def test_subgrid_hypsometric_volume_balance(tmp_path):
    """
    Verify qa_checks.volume_balance uses exact subgrid hypsometric volume from sfincs_subgrid.nc
    instead of naive (zs - z_zmin) * cell_area on steep cells.
    """
    # 2x2 grid (dx=dy=100m -> cell_area=10,000 m2), 4 active cells
    # Steep cell has z_zmin=0m, z_zmax=10m, z_volmax=50,000 m3 (triangular wedge, half of 10m*10000m2)
    # With zs=5m (halfway up z_level linear ramp), exact subgrid volume = 25,000 m3 per cell (100,000 m3 total),
    # whereas naive (5m - 0m) * 10,000 = 50,000 m3 per cell (200,000 m3 total — 2x overestimation!).
    model_dir = tmp_path / "subgrid_vol_test"
    model_dir.mkdir()
    (model_dir / "sfincs.inp").write_text("mmax = 2\nnmax = 2\ndx = 100\ndy = 100\n")

    # 1-based Fortran linear indices for 2x2 grid
    np.array([1, 2, 3, 4], dtype=np.int32).tofile(model_dir / "sfincs.ind")

    levels = np.linspace(0.0, 10.0, 10, dtype=np.float32)
    sbg = xr.Dataset(
        {
            "z_zmin": (("np",), np.zeros(4, dtype=np.float32)),
            "z_zmax": (("np",), np.full(4, 10.0, dtype=np.float32)),
            "z_volmax": (("np",), np.full(4, 50000.0, dtype=np.float32)),
            "z_level": (("np", "levels"), np.tile(levels, (4, 1))),
        }
    )
    sbg.to_netcdf(model_dir / "sfincs_subgrid.nc")

    times = pd.date_range("2024-01-01", periods=3, freq="1h")
    zs = np.full((3, 2, 2), 5.0, dtype=np.float32)
    zb = np.zeros((2, 2), dtype=np.float32)
    msk = np.ones((2, 2), dtype=np.int8)
    ds_map = xr.Dataset(
        {"zs": (("time", "y", "x"), zs), "zb": (("y", "x"), zb), "msk": (("y", "x"), msk)},
        coords={"time": times},
        attrs={"dx": 100.0, "dy": 100.0},
    )
    ds_map.to_netcdf(model_dir / "sfincs_map.nc")

    # Rain: 100 mm/hr for 1 hr -> 0.1m * 40,000 m2 = 4,000 m3 (synthetic)
    p = np.full((3, 2, 2), 100.0, dtype=np.float32)
    xr.Dataset({"precip_2d": (("time", "y", "x"), p)}, coords={"time": times}).to_netcdf(model_dir / "precip_2d.nc")

    res = volume_balance(model_dir)
    assert res["storage_method"] == "subgrid_hypsometric"
    assert res["final_storage_volume_m3"] == pytest.approx(100000.0, rel=1e-3)
