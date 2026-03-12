from __future__ import annotations

import os
import re
from pathlib import Path

from . import deps

HAS_OIIO = deps.HAS_OIIO
HAS_PIL = deps.HAS_PIL
np = deps.np
oiio = deps.oiio
Image = deps.Image

SUPPORTED_READ_EXTS = {".exr", ".jpg", ".jpeg", ".png"}
SUPPORTED_EXPORT_EXTS = {".exr", ".jpg", ".jpeg", ".png"}


def expand_frame_path(seq_path: str, frame: int) -> str:
    if not seq_path:
        return ""
    if re.search(r"%\d*d", seq_path):
        try:
            return seq_path % frame
        except Exception:
            pass
    m = re.search(r"(#+)", seq_path)
    if m:
        hashes = m.group(1)
        return seq_path[: m.start()] + str(frame).zfill(len(hashes)) + seq_path[m.end() :]
    return seq_path


def make_sequence_pattern(filepath: str) -> str:
    parent = os.path.dirname(filepath)
    name = os.path.basename(filepath)
    matches = list(re.finditer(r"\d+", name))
    if not matches:
        return filepath
    m = matches[-1]
    pattern = name[: m.start()] + "#" * len(m.group()) + name[m.end() :]
    return os.path.join(parent, pattern)


def suggest_output_dir(display_path: str) -> str:
    if not display_path:
        return ""
    return str(Path(display_path).parent) + "_filtered"


def normalize_export_ext(ext: str) -> str:
    e = (ext or "").strip().lower()
    if not e:
        return ""
    if not e.startswith("."):
        e = "." + e
    if e not in SUPPORTED_EXPORT_EXTS:
        raise ValueError(
            "Unsupported export extension: %s. Supported: %s"
            % (e, ", ".join(sorted(SUPPORTED_EXPORT_EXTS)))
        )
    return e


class ImageIO:
    @staticmethod
    def _load_exr(path: str) -> tuple[np.ndarray, dict]:
        if not HAS_OIIO:
            raise RuntimeError(
                "OpenImageIO Python binding is required to read EXR files.\n"
                "Install: pip install openimageio"
            )
        inp = oiio.ImageInput.open(path)
        if inp is None:
            raise IOError("OIIO cannot open '%s': %s" % (path, oiio.geterror()))
        spec = inp.spec()
        pixels = inp.read_image(oiio.FLOAT)
        inp.close()
        if pixels is None:
            raise IOError("OIIO read_image failed for '%s'" % path)
        if pixels.ndim == 2:
            pixels = pixels[:, :, np.newaxis]
        meta = {
            "width": spec.width,
            "height": spec.height,
            "nchannels": spec.nchannels,
            "channelnames": list(spec.channelnames),
            "ext": ".exr",
        }
        return pixels.astype(np.float32), meta

    @staticmethod
    def _load_ldr(path: str) -> tuple[np.ndarray, dict]:
        if not HAS_PIL:
            raise RuntimeError(
                "Pillow is required to read PNG/JPG/JPEG files.\n"
                "Install: pip install pillow"
            )
        img = Image.open(path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        arr_u8 = np.asarray(img, dtype=np.uint8)
        if arr_u8.ndim == 2:
            arr_u8 = arr_u8[:, :, np.newaxis]
        arr_f = arr_u8.astype(np.float32) / 255.0
        nch = arr_f.shape[2] if arr_f.ndim == 3 else 1
        ch_names = ["R", "G", "B", "A"][:nch]
        return arr_f, {
            "width": arr_f.shape[1],
            "height": arr_f.shape[0],
            "nchannels": nch,
            "channelnames": ch_names,
            "ext": os.path.splitext(path)[1].lower(),
        }

    @staticmethod
    def load(path: str) -> tuple[np.ndarray, dict]:
        if not os.path.isfile(path):
            raise FileNotFoundError("Image not found: %s" % path)
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_READ_EXTS:
            raise RuntimeError(
                "Unsupported input extension: %s. Supported: %s"
                % (ext or "(none)", ", ".join(sorted(SUPPORTED_READ_EXTS)))
            )
        if ext == ".exr":
            return ImageIO._load_exr(path)
        return ImageIO._load_ldr(path)

    @staticmethod
    def _save_exr(path: str, pixels: np.ndarray, metadata: dict | None = None) -> None:
        if not HAS_OIIO:
            raise RuntimeError(
                "OpenImageIO Python binding is required to export EXR files.\n"
                "Install: pip install openimageio"
            )
        h, w = pixels.shape[:2]
        nc = pixels.shape[2] if pixels.ndim == 3 else 1
        spec = oiio.ImageSpec(w, h, nc, oiio.FLOAT)
        spec.attribute("compression", "zips")
        if metadata and "channelnames" in metadata:
            spec.channelnames = metadata["channelnames"]
        out = oiio.ImageOutput.create(path)
        if out is None:
            raise IOError("OIIO cannot create '%s': %s" % (path, oiio.geterror()))
        out.open(path, spec)
        out.write_image(pixels.astype(np.float32))
        out.close()

    @staticmethod
    def _save_ldr(path: str, pixels: np.ndarray) -> None:
        if not HAS_PIL:
            raise RuntimeError(
                "Pillow is required to export PNG/JPG/JPEG files.\n"
                "Install: pip install pillow"
            )
        arr = pixels.astype(np.float32)
        if arr.ndim == 2:
            arr = arr[:, :, np.newaxis]

        # LDR formats expect display-referred range; clamp to [0,1] then convert to uint8.
        arr = np.clip(arr, 0.0, 1.0)
        arr_u8 = (arr * 255.0 + 0.5).astype(np.uint8)

        ext = os.path.splitext(path)[1].lower()
        if arr_u8.shape[2] == 1:
            mode = "L"
            out_arr = arr_u8[:, :, 0]
        elif arr_u8.shape[2] >= 4 and ext == ".png":
            mode = "RGBA"
            out_arr = arr_u8[:, :, :4]
        else:
            mode = "RGB"
            out_arr = arr_u8[:, :, :3]

        img = Image.fromarray(out_arr, mode=mode)
        save_kwargs = {"quality": 95} if ext in {".jpg", ".jpeg"} else {}
        img.save(path, **save_kwargs)

    @staticmethod
    def save(path: str, pixels: np.ndarray, metadata: dict | None = None):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_EXPORT_EXTS:
            raise RuntimeError(
                "Unsupported output extension: %s. Supported: %s"
                % (ext or "(none)", ", ".join(sorted(SUPPORTED_EXPORT_EXTS)))
            )
        if ext == ".exr":
            ImageIO._save_exr(path, pixels, metadata)
            return
        ImageIO._save_ldr(path, pixels)
