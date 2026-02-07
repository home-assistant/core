"""Tests for the Compit water heater platform."""

from typing import Any
from unittest.mock import MagicMock

from compit_inext_api.consts import CompitParameter
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.water_heater import ATTR_TEMPERATURE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_compit_entities

from tests.common import MockConfigEntry


async def test_water_heater_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test for water heater entities creation, unique IDs, and device info."""
    await setup_integration(hass, mock_config_entry)

    snapshot_compit_entities(hass, entity_registry, snapshot, Platform.WATER_HEATER)


@pytest.mark.parametrize(
    "mock_return_value",
    [
        None,
        "invalid",
    ],
)
async def test_water_heater_unknown_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    mock_return_value: Any,
) -> None:
    """Test that water heater shows unknown temperature when get_current_value returns invalid values."""
    mock_connector.get_current_value.side_effect = lambda device_id, parameter_code: (
        mock_return_value
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("water_heater.r_900")
    assert state is not None
    assert state.attributes.get("temperature") is None
    assert state.attributes.get("current_temperature") is None


async def test_water_heater_set_temperature(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connector: MagicMock
) -> None:
    """Test setting water heater temperature."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "water_heater",
        "set_temperature",
        {
            ATTR_ENTITY_ID: "water_heater.r_900",
            ATTR_TEMPERATURE: 60.0,
        },
        blocking=True,
    )

    mock_connector.set_device_parameter.assert_called_once()
    assert (
        mock_connector.get_current_value(1, CompitParameter.DHW_TARGET_TEMPERATURE)
        == 60.0
    )


async def test_water_heater_turn_on(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connector: MagicMock
) -> None:
    """Test turning water heater on."""
    await mock_connector.select_device_option(1, CompitParameter.DHW_ON_OFF, "off")
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "water_heater",
        "turn_on",
        {ATTR_ENTITY_ID: "water_heater.r_900"},
        blocking=True,
    )

    assert mock_connector.get_current_option(1, CompitParameter.DHW_ON_OFF) == "on"


async def test_water_heater_turn_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connector: MagicMock
) -> None:
    """Test turning water heater off."""
    await mock_connector.select_device_option(1, CompitParameter.DHW_ON_OFF, "on")
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        "water_heater",
        "turn_off",
        {ATTR_ENTITY_ID: "water_heater.r_900"},
        blocking=True,
    )

    assert mock_connector.get_current_option(1, CompitParameter.DHW_ON_OFF) == "off"


async def test_water_heater_current_operation(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_connector: MagicMock
) -> None:
    """Test water heater current operation state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("water_heater.r_900")
    assert state is not None
    assert state.state == "performance"

    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {ATTR_ENTITY_ID: "water_heater.r_900", "operation_mode": "eco"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.r_900")
    assert state.state == "eco"
    assert (
        mock_connector.get_current_option(1, CompitParameter.DHW_ON_OFF) == "schedule"
    )
