#!/bin/bash

# Load environment variables from .env file if it exists
if [ -f "/workspace/.env" ]; then
    echo "Loading environment variables from /workspace/.env..."
    set -a  # Automatically export all variables
    source /workspace/.env
    set +a
else
    echo "No .env file found in /workspace. Skipping environment loading."
fi

# Conditionally install Decide tools
if [ -d "/workspace/decide" ]; then
    echo "Installing Decide tools from /workspace/decide..."
    /root/.local/bin/uv pip install -e /workspace/decide/
else
    echo "Decide directory not found. Skipping installation."
fi
# Fix versions at runtime
/root/.local/bin/uv pip install --force-reinstall numpy==1.26.4 pydicom==3.0.1

# Jupyter config (overwrite to avoid duplicates)
cat <<EOF > /root/.jupyter/jupyter_lab_config.py
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.allow_remote_access = True
c.ServerApp.token = '${JUPYTER_TOKEN}'
c.ServerApp.root_dir = '/workspace'
EOF

cd /workspace
exec jupyter lab --allow-root
