"""
rebuild_individual_clusters.py
==============================
Re-exports clean, unified individual cluster boundary files and catchment outlet points
from 'data/das_clusters/sumbar_das_cluster.gpkg' into 'data/das_clusters/individual/'.
Deletes the legacy 'data/das_clusters/chips/' directory.
"""

from pathlib import Path
import shutil
import geopandas as gpd
from shapely.geometry import Point

try:
    import scripts._env  # noqa: F401
except ImportError:
    import _env  # noqa: F401


def rebuild():
    # 1. Permanently remove legacy chips directory
    chips_dir = Path("data/das_clusters/chips")
    if chips_dir.exists():
        shutil.rmtree(chips_dir)
        print(f"[OK] Deleted legacy manual cache directory: {chips_dir}")

    # 2. Read master cluster layer
    master_path = Path("data/das_clusters/sumbar_das_cluster.gpkg")
    if not master_path.exists():
        raise FileNotFoundError(f"Master cluster layer not found: {master_path}")

    gdf = gpd.read_file(master_path)
    crs = gdf.crs
    print(f"[OK] Loaded master cluster layer: {len(gdf)} clusters from {master_path}")

    indiv_dir = Path("data/das_clusters/individual")
    indiv_dir.mkdir(parents=True, exist_ok=True)

    # 3. Clean up obsolete files in individual directory
    obsolete_files = ["101.0.gpkg", "DAS_108.gpkg", "DAS_108_outlet.gpkg"]
    for obs in obsolete_files:
        p = indiv_dir / obs
        if p.exists():
            p.unlink()
            print(f"[OK] Removed obsolete file: {p.name}")

    # 4. Re-export all 17 cluster polygons
    exported_clusters = []
    for _, row in gdf.iterrows():
        c_id = row["das_id"]
        out_gpkg = indiv_dir / f"{c_id}.gpkg"
        sub_gdf = gpd.GeoDataFrame([row], crs=crs)
        sub_gdf.to_file(out_gpkg, driver="GPKG")
        exported_clusters.append(c_id)

    print(f"[OK] Re-exported {len(exported_clusters)} clean cluster boundaries to {indiv_dir}")

    # 5. Define / verify all 17 outlet files
    mentawai_outlets = {
        "DAS_108_A": {
            "coords": (524008.573, 9823450.626),
            "kabkot": "Kabupaten Kepulauan Mentawai (Pulau Siberut)",
            "river": "Sungai Siberut",
        },
        "DAS_108_B": {
            "coords": (579055.527, 9762908.989),
            "kabkot": "Kabupaten Kepulauan Mentawai (Pulau Sipora)",
            "river": "Sungai Saureinu",
        },
        "DAS_108_C": {
            "coords": (629648.185, 9691117.352),
            "kabkot": "Kabupaten Kepulauan Mentawai (Pulau Pagai Utara)",
            "river": "Sungai Sikoko",
        },
        "DAS_108_D": {
            "coords": (650443.111, 9679265.179),
            "kabkot": "Kabupaten Kepulauan Mentawai (Pulau Pagai Selatan)",
            "river": "Sungai Mapoupou",
        },
    }

    for c_id, info in mentawai_outlets.items():
        out_file = indiv_dir / f"{c_id}_outlet.gpkg"
        pt = Point(info["coords"])
        outlet_gdf = gpd.GeoDataFrame(
            [{"das_id": c_id, "elevation_m": 0.0, "kabkot": info["kabkot"], "geometry": pt}],
            crs=crs,
        )
        outlet_gdf.to_file(out_file, driver="GPKG")
        print(f"[OK] Generated island river mouth outlet: {out_file.name} ({info['river']})")

    # 6. Final verification count
    all_gpkgs = list(indiv_dir.glob("*.gpkg"))
    boundary_gpkgs = [p for p in all_gpkgs if not p.name.endswith("_outlet.gpkg")]
    outlet_gpkgs = [p for p in all_gpkgs if p.name.endswith("_outlet.gpkg")]

    print("\n--- Final Individual Cluster Inventory ---")
    print(f"Total Boundary GPKGs : {len(boundary_gpkgs)} (Expected: 17)")
    print(f"Total Outlet GPKGs   : {len(outlet_gpkgs)} (Expected: 17)")
    assert len(boundary_gpkgs) == 17, f"Expected 17 boundaries, got {len(boundary_gpkgs)}"
    assert len(outlet_gpkgs) == 17, f"Expected 17 outlets, got {len(outlet_gpkgs)}"
    print("[SUCCESS] All 17 clusters have synchronized boundaries and outlet points!")


if __name__ == "__main__":
    rebuild()
