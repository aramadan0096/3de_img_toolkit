from __future__ import annotations

from .io_utils import expand_frame_path

import tde4  # type: ignore


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
            info["n_frames"] = int(n)
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


def set_camera_sequence_path(cam_id: str, pattern: str, first_frame: int = 1, last_frame: int = 1):
    for fn_name in ("setCameraPath", "setCameraSequencePath", "setSequencePath", "setCameraImagePath"):
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
