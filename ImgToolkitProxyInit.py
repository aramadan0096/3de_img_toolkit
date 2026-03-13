#
# 3DE4.script.name: Image Toolkit Proxy Init
#
# 3DE4.script.gui: None
#
# 3DE4.script.comment: Bootstraps img_toolkit.py from an external toolkit root.
#

import importlib.util
import os
import sys
import traceback

try:
    import tde4  # type: ignore
except ImportError:  # pragma: no cover - only available inside 3DEqualizer
    tde4 = None

# Relative in-repo default; installer rewrites this to an absolute static path.
IMG_TOOLKIT_ROOT = r"."
IMG_TOOLKIT_ENTRY = "img_toolkit.py"
_RUNTIME_MODULE_NAME = "img_toolkit_runtime_proxy"


def _iter_local_lib_dirs(toolkit_root):
    """Yield interpreter-matching local dependency dirs in priority order."""
    py_tag = "py%d%d" % (sys.version_info[0], sys.version_info[1])
    versioned_libs = os.path.join(toolkit_root, "libs", py_tag)
    if os.path.isdir(versioned_libs):
        yield versioned_libs

    # Backward compatibility with previous flat naming.
    legacy_versioned_libs = os.path.join(toolkit_root, "libs_%s" % py_tag)
    if os.path.isdir(legacy_versioned_libs):
        yield legacy_versioned_libs

    # Backward compatibility for the existing default folder.
    if sys.version_info[:2] == (3, 11):
        default_libs = os.path.join(toolkit_root, "libs")
        if os.path.isdir(default_libs):
            yield default_libs


def _notify_error(message):
    if tde4 is not None:
        try:
            tde4.postQuestionRequester("Image Toolkit", message, "Ok")
            return
        except Exception:
            pass

    try:
        print("[Image Toolkit] %s" % message)
    except Exception:
        pass


def _resolve_root():
    root = os.getenv("IMG_TOOLKIT_ROOT", IMG_TOOLKIT_ROOT)
    if not os.path.isabs(root):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), root)
    return os.path.abspath(os.path.normpath(root))


def _load_runtime_module(module_path):
    module = sys.modules.get(_RUNTIME_MODULE_NAME)
    if module is not None:
        cached_file = getattr(module, "__file__", None)
        same_file = cached_file and os.path.abspath(cached_file) == os.path.abspath(module_path)
        if same_file and callable(getattr(module, "main", None)):
            return module

        # Drop stale/partial module objects and reload from disk.
        sys.modules.pop(_RUNTIME_MODULE_NAME, None)

    spec = importlib.util.spec_from_file_location(_RUNTIME_MODULE_NAME, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to create module spec for img_toolkit.py")

    module = importlib.util.module_from_spec(spec)
    sys.modules[_RUNTIME_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        # Avoid returning a half-initialized cached module on the next launch.
        sys.modules.pop(_RUNTIME_MODULE_NAME, None)
        raise
    return module


def run():
    toolkit_root = _resolve_root()
    module_path = os.path.join(toolkit_root, IMG_TOOLKIT_ENTRY)

    if not os.path.isfile(module_path):
        raise RuntimeError(
            "img_toolkit.py was not found.\n\n"
            "Configured root: %s\n"
            "Expected file: %s" % (toolkit_root, module_path)
        )

    for lib_dir in _iter_local_lib_dirs(toolkit_root):
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
    if toolkit_root not in sys.path:
        sys.path.insert(0, toolkit_root)

    module = _load_runtime_module(module_path)
    main_fn = getattr(module, "main", None)
    if not callable(main_fn):
        raise RuntimeError("img_toolkit.py does not expose a callable main() function")

    return main_fn()


def bootstrap():
    try:
        return run()
    except Exception:
        _notify_error(
            "Failed to launch Image Toolkit.\n\n%s" % traceback.format_exc()
        )
        return None
