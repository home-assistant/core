"""Tests for the Compit fan platform."""

from typing import Any
from unittest.mock import MagicMock

from compit_inext_api.consts import CompitParameter
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_compit_entities

from tests.common import MockConfigEntry


async def test_fan_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test for fan entities creation, unique IDs, and device info."""
    await setup_integration(hass, mock_config_entry)

    snapshot_compit_entities(hass, entity_registry, snapshot, Platform.FAN)


async def test_fan_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test turning on the fan."""
    await setup_integration(hass, mock_config_entry)

    await mock_connector.select_device_option(
        2, CompitParameter.VENTILATION_ON_OFF, "off"
    )

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "fan.nano_color_2"}, blocking=True
    )

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.state == "on"


async def test_fan_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test turning off the fan."""
    await setup_integration(hass, mock_config_entry)

    await mock_connector.select_device_option(
        2, CompitParameter.VENTILATION_ON_OFF, "on"
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.nano_color_2"},
        blocking=True,
    )

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.state == "off"


async def test_fan_set_speed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test setting the fan speed."""
    await setup_integration(hass, mock_config_entry)

    await mock_connector.select_device_option(
        2, CompitParameter.VENTILATION_ON_OFF, "off"
    )  # Turn off fan first

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: "fan.nano_color_2",
            ATTR_PERCENTAGE: 60,
        },
        blocking=True,
    )

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("percentage") == 60


async def test_fan_set_speed_to_0(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test setting the fan speed to 0."""
    await setup_integration(hass, mock_config_entry)

    await mock_connector.select_device_option(
        2, CompitParameter.VENTILATION_ON_OFF, "on"
    )  # Turn on fan first

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: "fan.nano_color_2",
            ATTR_PERCENTAGE: 0,
        },
        blocking=True,
    )

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.state == "off"
    assert state.attributes.get("percentage") == 0


@pytest.mark.parametrize(
    "mock_return_value",
    [
        None,
        "invalid",
    ],
)
async def test_fan_invalid_speed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    mock_return_value: Any,
) -> None:
    """Test setting an invalid speed."""
    mock_connector.get_current_option.side_effect = lambda device_id, parameter_code: (
        mock_return_value
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.state == "unknown"
