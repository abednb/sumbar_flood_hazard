"""
Pytest configuration and environment bootstrap.
Initializes PROJ_DATA, GDAL_DATA, and PATH from scripts._env to isolate
from any external PostgreSQL/PostGIS or OSGeo4W installations.
"""

import scripts._env  # noqa: F401
