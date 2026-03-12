from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal  # type: ignore
from PySide6.QtGui import QColor, QPainter, QPixmap, QWheelEvent  # type: ignore
from PySide6.QtWidgets import (  # type: ignore
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class LabeledSlider(QWidget):
    valueChanged = Signal(float)

    def __init__(self, label: str, min_val: float, max_val: float, default: float, decimals: int = 2, parent=None):
        super().__init__(parent)
        self._scale = 10**decimals

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        self.lbl = QLabel(label)
        self.lbl.setFixedWidth(82)
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(min_val * self._scale), int(max_val * self._scale))
        self.slider.setValue(int(default * self._scale))
        self.slider.setSingleStep(1)
        self.slider.setPageStep(max(1, int(self._scale * 0.1)))

        self.spin = QDoubleSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setDecimals(decimals)
        self.spin.setSingleStep(10**-decimals)
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


class LabeledIntSlider(QWidget):
    valueChanged = Signal(float)

    def __init__(self, label: str, min_val: int, max_val: int, default: int, step: int = 2, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        self.lbl = QLabel(label)
        self.lbl.setFixedWidth(82)
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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

    def add_slider(self, key: str, slider: LabeledSlider | LabeledIntSlider):
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
        self.enable_cb.blockSignals(True)
        self.enable_cb.setChecked(enabled)
        for s in self._sliders.values():
            s.setEnabled(enabled)
        self.enable_cb.blockSignals(False)


class ImageViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap_filtered: QPixmap | None = None
        self._pixmap_original: QPixmap | None = None
        self._show_original = False

        self._zoom = 1.0
        self._offset = QPointF(0.0, 0.0)
        self._drag_start: QPointF | None = None
        self._drag_offset_start = QPointF(0.0, 0.0)

        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
        self._zoom = 1.0
        self._offset = QPointF(0.0, 0.0)
        self.update()

    def zoom_in(self):
        self._apply_zoom(1.25)

    def zoom_out(self):
        self._apply_zoom(0.8)

    def _apply_zoom(self, factor: float, center: QPointF | None = None):
        if center is None:
            center = QPointF(self.width() / 2.0, self.height() / 2.0)
        old_zoom = self._zoom
        self._zoom = max(0.05, min(self._zoom * factor, 32.0))
        scale_change = self._zoom / old_zoom
        self._offset = center + (self._offset - center) * scale_change
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111111"))
        pm = self._pixmap_original if self._show_original else self._pixmap_filtered
        if not pm or pm.isNull():
            painter.setPen(QColor("#555555"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No image loaded")
            return
        dw = pm.width() * self._zoom
        dh = pm.height() * self._zoom
        x = (self.width() - dw) / 2 + self._offset.x()
        y = (self.height() - dh) / 2 + self._offset.y()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(int(x), int(y), int(dw), int(dh), pm)
        painter.setPen(QColor(180, 180, 180, 160))
        painter.drawText(6, self.height() - 6, f"{self._zoom * 100:.0f}%")

    def resizeEvent(self, event):
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        factor = 1.12 if delta > 0 else (1.0 / 1.12)
        self._apply_zoom(factor, QPointF(event.position()))
        event.accept()

    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._drag_start = QPointF(event.position())
            self._drag_offset_start = QPointF(self._offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            delta = QPointF(event.position()) - self._drag_start
            self._offset = self._drag_offset_start + delta
            self.update()

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event):
        self.reset_zoom()
