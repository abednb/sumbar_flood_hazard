import os
import shutil
import nbformat
from pathlib import Path

# Base directories
dir_master = Path('notebook/master')
dir_sumbar = Path('notebook/sumbar2026')
dir_tools = Path('tools')

for d in [dir_master, dir_sumbar, dir_tools]:
    d.mkdir(parents=True, exist_ok=True)

# 1. Move 00, 01, 02 notebooks
for p in list(Path('.').glob('0[0-2]_*.ipynb')):
    dest = dir_master / p.name
    shutil.move(str(p), str(dest))
    print(f"Moved {p.name} -> {dest}")

# 2. Move Flood_Hazard notebooks
for p in list(Path('.').glob('Flood_Hazard_*.ipynb')):
    dest = dir_sumbar / p.name
    shutil.move(str(p), str(dest))
    print(f"Moved {p.name} -> {dest}")

# 3. Move tools notebooks
for p in list(Path('.').glob('tools_*.ipynb')):
    dest = dir_tools / p.name
    shutil.move(str(p), str(dest))
    print(f"Moved {p.name} -> {dest}")

# Ensure all notebooks have robust root CWD resolution so they run seamlessly in subfolders
def ensure_root_cwd(nb_path):
    with open(nb_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    
    modified = False
    for cell in nb.cells:
        if cell.cell_type == 'code':
            lines = cell.source.splitlines()
            if any('import sys' in l or 'import os' in l or 'import sfincs_standalone_pipeline' in l for l in lines):
                if 'project_root' not in cell.source:
                    prefix_code = [
                        "# Automatically set working directory to project root",
                        "from pathlib import Path",
                        "import os, sys",
                        "project_root = Path.cwd()",
                        "while not (project_root / 'data').exists() and project_root.parent != project_root:",
                        "    project_root = project_root.parent",
                        "os.chdir(project_root)",
                        "if str(project_root / 'scripts') not in sys.path:",
                        "    sys.path.insert(0, str(project_root / 'scripts'))",
                        "",
                    ]
                    cell.source = "\n".join(prefix_code) + "\n" + cell.source
                    modified = True
                break
    if modified:
        with open(nb_path, 'w', encoding='utf-8') as f:
            nbformat.write(nb, f)
        print(f"Updated root CWD handling in: {nb_path}")

for folder in [dir_master, dir_sumbar, dir_tools]:
    for nb_file in folder.glob('*.ipynb'):
        ensure_root_cwd(nb_file)

print("All notebooks organized and paths verified successfully!")
