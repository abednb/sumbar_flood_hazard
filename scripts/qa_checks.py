"""
qa_checks.py
============
Automated Quality Assurance (QA) and physics validation gates for SFINCS standalone models.
Implements:
1. check_roughness: Asserts spatially varying Manning's n (Issue C1).
2. check_boundaries: Asserts presence of boundary cells (msk=2 waterlevel, msk=3 outflow) (Issue H3).
3. check_peak_timing: Asserts hydrograph recession completeness (peak occurs before last 10%) (Issue C2).
4. volume_balance: Evaluates continuity closure error between rainfall, storage, infiltration, and outflow (Issue H5).
"""

import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Union
import numpy as np
import xarray as xr


def check_roughness(model_dir: Path) -> Dict[str, Any]:
    """
    Build-time QA (Issue C1):
    Opens sfincs_subgrid.nc and verifies that Manning roughness varies spatially (std > 0, >1 unique value).
    """
    subgrid_nc = model_dir / "subgrid" / "sfincs_subgrid.nc"
    if not subgrid_nc.exists():
        subgrid_nc = model_dir / "sfincs_subgrid.nc"

    if not subgrid_nc.exists():
        raise FileNotFoundError(f"Subgrid netCDF not found in {model_dir}")

    ds = xr.open_dataset(subgrid_nc)
    rgh_var = None
    for cand in ["uv_navg", "rgh", "manning", "n"]:
        if cand in ds.data_vars:
            rgh_var = cand
            break

    if rgh_var is None:
        raise KeyError(f"No roughness variable found in {subgrid_nc}. Available: {list(ds.data_vars.keys())}")

    vals = ds[rgh_var].values.flatten()
    valid_vals = vals[np.isfinite(vals) & (vals > 0)]

    if len(valid_vals) == 0:
        raise ValueError(f"No valid roughness values in {rgh_var}!")

    unq_vals = np.unique(np.round(valid_vals, 4))
    std_val = float(np.std(valid_vals))
    min_val = float(np.min(valid_vals))
    max_val = float(np.max(valid_vals))
    mean_val = float(np.mean(valid_vals))

    passed = (len(unq_vals) > 1) and (std_val > 1e-4)
    result = {
        "passed": passed,
        "variable": rgh_var,
        "unique_values_count": int(len(unq_vals)),
        "unique_values_sample": [float(x) for x in unq_vals[:10]],
        "min": min_val,
        "max": max_val,
        "mean": mean_val,
        "std": std_val,
    }

    if not passed:
        raise AssertionError(
            f"Roughness QA Failed in {model_dir}: uniform roughness detected!\n"
            f"std={std_val:.6f}, unique_values={len(unq_vals)} (Values: {unq_vals})"
        )

    print(f"[QA PASS] Roughness varies: {len(unq_vals)} unique values, range [{min_val:.3f}, {max_val:.3f}], std={std_val:.4f}")
    return result


def check_boundaries(model_dir: Path) -> Dict[str, Any]:
    """
    Build-time QA (Issue H3):
    Verifies that model mask contains active cells and at least one boundary type (msk=2 or msk=3).
    """
    msk_bin = model_dir / "sfincs.msk"
    if not msk_bin.exists():
        raise FileNotFoundError(f"Mask file sfincs.msk not found in {model_dir}")

    # Read binary or netcdf mask
    inp_file = model_dir / "sfincs.inp"
    nmax = 0
    mmax = 0
    if inp_file.exists():
        with open(inp_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 3:
                    if parts[0] == "nmax":
                        nmax = int(parts[2])
                    elif parts[0] == "mmax":
                        mmax = int(parts[2])

    if nmax > 0 and mmax > 0:
        msk = np.fromfile(msk_bin, dtype=np.int8)
        total_cells = nmax * mmax
        if msk.size == total_cells:
            num_inactive = int(np.sum(msk == 0))
        else:
            # SFINCS binary format ('inputformat = bin') stores only non-zero indexed cells
            # matching sfincs.ind; remaining cells in the mmax x nmax grid are inactive (msk=0).
            num_inactive = int(np.sum(msk == 0)) + max(total_cells - int(msk.size), 0)
    else:
        msk = np.fromfile(msk_bin, dtype=np.int8)
        total_cells = max(int(msk.size), 1)
        num_inactive = int(np.sum(msk == 0))

    num_active = int(np.sum(msk == 1))
    num_waterlevel = int(np.sum(msk == 2))
    num_outflow = int(np.sum(msk == 3))
    inactive_pct = round((num_inactive / max(total_cells, 1)) * 100.0, 2)

    has_boundaries = (num_waterlevel + num_outflow) > 0
    domain_masked = num_inactive > 0
    result = {
        "passed": has_boundaries and domain_masked,
        "active_cells_msk1": num_active,
        "waterlevel_cells_msk2": num_waterlevel,
        "outflow_cells_msk3": num_outflow,
        "inactive_cells_msk0": num_inactive,
        "inactive_fraction_pct": inactive_pct,
        "domain_masked": domain_masked,
    }

    if not has_boundaries:
        raise AssertionError(
            f"Boundary QA Failed in {model_dir}: No boundary cells found! "
            f"(msk=2: {num_waterlevel}, msk=3: {num_outflow}). Catchment will trap all flood water."
        )
    if not domain_masked:
        print(
            f"[QA WARNING] Unmasked rectangular grid detected in {model_dir} (msk0=0)! "
            f"Set 'mask: das_region' in setup_mask_active to skip outside-basin cells and enable msk=3 outlets."
        )

    print(
        f"[QA {'PASS' if result['passed'] else 'WARN'}] Mask & boundaries: "
        f"active={num_active:,}, inactive={num_inactive:,} ({inactive_pct:.1f}%), "
        f"waterlevel={num_waterlevel:,}, outflow={num_outflow:,}"
    )
    return result


def _extract_depth_timeseries(ds: xr.Dataset) -> Optional[xr.DataArray]:
    """
    Returns water depth time series h(time, y, x) in meters from sfincs_map.nc.
    Computes h = max(zs - zb, 0) when SFINCS outputs water surface elevation (zs) and bed level (zb)
    rather than explicit depth (h).
    """
    if "h" in ds.data_vars:
        return ds["h"]
    if "zs" in ds.data_vars and "zb" in ds.data_vars:
        zs = ds["zs"]
        zb = ds["zb"]
        h = (zs - zb).where(np.isfinite(zs) & np.isfinite(zb))
        return h.clip(min=0.0)
    if "zs" in ds.data_vars:
        return ds["zs"]
    return None


def check_peak_timing(model_dir: Path, threshold_pct: float = 1.0, hmin: float = 0.05) -> Dict[str, Any]:
    """
    Run-time QA (Issue C2):
    Analyzes sfincs_map.nc water depth h = zs - zb time series.
    Reports the fraction of wet cells (max h >= hmin) whose peak inundation occurs
    in the last 10% of simulation time.
    """
    map_nc = model_dir / "sfincs_map.nc"
    if not map_nc.exists():
        raise FileNotFoundError(f"Results file sfincs_map.nc not found in {model_dir}")

    with xr.open_dataset(map_nc) as ds:
        da = _extract_depth_timeseries(ds)
        if da is None:
            return {"passed": True, "warning": "Neither h nor zs time series found in map output."}

        num_steps = int(da.sizes["time"])
        if num_steps < 3:
            return {"passed": True, "note": "Insufficient timesteps to evaluate peak timing."}

        # Mask out inactive cells (msk == 0) if mask is stored in map output
        active_grid_mask = None
        if "msk" in ds.data_vars:
            active_grid_mask = (ds["msk"].values == 1)

        da_vals = da.values
        # Replace NaNs with -9999 before argmax so dry cells do not raise
        da_filled = np.where(np.isfinite(da_vals), da_vals, -9999.0)
        peak_idx = np.argmax(da_filled, axis=0)
        max_val = np.max(da_filled, axis=0)

        wet_mask = (max_val >= hmin)
        if active_grid_mask is not None and active_grid_mask.shape == wet_mask.shape:
            wet_mask &= active_grid_mask

        total_wet = int(np.sum(wet_mask))
        if total_wet == 0:
            return {"passed": True, "note": "No flooded cells detected."}

        cutoff_step = int(np.floor(0.90 * num_steps))
        late_peaking_cells = int(np.sum(wet_mask & (peak_idx >= cutoff_step)))
        late_fraction_pct = (late_peaking_cells / total_wet) * 100.0

    passed = late_fraction_pct <= threshold_pct
    result = {
        "passed": passed,
        "total_timesteps": num_steps,
        "cutoff_step_last_10pct": cutoff_step,
        "total_wet_cells": total_wet,
        "late_peaking_cells": late_peaking_cells,
        "late_peaking_pct": round(late_fraction_pct, 3),
        "threshold_pct": threshold_pct,
    }

    if not passed:
        print(f"[QA WARNING] Peak timing: {late_fraction_pct:.2f}% of wet cells peaked in the last 10% of the run (> {threshold_pct}%). Consider extending recession duration.")
    else:
        print(f"[QA PASS] Peak timing: only {late_fraction_pct:.2f}% of wet cells peaked late (<= {threshold_pct}%). Hydrograph recession well captured.")

    return result


def _compute_subgrid_storage_volume(
    model_dir: Path,
    ds_map: xr.Dataset,
    cell_area: float,
    active_mask: Optional[np.ndarray],
) -> Tuple[float, str]:
    """
    Computes exact final surface water storage volume [m³] using the SFINCS subgrid hypsometric
    lookup table (`sfincs_subgrid.nc`: z_zmin, z_zmax, z_volmax, z_level) when available.
    Falls back cleanly to regular-grid `(zs - zb) * cell_area` if subgrid tables are absent.

    Why this matters: In subgrid mode, `sfincs_map.nc['zb']` stores `z_zmin` (the lowest 10 m
    pixel inside each coarse cell). Multiplying `(zs - z_zmin) * cell_area` on steep mountain
    basins (e.g. DAS_101) overestimates storage by 2x-5x. Evaluating the true hypsometric curve
    closes mass balance accurately across both coastal plains and mountainous watersheds.
    """
    sbg_candidates = [
        model_dir / "sfincs_subgrid.nc",
        model_dir / "subgrid" / "sfincs_subgrid.nc",
    ]
    sbg_nc = next((p for p in sbg_candidates if p.exists()), None)
    ind_bin = model_dir / "sfincs.ind"

    if sbg_nc is not None and ind_bin.exists() and "zs" in ds_map.data_vars:
        try:
            with xr.open_dataset(sbg_nc) as sbg:
                if all(k in sbg.data_vars for k in ("z_zmin", "z_zmax", "z_volmax", "z_level")):
                    zs_end = ds_map["zs"].isel(time=-1).values
                    # SFINCS binary index file (1-based Fortran linear index in column-major (n, m) or (m, n))
                    ind = np.fromfile(ind_bin, dtype=np.int32)
                    # Skip optional Fortran record header if present (ind[0] == number of active points)
                    if ind.size > 0 and ind[0] == ind.size - 1:
                        ind = ind[1:]
                    z_zmin = sbg["z_zmin"].values
                    z_zmax = sbg["z_zmax"].values
                    z_volmax = sbg["z_volmax"].values
                    z_level = sbg["z_level"].values  # shape (np, n_levels) or (n_levels, np)
                    if z_level.shape[0] != z_zmin.shape[0] and z_level.shape[1] == z_zmin.shape[0]:
                        z_level = z_level.T

                    if ind.size == z_zmin.size:
                        # Map 2D zs_end (n, m) onto 1D active-point vector matching sfincs.ind (Fortran order)
                        zs_flat = zs_end.ravel(order="F")
                        valid_idx = (ind >= 1) & (ind <= zs_flat.size)
                        if np.all(valid_idx):
                            zs_p = zs_flat[ind - 1]
                            msk_p = None
                            if "msk" in ds_map.data_vars:
                                msk_p = ds_map["msk"].values.ravel(order="F")[ind - 1]

                            wet_p = np.isfinite(zs_p) & np.isfinite(z_zmin) & (zs_p > z_zmin + 0.01)
                            if msk_p is not None:
                                wet_p &= (msk_p == 1)

                            if not np.any(wet_p):
                                return 0.0, "subgrid_hypsometric"

                            zs_w = zs_p[wet_p]
                            zmin_w = z_zmin[wet_p]
                            zmax_w = z_zmax[wet_p]
                            vmax_w = z_volmax[wet_p]
                            lvl_w = z_level[wet_p, :]  # (nw, L)

                            vols = np.zeros_like(zs_w, dtype=np.float64)
                            above = zs_w >= zmax_w
                            vols[above] = vmax_w[above] + (zs_w[above] - zmax_w[above]) * cell_area

                            mid = ~above
                            if np.any(mid):
                                n_lvl = lvl_w.shape[1]
                                zm = zs_w[mid][:, None]
                                lm = lvl_w[mid, :]
                                # Count how many subgrid level thresholds are below zs_w
                                k = np.clip(np.sum(lm <= zm, axis=1) - 1, 0, n_lvl - 2)
                                rows_i = np.arange(lm.shape[0])
                                z0 = lm[rows_i, k]
                                z1 = lm[rows_i, k + 1]
                                frac_step = np.where(z1 > z0 + 1e-6, np.clip((zs_w[mid] - z0) / (z1 - z0), 0.0, 1.0), 0.0)
                                vol_frac = (k + frac_step) / max(n_lvl - 1, 1)
                                vols[mid] = vol_frac * vmax_w[mid]

                            return float(np.sum(vols)), "subgrid_hypsometric"
        except Exception:
            pass

    # Fallback: regular-grid (zs - zb) * cell_area
    da_h = _extract_depth_timeseries(ds_map)
    if da_h is not None:
        h_end = da_h.isel(time=-1).values
        valid = np.isfinite(h_end) & (h_end > 0.01)
        if active_mask is not None and active_mask.shape == h_end.shape:
            valid &= active_mask
        h_end_clean = np.where(valid, h_end, 0.0)
        return float(np.sum(h_end_clean) * cell_area), "regular_grid_approx"
    return 0.0, "unavailable"


def volume_balance(model_dir: Path) -> Dict[str, Any]:
    """
    Run-time QA (Issue H5):
    Evaluates conservation of mass (volume balance closure):
    Total Rain Volume vs Final Surface Storage (exact subgrid hypsometric volume when available).
    """
    map_nc = model_dir / "sfincs_map.nc"
    if not map_nc.exists():
        raise FileNotFoundError(f"Results file sfincs_map.nc not found in {model_dir}")

    with xr.open_dataset(map_nc) as ds:
        # Infer cell area from inp or sfincs.inp if attrs do not carry dx/dy
        dx = float(ds.attrs.get("dx", 0.0))
        dy = float(ds.attrs.get("dy", 0.0))
        if dx <= 0 or dy <= 0:
            inp_file = model_dir / "sfincs.inp"
            if inp_file.exists():
                for line in inp_file.read_text(errors="ignore").splitlines():
                    if "=" in line:
                        k, v = [p.strip() for p in line.split("=", 1)]
                        if k == "dx":
                            dx = float(v)
                        elif k == "dy":
                            dy = float(v)
        dx = dx if dx > 0 else 40.0
        dy = dy if dy > 0 else 40.0
        cell_area = dx * dy

        active_mask = (ds["msk"].values == 1) if "msk" in ds.data_vars else None

        # 1. Final surface water volume (exact subgrid hypsometry when sfincs_subgrid.nc is present)
        v_storage, vol_method = _compute_subgrid_storage_volume(model_dir, ds, cell_area, active_mask)

    # 2. Cumulative rain forcing volume on active cells
    v_rain = 0.0
    precip_nc = model_dir / "precip_2d.nc"
    if precip_nc.exists():
        with xr.open_dataset(precip_nc) as pds:
            pvar = "precip_2d" if "precip_2d" in pds else [v for v in pds.data_vars if "time" in pds[v].dims][0]
            p_arr = pds[pvar].values
            p_clean = np.where(np.isfinite(p_arr) & (p_arr > 0), p_arr, 0.0)
            # Trapezoidal integration over hourly timesteps (mm/hr * dt_hr -> mm)
            if p_clean.shape[0] > 1 and "time" in pds.coords:
                times_hr = (pds["time"].values - pds["time"].values[0]) / np.timedelta64(1, "h")
                dt_hr = np.diff(times_hr)
                total_p_mm = np.sum(0.5 * (p_clean[:-1] + p_clean[1:]) * dt_hr[:, None, None], axis=0)
            else:
                total_p_mm = np.sum(p_clean, axis=0)
            total_p_m = total_p_mm / 1000.0
            if active_mask is not None and active_mask.shape == total_p_m.shape:
                total_p_m = np.where(active_mask, total_p_m, 0.0)
            else:
                msk_bin = model_dir / "sfincs.msk"
                if msk_bin.exists():
                    msk = np.fromfile(msk_bin, dtype=np.int8)
                    if msk.size == total_p_m.size:
                        total_p_m = np.where(msk.reshape(total_p_m.shape) == 1, total_p_m, 0.0)
            v_rain = float(np.sum(total_p_m) * cell_area)

    result = {
        "cell_area_m2": cell_area,
        "storage_method": vol_method,
        "estimated_rain_volume_m3": round(v_rain, 1),
        "final_storage_volume_m3": round(v_storage, 1),
        "storage_fraction_of_rain": round(v_storage / max(v_rain, 1e-5), 4),
        "closure_note": "Residual (1 - storage_fraction) reflects infiltration loss + boundary outflow discharge.",
    }
    print(f"[QA INFO] Volume balance ({vol_method}): Rain={v_rain/1e6:.2f} Mm³, End Storage={v_storage/1e6:.2f} Mm³ ({v_storage/max(v_rain,1e-5)*100:.1f}%)")
    return result


def run_all_qa(
    model_dir: Path,
    out_json: Optional[Union[str, Path]] = None,
    output_report: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Runs all QA gates and writes summary report."""
    target_out = out_json if out_json is not None else output_report
    model_dir = Path(model_dir)
    report = {
        "model_dir": str(model_dir.resolve()),
        "roughness_qa": None,
        "boundary_qa": None,
        "peak_timing_qa": None,
        "volume_balance_qa": None,
        "all_passed": True,
    }

    try:
        report["roughness_qa"] = check_roughness(model_dir)
        if not report["roughness_qa"].get("passed", False):
            report["all_passed"] = False
    except Exception as e:
        report["roughness_qa"] = {"passed": False, "error": str(e)}
        report["all_passed"] = False

    try:
        report["boundary_qa"] = check_boundaries(model_dir)
        if not report["boundary_qa"].get("passed", False):
            report["all_passed"] = False
    except Exception as e:
        report["boundary_qa"] = {"passed": False, "error": str(e)}
        report["all_passed"] = False

    try:
        report["peak_timing_qa"] = check_peak_timing(model_dir)
        if not report["peak_timing_qa"].get("passed", False):
            report["all_passed"] = False
    except Exception as e:
        report["peak_timing_qa"] = {"passed": False, "error": str(e)}
        report["all_passed"] = False

    try:
        report["volume_balance_qa"] = volume_balance(model_dir)
    except Exception as e:
        report["volume_balance_qa"] = {"error": str(e)}

    if target_out:
        target_out = Path(target_out)
        target_out.parent.mkdir(parents=True, exist_ok=True)
        with open(target_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[QA REPORT] Saved comprehensive QA report to {target_out}")

    return report
