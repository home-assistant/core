"""The tests for the opnsense device tracker platform."""

from unittest import mock

from homeassistant.components.opnsense.device_tracker import async_get_scanner
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_get_scanner(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: mock.AsyncMock,
) -> None:
    """Test creating an opnsense scanner."""
    scanner = await async_get_scanner(hass, {})
    assert scanner is not None

    # With no specific tracker interfaces configured, all devices should be returned
    devices = await scanner.async_scan_devices()

    assert len(devices) == 2
    assert "ff:ff:ff:ff:ff:ff" in devices
    assert "ff:ff:ff:ff:ff:fe" in devices
