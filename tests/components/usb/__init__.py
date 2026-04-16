"""Tests for the USB Discovery integration."""

from unittest.mock import patch

from homeassistant.components.usb import async_request_scan as usb_async_request_scan
from homeassistant.core import HomeAssistant


def patch_scanned_serial_ports(**kwargs) -> None:
    """Patch the USB integration's list of scanned serial ports."""
    return patch("homeassistant.components.usb.utils.scan_serial_ports", **kwargs)


async def async_request_scan(hass: HomeAssistant) -> None:
    """Request a USB scan."""
    return await usb_async_request_scan(hass)
