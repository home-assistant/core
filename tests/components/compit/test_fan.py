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
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
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
        2, CompitParameter.VENTILATION_ON_OFF, STATE_OFF
    )

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "fan.nano_color_2"}, blocking=True
    )

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.state == STATE_ON


async def test_fan_turn_on_with_percentage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test turning on the fan with a percentage."""
    await setup_integration(hass, mock_config_entry)

    await mock_connector.select_device_option(
        2, CompitParameter.VENTILATION_ON_OFF, STATE_OFF
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.nano_color_2", ATTR_PERCENTAGE: 100},
        blocking=True,
    )

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get("percentage") == 100


async def test_fan_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test turning off the fan."""
    await setup_integration(hass, mock_config_entry)

    await mock_connector.select_device_option(
        2, CompitParameter.VENTILATION_ON_OFF, STATE_ON
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.nano_color_2"},
        blocking=True,
    )

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.state == STATE_OFF


async def test_fan_set_speed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test setting the fan speed."""
    await setup_integration(hass, mock_config_entry)

    await mock_connector.select_device_option(
        2, CompitParameter.VENTILATION_ON_OFF, STATE_ON
    )  # Ensure fan is on before setting speed

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: "fan.nano_color_2",
            ATTR_PERCENTAGE: 80,
        },
        blocking=True,
    )

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.attributes.get("percentage") == 80


async def test_fan_set_speed_while_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test setting the fan speed while the fan is off."""
    await setup_integration(hass, mock_config_entry)

    await mock_connector.select_device_option(
        2, CompitParameter.VENTILATION_ON_OFF, STATE_OFF
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: "fan.nano_color_2",
            ATTR_PERCENTAGE: 80,
        },
        blocking=True,
    )

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.state == STATE_OFF  # Fan should remain off until turned on
    assert state.attributes.get("percentage") == 0


async def test_fan_set_speed_to_not_in_step_percentage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test setting the fan speed to a percentage that is not in the step of the fan."""
    await setup_integration(hass, mock_config_entry)

    await mock_connector.select_device_option(
        2, CompitParameter.VENTILATION_ON_OFF, STATE_ON
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.nano_color_2", ATTR_PERCENTAGE: 65},
    )

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get("percentage") == 80


async def test_fan_set_speed_to_0(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test setting the fan speed to 0."""
    await setup_integration(hass, mock_config_entry)

    await mock_connector.select_device_option(
        2, CompitParameter.VENTILATION_ON_OFF, STATE_ON
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
    assert state.state == STATE_OFF  # Fan is turned off by setting the percentage to 0
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
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("gear", "expected_percentage"),
    [
        ("gear_0", 20),
        ("gear_1", 40),
        ("gear_2", 60),
        ("gear_3", 80),
        ("airing", 100),
    ],
)
async def test_fan_gear_to_percentage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    gear: str,
    expected_percentage: int,
) -> None:
    """Test the gear to percentage conversion."""
    mock_connector.get_current_option.side_effect = lambda device_id, parameter_code: (
        gear
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("fan.nano_color_2")
    assert state is not None
    assert state.attributes.get("percentage") == expected_percentage
