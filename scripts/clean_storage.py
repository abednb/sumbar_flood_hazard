"""
clean_storage.py
================
Safe workspace & geospatial cache cleaner for the HydroMT-SFINCS Flood Hazard Pipeline.
Reclaims disk space on both workspace (D:) and system temp/uv cache (C:) without touching
authoritative inputs, raw datasets, or final hazard deliverables.

Usage:
    .\.venv\Scripts\python.exe scripts/clean_storage.py --dry-run
    .\.venv\Scripts\python.exe scripts/clean_storage.py
    .\.venv\Scripts\python.exe scripts/clean_storage.py --include-temp-chips --include-user-temp
"""

import argparse
import os
import shutil
from pathlib import Path
from typing import List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def find_cleanup_targets(
    include_temp_chips: bool = False,
    include_user_temp: bool = False,
    include_models: bool = False,
) -> List[Tuple[Path, str]]:
    """Collects safe cleanup targets with human-readable reasons."""
    targets: List[Tuple[Path, str]] = []

    # 1. Python bytecode, pytest cache, notebook checkpoints (inside repo, excluding .venv/.git)
    for pattern, label in [
        ("__pycache__", "Python bytecode cache"),
        (".pytest_cache", "Pytest cache"),
        (".ruff_cache", "Ruff cache"),
        (".ipynb_checkpoints", "Jupyter checkpoints"),
    ]:
        for p in ROOT_DIR.rglob(pattern):
            if any(part == ".venv" or part == ".git" or part.startswith("env-") for part in p.parts):
                continue
            targets.append((p, label))

    # 2. Stray root logs
    for log_f in ROOT_DIR.glob("*.log"):
        targets.append((log_f, "Stray root log file"))

    # 3. Temporary DEM chips (regenerated automatically on demand)
    if include_temp_chips:
        chips_dir = ROOT_DIR / "temp" / "chips"
        if chips_dir.exists():
            targets.append((chips_dir, "Cached per-DAS DEM chips (auto-regenerated)"))

    # 4. Old SFINCS model build/run folders (explicit opt-in only!)
    if include_models:
        models_dir = ROOT_DIR / "models_sfincs_standalone"
        if models_dir.exists():
            for sub in models_dir.iterdir():
                if sub.is_dir():
                    targets.append((sub, "SFINCS model build/run directory"))

    # 5. User Windows Temp geospatial dump files (C:\Users\...\AppData\Local\Temp)
    if include_user_temp:
        tmp_root = Path(os.environ.get("TEMP", ""))
        if tmp_root.exists():
            for glob_pat in ["tmp*.tif", "gdal*", "rasterio*", "dask*", "hydromt*"]:
                for p in tmp_root.glob(glob_pat):
                    targets.append((p, "Windows Temp geospatial scratch file"))

    # Deduplicate while preserving order
    seen = set()
    unique_targets = []
    for p, reason in targets:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            unique_targets.append((p, reason))
    return unique_targets


def run_cleanup(
    dry_run: bool = False,
    include_temp_chips: bool = False,
    include_user_temp: bool = False,
    include_models: bool = False,
) -> float:
    targets = find_cleanup_targets(
        include_temp_chips=include_temp_chips,
        include_user_temp=include_user_temp,
        include_models=include_models,
    )

    total_bytes = 0
    mode_tag = "DRY-RUN" if dry_run else "CLEAN"
    print(f"=== Storage Cache Cleaner ({mode_tag}) ===")
    if not targets:
        print("Workspace is already clean! 0 MB to reclaim.")
        return 0.0

    for path, reason in targets:
        sz = _dir_size_bytes(path)
        total_bytes += sz
        sz_mb = sz / (1024 * 1024)
        rel = path.relative_to(ROOT_DIR) if str(path.resolve()).startswith(str(ROOT_DIR)) else path
        print(f"  [{mode_tag}] {rel} ({sz_mb:.2f} MB) — {reason}")
        if not dry_run:
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=False)
                elif path.exists():
                    path.unlink()
            except Exception as e:
                print(f"    [WARN] Skipped {rel}: {e}")

    total_mb = total_bytes / (1024 * 1024)
    print(f"\nTotal {'reclaimable' if dry_run else 'reclaimed'}: {total_mb:.2f} MB ({total_mb/1024:.2f} GB)")
    return total_mb


def main():
    parser = argparse.ArgumentParser(description="Clean temporary caches and geospatial scratch artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Report reclaimable space without deleting anything.")
    parser.add_argument("--include-temp-chips", action="store_true", help="Also delete cached temp/chips/ DEM chips.")
    parser.add_argument("--include-user-temp", action="store_true", help="Also purge geospatial dumps from Windows %TEMP%.")
    parser.add_argument("--include-models", action="store_true", help="Also purge models_sfincs_standalone/ runs (use after finalizing outputs!).")
    args = parser.parse_args()

    run_cleanup(
        dry_run=args.dry_run,
        include_temp_chips=args.include_temp_chips,
        include_user_temp=args.include_user_temp,
        include_models=args.include_models,
    )


if __name__ == "__main__":
    main()
