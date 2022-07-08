"""Tests for the Bluetooth integration."""

from unittest.mock import MagicMock

import bleak

from homeassistant.components.bluetooth import models
from homeassistant.components.bluetooth.models import HaBleakScannerWrapper
from homeassistant.components.bluetooth.usage import install_multiple_bleak_catcher


async def test_multiple_bleak_scanner_instances(hass):
    """Test creating multiple zeroconf throws without an integration."""
    assert models.HA_BLEAK_SCANNER is None
    mock_scanner = MagicMock()

    install_multiple_bleak_catcher(mock_scanner)

    instance = bleak.BleakScanner()

    assert isinstance(instance, HaBleakScannerWrapper)
    assert models.HA_BLEAK_SCANNER is mock_scanner
