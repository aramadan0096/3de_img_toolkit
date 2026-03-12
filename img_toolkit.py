# 3DE4.script.name:     R_Tools Image Filter Toolkit
# 3DE4.script.version:  v1.0
# 3DE4.script.gui:      r_tools/Start R img filter toolkit
# 3DE4.script.comment:  High-end image filter toolkit for camera footage sequences.
#                       Provides real-time preview and export of:
#                       - Sharpness (Unsharp Mask)
#                       - High-Pass Detail Enhancement
#                       - Contrast / Brightness
#                       Supports OpenEXR sequences (VFX industry standard).
#                       Requires: PySide6, numpy, scipy.
#                       Optional but recommended: OpenImageIO (oiio).
#
# Install location: ~/.3dequalizer/py_scripts/  or  $TDE4_SCRIPT_PATH

import sys
import os
import re
import copy
import time
import traceback
import numpy as np
from pathlib import Path

import tde4  # 3DEqualizer Python API

# ---------------------------------------------------------------------------
# PySide6
# ---------------------------------------------------------------------------
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSlider, QPushButton, QComboBox, QCheckBox,
    QGroupBox, QScrollArea, QSizePolicy, QProgressDialog,
    QMessageBox, QFrame, QSpinBox, QDoubleSpinBox,
    QFileDialog, QStatusBar, QToolButton, QSplitter,
    QLineEdit
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QSize, QRect, QPoint, QMutex
)
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QIcon,
    QPalette, QCursor
)

# ---------------------------------------------------------------------------
# Optional image I/O backends
# ---------------------------------------------------------------------------
HAS_OIIO = False
HAS_CV2   = False

try:
    import OpenImageIO as oiio   # type: ignore
    HAS_OIIO = True
except ImportError:
    pass

try:
    import cv2  # type: ignore
    HAS_CV2 = True
    os.environ["OPENCV_IO_ENABLE_OPENEXR"]="1"
except ImportError:
    pass

try:
    from scipy.ndimage import gaussian_filter as _scipy_gaussian  # type: ignore
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# ---------------------------------------------------------------------------
# Dark VFX-style stylesheet
# ---------------------------------------------------------------------------
DARK_STYLE = """
QWidget {
    background-color: #252526;
    color: #cccccc;
    font-family: "Segoe UI", "SF Pro Text", Arial, sans-serif;
    font-size: 11px;
}
QMainWindow, QDialog {
    background-color: #1e1e1e;
}
QGroupBox {
    border: 1px solid #3a3a3a;
    border-radius: 5px;
    margin-top: 10px;
    padding: 6px 4px 4px 4px;
    font-weight: bold;
    color: #8ab4e8;
    font-size: 11px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #3c3c3c;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #4a90d9;
    border: 1px solid #3a78bd;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #5aa0e8;
}
QSlider::sub-page:horizontal {
    background: #2a5f9e;
    border-radius: 2px;
}
QSlider::groove:horizontal:disabled {
    background: #2a2a2a;
}
QSlider::handle:horizontal:disabled {
    background: #404040;
    border-color: #383838;
}
QPushButton {
    background-color: #3c3c3c;
    border: 1px solid #505050;
    border-radius: 4px;
    padding: 5px 14px;
    color: #cccccc;
    min-height: 22px;
}
QPushButton:hover   { background-color: #4a4a4a; border-color: #606060; }
QPushButton:pressed { background-color: #2a2a2a; }
QPushButton:disabled{ background-color: #2e2e2e; color: #666; border-color: #383838; }
QPushButton#export_btn {
    background-color: #1e5c1e;
    border: 1px solid #2a7a2a;
    color: #88ff88;
    font-weight: bold;
    font-size: 12px;
    min-height: 30px;
    padding: 6px 20px;
}
QPushButton#export_btn:hover   { background-color: #256025; }
QPushButton#export_btn:pressed { background-color: #143314; }
QPushButton#export_btn:disabled{ background-color: #1a2e1a; color: #446644; }
QPushButton#reset_btn {
    background-color: #3a2828;
    border-color: #583838;
    color: #ffaaaa;
}
QPushButton#reset_btn:hover { background-color: #4a3030; }
QComboBox {
    background-color: #333333;
    border: 1px solid #505050;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    selection-background-color: #3a6ea8;
    border: 1px solid #505050;
}
QDoubleSpinBox, QSpinBox {
    background-color: #2d2d2d;
    border: 1px solid #484848;
    border-radius: 3px;
    padding: 2px 4px;
    min-width: 54px;
    max-width: 64px;
    min-height: 20px;
}
QDoubleSpinBox:disabled, QSpinBox:disabled { color: #555; background-color: #252525; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #555;
    border-radius: 3px;
    background-color: #2d2d2d;
}
QCheckBox::indicator:checked {
    background-color: #2a5f9e;
    border-color: #4a90d9;
    image: none;
}
QLabel#frame_label {
    font-size: 18px;
    font-weight: bold;
    color: #5bb0ff;
    qproperty-alignment: AlignCenter;
}
QLabel#status_label {
    color: #aaaaaa;
    font-size: 10px;
    padding: 2px 6px;
}
QLabel#section_title {
    font-size: 10px;
    color: #888888;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 4px 0 2px 0;
}
QScrollArea { border: none; }
QScrollBar:vertical {
    background: #1e1e1e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #484848;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QFrame#separator {
    background-color: #3a3a3a;
    max-height: 1px;
}
QLineEdit {
    background-color: #2d2d2d;
    border: 1px solid #484848;
    border-radius: 3px;
    padding: 3px 6px;
    color: #cccccc;
}
QProgressDialog {
    background-color: #252526;
    color: #cccccc;
}
"""

# ---------------------------------------------------------------------------
# Sequence / Frame Utilities
# ---------------------------------------------------------------------------

def expand_frame_path(seq_path: str, frame: int) -> str:
    """Expand a sequence path template to a concrete file path for *frame*."""
    if not seq_path:
        return ""
    # printf-style: %04d, %d, %05d …
    if re.search(r'%\d*d', seq_path):
        try:
            return seq_path % frame
        except Exception:
            pass
    # hash-style: ####, #####
    m = re.search(r'(#+)', seq_path)
    if m:
        hashes = m.group(1)
        padded = str(frame).zfill(len(hashes))
        return seq_path[:m.start()] + padded + seq_path[m.end():]
    # No pattern – single image
    return seq_path


def suggest_output_dir(seq_path: str) -> str:
    """Suggest an output directory based on the input sequence path."""
    if not seq_path:
        return ""
    parent = str(Path(seq_path).parent)
    return parent + "_filtered"


def build_output_path(input_seq_path: str, output_dir: str) -> str:
    """Build an output sequence path preserving the filename pattern."""
    filename = Path(input_seq_path).name
    return os.path.join(output_dir, filename)


# ---------------------------------------------------------------------------
# Image I/O
# ---------------------------------------------------------------------------

class ImageIO:
    """Abstraction layer over OIIO / OpenCV / basic fallback for EXR I/O."""

    @staticmethod
    def load(path: str) -> tuple[np.ndarray, dict]:
        """
        Load an image as float32 numpy array (H, W, C) in RGB(A) order.
        Returns (pixels, metadata_dict).
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Image not found: {path}")

        if HAS_OIIO:
            return ImageIO._load_oiio(path)
        elif HAS_CV2:
            return ImageIO._load_cv2(path)
        else:
            raise RuntimeError(
                "No image backend available.\n"
                "Please install OpenImageIO or OpenCV (cv2)."
            )

    @staticmethod
    def save(path: str, pixels: np.ndarray, metadata: dict | None = None):
        """Save float32 (H, W, C) array to *path* (EXR or other format)."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        if HAS_OIIO:
            ImageIO._save_oiio(path, pixels, metadata)
        elif HAS_CV2:
            ImageIO._save_cv2(path, pixels)
        else:
            raise RuntimeError("No image backend available for saving.")

    # -- OIIO --
    @staticmethod
    def _load_oiio(path: str):
        inp = oiio.ImageInput.open(path)
        if inp is None:
            raise IOError(f"OIIO: cannot open {path}")
        spec  = inp.spec()
        nch   = spec.nchannels
        pixels = inp.read_image(oiio.FLOAT)
        inp.close()
        if pixels is None:
            raise IOError(f"OIIO: read_image failed for {path}")
        # Ensure (H, W, C)
        if pixels.ndim == 2:
            pixels = pixels[:, :, np.newaxis]
        pixels = pixels.astype(np.float32)
        meta = {
            "width": spec.width,
            "height": spec.height,
            "nchannels": nch,
            "channelnames": list(spec.channelnames),
        }
        return pixels, meta

    @staticmethod
    def _save_oiio(path: str, pixels: np.ndarray, metadata: dict | None):
        h, w = pixels.shape[:2]
        nc = pixels.shape[2] if pixels.ndim == 3 else 1
        spec = oiio.ImageSpec(w, h, nc, oiio.FLOAT)
        spec.attribute("compression", "zips")
        if metadata and "channelnames" in metadata:
            spec.channelnames = metadata["channelnames"]
        out = oiio.ImageOutput.create(path)
        if out is None:
            raise IOError(f"OIIO: cannot create {path}")
        out.open(path, spec)
        out.write_image(pixels)
        out.close()

    # -- OpenCV --
    @staticmethod
    def _load_cv2(path: str):
        flags = cv2.IMREAD_UNCHANGED | cv2.IMREAD_ANYDEPTH | cv2.IMREAD_ANYCOLOR
        img = cv2.imread(path, flags)
        if img is None:
            raise IOError(f"cv2: cannot open {path}")
        if img.ndim == 2:
            img = img[:, :, np.newaxis]
        elif img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        img = img.astype(np.float32)
        if img.max() > 2.0:          # 8-bit or 16-bit range
            img /= 65535.0 if img.max() > 255.0 else 255.0
        meta = {"width": img.shape[1], "height": img.shape[0],
                "nchannels": img.shape[2]}
        return img, meta

    @staticmethod
    def _save_cv2(path: str, pixels: np.ndarray):
        ext = Path(path).suffix.lower()
        if ext == ".exr":
            img = pixels.copy()
        else:
            img = np.clip(pixels, 0, 1)
        if img.shape[2] == 3:
            img_out = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        elif img.shape[2] == 4:
            img_out = cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)
        else:
            img_out = img
        cv2.imwrite(path, img_out.astype(np.float32))


# ---------------------------------------------------------------------------
# Image Processing
# ---------------------------------------------------------------------------

def _gaussian(img: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur with available backend."""
    if HAS_SCIPY:
        return _scipy_gaussian(img, sigma=sigma, mode='reflect')
    elif HAS_CV2:
        k = int(sigma * 6) | 1          # ensure odd
        k = max(k, 3)
        return cv2.GaussianBlur(img, (k, k), sigmaX=sigma, sigmaY=sigma)
    else:
        # Pure-numpy separable approximation (slow, last resort)
        from numpy import pad
        radius = max(1, int(sigma * 3))
        x = np.arange(-radius, radius + 1)
        kern = np.exp(-x**2 / (2 * sigma**2))
        kern /= kern.sum()
        result = np.copy(img)
        for ax in (0, 1):
            result = np.apply_along_axis(
                lambda v: np.convolve(v, kern, mode='same'), ax, result
            )
        return result


class FilterParams:
    """Holds all filter parameter values."""
    def __init__(self):
        self.sharpen_enabled   = False
        self.sharpen_amount    = 1.0     # 0 – 3
        self.sharpen_radius    = 1.0     # 0.3 – 5.0

        self.highpass_enabled  = False
        self.highpass_amount   = 0.5     # 0 – 2
        self.highpass_radius   = 5.0     # 1 – 20

        self.contrast_enabled  = False
        self.contrast_value    = 1.0     # 0.25 – 3 (1 = neutral)
        self.brightness_value  = 0.0     # −1 – +1 (0 = neutral)

    def copy(self):
        return copy.copy(self)


class ImageProcessor:
    """Applies filter stack to a float32 numpy image array."""

    @staticmethod
    def process(img: np.ndarray, params: FilterParams) -> np.ndarray:
        result = img.astype(np.float32)

        if params.sharpen_enabled and params.sharpen_amount > 0:
            result = ImageProcessor._unsharp_mask(
                result, params.sharpen_amount, params.sharpen_radius)

        if params.highpass_enabled and params.highpass_amount > 0:
            result = ImageProcessor._highpass(
                result, params.highpass_amount, params.highpass_radius)

        if params.contrast_enabled:
            result = ImageProcessor._contrast(
                result, params.contrast_value, params.brightness_value)

        return result

    @staticmethod
    def _unsharp_mask(img, amount, radius):
        """Classic unsharp mask: sharpen = original + amount*(original - blur)."""
        blurred = _gaussian(img, sigma=radius)
        return img + amount * (img - blurred)

    @staticmethod
    def _highpass(img, amount, radius):
        """
        High-pass detail layer (soft-light blend).
        Separates broad low-frequency base from fine-detail layer,
        then re-applies the detail at *amount* strength.
        Mathematically: img + amount*(img - blur)
        with a larger radius than sharpening for mid-frequency content.
        """
        blurred = _gaussian(img, sigma=radius)
        hp = img - blurred  # zero-centred detail
        return img + amount * hp

    @staticmethod
    def _contrast(img, contrast, brightness):
        """
        Contrast around photographic gray pivot (0.18).
        contrast: 1.0 = neutral, >1 = more, <1 = less
        brightness: 0.0 = neutral, +/- in scene-linear units
        """
        PIVOT = 0.18
        return PIVOT + contrast * (img - PIVOT) + brightness


# ---------------------------------------------------------------------------
# Tone-mapping for display
# ---------------------------------------------------------------------------

def tonemap_display(img: np.ndarray, exposure: float = 0.0) -> np.ndarray:
    """
    Convert scene-linear float32 (H,W,C) → sRGB uint8 for Qt display.
    *exposure* is in EV stops (0 = neutral).
    Uses Reinhard tone-map then sRGB gamma.
    """
    gain = 2.0 ** exposure
    rgb = img[:, :, :3].astype(np.float32) * gain
    # Reinhard global operator
    rgb = rgb / (1.0 + rgb)
    np.clip(rgb, 0, 1, out=rgb)
    # sRGB approximate gamma
    rgb = np.where(rgb <= 0.0031308,
                   12.92 * rgb,
                   1.055 * np.power(rgb, 1.0 / 2.4) - 0.055)
    np.clip(rgb, 0, 1, out=rgb)
    return (rgb * 255).astype(np.uint8)


def numpy_to_qpixmap(arr: np.ndarray) -> QPixmap:
    """Convert uint8 (H,W,3) RGB numpy array to QPixmap."""
    arr = np.ascontiguousarray(arr)
    h, w, _ = arr.shape
    qimg = QImage(arr.data, w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


# ---------------------------------------------------------------------------
# 3DE Camera Utilities
# ---------------------------------------------------------------------------

def get_all_cameras() -> list[tuple[str, str]]:
    """Return [(cam_id, display_name), ...] across all point-groups."""
    cameras = []
    try:
        pgs = tde4.getPGroupList()
    except Exception:
        pgs = []

    # Also try without pgroup argument
    try:
        all_cams = tde4.getCameraList()   # some API versions accept no arg
        for cid in all_cams:
            name = tde4.getCameraName(cid)
            cameras.append((cid, name))
        return cameras
    except Exception:
        pass

    for pg in pgs:
        try:
            cams = tde4.getCameraList(pg)
            for cid in cams:
                try:
                    name = tde4.getCameraName(cid)
                    cameras.append((cid, f"{name}"))
                except Exception:
                    cameras.append((cid, f"<cam {cid}>"))
        except Exception:
            pass
    return cameras


def get_camera_sequence_info(cam_id: str) -> dict:
    """
    Return dict with keys: display_path, first_frame, last_frame, n_frames.

    Uses the same strategy as cam_fetch.py:
      - getCameraNoFrames()        → total frame count  (frames are 1-indexed)
      - getCameraFrameFilepath()   → actual path for each frame
      - getCameraPath()            → generic stored path for display only
      - getCameraProxyFootage()    → proxy path fallback for display
    """
    info = {
        "display_path": "",   # for UI label only; not used for actual I/O
        "first_frame":  1,
        "last_frame":   1,
        "n_frames":     0,
    }

    # --- frame count (1-indexed, range is [1 .. n_frames]) ---
    try:
        n = tde4.getCameraNoFrames(cam_id)
        if n:
            info["n_frames"]   = int(n)
            info["first_frame"] = 1
            info["last_frame"]  = int(n)
    except Exception:
        pass

    # --- display path for UI label (not used for loading) ---
    # Priority: getCameraPath → getCameraProxyFootage → getCameraFrameFilepath(1)
    for fn_name in ("getCameraPath", "getCameraProxyFootage"):
        fn = getattr(tde4, fn_name, None)
        if fn:
            try:
                p = fn(cam_id)
                if isinstance(p, (list, tuple)):
                    p = p[0] if p else ""
                if p:
                    info["display_path"] = str(p)
                    break
            except Exception:
                pass

    if not info["display_path"] and info["n_frames"] > 0:
        try:
            p = tde4.getCameraFrameFilepath(cam_id, 1)
            if p:
                info["display_path"] = p
        except Exception:
            pass

    return info


def get_camera_frame_filepath(cam_id: str, frame: int) -> str:
    """
    Return the actual on-disk file path for *frame* of *cam_id*.
    Mirrors cam_fetch.py: tde4.getCameraFrameFilepath(cam, f).
    Returns empty string if the path cannot be determined.
    """
    try:
        fp = tde4.getCameraFrameFilepath(cam_id, frame)
        return fp or ""
    except Exception:
        return ""


def set_camera_sequence_path(cam_id: str, new_path: str,
                             first_frame: int = 1, last_frame: int = 1):
    """
    Update the footage path of *cam_id* in 3DE.
    Tries the standard sequence-setter API names first.
    As a last resort, tries setCameraFrameFilepath per frame
    (only practical for short ranges or single images).
    """
    for fn_name in ("setCameraSequencePath", "setSequencePath",
                    "setCameraImagePath", "setCameraPath"):
        fn = getattr(tde4, fn_name, None)
        if fn:
            try:
                fn(cam_id, new_path)
                return
            except Exception:
                pass

    # Last resort: set per-frame paths when the above all fail
    set_fn = getattr(tde4, "setCameraFrameFilepath", None)
    if set_fn:
        for f in range(first_frame, last_frame + 1):
            frame_path = expand_frame_path(new_path, f)
            try:
                set_fn(cam_id, f, frame_path)
            except Exception:
                pass
        return

    raise RuntimeError(
        "Could not find any 3DE API function to set the camera footage path.\n"
        f"Please update the footage path manually to:\n{new_path}"
    )


# ---------------------------------------------------------------------------
# Reusable slider row widget
# ---------------------------------------------------------------------------

class LabeledSlider(QWidget):
    """
    A horizontal slider with a left label, a right value spin-box,
    and optional enable checkbox.
    valueChanged(float) is emitted whenever the value changes.
    """
    valueChanged = Signal(float)

    def __init__(self,
                 label: str,
                 min_val: float, max_val: float, default: float,
                 decimals: int = 2,
                 parent=None):
        super().__init__(parent)
        self._decimals = decimals
        self._min = min_val
        self._max = max_val
        self._scale = 10 ** decimals        # int ↔ float conversion factor

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        self.lbl = QLabel(label)
        self.lbl.setFixedWidth(76)
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(min_val * self._scale),
                             int(max_val * self._scale))
        self.slider.setValue(int(default * self._scale))
        self.slider.setSingleStep(1)
        self.slider.setPageStep(max(1, int(self._scale * 0.1)))

        self.spin = QDoubleSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setDecimals(decimals)
        self.spin.setSingleStep(10 ** -decimals)
        self.spin.setValue(default)
        self.spin.setFixedWidth(62)

        layout.addWidget(self.lbl)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)

        self.slider.valueChanged.connect(self._slider_changed)
        self.spin.valueChanged.connect(self._spin_changed)

    def _slider_changed(self, v: int):
        fv = v / self._scale
        self.spin.blockSignals(True)
        self.spin.setValue(fv)
        self.spin.blockSignals(False)
        self.valueChanged.emit(fv)

    def _spin_changed(self, fv: float):
        iv = int(round(fv * self._scale))
        self.slider.blockSignals(True)
        self.slider.setValue(iv)
        self.slider.blockSignals(False)
        self.valueChanged.emit(fv)

    def value(self) -> float:
        return self.spin.value()

    def setValue(self, v: float):
        self.slider.blockSignals(True)
        self.spin.blockSignals(True)
        self.slider.setValue(int(round(v * self._scale)))
        self.spin.setValue(v)
        self.slider.blockSignals(False)
        self.spin.blockSignals(False)

    def setEnabled(self, enabled: bool):
        self.slider.setEnabled(enabled)
        self.spin.setEnabled(enabled)
        super().setEnabled(enabled)


# ---------------------------------------------------------------------------
# Filter Group box
# ---------------------------------------------------------------------------

class FilterGroup(QGroupBox):
    """
    A collapsible GroupBox containing an enable checkbox + parameter sliders.
    paramsChanged() is emitted whenever any parameter changes.
    """
    paramsChanged = Signal()

    def __init__(self, title: str, sliders_cfg: list[dict], parent=None):
        super().__init__(title, parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 6)
        self._layout.setSpacing(2)

        self.enable_cb = QCheckBox("Enable")
        self.enable_cb.setChecked(False)
        self._layout.addWidget(self.enable_cb)

        self._sliders: dict[str, LabeledSlider] = {}
        for cfg in sliders_cfg:
            s = LabeledSlider(
                cfg["label"],
                cfg["min"], cfg["max"], cfg["default"],
                cfg.get("decimals", 2)
            )
            s.setEnabled(False)
            self._sliders[cfg["key"]] = s
            self._layout.addWidget(s)

        self.enable_cb.toggled.connect(self._on_toggle)
        for s in self._sliders.values():
            s.valueChanged.connect(lambda _: self.paramsChanged.emit())

    def _on_toggle(self, checked: bool):
        for s in self._sliders.values():
            s.setEnabled(checked)
        self.paramsChanged.emit()

    def is_enabled(self) -> bool:
        return self.enable_cb.isChecked()

    def get_value(self, key: str) -> float:
        return self._sliders[key].value()

    def set_value(self, key: str, v: float):
        self._sliders[key].setValue(v)

    def set_enabled(self, key: str, enabled: bool):
        self.enable_cb.setChecked(enabled)


# ---------------------------------------------------------------------------
# Image Viewer
# ---------------------------------------------------------------------------

class ImageViewer(QWidget):
    """Scales and centres an image pixmap; toggles original / filtered."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap_filtered: QPixmap | None = None
        self._pixmap_original: QPixmap | None = None
        self._show_original = False
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #111111;")

    def set_filtered(self, pm: QPixmap):
        self._pixmap_filtered = pm
        if not self._show_original:
            self.update()

    def set_original(self, pm: QPixmap):
        self._pixmap_original = pm
        if self._show_original:
            self.update()

    def show_original(self, flag: bool):
        self._show_original = flag
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111111"))
        pm = (self._pixmap_original if self._show_original
              else self._pixmap_filtered)
        if pm and not pm.isNull():
            scaled = pm.scaled(self.size(),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            x = (self.width()  - scaled.width())  // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.setPen(QColor("#555555"))
            painter.drawText(self.rect(),
                             Qt.AlignmentFlag.AlignCenter,
                             "No image loaded")

    def resizeEvent(self, event):
        self.update()


# ---------------------------------------------------------------------------
# Background export thread
# ---------------------------------------------------------------------------

class ExportThread(QThread):
    progress     = Signal(int, str)     # (frames_done, message)
    finished_ok  = Signal(str, str)     # (output_dir, first_output_path)
    error        = Signal(str)

    def __init__(self, cam_id: str, output_dir: str,
                 first: int, last: int, params: FilterParams):
        super().__init__()
        self._cam_id     = cam_id
        self._output_dir = output_dir
        self._first      = first
        self._last       = last
        self._params     = params.copy()
        self._abort      = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            os.makedirs(self._output_dir, exist_ok=True)
            total           = self._last - self._first + 1
            first_out_path  = ""
            frames_done     = 0

            for frame in range(self._first, self._last + 1):
                if self._abort:
                    self.error.emit("Export cancelled.")
                    return

                # ── resolve input path using the same API as cam_fetch.py ──
                in_path = get_camera_frame_filepath(self._cam_id, frame)
                if not in_path:
                    # frame has no path registered – skip silently
                    frames_done += 1
                    self.progress.emit(frames_done,
                                       f"Frame {frame} – no path, skipped")
                    continue

                # ── mirror the filename into output_dir ──
                out_path = os.path.join(
                    self._output_dir, os.path.basename(in_path))

                if not first_out_path:
                    first_out_path = out_path

                msg = (f"Frame {frame}  "
                       f"({frames_done + 1}/{total})  "
                       f"→  {os.path.basename(out_path)}")
                self.progress.emit(frames_done, msg)

                try:
                    pixels, meta = ImageIO.load(in_path)
                except FileNotFoundError:
                    frames_done += 1
                    self.progress.emit(frames_done,
                                       f"Frame {frame} – file not found, skipped")
                    continue

                filtered = ImageProcessor.process(pixels, self._params)
                ImageIO.save(out_path, filtered, meta)
                frames_done += 1

            self.finished_ok.emit(self._output_dir, first_out_path)

        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Preview update worker (runs in a thread to keep UI responsive)
# ---------------------------------------------------------------------------

class PreviewThread(QThread):
    done = Signal(np.ndarray, np.ndarray)  # (original_uint8, filtered_uint8)
    error = Signal(str)

    def __init__(self, img_float: np.ndarray,
                 params: FilterParams, exposure: float):
        super().__init__()
        self._img     = img_float
        self._params  = params.copy()
        self._exposure = exposure

    def run(self):
        try:
            orig     = tonemap_display(self._img, self._exposure)
            filtered = ImageProcessor.process(self._img, self._params)
            filt_tm  = tonemap_display(filtered, self._exposure)
            self.done.emit(orig, filt_tm)
        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# Main filter window
# ---------------------------------------------------------------------------

class FilterToolkitWindow(QMainWindow):
    def __init__(self, cam_id: str, cam_name: str):
        super().__init__()
        self.setWindowTitle(
            f"R_Tools  •  Image Filter Toolkit  •  [{cam_name}]"
        )
        self.resize(1420, 860)
        self.setStyleSheet(DARK_STYLE)

        self._cam_id   = cam_id
        self._cam_name = cam_name
        self._seq_info = get_camera_sequence_info(cam_id)
        self._current_frame_img: np.ndarray | None = None
        self._preview_thread: PreviewThread | None = None
        self._export_thread:  ExportThread  | None = None
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._trigger_preview)

        self._params = FilterParams()

        self._build_ui()
        self._load_frame(self._seq_info["first_frame"])

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left control panel ──────────────────────────────────────────────
        ctrl_scroll = QScrollArea()
        ctrl_scroll.setWidgetResizable(True)
        ctrl_scroll.setFixedWidth(310)
        ctrl_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(10, 10, 10, 10)
        ctrl_layout.setSpacing(6)
        ctrl_scroll.setWidget(ctrl_widget)

        # Camera info label
        info_lbl = QLabel(
            f"<b>{self._cam_name}</b><br>"
            f"<span style='color:#888;font-size:10px;'>"
            f"{self._seq_info['display_path'] or 'No footage path detected'}</span>"
        )
        info_lbl.setWordWrap(True)
        ctrl_layout.addWidget(info_lbl)

        ctrl_layout.addWidget(self._make_separator())

        # ── Frame Selector ──────────────────────────────────────────────────
        frame_grp = QGroupBox("Frame")
        frame_layout = QVBoxLayout(frame_grp)
        frame_layout.setSpacing(4)

        self._frame_display = QLabel(str(self._seq_info["first_frame"]))
        self._frame_display.setObjectName("frame_label")
        frame_layout.addWidget(self._frame_display)

        self._frame_slider = QSlider(Qt.Orientation.Horizontal)
        self._frame_slider.setRange(self._seq_info["first_frame"],
                                    self._seq_info["last_frame"])
        self._frame_slider.setValue(self._seq_info["first_frame"])
        self._frame_slider.setSingleStep(1)
        self._frame_slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self._frame_slider.valueChanged.connect(self._on_frame_changed)
        frame_layout.addWidget(self._frame_slider)

        frame_range_lbl = QLabel(
            f"Range:  {self._seq_info['first_frame']}  –  "
            f"{self._seq_info['last_frame']}")
        frame_range_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_range_lbl.setStyleSheet("color:#777;font-size:10px;")
        frame_layout.addWidget(frame_range_lbl)
        ctrl_layout.addWidget(frame_grp)

        # ── Display Exposure (preview only) ─────────────────────────────────
        disp_grp = QGroupBox("Display  (preview only)")
        disp_lay = QVBoxLayout(disp_grp)
        disp_lay.setSpacing(2)

        self._exposure_slider = LabeledSlider("Exposure", -6.0, 6.0, 0.0,
                                              decimals=2)
        self._exposure_slider.valueChanged.connect(
            lambda _: self._schedule_preview())
        disp_lay.addWidget(self._exposure_slider)

        self._compare_btn = QPushButton("Hold  [ Original ]")
        self._compare_btn.setCheckable(True)
        self._compare_btn.toggled.connect(self._on_compare_toggled)
        disp_lay.addWidget(self._compare_btn)
        ctrl_layout.addWidget(disp_grp)

        ctrl_layout.addWidget(self._make_separator())

        # ── Filter Groups ────────────────────────────────────────────────────
        ctrl_layout.addWidget(
            self._make_section_title("FILTERS"))

        self._sharpen_grp = FilterGroup(
            "Sharpness  (Unsharp Mask)",
            [
                {"key": "amount", "label": "Amount",
                 "min": 0.0, "max": 3.0, "default": 1.0, "decimals": 2},
                {"key": "radius", "label": "Radius px",
                 "min": 0.3, "max": 5.0, "default": 1.0, "decimals": 2},
            ]
        )
        self._sharpen_grp.paramsChanged.connect(self._on_filter_changed)
        ctrl_layout.addWidget(self._sharpen_grp)

        self._highpass_grp = FilterGroup(
            "High-Pass  (Detail Layer)",
            [
                {"key": "amount", "label": "Amount",
                 "min": 0.0, "max": 2.0, "default": 0.5, "decimals": 2},
                {"key": "radius", "label": "Radius px",
                 "min": 1.0, "max": 25.0, "default": 5.0, "decimals": 1},
            ]
        )
        self._highpass_grp.paramsChanged.connect(self._on_filter_changed)
        ctrl_layout.addWidget(self._highpass_grp)

        self._contrast_grp = FilterGroup(
            "Contrast  /  Brightness",
            [
                {"key": "contrast",   "label": "Contrast",
                 "min": 0.25, "max": 3.0, "default": 1.0, "decimals": 2},
                {"key": "brightness", "label": "Brightness",
                 "min": -1.0, "max": 1.0, "default": 0.0, "decimals": 3},
            ]
        )
        self._contrast_grp.paramsChanged.connect(self._on_filter_changed)
        ctrl_layout.addWidget(self._contrast_grp)

        ctrl_layout.addWidget(self._make_separator())

        # ── Export ───────────────────────────────────────────────────────────
        ctrl_layout.addWidget(self._make_section_title("EXPORT"))

        out_dir_grp = QGroupBox("Output Directory")
        out_dir_lay = QVBoxLayout(out_dir_grp)

        self._out_dir_edit = QLineEdit(suggest_output_dir(self._seq_info["display_path"]))
        self._out_dir_edit.setPlaceholderText("/path/to/output_folder")
        out_dir_lay.addWidget(self._out_dir_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_output_dir)
        out_dir_lay.addWidget(browse_btn)
        ctrl_layout.addWidget(out_dir_grp)

        # Reset + Export buttons
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset All")
        reset_btn.setObjectName("reset_btn")
        reset_btn.clicked.connect(self._reset_params)
        btn_row.addWidget(reset_btn)

        self._export_btn = QPushButton("⬡  Export Sequence")
        self._export_btn.setObjectName("export_btn")
        self._export_btn.clicked.connect(self._start_export)
        btn_row.addWidget(self._export_btn, 1)
        ctrl_layout.addLayout(btn_row)

        # Status / info
        self._status_lbl = QLabel("Ready.")
        self._status_lbl.setObjectName("status_label")
        self._status_lbl.setWordWrap(True)
        ctrl_layout.addWidget(self._status_lbl)

        ctrl_layout.addStretch(1)

        # ── Right image viewer ───────────────────────────────────────────────
        self._viewer = ImageViewer()

        root.addWidget(ctrl_scroll)
        root.addWidget(self._viewer, 1)

        # ── Status bar ───────────────────────────────────────────────────────
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        backend = ("OIIO" if HAS_OIIO
                   else "OpenCV" if HAS_CV2
                   else "No backend!")
        self._statusbar.showMessage(
            f"Backend: {backend}  |  Python {sys.version.split()[0]}  |"
            f"  scipy: {HAS_SCIPY}"
        )

    def _make_separator(self) -> QFrame:
        f = QFrame()
        f.setObjectName("separator")
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFixedHeight(1)
        return f

    def _make_section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section_title")
        return lbl

    # ---------------------------------------------------------------- Slots --

    def _on_frame_changed(self, frame: int):
        self._frame_display.setText(str(frame))
        self._load_frame(frame)

    def _on_filter_changed(self):
        self._collect_params()
        self._schedule_preview()

    def _on_compare_toggled(self, checked: bool):
        self._viewer.show_original(checked)
        self._compare_btn.setText("Release  [ Filtered ]" if checked
                                  else "Hold  [ Original ]")

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory",
                                             self._out_dir_edit.text())
        if d:
            self._out_dir_edit.setText(d)

    def _reset_params(self):
        self._sharpen_grp.set_enabled("enabled", False)
        self._sharpen_grp.set_value("amount", 1.0)
        self._sharpen_grp.set_value("radius", 1.0)
        self._highpass_grp.set_enabled("enabled", False)
        self._highpass_grp.set_value("amount", 0.5)
        self._highpass_grp.set_value("radius", 5.0)
        self._contrast_grp.set_enabled("enabled", False)
        self._contrast_grp.set_value("contrast",   1.0)
        self._contrast_grp.set_value("brightness", 0.0)
        self._exposure_slider.setValue(0.0)
        self._collect_params()
        self._schedule_preview()

    # ---------------------------------------------------------------- Logic --

    def _collect_params(self):
        self._params.sharpen_enabled  = self._sharpen_grp.is_enabled()
        self._params.sharpen_amount   = self._sharpen_grp.get_value("amount")
        self._params.sharpen_radius   = self._sharpen_grp.get_value("radius")
        self._params.highpass_enabled = self._highpass_grp.is_enabled()
        self._params.highpass_amount  = self._highpass_grp.get_value("amount")
        self._params.highpass_radius  = self._highpass_grp.get_value("radius")
        self._params.contrast_enabled = self._contrast_grp.is_enabled()
        self._params.contrast_value   = self._contrast_grp.get_value("contrast")
        self._params.brightness_value = self._contrast_grp.get_value("brightness")

    def _load_frame(self, frame: int):
        # Use the same per-frame API as cam_fetch.py
        path = get_camera_frame_filepath(self._cam_id, frame)
        if not path:
            self._set_status(
                f"Frame {frame}: no filepath returned by 3DE "
                f"(getCameraFrameFilepath returned empty).")
            self._current_frame_img = None
            return

        self._set_status(f"Loading  {os.path.basename(path)} …")
        try:
            pixels, _ = ImageIO.load(path)
            self._current_frame_img = pixels
            self._set_status(
                f"Frame {frame}   {pixels.shape[1]}×{pixels.shape[0]}"
                f"  ch:{pixels.shape[2]}   {os.path.basename(path)}"
            )
            self._schedule_preview(immediate=True)
        except Exception as e:
            self._current_frame_img = None
            self._set_status(f"⚠  {e}")

    def _schedule_preview(self, immediate=False):
        """Debounced preview update (200 ms)."""
        self._debounce_timer.stop()
        if immediate:
            self._trigger_preview()
        else:
            self._debounce_timer.start(200)

    def _trigger_preview(self):
        if self._current_frame_img is None:
            return
        if self._preview_thread and self._preview_thread.isRunning():
            return    # let previous thread finish; a new one starts on next slider settle

        self._collect_params()
        t = PreviewThread(self._current_frame_img, self._params,
                          self._exposure_slider.value())
        t.done.connect(self._on_preview_done)
        t.error.connect(lambda msg: self._set_status(f"Preview error: {msg}"))
        self._preview_thread = t
        t.start()

    def _on_preview_done(self, orig_u8: np.ndarray, filt_u8: np.ndarray):
        self._viewer.set_original(numpy_to_qpixmap(orig_u8))
        self._viewer.set_filtered(numpy_to_qpixmap(filt_u8))
        self._preview_thread = None
        # If slider changed while processing, re-trigger
        if self._debounce_timer.isActive():
            pass   # timer will fire soon anyway

    # ---------------------------------------------------------------- Export -

    def _start_export(self):
        if self._seq_info["n_frames"] == 0:
            QMessageBox.warning(self, "No Footage",
                                "This camera has no frames registered in 3DE.\n"
                                "(getCameraNoFrames returned 0)")
            return

        out_dir = self._out_dir_edit.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "No Output Directory",
                                "Please specify an output directory.")
            return

        total = self._seq_info["last_frame"] - self._seq_info["first_frame"] + 1
        reply = QMessageBox.question(
            self, "Confirm Export",
            f"Export  <b>{total}</b>  frame(s) to:<br><br>"
            f"<tt>{out_dir}</tt><br><br>"
            f"After export, 3DE camera footage path will be updated automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._collect_params()
        self._export_btn.setEnabled(False)
        self._set_status("Exporting …")

        self._progress_dlg = QProgressDialog(
            "Exporting filtered sequence …", "Cancel", 0, total, self)
        self._progress_dlg.setWindowTitle("Exporting")
        self._progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dlg.setMinimumDuration(500)
        self._progress_dlg.canceled.connect(self._cancel_export)
        self._progress_dlg.show()

        self._export_thread = ExportThread(
            cam_id     = self._cam_id,
            output_dir = out_dir,
            first      = self._seq_info["first_frame"],
            last       = self._seq_info["last_frame"],
            params     = self._params,
        )
        self._export_thread.progress.connect(self._on_export_progress)
        self._export_thread.finished_ok.connect(self._on_export_done)
        self._export_thread.error.connect(self._on_export_error)
        self._export_thread.start()

    def _cancel_export(self):
        if self._export_thread:
            self._export_thread.abort()

    def _on_export_progress(self, idx: int, msg: str):
        if hasattr(self, "_progress_dlg"):
            self._progress_dlg.setValue(idx + 1)
            self._progress_dlg.setLabelText(msg)
        self._set_status(msg)

    def _on_export_done(self, output_dir: str, first_out_path: str):
        self._export_btn.setEnabled(True)
        if hasattr(self, "_progress_dlg"):
            self._progress_dlg.close()

        # Update 3DE camera footage path
        # We pass the first exported frame's path; set_camera_sequence_path
        # tries the standard API names and falls back to per-frame setCameraFrameFilepath.
        try:
            set_camera_sequence_path(
                self._cam_id,
                first_out_path,
                self._seq_info["first_frame"],
                self._seq_info["last_frame"],
            )
            try:
                tde4.updateGUI(0)
            except Exception:
                pass
            # Refresh display path in our local info cache
            self._seq_info["display_path"] = first_out_path
            msg = (f"✔  Export complete.\n"
                   f"3DE footage path updated to:\n{output_dir}")
            self._set_status(msg.replace("\n", "  "))
            QMessageBox.information(self, "Export Complete",
                                    f"Frames written to:\n{output_dir}\n\n"
                                    f"3DE footage path updated successfully.")
        except Exception as e:
            self._set_status(f"Export done but could not update 3DE: {e}")
            QMessageBox.warning(
                self, "3DE Update Failed",
                f"Frames exported to:\n{output_seq_path}\n\n"
                f"Could not update 3DE camera path automatically:\n{e}\n\n"
                f"Please update the footage path manually in 3DE."
            )

    def _on_export_error(self, msg: str):
        self._export_btn.setEnabled(True)
        if hasattr(self, "_progress_dlg"):
            self._progress_dlg.close()
        self._set_status(f"⚠  Export failed.")
        QMessageBox.critical(self, "Export Error", msg)

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)
        self._statusbar.showMessage(msg, 6000)

    def closeEvent(self, event):
        if self._export_thread and self._export_thread.isRunning():
            reply = QMessageBox.question(
                self, "Export Running",
                "An export is in progress. Cancel and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._export_thread.abort()
                self._export_thread.wait(3000)
            else:
                event.ignore()
                return
        event.accept()


# ---------------------------------------------------------------------------
# Camera Picker Dialog
# ---------------------------------------------------------------------------

class CameraPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("R_Tools  •  Image Filter Toolkit")
        self.setFixedSize(440, 180)
        self.setStyleSheet(DARK_STYLE)
        self._selected_cam_id   = None
        self._selected_cam_name = None
        self._build_ui()
        self._populate_cameras()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Select Camera to Filter")
        title.setStyleSheet("font-size:14px;font-weight:bold;color:#88bbff;")
        layout.addWidget(title)

        self._cam_combo = QComboBox()
        self._cam_combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                                      QSizePolicy.Policy.Fixed)
        layout.addWidget(self._cam_combo)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        self._select_btn = QPushButton("Open Filter Toolkit  →")
        self._select_btn.setObjectName("export_btn")
        self._select_btn.clicked.connect(self._on_select)

        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._select_btn)
        layout.addLayout(btn_row)

        self._info_lbl = QLabel("")
        self._info_lbl.setStyleSheet("color:#888;font-size:10px;")
        self._info_lbl.setWordWrap(True)
        layout.addWidget(self._info_lbl)

        self._cam_combo.currentIndexChanged.connect(self._on_cam_selected)

    def _populate_cameras(self):
        self._cameras = get_all_cameras()
        if not self._cameras:
            self._info_lbl.setText(
                "⚠  No cameras found in the current 3DE project.")
            self._select_btn.setEnabled(False)
            return
        for cam_id, cam_name in self._cameras:
            self._cam_combo.addItem(cam_name, userData=cam_id)
        self._on_cam_selected(0)

    def _on_cam_selected(self, idx: int):
        if 0 <= idx < len(self._cameras):
            cam_id, cam_name = self._cameras[idx]
            info = get_camera_sequence_info(cam_id)
            path = info["display_path"] or "(no footage path detected)"
            n    = info["n_frames"]
            frames_str = (
                f"Frames: {info['first_frame']} – {info['last_frame']}  "
                f"({n} frames)"
                if n > 0 else "No frames registered (getCameraNoFrames = 0)"
            )
            self._info_lbl.setText(f"{path}\n{frames_str}")

    def _on_select(self):
        idx = self._cam_combo.currentIndex()
        if 0 <= idx < len(self._cameras):
            self._selected_cam_id, self._selected_cam_name = self._cameras[idx]
            self.accept()

    def selected_camera(self) -> tuple[str | None, str | None]:
        return self._selected_cam_id, self._selected_cam_name


# ---------------------------------------------------------------------------
# Entry point  (called by 3DE when menu item is triggered)
# ---------------------------------------------------------------------------

def main():
    # Re-use the existing Qt application (3DE is a Qt app)
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # ----- Check dependencies -----------------------------------------------
    if not (HAS_OIIO or HAS_CV2):
        QMessageBox.critical(
            None,
            "Missing Dependencies",
            "R_Tools Image Filter Toolkit requires at least one image backend:\n\n"
            "  • OpenImageIO  (pip install openimageio)   ← recommended\n"
            "  • OpenCV        (pip install opencv-python)\n\n"
            "Please install one and restart 3DEqualizer."
        )
        return

    if not HAS_SCIPY:
        reply = QMessageBox.question(
            None,
            "scipy Not Found",
            "scipy is not installed. The Gaussian blur will fall back to a slower\n"
            "pure-numpy implementation which may affect performance.\n\n"
            "Continue anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

    # ----- Camera picker dialog ----------------------------------------------
    picker = CameraPickerDialog()
    if picker.exec() != QDialog.DialogCode.Accepted:
        return

    cam_id, cam_name = picker.selected_camera()
    if not cam_id:
        return

    # ----- Main window -------------------------------------------------------
    win = FilterToolkitWindow(cam_id, cam_name)
    win.show()
    win.raise_()
    win.activateWindow()

    # Keep a reference so it isn't garbage-collected
    if not hasattr(main, "_windows"):
        main._windows = []
    main._windows.append(win)

    # If 3DE manages its own event loop, we don't call app.exec()
    # If running standalone (testing), we do.
    if not QApplication.instance().property("tde4_managed"):
        try:
            app.exec()
        except Exception:
            pass


# 3DE calls the script body directly; call main() here.
main()