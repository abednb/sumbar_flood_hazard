"""
split_das_108_mentawai.py
=========================
Splits the discontinuous archipelago cluster DAS 108 (Kabupaten Kepulauan Mentawai)
from 'data/modified_das_cluster/smaller_das_cluster.gpkg' into 4 distinct, standalone
island catchment clusters based on the 4 primary islands:

    - DAS_108_A: Pulau Siberut       (North, largest island)
    - DAS_108_B: Pulau Sipora        (Middle-North island)
    - DAS_108_C: Pulau Pagai Utara   (Middle-South island)
    - DAS_108_D: Pulau Pagai Selatan (South island)

All surrounding coastal islets are clustered into their closest parent island via
nearest-neighbor Euclidean distance.

Outputs:
    - data/modified_das_cluster/smaller_das_cluster_split_mentawai.gpkg (17 clusters)
    - data/das_clusters/individual/DAS_108_A.gpkg
    - data/das_clusters/individual/DAS_108_B.gpkg
    - data/das_clusters/individual/DAS_108_C.gpkg
    - data/das_clusters/individual/DAS_108_D.gpkg
"""

from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union
try:
    import scripts._env  # noqa: F401
except ImportError:
    import _env  # noqa: F401


def split_das_108(
    in_gpkg: str = "data/das_clusters/sumbar_das_cluster.gpkg",
    out_gpkg: str = "data/das_clusters/sumbar_das_cluster.gpkg",
    out_individual_dir: str = "data/das_clusters/individual",
) -> gpd.GeoDataFrame:
    in_path = Path(in_gpkg)
    if not in_path.exists():
        raise FileNotFoundError(f"Input cluster GPKG not found: {in_path}")

    print(f"Reading input clusters from: {in_path}")
    gdf = gpd.read_file(in_path)
    crs = gdf.crs

    # Check if already split
    if "DAS_108_A" in gdf["ID_Cluster"].values:
        print("[OK] Cluster 108 is already split into DAS_108_A, DAS_108_B, DAS_108_C, and DAS_108_D.")
        return gdf

    # Find DAS 108 row
    mask_108 = gdf["ID_Cluster"].astype(str).str.contains("108")
    if not mask_108.any():
        raise ValueError("Could not find Cluster 108 in input GeoPackage.")

    row_108 = gdf[mask_108].iloc[0]
    geom_108 = row_108.geometry
    orig_area_km2 = geom_108.area / 1e6

    # Extract all individual component polygons
    polys = list(geom_108.geoms) if isinstance(geom_108, MultiPolygon) else [geom_108]
    print(f"Cluster 108 comprises {len(polys)} discrete polygon components (Total Area: {orig_area_km2:.2f} km²)")

    # Sort polygons by area descending to identify 4 core main islands
    polys.sort(key=lambda p: p.area, reverse=True)
    if len(polys) < 4:
        raise ValueError(f"Expected at least 4 polygons for Mentawai main islands, found {len(polys)}.")

    core_4 = polys[:4]
    # Sort the 4 core islands from North to South by centroid Y coordinate
    core_4.sort(key=lambda p: p.centroid.y, reverse=True)

    island_configs = [
        {"id": "DAS_108_A", "name": "Pulau Siberut", "desc": "Kabupaten Kepulauan Mentawai (Pulau Siberut)"},
        {"id": "DAS_108_B", "name": "Pulau Sipora", "desc": "Kabupaten Kepulauan Mentawai (Pulau Sipora)"},
        {"id": "DAS_108_C", "name": "Pulau Pagai Utara", "desc": "Kabupaten Kepulauan Mentawai (Pulau Pagai Utara)"},
        {"id": "DAS_108_D", "name": "Pulau Pagai Selatan", "desc": "Kabupaten Kepulauan Mentawai (Pulau Pagai Selatan)"},
    ]

    island_polys = {cfg["id"]: [core_p] for cfg, core_p in zip(island_configs, core_4)}

    # Assign remaining fringe islets to nearest main island
    for islet in polys[4:]:
        min_dist = float("inf")
        nearest_id = None
        for cfg, core_p in zip(island_configs, core_4):
            dist = islet.distance(core_p)
            if dist < min_dist:
                min_dist = dist
                nearest_id = cfg["id"]
        island_polys[nearest_id].append(islet)

    # Build new rows for the 4 split clusters
    new_rows = []
    split_records = []
    total_split_area = 0.0

    for cfg in island_configs:
        c_id = cfg["id"]
        p_list = island_polys[c_id]
        merged_geom = unary_union(p_list)
        if isinstance(merged_geom, Polygon):
            merged_geom = MultiPolygon([merged_geom])

        area_km2 = round(merged_geom.area / 1e6, 2)
        total_split_area += area_km2

        record = {
            "ID_Cluster": c_id,
            "KabKot_DAS": cfg["desc"],
            "Luas_Original_km2": area_km2,
            "Luas": area_km2,
            "Reduction_pct": 0.0,
            "Status": "Split Island Cluster",
            "geometry": merged_geom,
        }
        new_rows.append(record)
        split_records.append((c_id, cfg["name"], len(p_list), area_km2))

    # Verify Area Conservation
    area_diff = abs(total_split_area - orig_area_km2)
    print("\n--- Mentawai Island Split Verification ---")
    for c_id, name, count, area in split_records:
        print(f"  • {c_id:10s} ({name:20s}): {count:2d} polygons | Area: {area:8.2f} km²")
    print(f"  Total Split Area : {total_split_area:.2f} km²")
    print(f"  Original Area    : {orig_area_km2:.2f} km² (Delta: {area_diff:.4f} km²)")
    assert area_diff < 0.05, f"Area mismatch exceeds tolerance: {area_diff} km²"

    # Assemble complete GeoDataFrame
    # Keep clusters 101 to 107, insert the 4 split clusters, then 109 to 114
    non_108_before = gdf.iloc[:7].copy()
    non_108_after = gdf.iloc[8:].copy()

    split_gdf = gpd.GeoDataFrame(new_rows, crs=crs)

    # Cast ID_Cluster to string for uniform column type
    combined_dfs = []
    for df in [non_108_before, split_gdf, non_108_after]:
        df = df.copy()
        df["ID_Cluster"] = df["ID_Cluster"].astype(str)
        combined_dfs.append(df)

    final_gdf = pd.concat(combined_dfs, ignore_index=True)
    final_gdf = gpd.GeoDataFrame(final_gdf, crs=crs)

    # Add das_id column for standard pipeline compatibility
    final_gdf["das_id"] = final_gdf["ID_Cluster"].apply(
        lambda x: x if x.startswith("DAS_") else f"DAS_{x}"
    )

    # Reorder columns logically
    cols = ["ID_Cluster", "das_id", "KabKot_DAS", "Luas_Original_km2", "Luas", "Reduction_pct", "Status", "geometry"]
    final_gdf = final_gdf[cols]

    # Save to new GPKG file
    out_p = Path(out_gpkg)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    final_gdf.to_file(out_p, driver="GPKG")
    print(f"\n[OK] Successfully saved new 17-cluster GPKG to: {out_p}")

    # Also save individual cluster files in out_individual_dir
    indiv_dir = Path(out_individual_dir)
    indiv_dir.mkdir(parents=True, exist_ok=True)
    for c_id in ["DAS_108_A", "DAS_108_B", "DAS_108_C", "DAS_108_D"]:
        sub_gdf = final_gdf[final_gdf["das_id"] == c_id].copy()
        out_indiv = indiv_dir / f"{c_id}.gpkg"
        sub_gdf.to_file(out_indiv, driver="GPKG")
        print(f"[OK] Individual cluster GPKG saved: {out_indiv}")

    return final_gdf


if __name__ == "__main__":
    split_das_108()
