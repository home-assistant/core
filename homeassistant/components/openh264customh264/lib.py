"""OpenH264 library detection and loading utilities."""
from __future__ import annotations
import ctypes
import os
import platform
from typing import Optional
from .const import LOGGER


def detect_default_lib_path() -> Optional[str]:
    """Detect default OpenH264 library path for the current system."""
    system = platform.system().lower()
    candidates: list[str] = []
    if system == "darwin":
        candidates = ["/opt/homebrew/lib/libopenh264.dylib", "/usr/local/lib/libopenh264.dylib"]
    elif system == "linux":
        candidates = ["/usr/lib/libopenh264.so", "/usr/local/lib/libopenh264.so"]
    elif system == "windows":
        candidates = [os.path.expandvars(r"%SystemRoot%\System32\openh264.dll")]
    
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def load_openh264(lib_path: Optional[str]) -> Optional[ctypes.CDLL]:
    """Load OpenH264 library from the given path or auto-detect."""
    path = lib_path or detect_default_lib_path()
    if not path or not os.path.exists(path):
        LOGGER.warning("OpenH264 library not found; tried path=%s", path)
        return None
    
    try:
        return ctypes.cdll.LoadLibrary(path)
    except Exception as err:
        LOGGER.error("Failed to load OpenH264 library at %s: %s", path, err)
        return None