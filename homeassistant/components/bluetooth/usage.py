"""bluetooth usage utility to handle multiple instances."""

from __future__ import annotations

import bleak

from .models import HaBleakScannerWrapper

ORIGINAL_BLEAK_SCANNER = bleak.BleakScanner


def install_multiple_bleak_catcher() -> None:
    """Wrap the bleak classes to return the shared instance if multiple instances are detected."""
    bleak.BleakScanner = HaBleakScannerWrapper  # type: ignore[misc, assignment]


def uninstall_multiple_bleak_catcher() -> None:
    """Unwrap the bleak classes."""
    bleak.BleakScanner = ORIGINAL_BLEAK_SCANNER  # type: ignore[misc]
