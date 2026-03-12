from __future__ import annotations

import concurrent.futures
import os
import traceback

from PySide6.QtCore import QThread, Signal  # type: ignore

from .io_utils import ImageIO, make_sequence_pattern
from .processing import FilterParams, ImageProcessor, downscale_for_preview, tonemap_display
from .tde_helpers import get_camera_frame_filepath
from .deps import np


class FrameLoaderThread(QThread):
    loaded = Signal(object, str, int)
    error = Signal(str, int)

    def __init__(self, cam_id: str, frame: int):
        super().__init__()
        self._cam_id = cam_id
        self._frame = frame
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        if self._abort:
            return
        path = get_camera_frame_filepath(self._cam_id, self._frame)
        if not path:
            self.error.emit(f"Frame {self._frame}: getCameraFrameFilepath returned empty.", self._frame)
            return
        try:
            pixels, _ = ImageIO.load(path)
            if not self._abort:
                self.loaded.emit(pixels, path, self._frame)
        except Exception as e:
            if not self._abort:
                self.error.emit(str(e), self._frame)


class PreviewThread(QThread):
    done = Signal(object, object)
    error = Signal(str)

    def __init__(self, img_float: np.ndarray, params: FilterParams, exposure: float):
        super().__init__()
        self._img = img_float
        self._params = params.copy()
        self._exposure = exposure
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            small = downscale_for_preview(self._img)
            if self._abort:
                return
            orig_u8 = tonemap_display(small, self._exposure)
            if self._abort:
                return
            filtered = ImageProcessor.process(small, self._params)
            if self._abort:
                return
            filt_u8 = tonemap_display(filtered, self._exposure)
            if not self._abort:
                self.done.emit(orig_u8, filt_u8)
        except Exception as e:
            if not self._abort:
                self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


class ExportThread(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(str, str)
    error = Signal(str)

    def __init__(
        self,
        cam_id: str,
        output_dir: str,
        first: int,
        last: int,
        params: FilterParams,
        export_ext: str,
    ):
        super().__init__()
        self._cam_id = cam_id
        self._output_dir = output_dir
        self._first = first
        self._last = last
        self._params = params.copy()
        self._abort = False
        self._export_ext = export_ext

    def abort(self):
        self._abort = True

    def _make_out_path(self, in_path: str) -> str:
        if self._export_ext:
            stem = os.path.splitext(os.path.basename(in_path))[0]
            return os.path.join(self._output_dir, stem + self._export_ext)
        return os.path.join(self._output_dir, os.path.basename(in_path))

    def _process_frame(self, frame: int) -> tuple[bool, str]:
        if self._abort:
            return False, ""
        in_path = get_camera_frame_filepath(self._cam_id, frame)
        if not in_path:
            return True, ""
        out_path = self._make_out_path(in_path)
        try:
            pixels, meta = ImageIO.load(in_path)
            filtered = ImageProcessor.process(pixels, self._params)
            ImageIO.save(out_path, filtered, meta)
            return True, out_path
        except FileNotFoundError:
            return True, ""
        except Exception as e:
            raise RuntimeError(f"Frame {frame}: {e}") from e

    def run(self):
        try:
            os.makedirs(self._output_dir, exist_ok=True)
            frames = list(range(self._first, self._last + 1))
            total = len(frames)
            first_out = ""
            frames_done = 0

            max_workers = min(4, os.cpu_count() or 2)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {pool.submit(self._process_frame, f): f for f in frames}
                for future in concurrent.futures.as_completed(future_map):
                    if self._abort:
                        pool.shutdown(wait=False, cancel_futures=True)
                        self.error.emit("Export cancelled.")
                        return
                    ok, out_path = future.result()
                    if ok and out_path and not first_out:
                        first_out = out_path
                    frames_done += 1
                    f = future_map[future]
                    self.progress.emit(
                        frames_done,
                        f"Frame {f}  ({frames_done}/{total})  -> {os.path.basename(out_path) if out_path else 'skipped'}",
                    )

            out_pattern = make_sequence_pattern(first_out) if first_out else ""
            self.finished_ok.emit(self._output_dir, out_pattern)

        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
