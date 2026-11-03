"""
test_cluster_matching.py
========================
Unit tests for find_cluster_geometry unambiguous matching and error handling (Issue M4).
"""

import geopandas as gpd
import pytest
from shapely.geometry import Polygon
from scripts.sfincs_standalone_pipeline import find_cluster_geometry


def create_synthetic_clusters():
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    data = {
        "ID_Cluster": [101.0, 102.0, 103.0, 104.0],
        "KabKot_DAS": ["Agam", "Padang", "Solok", "Pasaman"],
        "geometry": [poly, poly, poly, poly],
    }
    return gpd.GeoDataFrame(data, crs="EPSG:32747")


def test_unambiguous_cluster_matching():
    gdf = create_synthetic_clusters()

    # Exact string 'DAS_101' matching 101.0
    res, das_str = find_cluster_geometry(gdf, "DAS_101", id_column="ID_Cluster")
    assert len(res) == 1
    assert float(res["ID_Cluster"].iloc[0]) == 101.0

    # Numeric string '102'
    res, das_str = find_cluster_geometry(gdf, "102", id_column="ID_Cluster")
    assert len(res) == 1
    assert float(res["ID_Cluster"].iloc[0]) == 102.0

    # Alphanumeric 'DAS104'
    res, das_str = find_cluster_geometry(gdf, "DAS104", id_column="ID_Cluster")
    assert len(res) == 1
    assert float(res["ID_Cluster"].iloc[0]) == 104.0


def test_cluster_not_found_raises():
    gdf = create_synthetic_clusters()
    with pytest.raises(ValueError, match="was not found in dataset"):
        find_cluster_geometry(gdf, "DAS_999", id_column="ID_Cluster")


def test_ambiguous_cluster_match_raises():
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    # Duplicate cluster ID in dataset
    data = {
        "ID_Cluster": [101.0, 101.0, 102.0],
        "geometry": [poly, poly, poly],
    }
    gdf = gpd.GeoDataFrame(data, crs="EPSG:32747")

    with pytest.raises(ValueError, match="Ambiguous match: Found 2 rows"):
        find_cluster_geometry(gdf, "DAS_101", id_column="ID_Cluster")
