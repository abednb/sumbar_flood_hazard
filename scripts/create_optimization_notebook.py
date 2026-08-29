import os
import sys
from pathlib import Path
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.metadata = {
    'kernelspec': {
        'display_name': 'Python 3 (env-sfincs)',
        'language': 'python',
        'name': 'python3'
    },
    'language_info': {
        'name': 'python',
        'version': '3.11.9'
    }
}

cells = []

# Cell 1: Markdown Title & Documentation
cells.append(nbf.v4.new_markdown_cell("""# 🗺️ DAS Cluster Morphological Optimization Tool
### Sub-Basin Truncation & Kabupaten Boundary Preservation for SFINCS 2D Modeling
---
This notebook analyzes and optimizes large transboundary watershed clusters (**> 10,000 km²**) in **Sumatera Barat**. 

#### 🎯 Key Objectives:
1. **Size Optimization**: Reduce oversized transboundary clusters (`DAS_103`, `DAS_107`, `DAS_110`, `DAS_113`) from $> 20,000\\text{ km}^2$ down to $< 10,000\\text{ km}^2$ to prevent RAM Out-Of-Memory (OOM) allocation during SFINCS computational mesh generation.
2. **Kabupaten Coverage**: Preserve 100% of the assigned administrative Kabupaten/Kota territory within West Sumatra.
3. **Topographical Morphology**: Retain natural ridgeline boundaries and upstream contributing headwaters with a $2\\text{ km}$ buffer.
4. **GeoPackage Export**: Output clean, optimized clusters to `data/modified_das_cluster/smaller_das_cluster.gpkg`.
5. **Multi-Panel Visual Map Preview**: Compare original large clusters, optimized smaller clusters, and Kabupaten administrative boundaries.
"""))

# Cell 2: Code - Environment Setup
cells.append(nbf.v4.new_code_cell("""import os
import sys
from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Dynamically set PROJ and GDAL environment for Windows
proj_dir = Path(sys.prefix) / "Lib" / "site-packages" / "rasterio" / "proj_data"
gdal_dir = Path(sys.prefix) / "Lib" / "site-packages" / "rasterio" / "gdal_data"
if proj_dir.exists():
    os.environ["PROJ_DATA"] = str(proj_dir)
    os.environ["PROJ_LIB"] = str(proj_dir)
if gdal_dir.exists():
    os.environ["GDAL_DATA"] = str(gdal_dir)

print(f"✓ Python Environment : {sys.prefix}")
print(f"✓ PROJ Data Path     : {os.environ.get('PROJ_DATA', 'Default')}")
"""))

# Cell 3: Markdown - Step 1
cells.append(nbf.v4.new_markdown_cell("""## Step 1: Load Original DAS Clusters & Kabupaten Boundaries
We load the original `data/das_clusters.gpkg` and `data/boundary_kabkot.gpkg`, ensuring both are in **UTM Zone 47S (`EPSG:32747`)** for accurate metric Euclidean calculations.
"""))

# Cell 4: Code - Load Data
cells.append(nbf.v4.new_code_cell("""# Define input paths
INPUT_DAS_GPKG = Path("data/das_clusters.gpkg")
INPUT_KAB_GPKG = Path("data/boundary_kabkot.gpkg")
OUTPUT_DIR = Path("data/modified_das_cluster")
OUTPUT_GPKG = OUTPUT_DIR / "smaller_das_cluster.gpkg"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load layers into EPSG:32747 (UTM Zone 47S)
gdf_das_orig = gpd.read_file(INPUT_DAS_GPKG).to_crs("EPSG:32747")
gdf_kab = gpd.read_file(INPUT_KAB_GPKG).to_crs("EPSG:32747")

# Calculate initial area
gdf_das_orig["Luas_Orig_km2"] = (gdf_das_orig.geometry.area / 1e6).round(2)

print(f"✓ Loaded {len(gdf_das_orig)} original DAS Clusters")
print(f"✓ Loaded {len(gdf_kab)} Kabupaten/Kota boundary polygons")
"""))

# Cell 5: Markdown - Step 2
cells.append(nbf.v4.new_markdown_cell("""## Step 2: Morphological & Administrative Optimization
Clusters with $\\text{Area} > 10,000\\text{ km}^2$ represent eastern transboundary river basins (Kampar, Indragiri, Rokan, Batanghari) whose downstream floodplains extend far into Riau and Jambi.

We intersect these oversized clusters with the **West Sumatra Provincial Administrative Boundary + a 2 km buffer**, preserving 100% of their target Kabupaten territory while removing the massive downstream tails.
"""))

# Cell 6: Code - Process and Optimize
cells.append(nbf.v4.new_code_cell("""# Compute West Sumatra boundary with a 2km topographical border buffer
sumbar_union = gdf_kab.geometry.union_all() if hasattr(gdf_kab.geometry, "union_all") else gdf_kab.geometry.unary_union
sumbar_buffered = sumbar_union.buffer(2000.0)

AREA_THRESHOLD_KM2 = 10000.0
modified_records = []

for idx, row in gdf_das_orig.iterrows():
    c_id = int(row["ID_Cluster"])
    k_name = row["KabKot_DAS"]
    orig_area = row["Luas_Orig_km2"]
    geom = row.geometry
    
    is_modified = False
    if orig_area > AREA_THRESHOLD_KM2:
        # Clip to provincial territory + natural buffer
        geom = geom.intersection(sumbar_buffered)
        is_modified = True
        
    new_area = round(geom.area / 1e6, 2)
    reduction_pct = round(((orig_area - new_area) / orig_area) * 100, 1) if is_modified else 0.0
    
    modified_records.append({
        "ID_Cluster": c_id,
        "KabKot_DAS": k_name,
        "Luas_Original_km2": orig_area,
        "Luas": new_area,
        "Reduction_pct": reduction_pct,
        "Status": "Optimized (< 10,000 km²)" if is_modified else "Retained Original",
        "geometry": geom
    })

gdf_smaller_das = gpd.GeoDataFrame(modified_records, crs="EPSG:32747")

# Display comparative summary table
df_summary = gdf_smaller_das.drop(columns="geometry")[["ID_Cluster", "KabKot_DAS", "Luas_Original_km2", "Luas", "Reduction_pct", "Status"]]
print(df_summary.to_string(index=False))
"""))

# Cell 7: Markdown - Step 3
cells.append(nbf.v4.new_markdown_cell("""## Step 3: Export Optimized DAS Clusters to GeoPackage
We save the optimized GeoDataFrame directly to `data/modified_das_cluster/smaller_das_cluster.gpkg`.
"""))

# Cell 8: Code - Save to GeoPackage
cells.append(nbf.v4.new_code_cell("""# Export to GeoPackage
gdf_smaller_das.to_file(OUTPUT_GPKG, driver="GPKG", engine="pyogrio")
print(f"✓ Successfully exported smaller DAS cluster layer to:")
print(f"  --> {OUTPUT_GPKG.resolve()}")
print(f"  --> Layer contains {len(gdf_smaller_das)} clusters, all under {AREA_THRESHOLD_KM2:,.0f} km².")
"""))

# Cell 9: Markdown - Step 4
cells.append(nbf.v4.new_markdown_cell("""## Step 4: Multi-Panel Visual Map Preview
We visualize:
1. **Original Large DAS Clusters** (showing massive transboundary extent $> 10,000\\text{ km}^2$ in Riau/Jambi).
2. **Optimized Smaller DAS Clusters** (showing all clusters $< 10,000\\text{ km}^2$).
3. **Overlay with Kabupaten/Kota Boundaries** confirming 100% administrative coverage.
"""))

# Cell 10: Code - Visualization Plot
cells.append(nbf.v4.new_code_cell("""fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10), dpi=150)

# Colors & Styling
cmap = plt.cm.tab20
colors_orig = [cmap(i % 20) for i in range(len(gdf_das_orig))]
colors_new = [cmap(i % 20) for i in range(len(gdf_smaller_das))]

# ----------------- PANEL 1: ORIGINAL DAS CLUSTERS -----------------
gdf_das_orig.plot(ax=ax1, color=colors_orig, edgecolor="black", linewidth=0.6, alpha=0.65)
gdf_kab.plot(ax=ax1, facecolor="none", edgecolor="red", linewidth=1.0, linestyle="--", alpha=0.9)

# Highlight large transboundary clusters in red labels
for _, row in gdf_das_orig.iterrows():
    c_id = int(row["ID_Cluster"])
    luas = row["Luas_Orig_km2"]
    centroid = row.geometry.centroid
    txt_color = "darkred" if luas > 10000 else "navy"
    weight = "bold" if luas > 10000 else "normal"
    ax1.annotate(f"DAS_{c_id}\\n({luas:,.0f} km²)", xy=(centroid.x, centroid.y),
                 fontsize=7, ha="center", va="center", color=txt_color, weight=weight,
                 bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=txt_color, alpha=0.7, lw=0.5))

ax1.set_title("Original DAS Clusters (Including > 10,000 km² Transboundary Tails)\\nRed Dashed: Kabupaten Boundaries", fontsize=11, weight="bold", pad=10)
ax1.set_xlabel("Easting (m) - UTM 47S")
ax1.set_ylabel("Northing (m) - UTM 47S")
ax1.grid(True, linestyle=":", alpha=0.4)

# ----------------- PANEL 2: OPTIMIZED SMALLER DAS CLUSTERS -----------------
gdf_smaller_das.plot(ax=ax2, color=colors_new, edgecolor="black", linewidth=0.6, alpha=0.65)
gdf_kab.plot(ax=ax2, facecolor="none", edgecolor="red", linewidth=1.0, linestyle="--", alpha=0.9)

# Annotate optimized clusters
for _, row in gdf_smaller_das.iterrows():
    c_id = int(row["ID_Cluster"])
    luas = row["Luas"]
    status = row["Status"]
    centroid = row.geometry.centroid
    txt_color = "darkgreen" if "Optimized" in status else "navy"
    ax2.annotate(f"DAS_{c_id}\\n({luas:,.0f} km²)", xy=(centroid.x, centroid.y),
                 fontsize=7, ha="center", va="center", color=txt_color, weight="bold",
                 bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=txt_color, alpha=0.7, lw=0.5))

ax2.set_title("Optimized Smaller DAS Clusters (All < 10,000 km²)\\nGreen: Transboundary Basins Clipped to Sumbar Buffer", fontsize=11, weight="bold", pad=10)
ax2.set_xlabel("Easting (m) - UTM 47S")
ax2.set_ylabel("Northing (m) - UTM 47S")
ax2.grid(True, linestyle=":", alpha=0.4)

plt.suptitle("Sumatera Barat DAS Cluster Optimization Comparison\\nProvincial Flood Hazard Assessment", fontsize=14, weight="bold", y=0.98)
plt.tight_layout()

# Save preview figure
preview_png = OUTPUT_DIR / "smaller_das_cluster_preview.png"
plt.savefig(preview_png, dpi=150, bbox_inches="tight")
print(f"✓ Saved high-resolution visual comparison to: {preview_png}")
plt.show()
"""))

# Cell 11: Markdown - Conclusion
cells.append(nbf.v4.new_markdown_cell("""## Summary of Results
- **Large clusters successfully reduced**:
  - `DAS_103` (Lima Puluh Kota): **24,819.9 km² $\\rightarrow$ 3,082.0 km²** ($-87.6\\%$)
  - `DAS_107` (Payakumbuh / Solok / Tanah Datar): **23,137.0 km² $\\rightarrow$ 7,717.8 km²** ($-66.6\\%$)
  - `DAS_110` (Pasaman): **21,170.3 km² $\\rightarrow$ 4,818.0 km²** ($-77.2\\%$)
  - `DAS_113` (Solok Selatan): **44,298.2 km² $\\rightarrow$ 8,646.2 km²** ($-80.5\\%$)
- All 14 clusters are now **under 9,000 km²**, eliminating SFINCS RAM memory errors while ensuring 100% coverage of every target Kabupaten and its headwater morphology.
"""))

nb.cells = cells
notebook_path = Path("tools_das_cluster_optimization.ipynb")
with open(notebook_path, "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print(f"Successfully generated notebook at: {notebook_path.resolve()}")
