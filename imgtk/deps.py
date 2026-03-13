from __future__ import annotations

import sys
from pathlib import Path


oiio = None
scipy_gaussian = None
cv2 = None
cp = None
Image = None
OpenEXR = None
Imath = None


def _iter_local_lib_dirs(project_root: Path):
    py_tag = "py%d%d" % (sys.version_info[0], sys.version_info[1])
    versioned_libs = project_root / "libs" / py_tag
    if versioned_libs.is_dir():
        yield versioned_libs

    # Backward compatibility with previous flat naming.
    legacy_versioned_libs = project_root / ("libs_" + py_tag)
    if legacy_versioned_libs.is_dir():
        yield legacy_versioned_libs

    # Backward compatibility for existing default local libs folder.
    if sys.version_info[:2] == (3, 11):
        default_libs = project_root / "libs"
        if default_libs.is_dir():
            yield default_libs


def prepend_local_libs_path() -> None:
    """Prefer workspace-local bundled dependencies when available."""
    project_root = Path(__file__).resolve().parent.parent
    for libs_dir in _iter_local_lib_dirs(project_root):
        libs_str = str(libs_dir)
        if libs_str not in sys.path:
            sys.path.insert(0, libs_str)


prepend_local_libs_path()

try:
    import numpy as np
except ImportError as exc:
    py_ver = "%d.%d" % (sys.version_info[0], sys.version_info[1])
    raise RuntimeError(
        "NumPy is required but not available for Python %s.\n"
        "Install interpreter-matching dependencies into a local folder named libs\\py%s%s.\n"
        "Example: .\\install_uv_and_libs.bat 3.7" % (py_ver, sys.version_info[0], sys.version_info[1])
    ) from exc

try:
    import OpenImageIO as oiio  # type: ignore

    HAS_OIIO = True
except ImportError:
    oiio = None
    HAS_OIIO = False

try:
    import OpenEXR  # type: ignore
    import Imath  # type: ignore

    HAS_OPENEXR = True
except ImportError:
    OpenEXR = None
    Imath = None
    HAS_OPENEXR = False

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
