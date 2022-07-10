"""bluetooth usage utility to handle multiple instances."""
from __future__ import annotations

import bleak

from . import models
from .models import HaBleakScanner, HaBleakScannerWrapper


def install_multiple_bleak_catcher(hass_bleak_scanner: HaBleakScanner) -> None:
    """Wrap the bleak classes to return the shared instance if multiple instances are detected."""
    models.HA_BLEAK_SCANNER = hass_bleak_scanner
    bleak.BleakScanner = HaBleakScannerWrapper
