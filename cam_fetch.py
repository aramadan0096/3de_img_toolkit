# 3DE4.script.name: r_tools/footage fetch
# 3DE4.script.version: 1.0
# 3DE4.script.comment: Print all cameras and their footage file paths (per-frame if available)
# 3DE4.script.startup: false
# 3DE4.script.gui: true

from __future__ import print_function
import time
import os
import csv
import tempfile

try:
    import tde4
except Exception:
    raise RuntimeError("This script must be run inside 3DEqualizer (tde4 module missing).")

def get_all_cameras():
    cams = []
    # Prefer a direct list API if available
    try:
        cams = tde4.getCameraList() or []
    except Exception:
        try:
            cam = tde4.getFirstCamera()
            while cam:
                cams.append(cam)
                cam = tde4.getNextCamera()
        except Exception:
            pass
    return cams

def get_camera_name(cam):
    try:
        return tde4.getCameraName(cam) or "<unnamed>"
    except Exception:
        return "<unnamed>"

def gather_footage_records():
    records = []  # tuples (camera_name, frame_or_range, filepath)
    cams = get_all_cameras()
    if not cams:
        print("No cameras found in the current project.")
        return records

    for cam in cams:
        cam_name = get_camera_name(cam)
        # Attempt a camera-level stored path attribute
        try:
            cam_path = tde4.getCameraPath(cam)
            if cam_path:
                # cam_path may be a string or list/tuple
                if isinstance(cam_path, (list, tuple)):
                    for p in cam_path:
                        records.append((cam_name, "camera_path", p))
                else:
                    records.append((cam_name, "camera_path", cam_path))
        except Exception:
            pass

        # Proxy footage (if any)
        try:
            proxy = tde4.getCameraProxyFootage(cam)
            if proxy:
                records.append((cam_name, "proxy", proxy))
        except Exception:
            pass

        # Per-frame filepaths when supported
        nframes = 0
        try:
            nframes = int(tde4.getCameraNoFrames(cam) or 0)
        except Exception:
            nframes = 0

        if nframes > 0:
            # To avoid extremely long console output for very large ranges,
            # we will record each frame but you can switch to sample printing if preferred.
            for f in range(1, nframes + 1):
                try:
                    fp = tde4.getCameraFrameFilepath(cam, f)
                except Exception:
                    fp = None
                if fp:
                    records.append((cam_name, "frame_%d" % f, fp))
        else:
            # Fallback: try frame 1
            try:
                fp = tde4.getCameraFrameFilepath(cam, 1)
                if fp:
                    records.append((cam_name, "frame_1", fp))
            except Exception:
                pass

    return records

def write_csv(records, out_path):
    try:
        with open(out_path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["camera","frame_or_type","filepath"])
            for r in records:
                writer.writerow(r)
        return True
    except Exception as e:
        print("Failed to write CSV:", e)
        return False

def run():
    t0 = time.strftime("%Y%m%d_%H%M%S")
    records = gather_footage_records()
    if not records:
        print("No footage paths found.")
        return

    # Print a compact summary to the 3DE console
    print("\n=== Footage fetch results ===")
    cameras_seen = {}
    for cam, fr, path in records:
        # show only one sample per camera in console to be readable, but still record all to CSV
        if cam not in cameras_seen:
            print("Camera: %s" % cam)
            cameras_seen[cam] = 0
        cameras_seen[cam] += 1
        # show first few entries per camera (avoid giant dumps in console)
        if cameras_seen[cam] <= 5:
            print("   %s -> %s" % (fr, path))

    # Save full CSV into the OS temp folder and print its location
    tempdir = tempfile.gettempdir()
    out_file = os.path.join(tempdir, "3de_footage_paths_%s.csv" % t0)
    if write_csv(records, out_file):
        print("\nFull list written to:", out_file)
    else:
        print("\nFailed to write full CSV. Records count:", len(records))

# Entry point called by the 3DE menu/ScriptDB
if __name__ == "__main__":
    run()