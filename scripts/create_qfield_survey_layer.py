"""
Create Standardized QField Flood Hazard Survey GeoPackage Layer using SQLite3
Author: Senior Geospatial Intelligence Expert
Project: West Sumatra Flood Hazard Mapping (SFINCS Ground Truth)
"""

import os
import sqlite3

def create_survey_gpkg(output_path="d:/Project/sumbar_flood_hazard/data/survey_flood_ground_truth.gpkg"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if os.path.exists(output_path):
        os.remove(output_path)
        
    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()
    
    # 1. Enable WAL and standard pragmas
    cursor.execute("PRAGMA application_id = 0x47504B47;")  # 'GPKG'
    cursor.execute("PRAGMA user_version = 10200;")         # Version 1.2.0
    
    # 2. Create gpkg_spatial_ref_sys
    cursor.execute("""
    CREATE TABLE gpkg_spatial_ref_sys (
        srs_name TEXT NOT NULL,
        srs_id INTEGER NOT NULL PRIMARY KEY,
        organization TEXT NOT NULL,
        organization_coordsys_id INTEGER NOT NULL,
        definition TEXT NOT NULL,
        description TEXT
    );
    """)
    
    # Insert WGS 84 (EPSG:4326) and Undefined
    cursor.execute("""
    INSERT INTO gpkg_spatial_ref_sys VALUES
    ('Undefined Cartesian', -1, 'NONE', -1, 'undefined', 'undefined cartesian coordinate reference system'),
    ('Undefined Geographic', 0, 'NONE', 0, 'undefined', 'undefined geographic coordinate reference system'),
    ('WGS 84', 4326, 'EPSG', 4326, 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","6326"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AXIS["Latitude",NORTH],AXIS["Longitude",EAST],AUTHORITY["EPSG","4326"]]', 'WGS 84 geographic coordinate reference system');
    """)
    
    # 3. Create gpkg_contents
    cursor.execute("""
    CREATE TABLE gpkg_contents (
        table_name TEXT NOT NULL PRIMARY KEY,
        data_type TEXT NOT NULL,
        identifier TEXT UNIQUE,
        description TEXT DEFAULT '',
        last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        min_x DOUBLE,
        min_y DOUBLE,
        max_x DOUBLE,
        max_y DOUBLE,
        srs_id INTEGER,
        CONSTRAINT fk_gc_r_srs_id FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id)
    );
    """)
    
    # 4. Create gpkg_geometry_columns
    cursor.execute("""
    CREATE TABLE gpkg_geometry_columns (
        table_name TEXT NOT NULL,
        column_name TEXT NOT NULL,
        geometry_type_name TEXT NOT NULL,
        srs_id INTEGER NOT NULL,
        z TINYINT NOT NULL,
        m TINYINT NOT NULL,
        CONSTRAINT pk_geom_cols PRIMARY KEY (table_name, column_name),
        CONSTRAINT fk_gc_tn FOREIGN KEY (table_name) REFERENCES gpkg_contents(table_name),
        CONSTRAINT fk_gc_srs_id FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id)
    );
    """)
    
    # 5. Create feature table: flood_hwm_survey
    cursor.execute("""
    CREATE TABLE flood_hwm_survey (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        geom POINT,
        surveyor_id TEXT,
        event_date TEXT,
        hwm_type TEXT,
        water_depth_cm REAL,
        ground_ref_type TEXT,
        floor_elevation_cm REAL,
        peak_time TEXT,
        flood_duration_hrs REAL,
        flow_source TEXT,
        land_cover_ground TEXT,
        flow_velocity_est TEXT,
        photo_hwm TEXT,
        interviewee_name_role TEXT,
        notes TEXT
    );
    """)
    
    # Register in gpkg_contents & gpkg_geometry_columns
    cursor.execute("""
    INSERT INTO gpkg_contents (table_name, data_type, identifier, description, srs_id)
    VALUES ('flood_hwm_survey', 'features', 'flood_hwm_survey', 'SFINCS 2D Flood Ground Truth Survey Layer', 4326);
    """)
    
    cursor.execute("""
    INSERT INTO gpkg_geometry_columns (table_name, column_name, geometry_type_name, srs_id, z, m)
    VALUES ('flood_hwm_survey', 'geom', 'POINT', 4326, 0, 0);
    """)
    
    conn.commit()
    conn.close()
    print(f"Successfully generated OGC GeoPackage at: {output_path}")

if __name__ == "__main__":
    create_survey_gpkg()
