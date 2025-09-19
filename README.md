# DECIDE Docker

This repository contains scripts and configuration files to build and run a Docker container for image segmentation, post-editing, and (soon) anomaly detection as part of the **DECIDE** project.

---

## 🚀 Getting Started

### 1. Setup

- Clone or copy the `DecideDocker` repository to your working machine (local or cloud).
- Navigate into the `DecideDocker` directory:
```sh
cd DecideDocker
```
- Configure environment variables (or just set it in docker-compose.yml file):
  - Edit the `.env` file (make sure hidden files are visible in your system).
  - Alternatively, rename `default.env` to `.env`.

### 2. Run the Container

Use one of the following commands depending on your Docker version:

```sh
docker compose up -d
# or
sudo docker compose up -d
# or (for older versions)
docker-compose up -d
```

> 🔄 Please wait a few minutes after starting the container.
> The container performs runtime installations and builds (e.g., Plastimatch, Python packages, nnUNet patch) via the `startup.sh` script. This may take a few minutes depending on your system.

- Access JupyterLab at `http://<your_ip_address>:8888`
- Login using the configured token (default: `token123`)

To stop the container, use:

```sh
docker compose down
```

---

## 📁 Repository Structure

```
DecideDocker/
├── Dockerfile
├── docker-compose.yml
├── .env
├── startup.sh
├── workspace/
│   ├── decide/
│   │   ├── config/
│   │   │   └── config_total_segmentator.yaml
│   │   ├── logs/
│   │   ├── data/
│   │   ├── src/
│   │   │   └── decide/
│   │   └── pyproject.toml
│   └── notebooks/
└── nnUNet/
```

---

## 🛠 Dockerfile Overview

The Dockerfile uses a **multi-stage build**:

### Stage 1: JupyterLab Setup
- Base: `ubuntu:22.04`
- Installs latest JupyterLab and extensions

### Stage 2: DECIDE Environment
- Base: TotalSegmentator image
- Adds JupyterLab from Stage 1
- Installs:
  - **Plastimatch**
  - **PyRadiomics**
  - **nnUNet patch for Plastimatch**
  - **DECIDE tools** (including XNAT Python API)
- Resolves dependency issues
- Launches JupyterLab on port `8888`

---

## ⚙️ docker-compose.yml

Defines container behavior:

- Uses host IPC (required for nnUNet models)
- Enables GPU support
- Mounts `workspace/` directory for live sync between host and container

---
## 📜 startup.sh

The `startup.sh` script is executed when the container starts. It performs the following tasks:

- Builds and installs **Plastimatch** from source
- Installs required **Python packages** (e.g., PyRadiomics, Platipy)
- Applies a patch to **nnUNet** for compatibility
- Installs **DECIDE tools** if present in `/workspace/decide`
- Fixes specific package versions (e.g., `numpy`, `pydicom`)
- Registers the **Jupyter kernel**
- Configures and launches **JupyterLab** on port `8888`
## 🔐 .env File

Stores environment variables:

```env
JUPYTER_TOKEN=token123
```

---

## 📦 Workspace

- Mounted inside the container
- Contains all scripts, notebooks, and configurations
- `src/` includes Python packages for segmentation, post-editing, etc.

---

## 🧠 nnUNet Compatibility Fixes

### Common Errors

When installed platipy `platipy[nnunet]` or `platipy[cardiac]`  and deployed, encountered the error:

```text
UnpicklingError: Weights only load failed...
```

### Cause

PyTorch 2.6 changed the default `weights_only` argument in `torch.load` to `True`.

### Fix

1. Use nnUNet version `1.7.0`:
   ```sh
   git clone https://github.com/MIC-DKFZ/nnUNet.git
   cd nnUNet
   git checkout tags/v1.7.0 -b nnunet-1.7.0
   ```

2. Patch `model_restore.py`:

    ```python
    from torch.serialization import safe_globals
    import numpy

    with safe_globals([numpy.dtype]):
        all_params = [torch.load(i, map_location=torch.device('cpu'), weights_only=False) for i in all_best_model_files]
    ```

---

## 🧱 Architecture Comparison

### ARGOS-1

- Single Docker Compose managing XNAT, JupyterLab, and tools
- Adding new containers required editing XNAT's Docker Compose

    ![ARGOS Architecture](/images/argos_data_preprocessing.png)
---

### DECIDE

- Separation of data containers and tool containers
- No modification needed to data containers when adding/removing tools

    ![DECIDE Architecture](/images/decide_data_preprocessing.png)

## Test Data Attribution

This repository includes data derived from the NSCLC-Radiomics dataset available via the Imaging Data Commons (IDC).

Original dataset citation:
The Cancer Imaging Archive. https://www.cancerimagingarchive.net/collection/nsclc-radiomics/

License: CC BY-NC 3.0 — Non-commercial use only.