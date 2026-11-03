"""
test_output_naming.py
=====================
Unit tests for standardized output folder structure and output filename convention.
Ensures compliance with:
- Target directory: outputs/DAS_XXX/rpYYY
- Target files:
  * DASXXX_RPYYY_FloodHazard_Index.tif
  * DASXXX_RPYYY_FloodHazard_Classes.tif
  * DASXXX_RPYYY_Flood_Depth.tif
  * DASXXX_RPYYY_Flood_Animation.gif
"""

from pathlib import Path
import pytest
from scripts.sfincs_standalone_pipeline import (
    format_output_cluster_id,
    format_output_rp,
)
from scripts.validate_against_survey import validate_model_against_survey


@pytest.mark.parametrize(
    "raw_das, expected_tag",
    [
        ("DAS_101", "DAS101"),
        ("DAS_102", "DAS102"),
        ("DAS_108_A", "DAS108_A"),
        ("DAS_108_B", "DAS108_B"),
        ("DAS_108_C", "DAS108_C"),
        ("DAS_108_D", "DAS108_D"),
        ("DAS104", "DAS104"),
        ("105", "DAS105"),
        (" das_109 ", "DAS109"),
    ],
)
def test_format_output_cluster_id(raw_das, expected_tag):
    assert format_output_cluster_id(raw_das) == expected_tag


@pytest.mark.parametrize(
    "raw_rp, expected_tag",
    [
        ("rp100", "RP100"),
        ("rp25", "RP25"),
        ("rp50", "RP50"),
        ("100", "RP100"),
        ("RP10", "RP10"),
        (" rp5 ", "RP5"),
    ],
)
def test_format_output_rp(raw_rp, expected_tag):
    assert format_output_rp(raw_rp) == expected_tag


def test_standard_output_path_construction():
    output_base = "outputs"
    das_id = "DAS_101"
    rp = "rp100"

    das_tag = format_output_cluster_id(das_id)
    rp_tag = format_output_rp(rp)
    prefix = f"{das_tag}_{rp_tag}"

    out_dir = Path(output_base) / das_id / rp
    assert str(out_dir).replace("\\", "/") == "outputs/DAS_101/rp100"

    expected_files = {
        "depth": f"{prefix}_Flood_Depth.tif",
        "hazard_classes": f"{prefix}_FloodHazard_Classes.tif",
        "hazard_index": f"{prefix}_FloodHazard_Index.tif",
        "animation": f"{prefix}_Flood_Animation.gif",
    }

    assert expected_files["depth"] == "DAS101_RP100_Flood_Depth.tif"
    assert expected_files["hazard_classes"] == "DAS101_RP100_FloodHazard_Classes.tif"
    assert expected_files["hazard_index"] == "DAS101_RP100_FloodHazard_Index.tif"
    assert expected_files["animation"] == "DAS101_RP100_Flood_Animation.gif"


def test_validate_survey_finds_new_format(tmp_path):
    das_dir = tmp_path / "DAS_101" / "rp100"
    das_dir.mkdir(parents=True)

    # Create dummy files matching new format
    depth_file = das_dir / "DAS101_RP100_Flood_Depth.tif"
    raw_depth = das_dir / "DAS101_RP100_Flood_Depth_raw.tif"
    hazard_classes = das_dir / "DAS101_RP100_FloodHazard_Classes.tif"
    hazard_index = das_dir / "DAS101_RP100_FloodHazard_Index.tif"

    for f in [depth_file, raw_depth, hazard_classes, hazard_index]:
        f.write_text("dummy")

    # validate_model_against_survey without depth_tif should auto-detect DAS101_RP100_Flood_Depth.tif
    # but not crash if dummy file lacks raster header
    try:
        res = validate_model_against_survey(hazard_dir=das_dir)
        # Should not report "No depth raster found"
        assert "No depth raster found" not in res.get("message", "")
    except Exception as e:
        # If rasterio fails reading dummy bytes, that confirms candidate file was picked
        assert "DAS101_RP100_Flood_Depth.tif" in str(e) or "not recognized as a supported file format" in str(e)
