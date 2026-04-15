"""Tests for the USB Discovery integration."""

from unittest.mock import MagicMock, patch

from aiousbwatcher import InotifyNotAvailableError
import pytest

from homeassistant.components.usb import (
    DOMAIN,
    async_request_scan as usb_async_request_scan,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(name="force_usb_polling_watcher")
def force_usb_polling_watcher():
    """Patch the USB integration to not use inotify and fall back to polling."""
    with patch(
        "homeassistant.components.usb.AIOUSBWatcher.async_start",
        side_effect=InotifyNotAvailableError,
    ):
        yield


def patch_scanned_serial_ports(**kwargs) -> None:
    """Patch the USB integration's list of scanned serial ports."""
    return patch("homeassistant.components.usb.utils.scan_serial_ports", **kwargs)


@pytest.fixture(name="setup_usb")
async def setup_usb_fixture(
    hass: HomeAssistant, force_usb_polling_watcher: None
) -> MagicMock:
    """Set up USB integration and return the scanned serial ports mock."""
    with (
        patch("homeassistant.components.usb.async_get_usb", return_value=[]),
        patch_scanned_serial_ports(return_value=[]) as mock_serial_ports,
    ):
        assert await async_setup_component(hass, DOMAIN, {"usb": {}})
        await hass.async_block_till_done()
        yield mock_serial_ports


async def async_request_scan(hass: HomeAssistant) -> None:
    """Request a USB scan."""
    return await usb_async_request_scan(hass)
