# print_3de_cameras.py
# Run this from inside 3DEqualizer's Python console or as a 3DE4 script.
from __future__ import print_function
try:
    import tde4
except ImportError:
    raise RuntimeError("This must be executed inside 3DEqualizer (tde4 module not found).")

def get_all_cameras():
    """
    Try the direct list API first; if not available, fall back to first/next iteration.
    Returns a list of camera IDs/handles.
    """
    cams = []
    try:
        # Many versions provide getCameraList() which returns [cam,...]
        cams = tde4.getCameraList()
    except Exception:
        # Fallback: iterate first/next
        cam = tde4.getFirstCamera()
        while cam:
            cams.append(cam)
            cam = tde4.getNextCamera()
    return cams

def print_camera_paths():
    cams = get_all_cameras()
    if not cams:
        print("No cameras found in the current project.")
        return

    for cam in cams:
        try:
            name = tde4.getCameraName(cam)
        except Exception:
            name = "<unnamed camera>"

        print("Camera:", name)

        # Try to print generic stored camera path (if any)
        try:
            cam_path = tde4.getCameraPath(cam)
            # getCameraPath may return a string or a list/tuple depending on version
            if isinstance(cam_path, (list, tuple)):
                for p in cam_path:
                    print("  camera path:", p)
            elif cam_path:
                print("  camera path:", cam_path)
        except Exception:
            # ignore if function not present or fails
            pass

        # Try proxy footage (some projects use proxy)
        try:
            proxy = tde4.getCameraProxyFootage(cam)
            if proxy:
                print("  proxy footage:", proxy)
        except Exception:
            pass

        # Print per-frame filepaths when available
        try:
            nframes = tde4.getCameraNoFrames(cam) or 0
        except Exception:
            nframes = 0

        if nframes > 0:
            # Many projects have a frame range; printing every frame can be verbose.
            # We'll print only frames that return a path (non-empty).
            for f in range(1, nframes + 1):
                try:
                    filepath = tde4.getCameraFrameFilepath(cam, f)
                except Exception:
                    filepath = None
                if filepath:
                    print("   frame {:d}: {}".format(f, filepath))
        else:
            # Try a single-frame fallback (frame 1)
            try:
                fp = tde4.getCameraFrameFilepath(cam, 1)
                if fp:
                    print("   frame 1:", fp)
            except Exception:
                pass

        print("")  # blank line between cameras

if __name__ == "__main__":
    print_camera_paths()