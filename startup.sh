#!/bin/bash

# Upgrade pip
python3 -m pip install --upgrade pip setuptools wheel

# Build Plastimatch
apt-get update && apt-get install -y cmake g++ libinsighttoolkit4-dev
git clone https://gitlab.com/plastimatch/plastimatch.git /opt/plastimatch
cd /opt/plastimatch && mkdir build && cd build
cmake .. && make -j$(nproc) && make install
ldconfig
apt-get purge -y cmake g++ && apt-get autoremove -y
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install Python packages
pip install --no-cache-dir \
    ipywidgets \
    git+https://github.com/AIM-Harvard/pyradiomics.git@master \
    platipy

# nnUNet patch
sed -i 's/"sklearn"/"scikit-learn"/g' /opt/nnUNet/setup.py
pip install --no-cache-dir /opt/nnUNet

# Conditionally install Decide tools
if [ -d "/workspace/decide" ]; then
    echo "Installing Decide tools from /workspace/decide..."
    pip install -e /workspace/decide/
else
    echo "Decide directory not found. Skipping installation."
fi

# Fix versions
pip install --force-reinstall --no-cache-dir numpy==1.26.4 pydicom==3.0.1

# Register kernel
pip install ipykernel
python3 -m ipykernel install --prefix=/usr/local --name "python3" --display-name "Python 3"

# Jupyter config
jupyter lab --generate-config
echo "c.ServerApp.ip = '0.0.0.0'" >> /root/.jupyter/jupyter_lab_config.py
echo "c.ServerApp.port = 8888" >> /root/.jupyter/jupyter_lab_config.py
echo "c.ServerApp.open_browser = False" >> /root/.jupyter/jupyter_lab_config.py
echo "c.ServerApp.allow_remote_access = True" >> /root/.jupyter/jupyter_lab_config.py
echo "c.ServerApp.token = '${JUPYTER_TOKEN}'" >> /root/.jupyter/jupyter_lab_config.py
echo "c.ServerApp.root_dir = '/workspace'" >> /root/.jupyter/jupyter_lab_config.py

# Start JupyterLab
cd /workspace
exec jupyter lab --allow-root
