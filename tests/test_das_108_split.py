"""
test_das_108_split.py
=====================
Unit tests verifying the disaggregation of archipelago cluster DAS 108 into
the 4 distinct main island clusters of Kabupaten Kepulauan Mentawai:
    - DAS_108_A (Pulau Siberut)
    - DAS_108_B (Pulau Sipora)
    - DAS_108_C (Pulau Pagai Utara)
    - DAS_108_D (Pulau Pagai Selatan)
"""

from pathlib import Path
import geopandas as gpd
import pytest
from scripts.sfincs_standalone_pipeline import find_cluster_geometry


SPLIT_GPKG = Path("data/das_clusters/sumbar_das_cluster.gpkg")


def test_split_gpkg_exists_and_structure():
    assert SPLIT_GPKG.exists(), f"Split GPKG not found: {SPLIT_GPKG}"
    gdf = gpd.read_file(SPLIT_GPKG)

    # 17 clusters total (14 - 1 + 4)
    assert len(gdf) == 17
    assert gdf.crs.to_epsg() == 32747

    required_cols = {"ID_Cluster", "das_id", "KabKot_DAS", "Luas", "geometry"}
    assert required_cols.issubset(set(gdf.columns))


def test_mentawai_clusters_present_and_valid():
    gdf = gpd.read_file(SPLIT_GPKG)
    cluster_ids = set(gdf["das_id"].tolist())

    expected_mentawai = {"DAS_108_A", "DAS_108_B", "DAS_108_C", "DAS_108_D"}
    assert expected_mentawai.issubset(cluster_ids)

    # Verify each split island cluster has valid geometries and positive area
    for c_id in expected_mentawai:
        sub = gdf[gdf["das_id"] == c_id]
        assert len(sub) == 1
        geom = sub.iloc[0].geometry
        assert geom.is_valid
        assert not geom.is_empty
        assert geom.area > 1e8  # > 100 km2


def test_area_conservation():
    orig_area_km2 = 5863.54

    gdf_split = gpd.read_file(SPLIT_GPKG)
    mentawai_sub = gdf_split[gdf_split["das_id"].isin(["DAS_108_A", "DAS_108_B", "DAS_108_C", "DAS_108_D"])]
    split_area_km2 = mentawai_sub.geometry.area.sum() / 1e6

    assert abs(split_area_km2 - orig_area_km2) < 0.1


def test_pipeline_find_cluster_geometry_compatibility():
    gdf_split = gpd.read_file(SPLIT_GPKG)
    for target in ["DAS_108_A", "DAS_108_B", "DAS_108_C", "DAS_108_D", "108_A", "108_B"]:
        res_gdf, matched_str = find_cluster_geometry(gdf_split, target)
        assert len(res_gdf) == 1
        assert "Mentawai" in res_gdf.iloc[0]["KabKot_DAS"]


def test_individual_gpkg_files_exist():
    indiv_dir = Path("data/das_clusters/individual")
    for c_id in ["DAS_108_A", "DAS_108_B", "DAS_108_C", "DAS_108_D"]:
        p = indiv_dir / f"{c_id}.gpkg"
        assert p.exists(), f"Individual cluster file missing: {p}"
        gdf = gpd.read_file(p)
        assert len(gdf) == 1
