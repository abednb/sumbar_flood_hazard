"""
High-Performance Multi-Threaded Hillshade Generator for Sumatra Barat FABDEM
Author: Senior Geospatial Intelligence Expert
Project: West Sumatra Flood Hazard Mapping

Computes standard 315° NW solar illumination (azimuth=315°, altitude=45°, zFactor=1.0)
using parallel multi-threaded Horn's 3x3 convolution and LZW multi-core compression.
"""

import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import rasterio
import rasterio.windows
import numpy as np
from scipy.ndimage import convolve
from tqdm import tqdm
import pyproj

# Fix stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Fix PROJ and GDAL paths for Windows execution
proj_dir = os.path.abspath(r".\env-sfincs\Lib\site-packages\rasterio\proj_data")
gdal_dir = os.path.abspath(r".\env-sfincs\Lib\site-packages\rasterio\gdal_data")
if os.path.exists(proj_dir):
    os.environ["PROJ_DATA"] = proj_dir
    os.environ["PROJ_LIB"] = proj_dir
    pyproj.datadir.set_data_dir(proj_dir)
if os.path.exists(gdal_dir):
    os.environ["GDAL_DATA"] = gdal_dir

os.environ["GDAL_NUM_THREADS"] = "ALL_CPUS"


def generate_hillshade(
    input_dem: str = "data/fabdem_reprojected.tif",
    output_hillshade: str = "data/fabdem_hillshade.tif",
    azimuth: float = 315.0,
    altitude: float = 45.0,
    z_factor: float = 1.0,
    chunk_size: int = 4096,
    num_workers: int = 4,
):
    """
    Generates a high-resolution 8-bit Byte hillshade GeoTIFF from a digital elevation model (DEM).
    
    Parameters:
    -----------
    input_dem : str
        Path to input DEM raster (must be in projected coordinates like EPSG:32747).
    output_hillshade : str
        Path to output hillshade GeoTIFF.
    azimuth : float
        Light source azimuth direction in degrees (315° = North-West, standard).
    altitude : float
        Light source altitude angle in degrees (45° = standard cartographic elevation).
    z_factor : float
        Vertical exaggeration factor (1.0 = true elevation for projected UTM coordinates).
    chunk_size : int
        Processing tile dimension in pixels (default: 4096 x 4096).
    num_workers : int
        Number of parallel thread workers for concurrent block processing.
    """
    in_path = Path(input_dem).resolve()
    out_path = Path(output_hillshade).resolve()
    
    if not in_path.exists():
        raise FileNotFoundError(f"Input DEM not found at: {in_path}")
        
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        try:
            out_path.unlink()
        except Exception:
            pass
    
    print("=" * 80)
    print("GENERATING HIGH-RESOLUTION HILLSHADE FOR SUMATRA BARAT")
    print("=" * 80)
    print(f"Input DEM         : {in_path}")
    print(f"Output Hillshade  : {out_path}")
    print(f"Azimuth           : {azimuth} deg (North-West standard)")
    print(f"Altitude          : {altitude} deg")
    print(f"Z-Factor          : {z_factor}")
    print(f"Processing Engine : Parallel Multi-Threaded Horn 3x3 ({num_workers} workers)")
    print("=" * 80 + "\n")
    
    t0 = time.time()
    
    # Trigonometric constants for solar illumination
    azimuth_math = (360.0 - azimuth + 90.0) % 360.0
    azimuth_rad = np.deg2rad(azimuth_math)
    zenith_rad = np.deg2rad(90.0 - altitude)
    sin_zenith = np.sin(zenith_rad)
    cos_zenith = np.cos(zenith_rad)
    
    with rasterio.open(in_path) as src:
        height, width = src.height, src.width
        dx, dy = abs(src.res[0]), abs(src.res[1])
        nodata = src.nodata
        
        # Horn's 3x3 finite difference kernels (USGS/GDAL standard)
        kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32) / (8.0 * dx) * z_factor
        ky = np.array([[1, 2, 1], [0, 0, 0], [-1, -2, -1]], dtype=np.float32) / (8.0 * dy) * z_factor
        
        profile = src.profile.copy()
        profile.update({
            "dtype": "uint8",
            "nodata": 0,
            "count": 1,
            "compress": "lzw",
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "bigtiff": "yes",
            "predictor": 2,
            "num_threads": "all_cpus"
        })
        
        # Build grid of processing windows
        windows = []
        for r in range(0, height, chunk_size):
            h_win = min(chunk_size, height - r)
            for c in range(0, width, chunk_size):
                w_win = min(chunk_size, width - c)
                windows.append((r, c, h_win, w_win))
                
        print(f"Raster Dimensions: {width:,} x {height:,} ({width*height/1e9:.2f} Billion Pixels)")
        print(f"Total Chunks     : {len(windows)} processing blocks ({chunk_size}x{chunk_size}px)\n")
        
        write_lock = threading.Lock()
        
        with rasterio.open(out_path, "w", **profile) as dst:
            def process_tile(window_params):
                r, c, h_win, w_win = window_params
                r_start = max(0, r - 1)
                r_end = min(height, r + h_win + 1)
                c_start = max(0, c - 1)
                c_end = min(width, c + w_win + 1)
                
                buf_window = rasterio.windows.Window(c_start, r_start, c_end - c_start, r_end - r_start)
                
                with rasterio.open(in_path) as src_local:
                    dem_buf = src_local.read(1, window=buf_window).astype(np.float32)
                
                if nodata is not None:
                    valid_mask = (dem_buf != nodata) & ~np.isnan(dem_buf) & (dem_buf > -900.0)
                else:
                    valid_mask = ~np.isnan(dem_buf) & (dem_buf > -900.0)
                    
                # If entire tile is nodata (e.g. ocean/border), return zero tile quickly
                if not np.any(valid_mask):
                    out_tile = np.zeros((h_win, w_win), dtype=np.uint8)
                else:
                    dem_buf_clean = np.where(valid_mask, dem_buf, 0.0)
                    dz_dx = convolve(dem_buf_clean, kx, mode="nearest")
                    dz_dy = convolve(dem_buf_clean, ky, mode="nearest")
                    
                    slope = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
                    aspect = np.arctan2(-dz_dy, -dz_dx)
                    aspect = np.where(aspect < 0.0, aspect + 2.0 * np.pi, aspect)
                    
                    hillshade = 255.0 * (
                        (cos_zenith * np.cos(slope)) +
                        (sin_zenith * np.sin(slope) * np.cos(azimuth_rad - aspect))
                    )
                    hillshade = np.clip(hillshade, 1.0, 255.0).astype(np.uint8)
                    hillshade[~valid_mask] = 0
                    
                    r_crop_start = r - r_start
                    c_crop_start = c - c_start
                    out_tile = hillshade[r_crop_start : r_crop_start + h_win, c_crop_start : c_crop_start + w_win]
                    
                target_window = rasterio.windows.Window(c, r, w_win, h_win)
                with write_lock:
                    dst.write(out_tile, 1, window=target_window)
                    
                return True

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {executor.submit(process_tile, w): w for w in windows}
                for f in tqdm(as_completed(futures), total=len(windows), desc="Processing Hillshade Tiles", unit="tile"):
                    f.result()
                
    elapsed = time.time() - t0
    file_size_mb = out_path.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 80)
    print("HILLSHADE GENERATION COMPLETED SUCCESSFULLY!")
    print(f"Total Execution Time : {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
    print(f"Output File Size     : {file_size_mb:.2f} MB")
    print(f"Hillshade GeoTIFF    : {out_path}")
    print("=" * 80 + "\n")
    return str(out_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate Hillshade GeoTIFF for Sumatra Barat FABDEM")
    parser.add_argument("--dem", type=str, default="data/fabdem_reprojected.tif", help="Input DEM path")
    parser.add_argument("--out", type=str, default="data/fabdem_hillshade.tif", help="Output Hillshade path")
    parser.add_argument("--azimuth", type=float, default=315.0, help="Solar azimuth in degrees")
    parser.add_argument("--altitude", type=float, default=45.0, help="Solar altitude in degrees")
    parser.add_argument("--zfactor", type=float, default=1.0, help="Vertical exaggeration factor")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel thread workers")
    args = parser.parse_args()
    
    generate_hillshade(
        input_dem=args.dem,
        output_hillshade=args.out,
        azimuth=args.azimuth,
        altitude=args.altitude,
        z_factor=args.zfactor,
        num_workers=args.workers,
    )
