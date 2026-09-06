#!/usr/bin/env bash
# Sets up the SFINCS build/run/postprocess environment (hydromt core <0.10).
# Run from the repository root: bash env/setup_env_sfincs.sh
set -euo pipefail

uv venv env-sfincs --python 3.12
source env-sfincs/bin/activate
uv pip install "hydromt_sfincs==1.2.2" jupyterlab ipykernel rioxarray xugrid
python -m ipykernel install --user --name hydromt-sfincs --display-name "HydroMT-SFINCS"

echo ""
echo "=== Verifying plugin registration (expect 'sfincs' under Model plugins) ==="
hydromt --plugins

deactivate
echo ""
echo "env-sfincs ready. In Jupyter, select kernel 'HydroMT-SFINCS' for 02_sfincs_build_run.ipynb"
echo ""
echo "IMPORTANT: never 'uv pip install hydromt_wflow' into this same venv -- it"
echo "requires a different hydromt core major version and will break this env."
