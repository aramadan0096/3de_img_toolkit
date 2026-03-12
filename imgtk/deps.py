from __future__ import annotations

import sys
from pathlib import Path


oiio = None
scipy_gaussian = None
cv2 = None
cp = None
Image = None


def prepend_local_libs_path() -> None:
    """Prefer workspace-local bundled dependencies when available."""
    project_root = Path(__file__).resolve().parent.parent
    libs_dir = project_root / "libs"
    if libs_dir.is_dir():
        libs_str = str(libs_dir)
        if libs_str not in sys.path:
            sys.path.insert(0, libs_str)


prepend_local_libs_path()

import numpy as np

try:
    import OpenImageIO as oiio  # type: ignore

    HAS_OIIO = True
except ImportError:
    oiio = None
    HAS_OIIO = False

try:
    from scipy.ndimage import gaussian_filter as scipy_gaussian  # type: ignore

    HAS_SCIPY = True
except ImportError:
    scipy_gaussian = None
    HAS_SCIPY = False

try:
    import cv2  # type: ignore

    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

try:
    import cupy as cp  # type: ignore

    HAS_CUPY = True
except ImportError:
    cp = None
    HAS_CUPY = False

try:
    from PIL import Image  # type: ignore

    HAS_PIL = True
except ImportError:
    Image = None
    HAS_PIL = False
