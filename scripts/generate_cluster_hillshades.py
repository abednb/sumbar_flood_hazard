import os
import sys
import math
import time
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.windows import from_bounds, Window
from rasterio.features import rasterize
from rasterio.enums import Resampling
import pyproj

# Fix PROJ and GDAL paths for Windows
proj_dir = os.path.abspath(r".\env-sfincs\Lib\site-packages\rasterio\proj_data")
gdal_dir = os.path.abspath(r".\env-sfincs\Lib\site-packages\rasterio\gdal_data")
if os.path.exists(proj_dir):
    os.environ["PROJ_DATA"] = proj_dir
    os.environ["PROJ_LIB"] = proj_dir
    pyproj.datadir.set_data_dir(proj_dir)
if os.path.exists(gdal_dir):
    os.environ["GDAL_DATA"] = gdal_dir

def calculate_hillshade_numpy(dem_chunk, dx, dy, azimuth_deg=315.0, altitude_deg=45.0, z_factor=1.0, nodata_val=None):
    zenith_rad = math.radians(90.0 - altitude_deg)
    azimuth_math_rad = math.radians(360.0 - azimuth_deg + 90.0) % (2.0 * math.pi)
    
    valid_mask = np.ones(dem_chunk.shape, dtype=bool)
    if nodata_val is not None and not np.isnan(nodata_val):
        valid_mask = valid_mask & (dem_chunk != nodata_val)
    valid_mask = valid_mask & (~np.isnan(dem_chunk)) & (dem_chunk > -500) & (dem_chunk < 9000)
    
    z = np.where(valid_mask, dem_chunk.astype(np.float32) * float(z_factor), 0.0)
    
    za = z[0:-2, 0:-2]
    zb = z[0:-2, 1:-1]
    zc = z[0:-2, 2:]
    zd = z[1:-1, 0:-2]
    zf = z[1:-1, 2:]
    zg = z[2:, 0:-2]
    zh = z[2:, 1:-1]
    zi = z[2:, 2:]
    
    dz_dx = ((zc + 2.0 * zf + zi) - (za + 2.0 * zd + zg)) / (8.0 * dx)
    dz_dy = ((zg + 2.0 * zh + zi) - (za + 2.0 * zb + zc)) / (8.0 * dy)
    
    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
    aspect_rad = np.arctan2(dz_dy, -dz_dx)
    
    shaded = (
        np.cos(zenith_rad) * np.cos(slope_rad) +
        np.sin(zenith_rad) * np.sin(slope_rad) * np.cos(azimuth_math_rad - aspect_rad)
    )
    
    shaded = np.clip(shaded, 0.0, 1.0)
    hillshade_inner = np.round(255.0 * shaded).astype(np.uint8)
    hillshade = np.pad(hillshade_inner, pad_width=1, mode='edge')
    hillshade[~valid_mask] = 0
    return hillshade

def process_cluster_streaming(src, cluster_gdf, out_path, chunk_size=2048):
    t0 = time.time()
    src_crs = src.crs
    res_x, res_y = abs(src.res[0]), abs(src.res[1])
    nodata_val = src.nodata
    
    if cluster_gdf.crs != src_crs:
        cluster_gdf = cluster_gdf.to_crs(src_crs)
        
    buffered_geom = cluster_gdf.geometry.buffer(500).values
    total_bounds = cluster_gdf.geometry.buffer(500).total_bounds  # minx, miny, maxx, maxy
    
    # Calculate raster window from bounds
    cluster_win = from_bounds(*total_bounds, transform=src.transform)
    # Round window coordinates
    col_off = max(0, int(math.floor(cluster_win.col_off)))
    row_off = max(0, int(math.floor(cluster_win.row_off)))
    w = min(src.width - col_off, int(math.ceil(cluster_win.width)))
    h = min(src.height - row_off, int(math.ceil(cluster_win.height)))
    
    out_transform = rasterio.windows.transform(Window(col_off, row_off, w, h), src.transform)
    
    out_meta = {
        'driver': 'GTiff',
        'dtype': 'uint8',
        'nodata': 0,
        'width': w,
        'height': h,
        'count': 1,
        'crs': src_crs,
        'transform': out_transform,
        'tiled': True,
        'blockxsize': 256,
        'blockysize': 256,
        'compress': 'zstd',
        'zstd_level': 9,
        'predictor': 2,
        'interleave': 'band'
    }
    
    n_cols = math.ceil(w / chunk_size)
    n_rows = math.ceil(h / chunk_size)
    
    with rasterio.open(out_path, 'w', **out_meta) as dst:
        for r_idx in range(n_rows):
            local_row = r_idx * chunk_size
            win_h = min(chunk_size, h - local_row)
            
            for c_idx in range(n_cols):
                local_col = c_idx * chunk_size
                win_w = min(chunk_size, w - local_col)
                
                # Global coords in source DEM with 1-pixel halo
                src_row = row_off + local_row
                src_col = col_off + local_col
                
                read_row_off = max(0, src_row - 1)
                read_col_off = max(0, src_col - 1)
                read_h = min(src.height, src_row + win_h + 1) - read_row_off
                read_w = min(src.width, src_col + win_w + 1) - read_col_off
                
                pad_top = 1 if src_row > 0 else 0
                pad_left = 1 if src_col > 0 else 0
                
                chunk = src.read(1, window=Window(read_col_off, read_row_off, read_w, read_h))
                
                hs_chunk = calculate_hillshade_numpy(
                    chunk, dx=res_x, dy=res_y, azimuth_deg=315.0, altitude_deg=45.0, z_factor=1.0, nodata_val=nodata_val
                )
                
                hs_inner = hs_chunk[pad_top:pad_top + win_h, pad_left:pad_left + win_w]
                
                # Write to target GeoTIFF
                dst.write(hs_inner, 1, window=Window(local_col, local_row, win_w, win_h))
                
        # Build pyramids
        dst.build_overviews([2, 4, 8, 16], Resampling.average)
        dst.update_tags(ns='rio_overview', resampling='average')
        
    size_mb = os.path.getsize(out_path) / (1024 ** 2)
    elapsed = time.time() - t0
    return w, h, size_mb, elapsed

def main():
    dem_path = "data/fabdem_reprojected.tif"
    output_dir = Path("data/hillshade_clusters")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    clusters = ["DAS_101", "DAS_102", "DAS_103"]
    
    print("=" * 70)
    print("⛰️ GENERATING CLUSTER-SPECIFIC COMPACT HILLSHADES FOR QFIELD")
    print("=" * 70)
    print(f"📂 Source DEM       : {dem_path}")
    print(f"📁 Output Directory : {output_dir}")
    print(f"🎯 Target Clusters  : {', '.join(clusters)}")
    print("=" * 70)
    
    with rasterio.open(dem_path) as src:
        for cname in clusters:
            gpkg_path = Path(f"data/das_clusters/individual/{cname}.gpkg")
            if not gpkg_path.exists():
                gdf_all = gpd.read_file("data/das_clusters.gpkg")
                cid_num = float(cname.replace("DAS_", ""))
                col = 'ID_Cluster' if 'ID_Cluster' in gdf_all.columns else gdf_all.columns[0]
                cluster_gdf = gdf_all[gdf_all[col].astype(float) == cid_num]
            else:
                cluster_gdf = gpd.read_file(gpkg_path)
                
            out_file = output_dir / f"hillshade_{cname}.tif"
            print(f"\n🌊 Processing {cname} (Streaming Windowed COG)...")
            w, h, size_mb, elapsed = process_cluster_streaming(src, cluster_gdf, out_file, chunk_size=2048)
            print(f"   Grid Dimensions : {w:,} x {h:,} px ({w * h:,} pixels)")
            print(f"   💾 Saved File   : {out_file}")
            print(f"   📦 File Size    : {size_mb:.2f} MB (Tiled + Pyramids included)")
            print(f"   ⏱️ Time Taken   : {elapsed:.2f} seconds")
            
    print("\n" + "=" * 70)
    print("🎉 ALL 3 CLUSTER HILLSHADES GENERATED SUCCESSFULLY FOR QFIELD!")
    print("=" * 70)

if __name__ == "__main__":
    main()
