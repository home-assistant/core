"""Tests for the USB Discovery integration."""

from typing import Any
from unittest.mock import _patch, patch

from homeassistant.components.usb import async_request_scan as usb_async_request_scan
from homeassistant.core import HomeAssistant


def patch_scanned_serial_ports(**kwargs: Any) -> _patch:
    """Patch the USB integration's list of scanned serial ports."""
    return patch("homeassistant.components.usb.scan_serial_ports", **kwargs)


async def async_request_scan(hass: HomeAssistant) -> None:
    """Request a USB scan."""
    return await usb_async_request_scan(hass)
