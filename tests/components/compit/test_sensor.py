"""Tests for the Compit sensor platform."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_compit_entities

from tests.common import MockConfigEntry


async def test_sensor_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connector,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test for sensor entities creation, unique IDs, and device info."""
    await setup_integration(hass, mock_config_entry)

    snapshot_compit_entities(hass, entity_registry, snapshot, Platform.SENSOR)


@pytest.mark.parametrize(
    ("mock_return_value", "test_description"),
    [
        (None, "parameter is None"),
        ("damaged_supply_sensor", "parameter value is enum"),
    ],
)
async def test_sensor_return_value_enum_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    mock_return_value: Any | None,
    test_description: str,
) -> None:
    """Test that sensor entity shows unknown when get_current_option returns various invalid values."""
    mock_connector.get_current_value.side_effect = (
        lambda device_id, parameter_code: mock_return_value
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.nano_color_2_ventilation_alarm")
    assert state is not None
    assert state.state == mock_return_value if mock_return_value else "unknown"


async def test_sensor_enum_value_cannot_return_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test that sensor entity shows unknown when get_current_option returns various invalid values."""
    mock_connector.get_current_value.side_effect = (
        lambda device_id, parameter_code: 123  # Invalid enum value
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.nano_color_2_ventilation_alarm")
    assert state is None


@pytest.mark.parametrize(
    ("mock_return_value", "test_description"),
    [
        (None, "parameter is None"),
        (21, "parameter value is number"),
    ],
)
async def test_sensor_return_value_number_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    mock_return_value: Any | None,
    test_description: str,
) -> None:
    """Test that sensor entity shows correct number value."""
    mock_connector.get_current_value.side_effect = (
        lambda device_id, parameter_code: mock_return_value
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.r_900_calculated_buffer_temperature")
    assert state is not None
    assert state.state == str(mock_return_value) if mock_return_value else "unknown"


async def test_sensor_number_value_cannot_return_enum(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test that sensor entity shows unknown when get_current_value returns enum instead of number."""
    mock_connector.get_current_value.side_effect = (
        lambda device_id, parameter_code: "eco"  # Invalid number value
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.r_900_calculated_buffer_temperature")
    assert state is not None and state.state == "unknown"
