# ================= STAGE 1: Build JupyterLab =================
FROM ubuntu:22.04 AS jupyterlab-builder

RUN apt-get update && apt-get install -y \
    curl git python3 python3-pip build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g yarn \
    && pip install --upgrade pip setuptools wheel

# Build JupyterLab
RUN git clone https://github.com/jupyterlab/jupyterlab.git /opt/jupyterlab \
    && cd /opt/jupyterlab \
    && pip install jupyter_packaging \
    && python3 -m pip install . \
    && jupyter lab build

# Add JupyterLab Language Server
RUN pip install jupyterlab-lsp python-lsp-server[all] \
    && jupyter labextension install @krassowski/jupyterlab-lsp

# ================= STAGE 2: Final Image =================
FROM wasserth/totalsegmentator:2.10.0

ENV JUPYTER_TOKEN=token123

# System dependencies
RUN apt-get update && apt-get install -y \
    dcmtk git libinsighttoolkit4.13 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy JupyterLab from builder
COPY --from=jupyterlab-builder /usr/local /usr/local
COPY --from=jupyterlab-builder /opt/jupyterlab /opt/jupyterlab

# Copy nnUNet (still needed at build time)
COPY nnUNet/ /opt/nnUNet/

# Copy startup script
COPY startup.sh /usr/local/bin/startup.sh
RUN chmod +x /usr/local/bin/startup.sh

# Working directory
WORKDIR /workspace
RUN mkdir -p /workspace

EXPOSE 8888
CMD ["/usr/local/bin/startup.sh"]
