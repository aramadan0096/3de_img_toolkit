from __future__ import annotations

import os
import sys

from PySide6.QtCore import QPointF, QTimer, Qt  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

import tde4  # type: ignore

from .deps import HAS_CUPY, HAS_CV2, HAS_OIIO, HAS_SCIPY, np
from .display import numpy_to_qpixmap
from .io_utils import SUPPORTED_EXPORT_EXTS, normalize_export_ext, suggest_output_dir
from .processing import FilterParams
from .styles import DARK_STYLE
from .tde_helpers import (
    get_all_cameras,
    get_camera_sequence_info,
    set_camera_sequence_path,
)
from .threads import ExportThread, FrameLoaderThread, PreviewThread
from .widgets import FilterGroup, ImageViewer, LabeledIntSlider, LabeledSlider


class FilterToolkitWindow(QMainWindow):
    def __init__(self, cam_id: str, cam_name: str):
        super().__init__()
        self.setWindowTitle(f"R_Tools  Image Filter Toolkit  v2.0  [{cam_name}]")
        self.resize(1480, 900)
        self.setStyleSheet(DARK_STYLE)

        self._cam_id = cam_id
        self._cam_name = cam_name
        self._seq_info = get_camera_sequence_info(cam_id)

        self._current_frame_img: np.ndarray | None = None
        self._current_frame: int = self._seq_info["first_frame"]
        self._pending_frame: int = self._seq_info["first_frame"]

        self._loader_thread: FrameLoaderThread | None = None
        self._preview_thread: PreviewThread | None = None
        self._export_thread: ExportThread | None = None
        self._preview_dirty = False

        self._frame_debounce = QTimer()
        self._frame_debounce.setSingleShot(True)
        self._frame_debounce.timeout.connect(self._do_load_frame)

        self._preview_debounce = QTimer()
        self._preview_debounce.setSingleShot(True)
        self._preview_debounce.timeout.connect(self._trigger_preview)

        self._params = FilterParams()
        self._build_ui()
        self._do_load_frame()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        ctrl_scroll = QScrollArea()
        ctrl_scroll.setWidgetResizable(True)
        ctrl_scroll.setFixedWidth(326)
        ctrl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(10, 10, 10, 10)
        ctrl_layout.setSpacing(6)
        ctrl_scroll.setWidget(ctrl_widget)

        info_lbl = QLabel(
            f"<b>{self._cam_name}</b><br>"
            f"<span style='color:#888;font-size:10px;'>"
            f"{self._seq_info['display_path'] or 'No footage path detected'}"
            f"</span>"
        )
        info_lbl.setWordWrap(True)
        ctrl_layout.addWidget(info_lbl)
        ctrl_layout.addWidget(self._sep())

        frame_grp = QGroupBox("Frame")
        fl = QVBoxLayout(frame_grp)
        fl.setSpacing(4)
        self._frame_display = QLabel(str(self._seq_info["first_frame"]))
        self._frame_display.setObjectName("frame_label")
        fl.addWidget(self._frame_display)

        self._frame_slider = QSlider(Qt.Orientation.Horizontal)
        first = self._seq_info["first_frame"]
        last = max(self._seq_info["last_frame"], first + 1)
        self._frame_slider.setRange(first, last)
        self._frame_slider.setValue(first)
        self._frame_slider.setSingleStep(1)
        self._frame_slider.valueChanged.connect(self._on_frame_slider_changed)
        fl.addWidget(self._frame_slider)

        rng_lbl = QLabel(f"Range:  {first}  -  {self._seq_info['last_frame']}")
        rng_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rng_lbl.setStyleSheet("color:#777;font-size:10px;")
        fl.addWidget(rng_lbl)
        ctrl_layout.addWidget(frame_grp)

        disp_grp = QGroupBox("Display  (preview only)")
        dl = QVBoxLayout(disp_grp)
        dl.setSpacing(2)
        self._exposure_slider = LabeledSlider("Exposure", -6.0, 6.0, 0.0, 2)
        self._exposure_slider.valueChanged.connect(lambda _: self._schedule_preview())
        dl.addWidget(self._exposure_slider)

        self._compare_btn = QPushButton("Hold  [ Original ]")
        self._compare_btn.setCheckable(True)
        self._compare_btn.toggled.connect(self._on_compare_toggled)
        dl.addWidget(self._compare_btn)
        ctrl_layout.addWidget(disp_grp)
        ctrl_layout.addWidget(self._sep())

        ctrl_layout.addWidget(self._section("FILTERS  (applied in order)"))

        self._denoise_grp = FilterGroup("1  Denoise  (NL-Means)")
        self._denoise_grp.add_slider("h", LabeledSlider("Lum. str.", 1.0, 30.0, 10.0, decimals=1))
        self._denoise_grp.add_slider("hcolor", LabeledSlider("Color str.", 1.0, 30.0, 10.0, decimals=1))
        self._denoise_grp.add_slider("template_win", LabeledIntSlider("Tmpl win", 3, 21, 7, step=2))
        self._denoise_grp.add_slider("search_win", LabeledIntSlider("Search win", 7, 35, 21, step=2))
        self._denoise_grp.paramsChanged.connect(self._on_filter_changed)
        if not HAS_CV2:
            self._denoise_grp.setToolTip("OpenCV not installed - denoising unavailable.\npip install opencv-python")
            self._denoise_grp.setEnabled(False)
        ctrl_layout.addWidget(self._denoise_grp)

        self._sharpen_grp = FilterGroup("2  Sharpness  (Unsharp Mask)")
        self._sharpen_grp.add_slider("amount", LabeledSlider("Amount", 0.0, 3.0, 1.0, decimals=2))
        self._sharpen_grp.add_slider("radius", LabeledSlider("Radius px", 0.3, 5.0, 1.0, decimals=2))
        self._sharpen_grp.paramsChanged.connect(self._on_filter_changed)
        ctrl_layout.addWidget(self._sharpen_grp)

        self._highpass_grp = FilterGroup("3  High-Pass  (Detail Layer)")
        self._highpass_grp.add_slider("amount", LabeledSlider("Amount", 0.0, 2.0, 0.5, decimals=2))
        self._highpass_grp.add_slider("radius", LabeledIntSlider("Radius px", 1, 25, 5, step=1))
        self._highpass_grp.paramsChanged.connect(self._on_filter_changed)
        ctrl_layout.addWidget(self._highpass_grp)

        self._contrast_grp = FilterGroup("4  Contrast  /  Brightness")
        self._contrast_grp.add_slider("contrast", LabeledSlider("Contrast", 0.25, 3.0, 1.0, decimals=2))
        self._contrast_grp.add_slider("brightness", LabeledSlider("Brightness", -1.0, 1.0, 0.0, decimals=3))
        self._contrast_grp.paramsChanged.connect(self._on_filter_changed)
        ctrl_layout.addWidget(self._contrast_grp)

        ctrl_layout.addWidget(self._sep())
        ctrl_layout.addWidget(self._section("EXPORT"))

        out_grp = QGroupBox("Output Directory")
        ol = QVBoxLayout(out_grp)
        self._out_dir_edit = QLineEdit(suggest_output_dir(self._seq_info["display_path"]))
        self._out_dir_edit.setPlaceholderText("/path/to/filtered_output")
        ol.addWidget(self._out_dir_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output_dir)
        ol.addWidget(browse_btn)

        self._export_ext_combo = QComboBox()
        self._export_ext_combo.addItem("Same as input", userData="")
        for ext in sorted(SUPPORTED_EXPORT_EXTS):
            self._export_ext_combo.addItem(ext, userData=ext)
        ol.addWidget(QLabel("Export extension"))
        ol.addWidget(self._export_ext_combo)
        ctrl_layout.addWidget(out_grp)

        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset All")
        reset_btn.setObjectName("reset_btn")
        reset_btn.clicked.connect(self._reset_params)
        btn_row.addWidget(reset_btn)

        self._export_btn = QPushButton("Export Sequence")
        self._export_btn.setObjectName("export_btn")
        self._export_btn.clicked.connect(self._start_export)
        btn_row.addWidget(self._export_btn, 1)
        ctrl_layout.addLayout(btn_row)

        self._status_lbl = QLabel("Ready.")
        self._status_lbl.setObjectName("status_label")
        self._status_lbl.setWordWrap(True)
        ctrl_layout.addWidget(self._status_lbl)
        ctrl_layout.addStretch(1)

        viewer_container = QWidget()
        vc_layout = QVBoxLayout(viewer_container)
        vc_layout.setContentsMargins(0, 0, 0, 0)
        vc_layout.setSpacing(0)

        zoom_bar = QWidget()
        zoom_bar.setFixedHeight(30)
        zoom_bar.setStyleSheet("background:#1a1a1a;")
        zbl = QHBoxLayout(zoom_bar)
        zbl.setContentsMargins(6, 2, 6, 2)
        zbl.setSpacing(4)
        for txt, cb in (
            ("-", lambda: self._viewer.zoom_out()),
            ("+", lambda: self._viewer.zoom_in()),
            ("1:1", lambda: self._set_zoom_1to1()),
            ("Fit", lambda: self._viewer.reset_zoom()),
        ):
            b = QPushButton(txt)
            b.setObjectName("zoom_btn")
            b.setFixedWidth(36)
            b.clicked.connect(cb)
            zbl.addWidget(b)
        zbl.addStretch(1)
        hint = QLabel("Scroll = zoom  .  Drag = pan  .  Dbl-click = fit")
        hint.setStyleSheet("color:#555;font-size:10px;")
        zbl.addWidget(hint)

        self._viewer = ImageViewer()
        vc_layout.addWidget(zoom_bar)
        vc_layout.addWidget(self._viewer, 1)

        root.addWidget(ctrl_scroll)
        root.addWidget(viewer_container, 1)

        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        caps = []
        caps.append("OIIO EXR: available" if HAS_OIIO else "OIIO EXR: unavailable")
        caps.append("OpenCV: available" if HAS_CV2 else "OpenCV: unavailable")
        if HAS_SCIPY:
            caps.append("scipy: available")
        if HAS_CUPY:
            caps.append("CuPy: available")
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
        self._viewer._zoom = 1.0
        self._viewer._offset = QPointF(0.0, 0.0)
        self._viewer.update()

    def _on_frame_slider_changed(self, frame: int):
        self._frame_display.setText(str(frame))
        self._pending_frame = frame
        self._frame_debounce.stop()
        self._frame_debounce.start(180)

    def _do_load_frame(self):
        frame = self._pending_frame
        self._current_frame = frame

        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.abort()
            try:
                self._loader_thread.loaded.disconnect()
                self._loader_thread.error.disconnect()
            except Exception:
                pass

        self._set_status(f"Loading frame {frame} ...")
        t = FrameLoaderThread(self._cam_id, frame)
        t.loaded.connect(self._on_frame_loaded)
        t.error.connect(self._on_frame_load_error)
        self._loader_thread = t
        t.start()

    def _on_frame_loaded(self, pixels: np.ndarray, path: str, frame: int):
        if frame != self._current_frame:
            return
        self._current_frame_img = pixels
        self._set_status(
            f"Frame {frame}   {pixels.shape[1]}x{pixels.shape[0]}  ch:{pixels.shape[2]}   {os.path.basename(path)}"
        )
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
        self._compare_btn.setText("Release  [ Filtered ]" if checked else "Hold  [ Original ]")

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory", self._out_dir_edit.text())
        if d:
            self._out_dir_edit.setText(d)

    def _reset_params(self):
        for grp in (self._denoise_grp, self._sharpen_grp, self._highpass_grp, self._contrast_grp):
            grp.set_group_enabled(False)

        self._denoise_grp.set_value("h", 10.0)
        self._denoise_grp.set_value("hcolor", 10.0)
        self._denoise_grp.set_value("template_win", 7)
        self._denoise_grp.set_value("search_win", 21)
        self._sharpen_grp.set_value("amount", 1.0)
        self._sharpen_grp.set_value("radius", 1.0)
        self._highpass_grp.set_value("amount", 0.5)
        self._highpass_grp.set_value("radius", 5)
        self._contrast_grp.set_value("contrast", 1.0)
        self._contrast_grp.set_value("brightness", 0.0)
        self._exposure_slider.setValue(0.0)

        self._collect_params()
        self._schedule_preview(immediate=True)

    def _collect_params(self):
        p = self._params
        p.denoise_enabled = self._denoise_grp.is_enabled()
        p.denoise_h = self._denoise_grp.get_value("h")
        p.denoise_hcolor = self._denoise_grp.get_value("hcolor")
        p.denoise_template_window = int(self._denoise_grp.get_value("template_win"))
        p.denoise_search_window = int(self._denoise_grp.get_value("search_win"))
        p.sharpen_enabled = self._sharpen_grp.is_enabled()
        p.sharpen_amount = self._sharpen_grp.get_value("amount")
        p.sharpen_radius = self._sharpen_grp.get_value("radius")
        p.highpass_enabled = self._highpass_grp.is_enabled()
        p.highpass_amount = self._highpass_grp.get_value("amount")
        p.highpass_radius = float(self._highpass_grp.get_value("radius"))
        p.contrast_enabled = self._contrast_grp.is_enabled()
        p.contrast_value = self._contrast_grp.get_value("contrast")
        p.brightness_value = self._contrast_grp.get_value("brightness")

    def _schedule_preview(self, immediate: bool = False):
        self._preview_debounce.stop()
        if immediate:
            self._trigger_preview()
        else:
            self._preview_debounce.start(220)

    def _trigger_preview(self):
        if self._current_frame_img is None:
            return
        if self._preview_thread and self._preview_thread.isRunning():
            self._preview_dirty = True
            return
        self._preview_dirty = False
        self._collect_params()
        t = PreviewThread(self._current_frame_img, self._params, self._exposure_slider.value())
        t.done.connect(self._on_preview_done)
        t.error.connect(lambda msg: self._set_status(f"Preview error: {msg}"))
        self._preview_thread = t
        t.start()

    def _on_preview_done(self, orig_u8, filt_u8):
        self._viewer.set_original(numpy_to_qpixmap(orig_u8))
        self._viewer.set_filtered(numpy_to_qpixmap(filt_u8))
        self._preview_thread = None
        if self._preview_dirty:
            self._preview_dirty = False
            self._trigger_preview()

    def _selected_export_ext(self) -> str:
        ext = self._export_ext_combo.currentData()
        if not ext:
            return ""
        return normalize_export_ext(str(ext))

    def _start_export(self):
        if self._seq_info["n_frames"] == 0:
            QMessageBox.warning(
                self,
                "No Footage",
                "This camera has no frames registered in 3DE.\n(getCameraNoFrames returned 0)",
            )
            return
        out_dir = self._out_dir_edit.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "No Output Directory", "Please specify an output directory.")
            return

        try:
            export_ext = self._selected_export_ext()
        except Exception as e:
            QMessageBox.warning(self, "Invalid Export Extension", str(e))
            return

        if export_ext == ".exr" and not HAS_OIIO:
            QMessageBox.warning(
                self,
                "EXR Export Unavailable",
                "OpenImageIO is required to export EXR files.\nChoose PNG/JPG or install openimageio.",
            )
            return

        total = self._seq_info["last_frame"] - self._seq_info["first_frame"] + 1
        ext_label = export_ext or "(same as input)"
        if (
            QMessageBox.question(
                self,
                "Confirm Export",
                f"Export <b>{total}</b> frame(s) to:<br><br><tt>{out_dir}</tt><br><br>"
                f"Extension: <b>{ext_label}</b><br><br>"
                f"3DE footage path will be updated automatically after export.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        self._collect_params()
        self._export_btn.setEnabled(False)
        self._set_status("Exporting ...")

        self._progress_dlg = QProgressDialog("Exporting filtered sequence ...", "Cancel", 0, total, self)
        self._progress_dlg.setWindowTitle("Exporting")
        self._progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dlg.setMinimumDuration(500)
        self._progress_dlg.canceled.connect(self._cancel_export)
        self._progress_dlg.show()

        self._export_thread = ExportThread(
            cam_id=self._cam_id,
            output_dir=out_dir,
            first=self._seq_info["first_frame"],
            last=self._seq_info["last_frame"],
            params=self._params,
            export_ext=export_ext,
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
                self,
                "Export Complete",
                f"Frames written to:\n{output_dir}\n\n3DE footage path updated to:\n{out_pattern}",
            )
        except Exception as e:
            self._set_status(f"Export done - 3DE update failed: {e}")
            QMessageBox.warning(
                self,
                "3DE Update Failed",
                f"Frames exported to:\n{output_dir}\n\n"
                f"Could not update 3DE camera path automatically:\n{e}\n\n"
                f"Please set the footage path manually to:\n{out_pattern}",
            )

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
            if (
                QMessageBox.question(
                    self,
                    "Export Running",
                    "An export is in progress. Cancel and close?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            ):
                self._export_thread.abort()
                self._export_thread.wait(4000)
            else:
                event.ignore()
                return
        for t in (self._loader_thread, self._preview_thread):
            if t and t.isRunning():
                if hasattr(t, "abort"):
                    t.abort()
                t.wait(2000)
        event.accept()


class CameraPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("R_Tools  Image Filter Toolkit  v2.0")
        self.setFixedSize(480, 200)
        self.setStyleSheet(DARK_STYLE)
        self._selected_cam_id = None
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
        self._cam_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
            n = info["n_frames"]
            frames_str = (
                f"Frames: {info['first_frame']} - {info['last_frame']}  ({n} frames)"
                if n > 0
                else "No frames registered (getCameraNoFrames = 0)"
            )
            self._info_lbl.setText(f"{path}\n{frames_str}")

    def _on_select(self):
        idx = self._cam_combo.currentIndex()
        if 0 <= idx < len(self._cameras):
            self._selected_cam_id, self._selected_cam_name = self._cameras[idx]
            self.accept()

    def selected_camera(self) -> tuple[str | None, str | None]:
        return self._selected_cam_id, self._selected_cam_name


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    if not HAS_OIIO:
        QMessageBox.information(
            None,
            "EXR Support Disabled",
            "OpenImageIO is not installed.\n\n"
            "You can still load/export JPG, JPEG, and PNG sequences.\n"
            "Install openimageio to enable EXR support.",
        )

    if not HAS_CV2:
        QMessageBox.information(
            None,
            "OpenCV Not Found  (optional)",
            "OpenCV is not installed.\n\n"
            "The Denoise filter will be unavailable.\n"
            "All other filters work normally.\n\n"
            "To enable denoising:\n"
            "    pip install opencv-python",
        )

    picker = CameraPickerDialog()
    if picker.exec() != QDialog.DialogCode.Accepted:
        return
    cam_id, cam_name = picker.selected_camera()
    if not cam_id:
        return

    win = FilterToolkitWindow(cam_id, cam_name or "Camera")
    win.show()
    win.raise_()
    win.activateWindow()

    windows = getattr(main, "_windows", None)
    if windows is None:
        windows = []
        setattr(main, "_windows", windows)
    windows.append(win)

    if not QApplication.instance().property("tde4_managed"):
        try:
            app.exec()
        except Exception:
            pass
