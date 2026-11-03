"""
Update master notebooks and reference cluster notebooks to support:
- Extended duration (storm_hours=24, recession_hours=48 -> 72h)
- Perka BNPB classification method (default: "depth")
- Cosmetic flag (default: False for official products)
- QA checks (qa_checks.run_all_qa)
- Ground-truth survey validation (validate_against_survey.validate_model_against_survey)
"""

import json
from pathlib import Path

def update_notebook(nb_path: Path):
    print(f"Updating {nb_path}...")
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    
    for i, cell in enumerate(nb["cells"]):
        src = "".join(cell.get("source", []))
        # 1. Update User Configuration Control Panel (Cell 2)
        if "SELECTED_CLUSTERS =" in src and "OUTPUT_MODELS_DIR =" in src:
            if 'OUTPUT_MAPS_DIR = "outputs_standalone"' in src:
                src = src.replace('OUTPUT_MAPS_DIR = "outputs_standalone"', 'OUTPUT_MAPS_DIR = "outputs"')
                cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
                print(f"  Updated Cell {i} (OUTPUT_MAPS_DIR -> outputs)")

            if 'DAS_CLUSTERS_GPKG = "data/das_clusters.gpkg"' in src:
                src = src.replace('DAS_CLUSTERS_GPKG = "data/das_clusters.gpkg"', 'DAS_CLUSTERS_GPKG = "data/das_clusters/sumbar_das_cluster.gpkg"')
                cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
                print(f"  Updated Cell {i} (Cluster Boundary Path -> sumbar_das_cluster.gpkg)")
            elif 'DAS_CLUSTERS_GPKG = "data/modified_das_cluster/smaller_das_cluster.gpkg"' in src:
                src = src.replace('DAS_CLUSTERS_GPKG = "data/modified_das_cluster/smaller_das_cluster.gpkg"', 'DAS_CLUSTERS_GPKG = "data/das_clusters/sumbar_das_cluster.gpkg"')
                cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
                print(f"  Updated Cell {i} (Cluster Boundary Path -> sumbar_das_cluster.gpkg)")

            if "STORM_HOURS =" not in src:
                # Add parameters
                addition = (
                    "\n# ==============================================================================\n"
                    "# 4. HYDRODYNAMIC & POST-PROCESSING REMEDIATION PARAMETERS\n"
                    "# ==============================================================================\n"
                    "STORM_HOURS = 24            # Rainfall event duration (hours)\n"
                    "RECESSION_HOURS = 12        # Catchment drain-down recession duration (hours) -> Total 36h\n"
                    "CLASSIFICATION_METHOD = 'depth'  # 'depth' (official Perka BNPB No. 02/2012) or 'fuzzy'\n"
                    "COSMETIC = False            # False preserves raw hydrodynamic depths; True generates display map\n"
                )
                print_addition = (
                    "print(f\"⏱️ Simulation Timeline     : {STORM_HOURS}h storm + {RECESSION_HOURS}h recession = {STORM_HOURS + RECESSION_HOURS}h total\")\n"
                    "print(f\"🏷️ Classification Method  : {CLASSIFICATION_METHOD.upper()} (Perka BNPB No. 02/2012)\")\n"
                    "print(f\"🎨 Cosmetic Filtering     : {COSMETIC}\")\n"
                )
                # Insert before the last prints
                if 'print(f"🎯 Active Target Clusters' in src:
                    idx = src.find('print(f"🎯 Active Target Clusters')
                    new_src = src[:idx] + addition + "\n" + src[idx:] + print_addition
                else:
                    new_src = src + addition + print_addition
                cell["source"] = [line + "\n" for line in new_src.split("\n")[:-1]] + [new_src.split("\n")[-1]]
                print(f"  Updated Cell {i} (Configuration Panel)")
            elif "RECESSION_HOURS = 48" in src:
                new_src = src.replace("RECESSION_HOURS = 48", "RECESSION_HOURS = 12").replace("Total 72h", "Total 36h")
                cell["source"] = [line + "\n" for line in new_src.split("\n")[:-1]] + [new_src.split("\n")[-1]]
                print(f"  Updated Cell {i} (Configuration Panel -> 36h)")

        # 2. Update Environment Initialization (Cell 4)
        if "from sfincs_standalone_pipeline import" in src and "run_all_qa" not in src:
            new_src = src.replace(
                "from sfincs_standalone_pipeline import (\n    build_sfincs_standalone,\n    prepare_sfincs_direct_rain_forcing,\n    run_sfincs_model,\n    postprocess_sfincs_hazard,\n    create_sfincs_flood_animation,\n)",
                "from sfincs_standalone_pipeline import (\n    build_sfincs_standalone,\n    prepare_sfincs_direct_rain_forcing,\n    run_sfincs_model,\n    postprocess_sfincs_hazard,\n    create_sfincs_flood_animation,\n)\nfrom qa_checks import run_all_qa\nfrom validate_against_survey import validate_model_against_survey"
            )
            cell["source"] = [line + "\n" for line in new_src.split("\n")[:-1]] + [new_src.split("\n")[-1]]
            print(f"  Updated Cell {i} (Environment & QA Imports)")

        # 3. Update Forcing Preparation (Cell 8)
        if "prepare_sfincs_direct_rain_forcing(" in src and "storm_hours=" not in src:
            new_src = src.replace(
                "        bws_inflow_hydrographs=BWS_INFLOW_HYDROGRAPHS,\n    )",
                "        bws_inflow_hydrographs=BWS_INFLOW_HYDROGRAPHS,\n        storm_hours=STORM_HOURS,\n        recession_hours=RECESSION_HOURS,\n    )"
            )
            cell["source"] = [line + "\n" for line in new_src.split("\n")[:-1]] + [new_src.split("\n")[-1]]
            print(f"  Updated Cell {i} (Forcing Timeline)")

        # 4. Update Post-processing & QA (Cell 12)
        if "postprocess_sfincs_hazard(" in src and "classification_method=" not in src:
            replacement = (
                "        postprocess_sfincs_hazard(\n"
                "            das_id=das_id,\n"
                "            rp=rp,\n"
                "            base_model_dir=OUTPUT_MODELS_DIR,\n"
                "            output_maps_dir=OUTPUT_MAPS_DIR,\n"
                "            hmin=0.05,\n"
                "            classification_method=CLASSIFICATION_METHOD,\n"
                "            cosmetic=COSMETIC,\n"
                "        )\n"
                "        # Execute Build-time & Simulation QA Gates\n"
                "        model_dir = Path(OUTPUT_MODELS_DIR) / f\"{das_id}_{rp}\"\n"
                "        qa_report_path = Path(OUTPUT_MAPS_DIR) / das_id / rp / \"qa_report.json\"\n"
                "        print(f\"\\n🔍 [QA QC] Running automated quality gates for {das_id} {rp}...\")\n"
                "        qa_results = run_all_qa(model_dir, out_json=qa_report_path)\n"
                "        \n"
                "        # Execute Ground-truth Survey Validation (QField)\n"
                "        val_results = validate_model_against_survey(\n"
                "            hazard_dir=Path(OUTPUT_MAPS_DIR) / das_id / rp,\n"
                "            survey_path=\"data/qfield_result\",\n"
                "            das_clusters_path=DAS_CLUSTERS_GPKG if 'DAS_CLUSTERS_GPKG' in locals() else 'data/das_clusters.gpkg',\n"
                "            das_id=das_id,\n"
                "        )"
            )
            new_src = src.replace(
                "        postprocess_sfincs_hazard(\n            das_id=das_id,\n            rp=rp,\n            base_model_dir=OUTPUT_MODELS_DIR,\n            output_maps_dir=OUTPUT_MAPS_DIR,\n            hmin=0.05,\n        )",
                replacement
            )
            cell["source"] = [line + "\n" for line in new_src.split("\n")[:-1]] + [new_src.split("\n")[-1]]
            print(f"  Updated Cell {i} (Post-processing & QA/Validation)")

        if "output_report=qa_report_path" in src:
            src = src.replace("output_report=qa_report_path", "out_json=qa_report_path")
            cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
            print(f"  Updated Cell {i} (run_all_qa out_json parameter)")

        # 5. Update Visualization Cartography (Cell 14)
        if "from matplotlib.colors import ListedColormap, BoundaryNorm" in src:
            src = src.replace(
                "from matplotlib.colors import ListedColormap, BoundaryNorm",
                "from matplotlib.colors import ListedColormap, LinearSegmentedColormap, BoundaryNorm"
            )
            cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]

        if 'cmap="YlOrRd"' in src:
            src = src.replace('cmap="YlOrRd"', 'cmap=cmap_fhi')
            if 'cmap_fhi =' not in src:
                src = src.replace(
                    '    # 2. Continuous Flood Hazard Index (Fuzzy Large: 0 to 1)\n    if fhi_path.exists():\n        with rasterio.open(fhi_path) as src_f:\n            fhi_data = src_f.read(1)\n',
                    '    # 2. Continuous Flood Hazard Index (Fuzzy Large: 0 to 1)\n    # Cartographic continuous ramp: Rendah (#34A853) -> Sedang (#FBBC05) -> Tinggi (#EA4335)\n    cmap_fhi = LinearSegmentedColormap.from_list("fhi_continuous", ["#34A853", "#FBBC05", "#EA4335"])\n    if fhi_path.exists():\n        with rasterio.open(fhi_path) as src_f:\n            fhi_data = src_f.read(1)\n'
                )
            cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
            print(f"  Updated Cell {i} (Continuous FHI Color Ramp)")

        if 'ListedColormap(["#FFFF00", "#FFA500", "#FF0000"])' in src:
            src = src.replace(
                'ListedColormap(["#FFFF00", "#FFA500", "#FF0000"])  # Rendah (Yellow), Sedang (Orange), Tinggi (Red)',
                'ListedColormap(["#34A853", "#FBBC05", "#EA4335"])  # Rendah (#34A853), Sedang (#FBBC05), Tinggi (#EA4335)'
            )
            cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
            print(f"  Updated Cell {i} (Discrete BNPB Hazard Colors)")

        if 'cbar.ax.set_yticklabels(["Rendah (FHI <= 0.333)"' in src:
            src = src.replace(
                'cbar.ax.set_yticklabels(["Rendah (FHI <= 0.333)", "Sedang (0.333 - 0.666)", "Tinggi (FHI > 0.666)"])',
                'cbar.ax.set_yticklabels(["Rendah (h < 0.76 m)", "Sedang (0.76 - 1.50 m)", "Tinggi (h > 1.50 m)"])'
            )
            cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
            print(f"  Updated Cell {i} (BNPB Map Legend)")

        if 'depth_path = Path(OUTPUT_MAPS_DIR) / PLOT_DAS / PLOT_RP / "flood_depth_10m.tif"' in src:
            old_block = (
                'depth_path = Path(OUTPUT_MAPS_DIR) / PLOT_DAS / PLOT_RP / "flood_depth_10m.tif"\n'
                'fhi_path = Path(OUTPUT_MAPS_DIR) / PLOT_DAS / PLOT_RP / "flood_hazard_index.tif"\n'
                'hazard_path = Path(OUTPUT_MAPS_DIR) / PLOT_DAS / PLOT_RP / "hazard_class_perka2012.tif"'
            )
            new_block = (
                'das_tag = "DAS" + PLOT_DAS[4:] if PLOT_DAS.upper().startswith("DAS_") else (PLOT_DAS.upper() if PLOT_DAS.upper().startswith("DAS") else f"DAS{PLOT_DAS}")\n'
                'rp_tag = f"RP{PLOT_RP[2:]}" if PLOT_RP.lower().startswith("rp") else f"RP{PLOT_RP}"\n'
                'prefix = f"{das_tag}_{rp_tag}"\n'
                'plot_dir = Path(OUTPUT_MAPS_DIR) / PLOT_DAS / PLOT_RP\n'
                'depth_path = plot_dir / f"{prefix}_Flood_Depth.tif"\n'
                'if not depth_path.exists():\n'
                '    depth_path = plot_dir / "flood_depth_10m.tif"\n'
                'fhi_path = plot_dir / f"{prefix}_FloodHazard_Index.tif"\n'
                'if not fhi_path.exists():\n'
                '    fhi_path = plot_dir / "flood_hazard_index.tif"\n'
                'hazard_path = plot_dir / f"{prefix}_FloodHazard_Classes.tif"\n'
                'if not hazard_path.exists():\n'
                '    hazard_path = plot_dir / "hazard_class_perka2012.tif"'
            )
            src = src.replace(old_block, new_block)
            cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
            print(f"  Updated Cell {i} (Standardized Output Map File Paths)")

        # 6. Update Animation Call (Cell 16)
        if 'das_clusters_gpkg="data/das_clusters.gpkg"' in src:
            src = src.replace('das_clusters_gpkg="data/das_clusters.gpkg"', 'das_clusters_gpkg=DAS_CLUSTERS_GPKG')
            cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
            print(f"  Updated Cell {i} (Animation Cluster Boundary Path)")
        elif 'das_clusters_gpkg="data/modified_das_cluster/smaller_das_cluster.gpkg"' in src:
            src = src.replace('das_clusters_gpkg="data/modified_das_cluster/smaller_das_cluster.gpkg"', 'das_clusters_gpkg=DAS_CLUSTERS_GPKG')
            cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
            print(f"  Updated Cell {i} (Animation Cluster Boundary Path)")

        # 7. Update Animation Markdown Description (Cell 15)
        if "24-Hour Flood Wave Propagation Animation" in src:
            src = src.replace("24-Hour Flood Wave Propagation Animation", "36-Hour Flood Wave Propagation Animation")
            src = src.replace("flood_propagation_24h.gif", "DASXXX_RPYYY_Flood_Animation.gif")
            cell["source"] = [line + "\n" for line in src.split("\n")[:-1]] + [src.split("\n")[-1]]
            print(f"  Updated Cell {i} (Animation Markdown Header)")

    nb_path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Done updating {nb_path}\n")

if __name__ == "__main__":
    targets = sorted(list(Path("notebook").rglob("*.ipynb")))
    for target in targets:
        if target.exists() and "00_data_preparation" not in target.name:
            update_notebook(target)
