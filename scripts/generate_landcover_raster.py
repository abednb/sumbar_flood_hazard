"""
generate_landcover_raster.py
============================
Generates an integer-coded, analysis-ready land-cover raster from the Badan Informasi
Geospasial (BIG) RBI vector dataset (data_raw/rbi/landcover.gpkg, layer lc_sumbar_lok26),
snapped to the regional DEM grid.

Also generates the companion integer lookup table (lookup_tables/manning_lookup.csv)
with Manning's roughness coefficient 'N' parameterized according to Chow (1959) and
Arcement & Schneider (1989).
"""

import argparse
import sys
import time
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize

# Import centralized environment
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))
import _env

TARGET_CRS = "EPSG:32747"

# Standard Manning n mapping based on Chow (1959) and Arcement & Schneider (1989)
# Macro-roughness for dense urban structures follows standard 2D flood practice (n = 0.120)
MANNING_BASE_MAP = {
    # Open water & Aquaculture
    "Waduk": (0.025, "Reservoir / Open Water"),
    "Danau/Situ": (0.025, "Natural Lake / Open Water"),
    "Laut": (0.020, "Sea / Coastal Open Water"),
    "Sungai": (0.030, "River Channel / Stream"),
    "Saluran Irigasi/Drainase": (0.025, "Irrigation / Drainage Channel"),
    "Kolam": (0.025, "Fish Pond"),
    "Kolam Air Budidaya": (0.025, "Aquaculture Pond"),
    "Empang": (0.025, "Freshwater Pond"),
    "Tambak": (0.030, "Brackish Water Fish/Shrimp Pond"),
    "Gosong Sungai": (0.030, "River Sandbar"),
    # Wetlands & Mangroves
    "Rawa": (0.080, "Freshwater Marsh / Swamp"),
    "Hutan Rawa/Gambut": (0.100, "Peat Swamp Forest"),
    "Hutan Bakau/Mangrove": (0.140, "Mangrove Forest"),
    # Bare ground & Coastal Sand
    "Pasir/Bukit Pasir Laut": (0.030, "Coastal Dune / Beach Sand"),
    "Pasir/Bukit Pasir Darat": (0.030, "Inland Sand / Bare Deposits"),
    "Tanah Kosong": (0.030, "Bare Soil / Vacant Land"),
    "Tanah Kosong/Gundul": (0.030, "Bare Ground / Degraded Land"),
    "Pertambangan Batu Bara": (0.035, "Coal Mining / Extraction Site"),
    # Grassland & Open Fields
    "Padang Rumput": (0.035, "Pasture / Natural Grassland"),
    "Rumput": (0.035, "Grassland"),
    "Lapangan": (0.035, "Open Field / Ground"),
    "Lapangan Sepakbola": (0.035, "Sports Field / Soccer Pitch"),
    # Agriculture
    "Sawah": (0.040, "Paddy Field / Lowland Agriculture"),
    "Tegalan/Ladang": (0.045, "Dryland Farm / Upland Cropland"),
    "Tanaman Campur": (0.055, "Mixed Crops / Agroforestry"),
    "Perkebunan": (0.060, "Estate Plantation"),
    "Perkebunan/Kebun": (0.060, "Smallholder Plantation / Orchard"),
    "Perkebunan Campuran": (0.060, "Mixed Tree Crops Plantation"),
    # Shrub & Secondary Vegetation
    "Semak Belukar": (0.070, "Shrubland / Dense Brush"),
    "Vegetasi Non Budidaya Lainnya": (0.070, "Other Natural Non-Cultivated Vegetation"),
    "Vegetasi Budidaya Lainnya": (0.055, "Other Cultivated Vegetation"),
    # Forests
    "Hutan": (0.120, "Forest"),
    "Hutan Rimba": (0.120, "Dense Natural Rain Forest"),
    "Hutan lahan tinggi primer kerapatan tinggi": (0.120, "Dense Primary Highland Rain Forest"),
    "Hutan Rakyat/Tanaman Campur": (0.090, "Community Forest / Agroforest"),
    "Hutan Tanaman Industri": (0.100, "Timber Plantation Forest"),
    # Transportation & Paved Infrastructure
    "Landas Pacu": (0.015, "Airport Runway (Paved Asphalt/Concrete)"),
    "Taxiway": (0.015, "Airport Taxiway (Paved)"),
    "Apron": (0.015, "Airport Apron (Paved)"),
    "Bandara": (0.030, "Airport Complex Ground"),
    "Dermaga": (0.020, "Pier / Harbor Wharf"),
    "Pelabuhan Antar Pulau": (0.050, "Inter-island Ferry Harbor Complex"),
    "Terminal Bus/Angkutan Kendaraan Lainnya": (0.040, "Bus / Transit Terminal"),
    # Built-up, Settlements & Commercial (Macro-roughness for 2D shallow water)
    "Permukiman dan Tempat Kegiatan": (0.120, "Settlement / Residential Area"),
    "Gedung/Bangunan": (0.120, "General Buildings"),
    "Bangunan Industri": (0.120, "Industrial Complex"),
    "Industri Manufaktur Lainnya": (0.120, "Manufacturing Industry"),
    "Industri Bahan Dasar Kimia": (0.120, "Chemical Basic Industry"),
    "Industri Bahan Pangan dan Makanan": (0.120, "Food & Beverage Processing Industry"),
    "Industri Sarana dan Bahan Perkantoran": (0.120, "Office Supply Industry"),
    "Pusat Bisnis dan Perdagangan Lainnya": (0.120, "Commercial & Business Center"),
    "Pusat Perdagangan dan Niaga Kota (Mal/Toserba)": (0.120, "Urban Commercial Center / Shopping Mall"),
    "Pusat Perdagangan Tradisional (Pasar Eceran/Grosir/Induk)": (0.120, "Traditional Market Complex"),
    "Pusat Pergudangan/Terminal Peti Kemas/Cargo": (0.100, "Warehouse / Container Cargo Terminal"),
    "Stasiun Pompa Bahan Bakar Umum": (0.080, "Gas Station (SPBU)"),
    # Public & Government Facilities
    "Kantor Gubernur": (0.120, "Governor's Office"),
    "Kantor Bupati": (0.120, "Regent's (Bupati) Office"),
    "Kantor Wali Kota": (0.120, "Mayor's Office"),
    "Kantor DPRD": (0.120, "Regional Parliament (DPRD) Office"),
    "Kantor Lembaga Negara": (0.120, "State Institution Office"),
    "Kantor Camat": (0.120, "District (Camat) Office"),
    "Kantor Lurah": (0.120, "Subdistrict (Lurah) Office"),
    "Kantor Kepala Desa": (0.120, "Village Head Office"),
    "Kantor Polisi": (0.120, "Police Station"),
    "Kantor Bank": (0.120, "Banking Institution"),
    "Kantor PLN": (0.120, "State Electricity (PLN) Office"),
    "Kantor PAM": (0.120, "Water Utility (PAM) Office"),
    "Kantor Televisi": (0.120, "Television Station"),
    "Kantor Pemerintah Lainnya": (0.120, "Other Government Offices"),
    "Lembaga Pemasyarakatan": (0.120, "Correctional Institution / Prison"),
    "Instalasi TNI (AD/AL/AU)": (0.120, "Military Installation"),
    # Healthcare
    "Rumah Sakit Umum": (0.120, "General Hospital"),
    "Rumah Sakit Khusus": (0.120, "Specialized Hospital"),
    "Puskesmas/Puskesmas Pembantu": (0.120, "Public Health Center (Puskesmas)"),
    # Education & Religious Facilities
    "Pendidikan Anak Usia Dini": (0.120, "Early Childhood Education"),
    "Pendidikan Dasar": (0.120, "Primary School (SD)"),
    "Pendidikan Menengah Pertama": (0.120, "Junior High School (SMP)"),
    "Pendidikan Menengah Umum": (0.120, "Senior High School (SMA)"),
    "Pendidikan Menengah Kejuruan": (0.120, "Vocational High School (SMK)"),
    "Pendidikan Tinggi": (0.120, "University / College"),
    "Pendidikan Keagamaan": (0.120, "Religious School / Madrasah / Pesantren"),
    "Pendidikan Khusus": (0.120, "Special Education School"),
    "Masjid": (0.120, "Mosque"),
    "Gereja": (0.120, "Church"),
    "Vihara": (0.120, "Buddhist Temple (Vihara)"),
    "Rumah Panti Asuhan Anak Yatim Piatu": (0.120, "Orphanage"),
    # Utilities & Energy
    "Gardu Induk Tegangan Ekstra Tinggi": (0.080, "High-Voltage Electrical Substation"),
    "Menara Telepon": (0.050, "Telecommunication Tower"),
    "Pembangkit Listrik Tenaga Air": (0.050, "Hydroelectric Power Plant (PLTA)"),
    "Pembangkit Listrik Tenaga Gas": (0.080, "Gas-Fired Power Plant (PLTG)"),
    "Pengolahan Bahan Bakar Gas": (0.080, "Gas Fuel Processing Plant"),
    # Recreation & Cemeteries
    "Pariwisata/Rekreasi Pantai": (0.040, "Coastal Tourism / Recreation Area"),
    "Pariwisata/Seni/Budaya/Olah Raga Lainnya": (0.060, "Cultural / Sports Tourism Area"),
    "Stadion/Tribun/Bangunan Olah Raga": (0.080, "Stadium / Sports Arena"),
    "Pemakaman Umum": (0.040, "Public Cemetery"),
    "Makam": (0.040, "Cemetery / Gravesite"),
}

# Synonyms and typo normalizations in raw RBI data
SYNONYM_MAP = {
    "Tagalan/Ladang": "Tegalan/Ladang",
    "PUSKESMAS": "Puskesmas/Puskesmas Pembantu",
    "SARANAIBADAH": "Masjid",
    "ARENAOLAHRAGA": "Stadion/Tribun/Bangunan Olah Raga",
}


def build_manning_lookup_table(
    unique_classes: list,
    out_csv: Path,
) -> tuple[dict, pd.DataFrame]:
    """
    Builds the integer-keyed Manning roughness lookup table and saves to CSV.
    Ensures column 'N' exists as expected by HydroMT-SFINCS.
    """
    rows = []
    # Row 0: Explicit Nodata / Unclassified
    rows.append({
        "rbi_id": 0,
        "rbi_class_name": "Nodata / Unclassified",
        "N": 0.040,
        "description": "Default floodplain / unclassified surface (Chow 1959)",
    })

    class_to_id = {}
    for idx, raw_name in enumerate(sorted(unique_classes), start=1):
        clean_name = SYNONYM_MAP.get(raw_name, raw_name)
        if clean_name in MANNING_BASE_MAP:
            n_val, desc = MANNING_BASE_MAP[clean_name]
        else:
            n_val, desc = 0.050, f"Unspecified vegetative cover: {clean_name}"

        class_to_id[raw_name] = idx
        rows.append({
            "rbi_id": idx,
            "rbi_class_name": clean_name,
            "N": round(n_val, 4),
            "description": desc,
        })

    df = pd.DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"[OK] Generated Manning lookup table with {len(df)} rows at: {out_csv}")
    return class_to_id, df


def generate_landcover_raster(
    rbi_gpkg: str = "data_raw/rbi/landcover.gpkg",
    layer: str = "lc_sumbar_lok26",
    ref_dem: str = "data/fabdem_reprojected.tif",
    out_raster: str = "data/landcover_rbi.tif",
    out_lookup: str = "lookup_tables/manning_lookup.csv",
    resolution: float = 30.0,
) -> Path:
    """
    Rasterizes the vector RBI land cover onto a regular grid snapped to the reference DEM.
    """
    t_start = time.time()
    rbi_path = Path(rbi_gpkg).resolve()
    dem_path = Path(ref_dem).resolve()
    out_raster_path = Path(out_raster).resolve()
    out_lookup_path = Path(out_lookup).resolve()

    if not rbi_path.exists():
        raise FileNotFoundError(f"RBI landcover vector not found at {rbi_path}")
    if not dem_path.exists():
        raise FileNotFoundError(f"Reference DEM not found at {dem_path}")

    print(f"=== Generating Harmonized RBI Land-Cover Raster ({resolution}m) ===")
    print(f"Loading vector layer '{layer}' from {rbi_path}...")
    gdf = gpd.read_file(rbi_path, layer=layer)
    if str(gdf.crs) != TARGET_CRS:
        print(f"Reprojecting RBI layer from {gdf.crs} to {TARGET_CRS}...")
        gdf = gdf.to_crs(TARGET_CRS)

    # Clean classes and build integer ID lookup
    unique_raw_classes = sorted(gdf["REMARK"].dropna().unique().tolist())
    print(f"Found {len(unique_raw_classes)} unique land cover classes in raw RBI layer.")
    class_to_id, lookup_df = build_manning_lookup_table(unique_raw_classes, out_lookup_path)

    gdf["rbi_id"] = gdf["REMARK"].map(class_to_id).fillna(0).astype("uint8")

    # Compute target raster grid aligned and snapped to DEM bounds
    with rasterio.open(dem_path) as src_dem:
        dem_bounds = src_dem.bounds

    minx = dem_bounds.left
    maxy = dem_bounds.top
    maxx = minx + np.ceil((dem_bounds.right - minx) / resolution) * resolution
    miny = maxy - np.ceil((maxy - dem_bounds.bottom) / resolution) * resolution
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)
    transform = rasterio.transform.from_bounds(minx, miny, maxx, maxy, width, height)

    print(f"Target grid: {width} x {height} cells @ {resolution}m ({TARGET_CRS})")
    print(f"Rasterizing {len(gdf)} features...")

    shapes = ((geom, val) for geom, val in zip(gdf.geometry, gdf["rbi_id"]) if geom is not None and not geom.is_empty)
    raster_data = rasterize(
        shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype="uint8",
    )

    unq_vals = np.unique(raster_data)
    print(f"Rasterization completed in {time.time() - t_start:.1f}s. Unique raster IDs: {len(unq_vals)}")

    out_raster_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "nodata": 0,
        "width": width,
        "height": height,
        "count": 1,
        "crs": TARGET_CRS,
        "transform": transform,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "compress": "lzw",
        "BIGTIFF": "YES",
    }

    with rasterio.open(out_raster_path, "w", **profile) as dst:
        dst.write(raster_data, 1)
        dst.set_band_description(1, "BIG RBI Land Cover Integer Class ID (Sumatera Barat)")

    print(f"[OK] GeoTIFF written successfully to: {out_raster_path}")
    return out_raster_path


def main():
    parser = argparse.ArgumentParser(description="Rasterize BIG RBI land cover and create Manning lookup table.")
    parser.add_argument("--rbi", default="data_raw/rbi/landcover.gpkg", help="Path to RBI landcover GPKG")
    parser.add_argument("--layer", default="lc_sumbar_lok26", help="Layer name in GPKG")
    parser.add_argument("--dem", default="data/fabdem_reprojected.tif", help="Reference DEM for spatial bounds")
    parser.add_argument("--out-raster", default="data/landcover_rbi.tif", help="Output GeoTIFF path")
    parser.add_argument("--out-lookup", default="lookup_tables/manning_lookup.csv", help="Output lookup CSV path")
    parser.add_argument("--res", type=float, default=30.0, help="Grid resolution in meters (default: 30m)")
    args = parser.parse_args()

    generate_landcover_raster(
        rbi_gpkg=args.rbi,
        layer=args.layer,
        ref_dem=args.dem,
        out_raster=args.out_raster,
        out_lookup=args.out_lookup,
        resolution=args.res,
    )


if __name__ == "__main__":
    main()
