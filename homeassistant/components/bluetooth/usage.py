"""bluetooth usage utility to handle multiple instances."""
from __future__ import annotations

from typing import Any

from bleak import BleakScanner

from .models import HaBleakScanner, HaBleakScannerWrapper


def install_multiple_bleak_catcher(hass_bleak_scanner: HaBleakScanner) -> None:
    """Wrap the bleak classes to return the shared instance if multiple instances are detected."""

    def new_scanner_new(
        self: BleakScanner, *args: Any, **kwargs: Any
    ) -> HaBleakScannerWrapper:
        wrapped = HaBleakScannerWrapper(*args, **kwargs)
        wrapped._hass_bleak_scanner = (  # pylint: disable=protected-access
            hass_bleak_scanner
        )
        return wrapped

    def new_scanner_init(self: BleakScanner, *args: Any, **kwargs: Any) -> None:
        return

    BleakScanner.__new__ = new_scanner_new
    BleakScanner.__init__ = new_scanner_init
