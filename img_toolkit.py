# 3DE4.script.name:	Image toolkit
#
# 3DE4.script.gui:	Main Window::R Tools
#
# 3DE4.script.comment:	Run R_tools image toolkit GUI.

from __future__ import annotations
import sys
import os
import re
import copy
import traceback
import concurrent.futures
from pathlib import Path


def _prepend_local_libs_path() -> None:
    """Prefer workspace-local bundled dependencies when available."""
    script_dir = Path(__file__).resolve().parent
    libs_dir = script_dir / "libs"
    if libs_dir.is_dir():
        libs_str = str(libs_dir)
        if libs_str not in sys.path:
            sys.path.insert(0, libs_str)


_prepend_local_libs_path()

import numpy as np

import tde4  # 3DEqualizer Python API

# ---------------------------------------------------------------------------
# PySide6
# ---------------------------------------------------------------------------
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog,
    QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QPushButton, QComboBox, QCheckBox,
    QGroupBox, QScrollArea, QSizePolicy, QProgressDialog,
    QMessageBox, QFrame, QDoubleSpinBox,
    QFileDialog, QStatusBar, QLineEdit,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPointF
from PySide6.QtGui  import QPixmap, QImage, QPainter, QColor, QWheelEvent

# ---------------------------------------------------------------------------
# Mandatory: OpenImageIO  (fix #7 - CV2 EXR codec disabled in stock wheels)
# ---------------------------------------------------------------------------
try:
    import OpenImageIO as oiio   # type: ignore
    HAS_OIIO = True
except ImportError:
    HAS_OIIO = False

# ---------------------------------------------------------------------------
# Optional backends
# ---------------------------------------------------------------------------
try:
    from scipy.ndimage import gaussian_filter as _scipy_gaussian  # type: ignore
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    import cv2  # type: ignore  -- used ONLY for denoising (uint8), never for EXR
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import cupy as cp   # type: ignore  -- GPU acceleration
    HAS_CUPY = True
except ImportError:
    HAS_CUPY = False

# ---------------------------------------------------------------------------
# Dark VFX stylesheet
# ---------------------------------------------------------------------------
DARK_STYLE = """
QWidget {
    background-color:#252526; color:#cccccc;
    font-family:"Segoe UI","SF Pro Text",Arial,sans-serif; font-size:11px;
}
QMainWindow,QDialog { background-color:#1e1e1e; }
QGroupBox {
    border:1px solid #3a3a3a; border-radius:5px;
    margin-top:10px; padding:6px 4px 4px 4px;
    font-weight:bold; color:#8ab4e8; font-size:11px;
}
QGroupBox::title { subcontrol-origin:margin; subcontrol-position:top left;
    left:8px; padding:0 4px; }
QSlider::groove:horizontal { height:4px; background:#3c3c3c; border-radius:2px; }
QSlider::handle:horizontal {
    background:#4a90d9; border:1px solid #3a78bd;
    width:14px; height:14px; margin:-5px 0; border-radius:7px;
}
QSlider::handle:horizontal:hover  { background:#5aa0e8; }
QSlider::sub-page:horizontal      { background:#2a5f9e; border-radius:2px; }
QSlider::groove:horizontal:disabled  { background:#2a2a2a; }
QSlider::handle:horizontal:disabled  { background:#404040; border-color:#383838; }
QPushButton {
    background-color:#3c3c3c; border:1px solid #505050;
    border-radius:4px; padding:5px 14px; color:#cccccc; min-height:22px;
}
QPushButton:hover   { background-color:#4a4a4a; border-color:#606060; }
QPushButton:pressed { background-color:#2a2a2a; }
QPushButton:disabled{ background-color:#2e2e2e; color:#666; border-color:#383838; }
QPushButton#export_btn {
    background-color:#1e5c1e; border:1px solid #2a7a2a;
    color:#88ff88; font-weight:bold; font-size:12px;
    min-height:30px; padding:6px 20px;
}
QPushButton#export_btn:hover   { background-color:#256025; }
QPushButton#export_btn:pressed { background-color:#143314; }
QPushButton#export_btn:disabled{ background-color:#1a2e1a; color:#446644; }
QPushButton#reset_btn { background-color:#3a2828; border-color:#583838; color:#ffaaaa; }
QPushButton#reset_btn:hover { background-color:#4a3030; }
QPushButton#zoom_btn {
    background-color:#2a2a3a; border:1px solid #404060;
    color:#aaaaee; padding:2px 8px; min-height:18px; font-size:13px;
}
QPushButton#zoom_btn:hover { background-color:#333350; }
QComboBox {
    background-color:#333333; border:1px solid #505050;
    border-radius:4px; padding:4px 8px; min-height:22px;
}
QComboBox::drop-down { border:none; width:20px; }
QComboBox QAbstractItemView {
    background-color:#2d2d2d; selection-background-color:#3a6ea8;
    border:1px solid #505050;
}
QDoubleSpinBox {
    background-color:#2d2d2d; border:1px solid #484848;
    border-radius:3px; padding:2px 4px;
    min-width:54px; max-width:64px; min-height:20px;
}
QDoubleSpinBox:disabled { color:#555; background-color:#252525; }
QCheckBox::indicator {
    width:14px; height:14px; border:1px solid #555;
    border-radius:3px; background-color:#2d2d2d;
}
QCheckBox::indicator:checked { background-color:#2a5f9e; border-color:#4a90d9; }
QLabel#frame_label  { font-size:18px; font-weight:bold; color:#5bb0ff;
    qproperty-alignment:AlignCenter; }
QLabel#status_label { color:#aaaaaa; font-size:10px; padding:2px 6px; }
QLabel#section_title{ font-size:10px; color:#888888; font-weight:bold;
    letter-spacing:1px; padding:4px 0 2px 0; }
QScrollArea { border:none; }
QScrollBar:vertical { background:#1e1e1e; width:8px; border-radius:4px; }
QScrollBar::handle:vertical { background:#484848; border-radius:4px; min-height:20px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QFrame#separator { background-color:#3a3a3a; max-height:1px; }
QLineEdit {
    background-color:#2d2d2d; border:1px solid #484848;
    border-radius:3px; padding:3px 6px; color:#cccccc;
}
"""

# ---------------------------------------------------------------------------
# Sequence / path helpers
# ---------------------------------------------------------------------------

def expand_frame_path(seq_path: str, frame: int) -> str:
    if not seq_path:
        return ""
    if re.search(r'%\d*d', seq_path):
        try:
            return seq_path % frame
        except Exception:
            pass
    m = re.search(r'(#+)', seq_path)
    if m:
        hashes = m.group(1)
        return seq_path[:m.start()] + str(frame).zfill(len(hashes)) + seq_path[m.end():]
    return seq_path


def make_sequence_pattern(filepath: str) -> str:
    """
    /shots/seq.0042.exr  ->  /shots/seq.####.exr
    Replaces the last contiguous digit run in the filename with # chars.
    fix #5: 3DE Pattern field needs #### not an absolute frame path.
    """
    parent  = os.path.dirname(filepath)
    name    = os.path.basename(filepath)
    matches = list(re.finditer(r'\d+', name))
    if not matches:
        return filepath
    m       = matches[-1]
    pattern = name[:m.start()] + '#' * len(m.group()) + name[m.end():]
    return os.path.join(parent, pattern)


def suggest_output_dir(display_path: str) -> str:
    if not display_path:
        return ""
    return str(Path(display_path).parent) + "_filtered"


# ---------------------------------------------------------------------------
# Image I/O  --  OIIO only for EXR  (fix #7)
# ---------------------------------------------------------------------------

class ImageIO:

    @staticmethod
    def load(path: str) -> tuple[np.ndarray, dict]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Image not found: {path}")
        if not HAS_OIIO:
            raise RuntimeError(
                "OpenImageIO Python binding is required.\n"
                "Install:  pip install openimageio\n"
                "(The system OIIO binary is NOT sufficient.)"
            )
        inp = oiio.ImageInput.open(path)
        if inp is None:
            raise IOError(f"OIIO cannot open '{path}': {oiio.geterror()}")
        spec   = inp.spec()
        pixels = inp.read_image(oiio.FLOAT)
        inp.close()
        if pixels is None:
            raise IOError(f"OIIO read_image failed for '{path}'")
        if pixels.ndim == 2:
            pixels = pixels[:, :, np.newaxis]
        meta = {
            "width":        spec.width,
            "height":       spec.height,
            "nchannels":    spec.nchannels,
            "channelnames": list(spec.channelnames),
        }
        return pixels.astype(np.float32), meta

    @staticmethod
    def save(path: str, pixels: np.ndarray, metadata: dict | None = None):
        if not HAS_OIIO:
            raise RuntimeError("OpenImageIO is required for saving.")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        h, w = pixels.shape[:2]
        nc   = pixels.shape[2] if pixels.ndim == 3 else 1
        spec = oiio.ImageSpec(w, h, nc, oiio.FLOAT)
        spec.attribute("compression", "zips")
        if metadata and "channelnames" in metadata:
            spec.channelnames = metadata["channelnames"]
        out = oiio.ImageOutput.create(path)
        if out is None:
            raise IOError(f"OIIO cannot create '{path}': {oiio.geterror()}")
        out.open(path, spec)
        out.write_image(pixels)
        out.close()


# ---------------------------------------------------------------------------
# Performance helpers  (fix #1)
# ---------------------------------------------------------------------------

PREVIEW_MAX_PX = 1440   # longest-edge cap for interactive preview

def downscale_for_preview(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= PREVIEW_MAX_PX:
        return img
    scale = PREVIEW_MAX_PX / max(h, w)
    nh, nw = max(1, int(h * scale)), max(1, int(w * scale))
    if HAS_CV2:
        return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    # numpy nearest-neighbour fallback
    row_idx = np.linspace(0, h - 1, nh, dtype=int)
    col_idx = np.linspace(0, w - 1, nw, dtype=int)
    return img[np.ix_(row_idx, col_idx)]


# ---------------------------------------------------------------------------
# Gaussian blur  (scipy > cv2 > pure-numpy)
# ---------------------------------------------------------------------------

def _gaussian(img: np.ndarray, sigma: float) -> np.ndarray:
    if HAS_SCIPY:
        return _scipy_gaussian(img, sigma=sigma, mode='reflect')
    if HAS_CV2:
        k = max(3, int(sigma * 6) | 1)
        return cv2.GaussianBlur(img, (k, k), sigmaX=sigma, sigmaY=sigma)
    radius = max(1, int(sigma * 3))
    x      = np.arange(-radius, radius + 1, dtype=np.float32)
    kern   = np.exp(-x**2 / (2.0 * sigma**2))
    kern  /= kern.sum()
    result = np.copy(img)
    for ax in (0, 1):
        result = np.apply_along_axis(
            lambda v: np.convolve(v, kern, mode='same'), ax, result)
    return result


# ---------------------------------------------------------------------------
# Filter parameters
# ---------------------------------------------------------------------------

class FilterParams:
    def __init__(self):
        # 1. Denoise (runs first)
        self.denoise_enabled         = False
        self.denoise_h               = 10.0
        self.denoise_hcolor          = 10.0
        self.denoise_template_window = 7
        self.denoise_search_window   = 21

        # 2. Sharpness
        self.sharpen_enabled  = False
        self.sharpen_amount   = 1.0
        self.sharpen_radius   = 1.0

        # 3. High-Pass
        self.highpass_enabled = False
        self.highpass_amount  = 0.5
        self.highpass_radius  = 5.0

        # 4. Contrast / Brightness
        self.contrast_enabled  = False
        self.contrast_value    = 1.0
        self.brightness_value  = 0.0

    def copy(self) -> FilterParams:
        return copy.copy(self)


# ---------------------------------------------------------------------------
# Image processing pipeline
# ---------------------------------------------------------------------------

class ImageProcessor:
    """Order: Denoise -> Sharpen -> High-Pass -> Contrast"""

    @staticmethod
    def process(img: np.ndarray, params: FilterParams) -> np.ndarray:
        result = img.astype(np.float32)

        if params.denoise_enabled:
            result = ImageProcessor._denoise(
                result,
                params.denoise_h,
                params.denoise_hcolor,
                int(params.denoise_template_window),
                int(params.denoise_search_window),
            )
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

    # ── Denoise (fix #2) ──────────────────────────────────────────────────
    @staticmethod
    def _denoise(img: np.ndarray, h: float, hcolor: float,
                 tmpl_win: int, search_win: int) -> np.ndarray:
        """
        cv2.fastNlMeansDenoisingColored wrapped for float32 scene-linear EXR.
        Docs: https://docs.opencv.org/3.4/d1/d79/group__photo__denoise.html
        NLM operates on uint8 BGR. We normalise to [0,255], denoise, then
        invert-normalise to restore the original scene-linear scale.
        """
        if not HAS_CV2:
            return img

        # Ensure odd window sizes as required by NLM
        tmpl_win   = tmpl_win   if tmpl_win   % 2 == 1 else tmpl_win   + 1
        search_win = search_win if search_win % 2 == 1 else search_win + 1

        rgb_f   = np.clip(img[:, :, :3], 0, None).astype(np.float32)
        # Per-channel max to preserve HDR range after round-trip
        ch_max  = rgb_f.max(axis=(0, 1), keepdims=True).clip(1e-6)
        rgb_u8  = ((rgb_f / ch_max) * 255).astype(np.uint8)

        bgr_u8  = cv2.cvtColor(rgb_u8,  cv2.COLOR_RGB2BGR)
        bgr_den = cv2.fastNlMeansDenoisingColored(
            bgr_u8, None,
            h=float(h), hColor=float(hcolor),
            templateWindowSize=tmpl_win,
            searchWindowSize=search_win,
        )
        rgb_den = cv2.cvtColor(bgr_den, cv2.COLOR_BGR2RGB)

        # Restore scene-linear scale
        rgb_out = (rgb_den.astype(np.float32) / 255.0) * ch_max

        result           = img.copy()
        result[:, :, :3] = rgb_out
        return result

    # ── Sharpness ────────────────────────────────────────────────────────────
    @staticmethod
    def _unsharp_mask(img, amount, radius):
        blurred = _gaussian(img, sigma=radius)
        return img + amount * (img - blurred)

    # ── High-Pass ─────────────────────────────────────────────────────────────
    @staticmethod
    def _highpass(img, amount, radius):
        blurred = _gaussian(img, sigma=radius)
        return img + amount * (img - blurred)

    # ── Contrast / Brightness ─────────────────────────────────────────────────
    @staticmethod
    def _contrast(img, contrast, brightness):
        PIVOT = 0.18
        return PIVOT + contrast * (img - PIVOT) + brightness


# ---------------------------------------------------------------------------
# Tone-mapping (preview only)
# ---------------------------------------------------------------------------

def tonemap_display(img: np.ndarray, exposure: float = 0.0) -> np.ndarray:
    gain = 2.0 ** exposure
    rgb  = img[:, :, :3].astype(np.float32) * gain
    rgb  = rgb / (1.0 + rgb)
    np.clip(rgb, 0, 1, out=rgb)
    rgb  = np.where(rgb <= 0.0031308,
                    12.92 * rgb,
                    1.055 * np.power(rgb, 1.0 / 2.4) - 0.055)
    np.clip(rgb, 0, 1, out=rgb)
    return (rgb * 255).astype(np.uint8)


def numpy_to_qpixmap(arr: np.ndarray) -> QPixmap:
    arr  = np.ascontiguousarray(arr)
    h, w, _ = arr.shape
    qimg = QImage(arr.data, w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())   # .copy() detaches from numpy buffer


# ---------------------------------------------------------------------------
# 3DE camera API helpers
# ---------------------------------------------------------------------------

def get_all_cameras() -> list[tuple[str, str]]:
    cameras: list[tuple[str, str]] = []
    try:
        for cid in tde4.getCameraList():
            try:
                name = tde4.getCameraName(cid)
            except Exception:
                name = f"<cam {cid}>"
            cameras.append((cid, name))
        if cameras:
            return cameras
    except Exception:
        pass
    try:
        cam = tde4.getFirstCamera()
        while cam:
            try:
                name = tde4.getCameraName(cam)
            except Exception:
                name = f"<cam {cam}>"
            cameras.append((cam, name))
            cam = tde4.getNextCamera()
    except Exception:
        pass
    return cameras


def get_camera_sequence_info(cam_id: str) -> dict:
    info = {"display_path": "", "first_frame": 1, "last_frame": 1, "n_frames": 0}
    try:
        n = tde4.getCameraNoFrames(cam_id)
        if n:
            info["n_frames"]   = int(n)
            info["last_frame"] = int(n)
    except Exception:
        pass
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
    try:
        fp = tde4.getCameraFrameFilepath(cam_id, frame)
        return fp or ""
    except Exception:
        return ""


def set_camera_sequence_path(cam_id: str, pattern: str,
                             first_frame: int = 1, last_frame: int = 1):
    for fn_name in ("setCameraPath", "setCameraSequencePath",
                    "setSequencePath", "setCameraImagePath"):
        fn = getattr(tde4, fn_name, None)
        if fn:
            try:
                fn(cam_id, pattern)
                return
            except Exception:
                pass
    set_fn = getattr(tde4, "setCameraFrameFilepath", None)
    if set_fn:
        for f in range(first_frame, last_frame + 1):
            try:
                set_fn(cam_id, f, expand_frame_path(pattern, f))
            except Exception:
                pass
        return
    raise RuntimeError(
        f"No 3DE API found to set camera footage path.\n"
        f"Please set manually to:\n{pattern}"
    )


# ---------------------------------------------------------------------------
# Labeled float slider
# ---------------------------------------------------------------------------

class LabeledSlider(QWidget):
    valueChanged = Signal(float)

    def __init__(self, label: str, min_val: float, max_val: float,
                 default: float, decimals: int = 2, parent=None):
        super().__init__(parent)
        self._scale = 10 ** decimals

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        self.lbl = QLabel(label)
        self.lbl.setFixedWidth(82)
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignRight |
                               Qt.AlignmentFlag.AlignVCenter)
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
        self.spin.setFixedWidth(64)

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
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(fv * self._scale)))
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
# Labeled integer slider (for NLM odd window sizes)
# ---------------------------------------------------------------------------

class LabeledIntSlider(QWidget):
    valueChanged = Signal(float)   # emits float for uniform FilterGroup API

    def __init__(self, label: str, min_val: int, max_val: int,
                 default: int, step: int = 2, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        self.lbl = QLabel(label)
        self.lbl.setFixedWidth(82)
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignRight |
                               Qt.AlignmentFlag.AlignVCenter)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default)
        self.slider.setSingleStep(step)
        self.slider.setPageStep(step * 2)

        self.val_lbl = QLabel(str(default))
        self.val_lbl.setFixedWidth(28)
        self.val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.lbl)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.val_lbl)

        self.slider.valueChanged.connect(self._on_changed)

    def _on_changed(self, v: int):
        self.val_lbl.setText(str(v))
        self.valueChanged.emit(float(v))

    def value(self) -> float:
        return float(self.slider.value())

    def setValue(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(int(v))
        self.val_lbl.setText(str(int(v)))
        self.slider.blockSignals(False)

    def setEnabled(self, enabled: bool):
        self.slider.setEnabled(enabled)
        super().setEnabled(enabled)


# ---------------------------------------------------------------------------
# Filter Group
# ---------------------------------------------------------------------------

class FilterGroup(QGroupBox):
    paramsChanged = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 6)
        self._layout.setSpacing(2)

        self.enable_cb = QCheckBox("Enable")
        self.enable_cb.setChecked(False)
        self._layout.addWidget(self.enable_cb)

        self._sliders: dict[str, LabeledSlider | LabeledIntSlider] = {}
        self.enable_cb.toggled.connect(self._on_toggle)

    def add_slider(self, key: str,
                   slider: LabeledSlider | LabeledIntSlider):
        slider.setEnabled(False)
        self._sliders[key] = slider
        self._layout.addWidget(slider)
        slider.valueChanged.connect(lambda _: self.paramsChanged.emit())

    def _on_toggle(self, checked: bool):
        for s in self._sliders.values():
            s.setEnabled(checked)
        self.paramsChanged.emit()

    def is_enabled(self) -> bool:
        return self.enable_cb.isChecked()

    def get_value(self, key: str):
        return self._sliders[key].value()

    def set_value(self, key: str, v):
        self._sliders[key].setValue(v)

    def set_group_enabled(self, enabled: bool):
        """Set enabled state silently (no paramsChanged signal)."""
        self.enable_cb.blockSignals(True)
        self.enable_cb.setChecked(enabled)
        for s in self._sliders.values():
            s.setEnabled(enabled)
        self.enable_cb.blockSignals(False)


# ---------------------------------------------------------------------------
# Image Viewer  with zoom + pan  (fix #3)
# ---------------------------------------------------------------------------

class ImageViewer(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap_filtered: QPixmap | None = None
        self._pixmap_original: QPixmap | None = None
        self._show_original = False

        self._zoom   = 1.0
        self._offset = QPointF(0.0, 0.0)
        self._drag_start: QPointF | None = None
        self._drag_offset_start = QPointF(0.0, 0.0)

        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color:#111111;")
        self.setMouseTracking(True)

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

    def reset_zoom(self):
        self._zoom   = 1.0
        self._offset = QPointF(0.0, 0.0)
        self.update()

    def zoom_in(self):
        self._apply_zoom(1.25)

    def zoom_out(self):
        self._apply_zoom(0.8)

    def _apply_zoom(self, factor: float, center: QPointF | None = None):
        if center is None:
            center = QPointF(self.width() / 2.0, self.height() / 2.0)
        old_zoom     = self._zoom
        self._zoom   = max(0.05, min(self._zoom * factor, 32.0))
        scale_change = self._zoom / old_zoom
        self._offset = center + (self._offset - center) * scale_change
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111111"))
        pm = (self._pixmap_original if self._show_original
              else self._pixmap_filtered)
        if not pm or pm.isNull():
            painter.setPen(QColor("#555555"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No image loaded")
            return
        dw = pm.width()  * self._zoom
        dh = pm.height() * self._zoom
        x  = (self.width()  - dw) / 2 + self._offset.x()
        y  = (self.height() - dh) / 2 + self._offset.y()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(int(x), int(y), int(dw), int(dh), pm)
        painter.setPen(QColor(180, 180, 180, 160))
        painter.drawText(6, self.height() - 6, f"{self._zoom * 100:.0f}%")

    def resizeEvent(self, event):
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        delta  = event.angleDelta().y()
        factor = 1.12 if delta > 0 else (1.0 / 1.12)
        self._apply_zoom(factor, QPointF(event.position()))
        event.accept()

    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.MiddleButton,
                               Qt.MouseButton.LeftButton):
            self._drag_start        = QPointF(event.position())
            self._drag_offset_start = QPointF(self._offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            delta        = QPointF(event.position()) - self._drag_start
            self._offset = self._drag_offset_start + delta
            self.update()

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event):
        self.reset_zoom()


# ---------------------------------------------------------------------------
# Background threads
# ---------------------------------------------------------------------------

class FrameLoaderThread(QThread):
    """
    Loads one EXR frame from disk without blocking the main thread.
    fix #4: frame slider crash was caused by synchronous disk I/O on the
    main thread locking Qt/3DE's event loop.
    """
    loaded = Signal(object, str, int)   # (np.ndarray pixels, path, frame)
    error  = Signal(str, int)

    def __init__(self, cam_id: str, frame: int):
        super().__init__()
        self._cam_id = cam_id
        self._frame  = frame
        self._abort  = False

    def abort(self):
        self._abort = True

    def run(self):
        if self._abort:
            return
        path = get_camera_frame_filepath(self._cam_id, self._frame)
        if not path:
            self.error.emit(
                f"Frame {self._frame}: getCameraFrameFilepath returned empty.",
                self._frame)
            return
        try:
            pixels, _ = ImageIO.load(path)
            if not self._abort:
                self.loaded.emit(pixels, path, self._frame)
        except Exception as e:
            if not self._abort:
                self.error.emit(str(e), self._frame)


class PreviewThread(QThread):
    """
    Runs filter stack + tonemapping in a background thread.
    fix #4: never blocks main thread.
    fix #6: emits done so _on_preview_done can re-trigger if dirty.
    """
    done  = Signal(object, object)   # orig_uint8, filtered_uint8 (np arrays)
    error = Signal(str)

    def __init__(self, img_float: np.ndarray,
                 params: FilterParams, exposure: float):
        super().__init__()
        self._img      = img_float
        self._params   = params.copy()
        self._exposure = exposure
        self._abort    = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            small = downscale_for_preview(self._img)   # fix #1
            if self._abort:
                return
            orig_u8 = tonemap_display(small, self._exposure)
            if self._abort:
                return
            filtered = ImageProcessor.process(small, self._params)
            if self._abort:
                return
            filt_u8  = tonemap_display(filtered, self._exposure)
            if not self._abort:
                self.done.emit(orig_u8, filt_u8)
        except Exception as e:
            if not self._abort:
                self.error.emit(
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


class ExportThread(QThread):
    """
    Full-resolution export with parallel frame processing (fix #1).
    """
    progress    = Signal(int, str)       # (frames_done, message)
    finished_ok = Signal(str, str)       # (output_dir, #### pattern)
    error       = Signal(str)

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

    def _process_frame(self, frame: int) -> tuple[bool, str]:
        if self._abort:
            return False, ""
        in_path = get_camera_frame_filepath(self._cam_id, frame)
        if not in_path:
            return True, ""
        out_path = os.path.join(self._output_dir, os.path.basename(in_path))
        try:
            pixels, meta = ImageIO.load(in_path)
            filtered     = ImageProcessor.process(pixels, self._params)
            ImageIO.save(out_path, filtered, meta)
            return True, out_path
        except FileNotFoundError:
            return True, ""
        except Exception as e:
            raise RuntimeError(f"Frame {frame}: {e}") from e

    def run(self):
        try:
            os.makedirs(self._output_dir, exist_ok=True)
            frames      = list(range(self._first, self._last + 1))
            total       = len(frames)
            first_out   = ""
            frames_done = 0

            max_workers = min(4, os.cpu_count() or 2)
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers) as pool:
                future_map = {pool.submit(self._process_frame, f): f
                              for f in frames}
                for future in concurrent.futures.as_completed(future_map):
                    if self._abort:
                        pool.shutdown(wait=False, cancel_futures=True)
                        self.error.emit("Export cancelled.")
                        return
                    ok, out_path = future.result()
                    if out_path and not first_out:
                        first_out = out_path
                    frames_done += 1
                    f = future_map[future]
                    self.progress.emit(
                        frames_done,
                        f"Frame {f}  ({frames_done}/{total})  "
                        f"-> {os.path.basename(out_path) if out_path else 'skipped'}"
                    )

            # fix #5: build #### pattern from first exported path
            out_pattern = make_sequence_pattern(first_out) if first_out else ""
            self.finished_ok.emit(self._output_dir, out_pattern)

        except Exception as e:
            self.error.emit(
                f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class FilterToolkitWindow(QMainWindow):

    def __init__(self, cam_id: str, cam_name: str):
        super().__init__()
        self.setWindowTitle(
            f"R_Tools  Image Filter Toolkit  v2.0  [{cam_name}]")
        self.resize(1480, 900)
        self.setStyleSheet(DARK_STYLE)

        self._cam_id   = cam_id
        self._cam_name = cam_name
        self._seq_info = get_camera_sequence_info(cam_id)

        self._current_frame_img: np.ndarray | None = None
        self._current_frame: int = self._seq_info["first_frame"]
        self._pending_frame: int = self._seq_info["first_frame"]

        self._loader_thread:  FrameLoaderThread | None = None
        self._preview_thread: PreviewThread     | None = None
        self._export_thread:  ExportThread      | None = None
        self._preview_dirty = False   # fix #6

        # fix #4: debounce frame loading so slider drag doesn't spawn a thread
        # per pixel moved
        self._frame_debounce = QTimer()
        self._frame_debounce.setSingleShot(True)
        self._frame_debounce.timeout.connect(self._do_load_frame)

        self._preview_debounce = QTimer()
        self._preview_debounce.setSingleShot(True)
        self._preview_debounce.timeout.connect(self._trigger_preview)

        self._params = FilterParams()
        self._build_ui()

        # Kick off first frame load asynchronously
        self._do_load_frame()

    # ================================================================= UI ===

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left control panel ──────────────────────────────────────────────
        ctrl_scroll = QScrollArea()
        ctrl_scroll.setWidgetResizable(True)
        ctrl_scroll.setFixedWidth(326)
        ctrl_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(10, 10, 10, 10)
        ctrl_layout.setSpacing(6)
        ctrl_scroll.setWidget(ctrl_widget)

        # Camera info
        info_lbl = QLabel(
            f"<b>{self._cam_name}</b><br>"
            f"<span style='color:#888;font-size:10px;'>"
            f"{self._seq_info['display_path'] or 'No footage path detected'}"
            f"</span>")
        info_lbl.setWordWrap(True)
        ctrl_layout.addWidget(info_lbl)
        ctrl_layout.addWidget(self._sep())

        # Frame selector
        frame_grp = QGroupBox("Frame")
        fl = QVBoxLayout(frame_grp)
        fl.setSpacing(4)
        self._frame_display = QLabel(str(self._seq_info["first_frame"]))
        self._frame_display.setObjectName("frame_label")
        fl.addWidget(self._frame_display)

        self._frame_slider = QSlider(Qt.Orientation.Horizontal)
        first = self._seq_info["first_frame"]
        last  = max(self._seq_info["last_frame"], first + 1)
        self._frame_slider.setRange(first, last)
        self._frame_slider.setValue(first)
        self._frame_slider.setSingleStep(1)
        # fix #4: debounced — does NOT call _load_frame directly
        self._frame_slider.valueChanged.connect(self._on_frame_slider_changed)
        fl.addWidget(self._frame_slider)

        rng_lbl = QLabel(f"Range:  {first}  –  {self._seq_info['last_frame']}")
        rng_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rng_lbl.setStyleSheet("color:#777;font-size:10px;")
        fl.addWidget(rng_lbl)
        ctrl_layout.addWidget(frame_grp)

        # Display options
        disp_grp = QGroupBox("Display  (preview only)")
        dl = QVBoxLayout(disp_grp)
        dl.setSpacing(2)
        self._exposure_slider = LabeledSlider("Exposure", -6.0, 6.0, 0.0, 2)
        self._exposure_slider.valueChanged.connect(
            lambda _: self._schedule_preview())
        dl.addWidget(self._exposure_slider)

        self._compare_btn = QPushButton("Hold  [ Original ]")
        self._compare_btn.setCheckable(True)
        self._compare_btn.toggled.connect(self._on_compare_toggled)
        dl.addWidget(self._compare_btn)
        ctrl_layout.addWidget(disp_grp)
        ctrl_layout.addWidget(self._sep())

        # ── Filter groups ────────────────────────────────────────────────────
        ctrl_layout.addWidget(self._section("FILTERS  (applied in order)"))

        # 1. Denoise  (fix #2)
        self._denoise_grp = FilterGroup("①  Denoise  (NL-Means)")
        self._denoise_grp.add_slider("h",
            LabeledSlider("Lum. str.",   1.0, 30.0, 10.0, decimals=1))
        self._denoise_grp.add_slider("hcolor",
            LabeledSlider("Color str.",  1.0, 30.0, 10.0, decimals=1))
        self._denoise_grp.add_slider("template_win",
            LabeledIntSlider("Tmpl win", 3, 21, 7, step=2))
        self._denoise_grp.add_slider("search_win",
            LabeledIntSlider("Search win", 7, 35, 21, step=2))
        self._denoise_grp.paramsChanged.connect(self._on_filter_changed)
        if not HAS_CV2:
            self._denoise_grp.setToolTip(
                "OpenCV not installed — denoising unavailable.\n"
                "pip install opencv-python")
            self._denoise_grp.setEnabled(False)
        ctrl_layout.addWidget(self._denoise_grp)

        # 2. Sharpness
        self._sharpen_grp = FilterGroup("②  Sharpness  (Unsharp Mask)")
        self._sharpen_grp.add_slider("amount",
            LabeledSlider("Amount",    0.0, 3.0, 1.0, decimals=2))
        self._sharpen_grp.add_slider("radius",
            LabeledSlider("Radius px", 0.3, 5.0, 1.0, decimals=2))
        self._sharpen_grp.paramsChanged.connect(self._on_filter_changed)
        ctrl_layout.addWidget(self._sharpen_grp)

        # 3. High-Pass
        self._highpass_grp = FilterGroup("③  High-Pass  (Detail Layer)")
        self._highpass_grp.add_slider("amount",
            LabeledSlider("Amount",    0.0, 2.0, 0.5, decimals=2))
        self._highpass_grp.add_slider("radius",
            LabeledIntSlider("Radius px", 1, 25, 5, step=1))
        self._highpass_grp.paramsChanged.connect(self._on_filter_changed)
        ctrl_layout.addWidget(self._highpass_grp)

        # 4. Contrast
        self._contrast_grp = FilterGroup("④  Contrast  /  Brightness")
        self._contrast_grp.add_slider("contrast",
            LabeledSlider("Contrast",   0.25, 3.0, 1.0, decimals=2))
        self._contrast_grp.add_slider("brightness",
            LabeledSlider("Brightness", -1.0, 1.0, 0.0, decimals=3))
        self._contrast_grp.paramsChanged.connect(self._on_filter_changed)
        ctrl_layout.addWidget(self._contrast_grp)

        ctrl_layout.addWidget(self._sep())

        # ── Export ──────────────────────────────────────────────────────────
        ctrl_layout.addWidget(self._section("EXPORT"))

        out_grp = QGroupBox("Output Directory")
        ol = QVBoxLayout(out_grp)
        self._out_dir_edit = QLineEdit(
            suggest_output_dir(self._seq_info["display_path"]))
        self._out_dir_edit.setPlaceholderText("/path/to/filtered_output")
        ol.addWidget(self._out_dir_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_output_dir)
        ol.addWidget(browse_btn)
        ctrl_layout.addWidget(out_grp)

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

        self._status_lbl = QLabel("Ready.")
        self._status_lbl.setObjectName("status_label")
        self._status_lbl.setWordWrap(True)
        ctrl_layout.addWidget(self._status_lbl)
        ctrl_layout.addStretch(1)

        # ── Right: zoom bar + viewer ─────────────────────────────────────────
        viewer_container = QWidget()
        vc_layout = QVBoxLayout(viewer_container)
        vc_layout.setContentsMargins(0, 0, 0, 0)
        vc_layout.setSpacing(0)

        # Zoom toolbar  (fix #3)
        zoom_bar = QWidget()
        zoom_bar.setFixedHeight(30)
        zoom_bar.setStyleSheet("background:#1a1a1a;")
        zbl = QHBoxLayout(zoom_bar)
        zbl.setContentsMargins(6, 2, 6, 2)
        zbl.setSpacing(4)
        for txt, cb in (
            ("−",   lambda: self._viewer.zoom_out()),
            ("+",   lambda: self._viewer.zoom_in()),
            ("1:1", lambda: self._set_zoom_1to1()),
            ("Fit", lambda: self._viewer.reset_zoom()),
        ):
            b = QPushButton(txt)
            b.setObjectName("zoom_btn")
            b.setFixedWidth(36)
            b.clicked.connect(cb)
            zbl.addWidget(b)
        zbl.addStretch(1)
        hint = QLabel("Scroll = zoom  ·  Drag = pan  ·  Dbl-click = fit")
        hint.setStyleSheet("color:#555;font-size:10px;")
        zbl.addWidget(hint)

        self._viewer = ImageViewer()
        vc_layout.addWidget(zoom_bar)
        vc_layout.addWidget(self._viewer, 1)

        root.addWidget(ctrl_scroll)
        root.addWidget(viewer_container, 1)

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        caps = []
        caps.append("OIIO ✓" if HAS_OIIO else "OIIO ✗ (REQUIRED)")
        caps.append("OpenCV ✓" if HAS_CV2   else "OpenCV ✗ (denoise off)")
        if HAS_SCIPY:  caps.append("scipy ✓")
        if HAS_CUPY:   caps.append("GPU/CuPy ✓")
        self._statusbar.showMessage("  |  ".join(caps))

    def _sep(self) -> QFrame:
        f = QFrame()
        f.setObjectName("separator")
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFixedHeight(1)
        return f

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section_title")
        return lbl

    def _set_zoom_1to1(self):
        self._viewer._zoom   = 1.0
        self._viewer._offset = QPointF(0.0, 0.0)
        self._viewer.update()

    # ============================================================== Slots ===

    def _on_frame_slider_changed(self, frame: int):
        """fix #4: only update label immediately; debounce the actual load."""
        self._frame_display.setText(str(frame))
        self._pending_frame = frame
        self._frame_debounce.stop()
        self._frame_debounce.start(180)

    def _do_load_frame(self):
        """Start background EXR load (fix #4)."""
        frame = self._pending_frame
        self._current_frame = frame

        # Abort stale loader
        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.abort()
            try:
                self._loader_thread.loaded.disconnect()
                self._loader_thread.error.disconnect()
            except Exception:
                pass

        self._set_status(f"Loading frame {frame} …")
        t = FrameLoaderThread(self._cam_id, frame)
        t.loaded.connect(self._on_frame_loaded)
        t.error.connect(self._on_frame_load_error)
        self._loader_thread = t
        t.start()

    def _on_frame_loaded(self, pixels: np.ndarray, path: str, frame: int):
        if frame != self._current_frame:
            return   # stale result from aborted load
        self._current_frame_img = pixels
        self._set_status(
            f"Frame {frame}   {pixels.shape[1]}x{pixels.shape[0]}"
            f"  ch:{pixels.shape[2]}   {os.path.basename(path)}")
        self._schedule_preview(immediate=True)

    def _on_frame_load_error(self, msg: str, frame: int):
        if frame != self._current_frame:
            return
        self._current_frame_img = None
        self._set_status(f"Load error: {msg}")

    def _on_filter_changed(self):
        self._collect_params()
        self._schedule_preview()

    def _on_compare_toggled(self, checked: bool):
        self._viewer.show_original(checked)
        self._compare_btn.setText("Release  [ Filtered ]" if checked
                                  else "Hold  [ Original ]")

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self._out_dir_edit.text())
        if d:
            self._out_dir_edit.setText(d)

    def _reset_params(self):
        """Reset all params silently, then force a single re-render (fix #6)."""
        for grp in (self._denoise_grp, self._sharpen_grp,
                    self._highpass_grp, self._contrast_grp):
            grp.set_group_enabled(False)

        self._denoise_grp.set_value("h",            10.0)
        self._denoise_grp.set_value("hcolor",        10.0)
        self._denoise_grp.set_value("template_win",  7)
        self._denoise_grp.set_value("search_win",    21)
        self._sharpen_grp.set_value("amount",        1.0)
        self._sharpen_grp.set_value("radius",        1.0)
        self._highpass_grp.set_value("amount",       0.5)
        self._highpass_grp.set_value("radius",       5)
        self._contrast_grp.set_value("contrast",     1.0)
        self._contrast_grp.set_value("brightness",   0.0)
        self._exposure_slider.setValue(0.0)

        self._collect_params()
        self._schedule_preview(immediate=True)   # fix #6: force re-render now

    # ============================================================= Logic ===

    def _collect_params(self):
        p = self._params
        p.denoise_enabled         = self._denoise_grp.is_enabled()
        p.denoise_h               = self._denoise_grp.get_value("h")
        p.denoise_hcolor          = self._denoise_grp.get_value("hcolor")
        p.denoise_template_window = int(self._denoise_grp.get_value("template_win"))
        p.denoise_search_window   = int(self._denoise_grp.get_value("search_win"))
        p.sharpen_enabled         = self._sharpen_grp.is_enabled()
        p.sharpen_amount          = self._sharpen_grp.get_value("amount")
        p.sharpen_radius          = self._sharpen_grp.get_value("radius")
        p.highpass_enabled        = self._highpass_grp.is_enabled()
        p.highpass_amount         = self._highpass_grp.get_value("amount")
        p.highpass_radius         = float(self._highpass_grp.get_value("radius"))
        p.contrast_enabled        = self._contrast_grp.is_enabled()
        p.contrast_value          = self._contrast_grp.get_value("contrast")
        p.brightness_value        = self._contrast_grp.get_value("brightness")

    def _schedule_preview(self, immediate: bool = False):
        self._preview_debounce.stop()
        if immediate:
            self._trigger_preview()
        else:
            self._preview_debounce.start(220)

    def _trigger_preview(self):
        """
        Launch preview render thread.
        fix #6: if already running, mark dirty so _on_preview_done re-triggers.
        """
        if self._current_frame_img is None:
            return
        if self._preview_thread and self._preview_thread.isRunning():
            self._preview_dirty = True
            return
        self._preview_dirty = False
        self._collect_params()
        t = PreviewThread(self._current_frame_img, self._params,
                          self._exposure_slider.value())
        t.done.connect(self._on_preview_done)
        t.error.connect(lambda msg: self._set_status(f"Preview error: {msg}"))
        self._preview_thread = t
        t.start()

    def _on_preview_done(self, orig_u8, filt_u8):
        self._viewer.set_original(numpy_to_qpixmap(orig_u8))
        self._viewer.set_filtered(numpy_to_qpixmap(filt_u8))
        self._preview_thread = None
        # fix #6: re-render if params changed while previous render was running
        if self._preview_dirty:
            self._preview_dirty = False
            self._trigger_preview()

    # ============================================================= Export ===

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
        if QMessageBox.question(
            self, "Confirm Export",
            f"Export  <b>{total}</b>  frame(s) to:<br><br>"
            f"<tt>{out_dir}</tt><br><br>"
            f"3DE footage path will be updated automatically after export.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        ) != QMessageBox.StandardButton.Yes:
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

    def _on_export_progress(self, done: int, msg: str):
        if hasattr(self, "_progress_dlg"):
            self._progress_dlg.setValue(done)
            self._progress_dlg.setLabelText(msg)
        self._set_status(msg)

    def _on_export_done(self, output_dir: str, out_pattern: str):
        self._export_btn.setEnabled(True)
        if hasattr(self, "_progress_dlg"):
            self._progress_dlg.close()

        # Update 3DE camera footage path using #### pattern  (fix #5)
        try:
            set_camera_sequence_path(
                self._cam_id,
                out_pattern,
                self._seq_info["first_frame"],
                self._seq_info["last_frame"],
            )
            try:
                tde4.updateGUI(0)
            except Exception:
                pass
            self._seq_info["display_path"] = out_pattern
            self._set_status(f"Export done. Pattern: {out_pattern}")
            QMessageBox.information(
                self, "Export Complete",
                f"Frames written to:\n{output_dir}\n\n"
                f"3DE footage path updated to:\n{out_pattern}"
            )
        except Exception as e:
            self._set_status(f"Export done – 3DE update failed: {e}")
            QMessageBox.warning(
                self, "3DE Update Failed",
                f"Frames exported to:\n{output_dir}\n\n"
                f"Could not update 3DE camera path automatically:\n{e}\n\n"
                f"Please set the footage path manually to:\n{out_pattern}"
            )

        # fix #6: reload current frame from new location to re-enable preview
        self._pending_frame = self._current_frame
        self._do_load_frame()

    def _on_export_error(self, msg: str):
        self._export_btn.setEnabled(True)
        if hasattr(self, "_progress_dlg"):
            self._progress_dlg.close()
        self._set_status("Export failed.")
        QMessageBox.critical(self, "Export Error", msg)

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)
        self._statusbar.showMessage(msg, 8000)

    def closeEvent(self, event):
        if self._export_thread and self._export_thread.isRunning():
            if QMessageBox.question(
                self, "Export Running",
                "An export is in progress. Cancel and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes:
                self._export_thread.abort()
                self._export_thread.wait(4000)
            else:
                event.ignore()
                return
        for t in (self._loader_thread, self._preview_thread):
            if t and t.isRunning():
                if hasattr(t, 'abort'):
                    t.abort()
                t.wait(2000)
        event.accept()


# ---------------------------------------------------------------------------
# Camera Picker Dialog
# ---------------------------------------------------------------------------

class CameraPickerDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("R_Tools  Image Filter Toolkit  v2.0")
        self.setFixedSize(480, 200)
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
        self._select_btn = QPushButton("Open Filter Toolkit  ->")
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
            self._info_lbl.setText("No cameras found in the current project.")
            self._select_btn.setEnabled(False)
            return
        for cam_id, cam_name in self._cameras:
            self._cam_combo.addItem(cam_name, userData=cam_id)
        self._on_cam_selected(0)

    def _on_cam_selected(self, idx: int):
        if 0 <= idx < len(self._cameras):
            cam_id, _ = self._cameras[idx]
            info = get_camera_sequence_info(cam_id)
            path = info["display_path"] or "(no footage path detected)"
            n    = info["n_frames"]
            frames_str = (
                f"Frames: {info['first_frame']} - {info['last_frame']}  ({n} frames)"
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
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = QApplication.instance() or QApplication(sys.argv)

    # fix #7: OIIO Python binding is required (system binary alone is not enough)
    if not HAS_OIIO:
        QMessageBox.critical(
            None,
            "OpenImageIO Python Binding Required",
            "R_Tools Image Filter Toolkit requires the OpenImageIO Python binding.\n\n"
            "Install it with:\n"
            "    pip install openimageio\n\n"
            "Note: having the system OIIO binary on PATH is NOT sufficient.\n"
            "The Python package must be installed into 3DE's Python environment."
        )
        return

    if not HAS_CV2:
        QMessageBox.information(
            None,
            "OpenCV Not Found  (optional)",
            "OpenCV is not installed.\n\n"
            "The Denoise filter will be unavailable.\n"
            "All other filters (Sharpen, High-Pass, Contrast) work normally.\n\n"
            "To enable denoising:\n"
            "    pip install opencv-python"
        )

    picker = CameraPickerDialog()
    if picker.exec() != QDialog.DialogCode.Accepted:
        return
    cam_id, cam_name = picker.selected_camera()
    if not cam_id:
        return

    win = FilterToolkitWindow(cam_id, cam_name)
    win.show()
    win.raise_()
    win.activateWindow()

    if not hasattr(main, "_windows"):
        main._windows = []
    main._windows.append(win)

    if not QApplication.instance().property("tde4_managed"):
        try:
            app.exec()
        except Exception:
            pass


if __name__ == "__main__":
    main()
