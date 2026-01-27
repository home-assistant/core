"""Tests for the Compit binary sensor platform."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_compit_entities

from tests.common import MockConfigEntry


async def test_binary_sensor_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connector,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test for binary sensor entities creation, unique IDs, and device info."""
    await setup_integration(hass, mock_config_entry)

    snapshot_compit_entities(hass, entity_registry, snapshot, Platform.BINARY_SENSOR)


@pytest.mark.parametrize(
    ("mock_return_value", "expected_state"),
    [
        (None, "unknown"),
        ("on", "on"),
        ("off", "off"),
        ("yes", "on"),
        ("no", "off"),
        ("charging", "on"),
        ("not_charging", "off"),
        ("alert", "on"),
        ("no_alert", "off"),
    ],
)
async def test_binary_sensor_return_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
    mock_return_value: Any | None,
    expected_state: str,
) -> None:
    """Test that binary sensor entity shows correct state for various values."""
    mock_connector.get_current_value.side_effect = (
        lambda device_id, parameter_code: mock_return_value
    )
    await setup_integration(hass, mock_config_entry)

    # Test airing sensor
    state = hass.states.get("binary_sensor.nano_color_2_airing")
    if state is not None:
        assert state.state == expected_state

    # Test pump_status sensor
    state = hass.states.get("binary_sensor.af_1_pump_status")
    if state is not None:
        assert state.state == expected_state


async def test_binary_sensor_no_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_connector: MagicMock,
) -> None:
    """Test that binary sensor entities with NO_SENSOR value are not created."""
    mock_connector.get_current_value.side_effect = (
        lambda device_id, parameter_code: "no_sensor"
    )
    await setup_integration(hass, mock_config_entry)

    # Check that airing sensor is not created
    airing_entity = entity_registry.async_get("binary_sensor.nano_color_2_airing")
    assert airing_entity is None

    # Check that pump_status sensor is not created
    pump_status_entity = entity_registry.async_get("binary_sensor.af_1_pump_status")
    assert pump_status_entity is None
