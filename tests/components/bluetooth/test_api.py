"""Tests for the Bluetooth integration API."""


from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import async_scanner_by_source

from . import FakeScanner


async def test_scanner_by_source(hass, enable_bluetooth):
    """Test we can get a scanner by source."""

    hci2_scanner = FakeScanner(hass, "hci2", "hci2")
    cancel_hci2 = bluetooth.async_register_scanner(hass, hci2_scanner, True)

    assert async_scanner_by_source(hass, "hci2") is hci2_scanner
    cancel_hci2()
    assert async_scanner_by_source(hass, "hci2") is None
