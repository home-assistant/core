"""Tests for the Tuya component."""

from __future__ import annotations

from unittest.mock import patch

from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_MOCKS = {
    "clkg_curtain_switch": [
        # https://github.com/home-assistant/core/issues/136055
        Platform.COVER,
        Platform.LIGHT,
    ],
    "cs_arete_two_12l_dehumidifier_air_purifier": [
        Platform.FAN,
        Platform.HUMIDIFIER,
        Platform.SELECT,
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cwwsq_cleverio_pf100": [
        # https://github.com/home-assistant/core/issues/144745
        Platform.NUMBER,
        Platform.SENSOR,
    ],
    "cwysj_pixi_smart_drinking_fountain": [
        # https://github.com/home-assistant/core/pull/146599
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "cz_dual_channel_metering": [
        # https://github.com/home-assistant/core/issues/147149
        Platform.SENSOR,
        Platform.SWITCH,
    ],
    "kg_smart_valve": [
        # https://github.com/home-assistant/core/issues/148347
        Platform.SWITCH,
    ],
    "kj_bladeless_tower_fan": [
        # https://github.com/orgs/home-assistant/discussions/61
        Platform.FAN,
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "mcs_door_sensor": [
        # https://github.com/home-assistant/core/issues/108301
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    "rqbj_gas_sensor": [
        # https://github.com/orgs/home-assistant/discussions/100
        Platform.BINARY_SENSOR,
        Platform.SENSOR,
    ],
    "sfkzq_valve_controller": [
        # https://github.com/home-assistant/core/issues/148116
        Platform.SWITCH,
    ],
    "tdq_4_443": [
        # https://github.com/home-assistant/core/issues/146845
        Platform.SELECT,
        Platform.SWITCH,
    ],
    "wk_wifi_smart_gas_boiler_thermostat": [
        # https://github.com/orgs/home-assistant/discussions/243
        Platform.CLIMATE,
        Platform.SWITCH,
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
