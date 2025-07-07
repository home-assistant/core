"""Tests for the Tuya component."""

from __future__ import annotations

from unittest.mock import patch

from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_MOCKS = {
    "cs_arete_two_12l_dehumidifier_air_purifier": [
        Platform.FAN,
        Platform.HUMIDIFIER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cwwsq_cleverio_pf100": [
        Platform.NUMBER,
        Platform.SENSOR,
    ],
    "cwysj_pixi_smart_drinking_fountain": [
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "mcs_door_sensor": [
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
}


async def initialize_entry(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Initialize the Tuya component with a mock manager and config entry."""
    # Setup
    mock_manager.device_map = {
        mock_device.id: mock_device,
    }
    mock_config_entry.add_to_hass(hass)

    # Initialize the component
    with patch(
        "homeassistant.components.tuya.ManagerCompat", return_value=mock_manager
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
