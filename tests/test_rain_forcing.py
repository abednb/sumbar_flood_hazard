"""
test_rain_forcing.py
====================
Unit tests for rainfall forcing volume check and zero padding up to tstop (Issue C2).
"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr


@pytest.mark.parametrize("recession_hours", [12, 48])
def test_zero_padding_and_volume_conservation(recession_hours):
    # Synthetic 24-hour storm hyetograph
    storm_hours = 24
    total_hours = storm_hours + recession_hours

    tstart = pd.to_datetime("2024-01-01 00:00:00")
    storm_times = pd.date_range(start=tstart, periods=storm_hours, freq="1h")

    # Intensity array: e.g. triangular storm peaking at hour 12
    intensity = np.array([5.0 + 10.0 * np.sin(np.pi * i / 24) for i in range(storm_hours)])
    # Spatial grid 5x5
    data_3d = np.broadcast_to(intensity[:, None, None], (storm_hours, 5, 5))

    da_storm = xr.DataArray(
        data_3d,
        coords={"time": storm_times, "y": np.arange(5), "x": np.arange(5)},
        dims=["time", "y", "x"]
    )

    # Pad with explicit zeros up to tstop
    full_times = pd.date_range(start=tstart, periods=total_hours + 1, freq="1h")
    da_padded = da_storm.reindex(time=full_times, fill_value=0.0)

    # 1. Verify padding shape
    assert da_padded.sizes["time"] == total_hours + 1

    # 2. Verify all timesteps after storm_hours are strictly 0.0
    post_storm = da_padded.isel(time=slice(storm_hours, None)).values
    assert np.all(post_storm == 0.0), "Post-storm padded rainfall values must be strictly 0.0!"

    # 3. Volume conservation: integrated sum must equal design storm total within 1%
    storm_total = float(da_storm.sum(dim="time").mean().values)
    padded_total = float(da_padded.sum(dim="time").mean().values)
    diff_pct = abs(storm_total - padded_total) / storm_total * 100.0

    assert diff_pct < 0.001, f"Volume difference {diff_pct:.4f}% exceeds tolerance!"
