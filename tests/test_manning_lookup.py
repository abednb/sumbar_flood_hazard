"""
test_manning_lookup.py
======================
Unit tests verifying Manning lookup table schema and coverage against the integer raster (Issue C1).
"""

from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
import pytest


def test_manning_lookup_table_schema():
    lookup_path = Path("lookup_tables/manning_lookup.csv")
    assert lookup_path.exists(), "lookup_tables/manning_lookup.csv missing!"

    df = pd.read_csv(lookup_path)

    # 1. First column must be an integer identifier
    first_col = df.columns[0]
    assert first_col == "rbi_id", f"First column must be 'rbi_id', got '{first_col}'"
    assert pd.api.types.is_integer_dtype(df[first_col]), "First column is not integer typed!"

    # 2. Must contain exactly 'N' column for HydroMT-SFINCS
    assert "N" in df.columns, "Column 'N' missing from lookup table!"
    assert pd.api.types.is_float_dtype(df["N"]), "Column 'N' is not float typed!"
    assert np.all(df["N"] > 0), "All Manning n values must be positive!"

    # 3. Explicit row for nodata / unclassified (0)
    row_zero = df[df[first_col] == 0]
    assert not row_zero.empty, "Explicit row 0 for nodata/unclassified is missing!"
    assert float(row_zero["N"].iloc[0]) == 0.04, "Row 0 default Manning n should be 0.04!"


def test_raster_class_coverage_in_lookup():
    raster_path = Path("data/landcover_rbi.tif")
    lookup_path = Path("lookup_tables/manning_lookup.csv")

    if not raster_path.exists():
        pytest.skip("data/landcover_rbi.tif has not been generated yet.")

    df = pd.read_csv(lookup_path)
    lookup_ids = set(df["rbi_id"].tolist())

    with rasterio.open(raster_path) as src:
        # Sample or read unique values
        data = src.read(1, window=rasterio.windows.Window(0, 0, min(1000, src.width), min(1000, src.height)))
        raster_ids = set(np.unique(data))

    # Assert all raster IDs exist in lookup table
    missing_ids = raster_ids - lookup_ids
    assert len(missing_ids) == 0, f"Raster contains classes not present in lookup table: {missing_ids}"
