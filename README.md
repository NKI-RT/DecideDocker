# DECIDE Docker

This repository contains scripts and configuration files to build and run a Docker container for image segmentation, post-editing, and (soon) anomaly detection as part of the **DECIDE** project.

---

## 🚀 Getting Started

### 1. Setup

- **Clone** the repository to your machine:
  ```sh
  git clone https://github.com/NKI-RT/DecideDocker.git
  ```
- **Navigate** into the directory:
  ```sh
  cd DecideDocker
  ```
- **Configure environment variables:**
  - Edit the `workspace/.env` file (make sure hidden files are visible).
  - Or, rename `default.env` to `.env`.

### 2. Run the Container

```sh
sudo docker compose up -d
```

> 🔄 **Note:**  
> The container will perform runtime installations and builds via the `startup.sh` script. This may take a few minutes.

- **Access JupyterLab:**  
  Open http://<your_ip_address>:8888 in your browser.
- **Login Token:**  
  Use the configured token (default: `token123`).

To **stop** the container:
```sh
sudo docker compose down
```

---
## ☁️ Cloud Compute Deployment (ARGOS-1 Architecture)

If you're using **cloud computing** and your **virtual machine's IP address is not public**, follow these steps to deploy **XNAT** and **Decide** together using a shared proxy network.

### 📦 Setup Instructions

1. **Stop the existing XNAT container**:
   ```sh
   cd xnat-docker-compose
   ```
   ```sh
   sudo docker compose down
   ```
   
2. **Download this repository** into the same directory.:
   ```sh
   git clone https://github.com/NKI-RT/DecideDocker.git
   ```

3. **Copy the cloud compute Docker Compose file**:
   ```sh
   cp DecideDocker/docker-compose-cloudcompute.yml ./
   ```

4. **Run the integrated deployment**:
   ```sh
   sudo docker compose -f docker-compose-cloudcompute.yml up -d
   ```

5. **To stop the deployment**:
   ```sh
   sudo docker compose -f docker-compose-cloudcompute.yml down
   ```

---

### 🔗 Notes

- This setup runs **XNAT**, **Decide**, and **NGINX** in a shared `proxynet` Docker network.
- Ensure your `.env` file is properly configured and placed in the same directory.
- The container will expose:
  - **XNAT** on port `8104`
  - **JupyterLab (Decide)** on port `8888`
  - **NGINX proxy** on port `80`

---

## 🔄 Staying Up to Date (Force Sync with Upstream)

To update your local copy with the latest changes from the original repository and **discard any local changes**:

1. **Add the original repo as a remote (if not already):**
   ```sh
   git remote add upstream https://github.com/NKI-RT/DecideDocker.git
   ```

2. **Fetch the latest changes from upstream:**
   ```sh
   git fetch upstream
   ```

3. **Reset your local `main` branch to match `upstream/main`:**
   ```sh
   git checkout main
   git reset --hard upstream/main
   ```

4. *(Optional)* **Clean up untracked files and directories:**
   ```sh
   git clean -fd
   ```

> ⚠️ **Warning:** This will permanently discard all local changes, including uncommitted edits and untracked files.

---

## 📢 Updates

We will release more features and scripts/notebooks as the project progresses.  
**Stay tuned and keep your local copy up to date!**

---

## 📁 Repository Structure

```
DecideDocker/
├── Dockerfile
├── docker-compose.yml
├── docker-compose-cloudcompute.yml
├── startup.sh
├── workspace/
│   ├── .env (default.env)
│   ├── decide/
│   │   ├── config/
│   │   │   ├── config_total_segmentator.yaml
│   │   │   └── dicomdata_config.yaml
│   │   ├── logs/
│   │   ├── data/
│   │   |   └── LUNG1-001/
│   │   |       ├── CT
│   │   |       ├── RTSTRUCT
│   │   |       └── NIfTI
│   │   ├── src/
│   │   │   └── decide/
│   │   └── pyproject.toml
│   ├── notebooks/
│   │   ├── 001_test_essentials.ipynb
│   │   ├── 002_get_nifti.ipynb
│   |   └── 002_get_niftiv2.ipynb
│   └── scripts/
│       └── get_nifti.py
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