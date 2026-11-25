"""Tests for the Gree Climate diagnostics."""

from unittest.mock import MagicMock

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import async_setup_gree


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_device = device.return_value
    mock_device.device_info.brand = "gree"
    mock_device.device_info.model = "gree"
    mock_device.device_info.version = "V1.2.1"
    mock_device.hid = "362001000762+U-CS532AE(LT)V3.31.bin"
    mock_device.version = "3.31"
    mock_device.raw_properties = {
        "Pow": 1,
        "Mod": 1,
        "SetTem": 22,
        "TemSen": 64,
        "TemUn": 0,
        "WdSpd": 0,
        "Lig": 1,
        "Quiet": 0,
        "Tur": 0,
    }

    entry = await async_setup_gree(hass)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
