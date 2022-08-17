"""Tests for the Bluetooth integration."""

from homeassistant.components.bluetooth import models


def _get_underlying_scanner():
    """Return the underlying scanner that has been wrapped."""
    return models.HA_BLEAK_SCANNER
