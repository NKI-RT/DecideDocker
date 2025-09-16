# src/decide/paths.py
"""Commonly used Paths."""

from __future__ import annotations

import os
import sysconfig
from pathlib import Path

# Markers that typically indicate the project/repo root
_PROJECT_MARKERS = ("pyproject.toml", ".git", ".hg")


def _is_within_site_packages(path: Path) -> bool:
    paths = sysconfig.get_paths()
    candidates = [paths.get("purelib"), paths.get("platlib")]
    for p in candidates:
        if not p:
            continue
        try:
            if path.resolve().is_relative_to(Path(p).resolve()):
                return True
        except AttributeError:
            # Python < 3.9 fallback (not needed for Python >=3.10, but kept for completeness)
            rp = path.resolve()
            if str(rp).startswith(str(Path(p).resolve())):
                return True
    return False


def _find_project_root(start: Path | None = None) -> Path:
    here = Path(start or __file__).resolve()
    if here.is_file():
        here = here.parent

    for parent in (here, *here.parents):
        if any((parent / m).exists() for m in _PROJECT_MARKERS):
            return parent

    # Fallback: if the current working directory looks like a project, use it
    cwd = Path.cwd()
    if any((cwd / m).exists() for m in _PROJECT_MARKERS):
        return cwd

    # Last resort: use CWD
    return cwd


# --- Resolve the project root safely ---
# Try to find the real project root (repo root). If that resolves inside site-packages (typical for
# non-editable installs), we *do not* want to create directories there → fall back to CWD.
_detected_root = _find_project_root(Path(__file__).parent)
if _is_within_site_packages(_detected_root):
    PROJECT_ROOT = Path.cwd()
else:
    PROJECT_ROOT = _detected_root

# --- Public paths (always anchored to the project directory) ---
CONFIG_DIR = PROJECT_ROOT / "config"
LOG_DIR = PROJECT_ROOT / "logs"
TEST_DATA_DIR = PROJECT_ROOT / "data"


def ensure_project_dirs() -> None:
    """Create CONFIG_DIR, LOG_DIR, and TEST_DATA_DIR if they do not exist. Safe to call multiple times."""
    for d in (CONFIG_DIR, LOG_DIR, TEST_DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)


# By default, auto-create on import. You can opt-out by setting DECIDE_AUTO_CREATE_DIRS=0
if os.getenv("DECIDE_AUTO_CREATE_DIRS", "1") not in {"0", "false", "False"}:
    ensure_project_dirs()
