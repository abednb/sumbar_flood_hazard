"""
validate_against_survey.py
==========================
Validates modeled 2D flood hazard extents and depths against ground-truth field survey
data collected via QField (data/qfield_result/*.gpkg).

Computes standard hydrodynamic flood model performance metrics:
- Contingency Matrix: Hits (H), Misses (M), False Alarms (F), Correct Rejections (C)
- Hit Rate / Probability of Detection (POD) = H / (H + M)
- False Alarm Ratio (FAR) = F / (H + F)
- Critical Success Index (CSI / Threat Score) = H / (H + M + F)
- Depth Accuracy: Mean Error / Bias (m), Root Mean Square Error (RMSE, m)
- Fits empirical calibration parameters: depth_scale (alpha), depth_offset (beta)
"""

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import geopandas as gpd
import numpy as np
import rasterio

# Import centralized environment
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))
import _env


def load_all_survey_points(
    survey_dirs: list[str] = ["data/qfield_result", "data"],
    target_crs: str = "EPSG:32747",
) -> gpd.GeoDataFrame:
    """Loads and aggregates all survey ground truth GeoPackage files."""
    gdfs = []
    for s_dir in survey_dirs:
        for f in glob.glob(f"{s_dir}/*.gpkg"):
            f_name = Path(f).name.lower()
            if "data" in f_name or "survey" in f_name or "ground" in f_name:
                try:
                    gdf = gpd.read_file(f)
                    if not gdf.empty and gdf.geometry.notna().any():
                        if str(gdf.crs) != target_crs:
                            gdf = gdf.to_crs(target_crs)
                        gdfs.append(gdf)
                except Exception:
                    pass

    if not gdfs:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    combined = gpd.GeoDataFrame(pd_concat(gdfs), crs=target_crs)
    return combined


def pd_concat(gdfs):
    import pandas as pd
    return pd.concat(gdfs, ignore_index=True)


def validate_flood_map(
    depth_tif: str,
    das_geom_gpkg: Optional[str] = None,
    survey_gpkg: Optional[str] = None,
    hmin: float = 0.05,
    out_json: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validates a modeled flood depth raster against survey observations.
    """
    depth_path = Path(depth_tif).resolve()
    if not depth_path.exists():
        raise FileNotFoundError(f"Flood depth raster not found at {depth_path}")

    # Load survey points
    if survey_gpkg and Path(survey_gpkg).exists():
        survey_gdf = gpd.read_file(survey_gpkg)
    else:
        survey_gdf = load_all_survey_points()

    with rasterio.open(depth_path) as src:
        raster_crs = src.crs
        transform = src.transform
        depth_arr = src.read(1)
        nodata = src.nodata

    if str(survey_gdf.crs) != str(raster_crs):
        survey_gdf = survey_gdf.to_crs(raster_crs)

    # Filter to catchment boundary if provided
    if das_geom_gpkg and Path(das_geom_gpkg).exists():
        das_gdf = gpd.read_file(das_geom_gpkg).to_crs(raster_crs)
        union_geom = das_gdf.geometry.union_all() if hasattr(das_gdf.geometry, "union_all") else das_gdf.geometry.unary_union
        survey_gdf = survey_gdf[survey_gdf.intersects(union_geom)].copy()

    total_pts = len(survey_gdf)
    if total_pts == 0:
        result = {
            "survey_points_count": 0,
            "message": "No survey ground truth points located within the model domain.",
            "fitted_depth_scale": 1.0,
            "fitted_depth_offset": 0.0,
        }
        if out_json:
            Path(out_json).parent.mkdir(parents=True, exist_ok=True)
            with open(out_json, "w") as f:
                json.dump(result, f, indent=2)
        return result

    # Sample raster at survey points
    coords = [(geom.x, geom.y) for geom in survey_gdf.geometry if geom is not None]
    sampled_depths = []
    with rasterio.open(depth_path) as src:
        for val in src.sample(coords):
            sampled_depths.append(float(val[0]))

    sampled_depths = np.array(sampled_depths)
    if nodata is not None:
        sampled_depths = np.where(sampled_depths == nodata, np.nan, sampled_depths)

    # Extract observed depths
    obs_col = None
    for cand in ["water_depth_cm", "depth_cm", "water_depth", "depth_m", "depth"]:
        if cand in survey_gdf.columns:
            obs_col = cand
            break

    obs_depths_m = []
    if obs_col:
        for val in survey_gdf[obs_col]:
            try:
                v = float(val)
                # If values are in cm (typically > 5 for moderate floods), convert to meters
                if "cm" in obs_col.lower() or v > 10.0:
                    obs_depths_m.append(v / 100.0)
                else:
                    obs_depths_m.append(v)
            except (ValueError, TypeError):
                obs_depths_m.append(np.nan)
    else:
        # Default: all survey points were taken at flooded locations
        obs_depths_m = [0.50] * total_pts

    obs_depths_m = np.array(obs_depths_m)

    # Contingency evaluation
    # Flooded: depth >= hmin
    pred_flooded = (sampled_depths >= hmin) & np.isfinite(sampled_depths)
    obs_flooded = (obs_depths_m >= hmin) & np.isfinite(obs_depths_m)

    hits = int(np.sum(pred_flooded & obs_flooded))
    misses = int(np.sum((~pred_flooded) & obs_flooded))
    false_alarms = int(np.sum(pred_flooded & (~obs_flooded)))
    correct_rejections = int(np.sum((~pred_flooded) & (~obs_flooded)))

    pod = hits / max(hits + misses, 1)
    far = false_alarms / max(hits + false_alarms, 1)
    csi = hits / max(hits + misses + false_alarms, 1)

    # Depth accuracy for points where both observed and modeled are valid & wet
    valid_pair = np.isfinite(sampled_depths) & np.isfinite(obs_depths_m) & (obs_depths_m > 0)
    if np.sum(valid_pair) >= 3:
        p_wet = sampled_depths[valid_pair]
        o_wet = obs_depths_m[valid_pair]
        bias = float(np.mean(p_wet - o_wet))
        rmse = float(np.sqrt(np.mean((p_wet - o_wet) ** 2)))

        # Fit least squares calibration: o = alpha * p + beta
        try:
            poly = np.polyfit(p_wet, o_wet, 1)
            depth_scale = round(float(poly[0]), 4)
            depth_offset = round(float(poly[1]), 4)
        except Exception:
            depth_scale = 1.0
            depth_offset = 0.0
    else:
        bias = 0.0
        rmse = 0.0
        depth_scale = 1.0
        depth_offset = 0.0

    result = {
        "survey_points_evaluated": total_pts,
        "contingency": {
            "hits": hits,
            "misses": misses,
            "false_alarms": false_alarms,
            "correct_rejections": correct_rejections,
        },
        "hit_rate_pod": round(pod, 4),
        "false_alarm_ratio_far": round(far, 4),
        "critical_success_index_csi": round(csi, 4),
        "depth_rmse_m": round(rmse, 4),
        "depth_bias_m": round(bias, 4),
        "fitted_depth_scale": depth_scale,
        "fitted_depth_offset": depth_offset,
    }

    print(f"[SURVEY VALIDATION] Evaluated {total_pts} points: Hits={hits}, Misses={misses}, POD={pod:.2f}, CSI={csi:.2f}, RMSE={rmse:.2f}m")
    if out_json:
        out_p = Path(out_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"[SURVEY VALIDATION] Metrics report saved to: {out_p}")

    return result


def validate_model_against_survey(
    hazard_dir: Optional[str | Path] = None,
    depth_tif: Optional[str | Path] = None,
    das_geom_gpkg: Optional[str] = None,
    das_clusters_path: Optional[str] = None,
    das_id: Optional[str] = None,
    survey_path: Optional[str] = None,
    survey_gpkg: Optional[str] = None,
    hmin: float = 0.05,
    out_json: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience wrapper for pipeline & notebook calls."""
    if depth_tif is None and hazard_dir is not None:
        hdir = Path(hazard_dir)
        # Search for new format *Flood_Depth.tif or legacy *flood_depth*.tif, excluding raw/display
        all_candidates = (
            list(hdir.glob("*Flood_Depth.tif"))
            + list(hdir.glob("*flood_depth*.tif"))
            + list(hdir.glob("*.tif"))
        )
        candidates = [
            f for f in all_candidates
            if not f.name.endswith("_raw.tif")
            and not f.name.endswith("_display.tif")
            and "Classes" not in f.name
            and "Index" not in f.name
            and ("Flood_Depth" in f.name or "depth" in f.name.lower())
        ]
        if candidates:
            depth_tif = candidates[0]
        else:
            return {"survey_points_count": 0, "message": f"No depth raster found in {hdir}"}

    das_geom = das_geom_gpkg or das_clusters_path
    survey_file = survey_gpkg or survey_path
    if survey_file and Path(survey_file).is_dir():
        survey_file = None  # let validate_flood_map load from dir

    return validate_flood_map(
        depth_tif=str(depth_tif),
        das_geom_gpkg=str(das_geom) if das_geom else None,
        survey_gpkg=str(survey_file) if survey_file else None,
        hmin=hmin,
        out_json=out_json,
    )


def main():
    parser = argparse.ArgumentParser(description="Validate modeled flood depth raster against QField survey ground truth.")
    parser.add_argument("--depth", required=True, help="Path to flood_depth_10m.tif")
    parser.add_argument("--das-geom", default=None, help="Path to DAS polygon GPKG")
    parser.add_argument("--survey", default=None, help="Path to survey ground truth GPKG")
    parser.add_argument("--out-json", default=None, help="Path to output JSON metrics file")
    args = parser.parse_args()

    validate_flood_map(
        depth_tif=args.depth,
        das_geom_gpkg=args.das_geom,
        survey_gpkg=args.survey,
        out_json=args.out_json,
    )


if __name__ == "__main__":
    main()
