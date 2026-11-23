"""
test_qa_checks.py
=================
Unit tests verifying fixed QA gates in scripts/qa_checks.py:
1. check_peak_timing computes depth h = zs - zb (never treats high-elevation dry cells as wet).
2. volume_balance computes non-zero end-of-run storage from zs - zb when 'h' is absent.
3. run_all_qa propagates peak_timing_qa failure and unmasked boundary warning into all_passed.
"""

import numpy as np
import pandas as pd
import xarray as xr
from scripts.qa_checks import check_boundaries, check_peak_timing, volume_balance, run_all_qa


def _write_synthetic_sfincs_model(model_dir, late_peak=False, include_inactive=True):
    model_dir.mkdir(parents=True, exist_ok=True)
    ny, nx, nt = 10, 10, 20

    # 1. sfincs.inp
    (model_dir / "sfincs.inp").write_text(
        "mmax = 10\nnmax = 10\ndx = 40\ndy = 40\n", encoding="utf-8"
    )

    # 2. sfincs.msk (include inactive=0, active=1, outflow=3)
    msk = np.ones((ny, nx), dtype=np.int8)
    if include_inactive:
        msk[0, :] = 0
        msk[-1, :] = 0
    msk[5, -1] = 3
    msk.tofile(model_dir / "sfincs.msk")

    # 3. sfincs_subgrid.nc with spatially varying Manning roughness
    rgh = np.linspace(0.03, 0.12, ny * nx, dtype=np.float32).reshape((ny, nx))
    xr.Dataset({"uv_navg": (("n", "m"), rgh)}).to_netcdf(model_dir / "sfincs_subgrid.nc")

    # 4. sfincs_map.nc using zs and zb (NO 'h' variable — matches real SFINCS v2.4 output!)
    # High-elevation mountain terrain (500m) so naive zs > 0.05 would falsely flag dry cells!
    zb = np.full((ny, nx), 500.0, dtype=np.float32)
    h_series = np.zeros((nt, ny, nx), dtype=np.float32)
    # Wet valley pixels in rows 4..6, peaking early (t=5) or late (t=19)
    t_peak = 19 if late_peak else 5
    for t in range(nt):
        h_val = max(0.0, 1.5 - 0.1 * abs(t - t_peak))
        h_series[t, 4:7, 2:8] = h_val
    # Keep a non-zero tail at t=-1 so volume_balance finds real storage
    h_series[-1, 4:7, 2:8] = 0.5
    zs = zb[None, :, :] + h_series

    times = pd.date_range("2024-01-01", periods=nt, freq="1h")
    xr.Dataset(
        {
            "zb": (("n", "m"), zb),
            "zs": (("time", "n", "m"), zs),
            "msk": (("n", "m"), msk),
        },
        coords={"time": times},
    ).to_netcdf(model_dir / "sfincs_map.nc")

    # 5. precip_2d.nc (40 mm/hr for first 5 hours -> ~180-200 mm total > residual valley storage)
    p = np.zeros((nt, ny, nx), dtype=np.float32)
    p[:5, :, :] = 40.0
    xr.Dataset(
        {"precip_2d": (("time", "y", "x"), p)},
        coords={"time": times},
    ).to_netcdf(model_dir / "precip_2d.nc")


def test_qa_peak_timing_and_volume_balance_pass(tmp_path):
    mdir = tmp_path / "DAS_TEST_pass"
    _write_synthetic_sfincs_model(mdir, late_peak=False, include_inactive=True)

    b_res = check_boundaries(mdir)
    assert b_res["passed"] is True
    assert b_res["inactive_cells_msk0"] == 20
    assert b_res["outflow_cells_msk3"] == 1

    pt_res = check_peak_timing(mdir, threshold_pct=1.0)
    assert pt_res["passed"] is True
    # Only the 3x6=18 wet valley cells should be counted (NOT all 100 highland cells at zb=500m!)
    assert pt_res["total_wet_cells"] == 18
    assert pt_res["late_peaking_cells"] == 0

    vb_res = volume_balance(mdir)
    assert vb_res["final_storage_volume_m3"] > 0.0
    assert vb_res["estimated_rain_volume_m3"] > 0.0
    assert 0.0 < vb_res["storage_fraction_of_rain"] < 1.0

    rep = run_all_qa(mdir)
    assert rep["all_passed"] is True


def test_qa_propagates_late_peak_failure_to_all_passed(tmp_path):
    mdir = tmp_path / "DAS_TEST_late"
    _write_synthetic_sfincs_model(mdir, late_peak=True, include_inactive=True)

    rep = run_all_qa(mdir)
    assert rep["peak_timing_qa"]["passed"] is False
    assert rep["all_passed"] is False


def test_qa_flags_unmasked_rectangular_grid(tmp_path):
    mdir = tmp_path / "DAS_TEST_unmasked"
    _write_synthetic_sfincs_model(mdir, late_peak=False, include_inactive=False)

    b_res = check_boundaries(mdir)
    assert b_res["inactive_cells_msk0"] == 0
    assert b_res["domain_masked"] is False
    assert b_res["passed"] is False
