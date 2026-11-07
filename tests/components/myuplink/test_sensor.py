"""Tests for myuplink sensor module."""

from unittest.mock import MagicMock, patch

from myuplink import DevicePoint
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import setup_integration


def _energy_point(
    parameter_id: str,
    name: str,
    category: str = "Energy Log",
) -> DevicePoint:
    """Return an energy device point."""
    return DevicePoint(
        {
            "category": category,
            "parameterId": parameter_id,
            "parameterName": name,
            "parameterUnit": "kWh",
            "writable": False,
            "timestamp": "2026-11-05T08:50:00+00:00",
            "value": 0.5,
            "strVal": "0.5kWh",
            "smartHomeCategories": [],
            "minValue": None,
            "maxValue": None,
            "stepValue": 1,
            "enumValues": [],
            "scaleValue": "1",
            "zoneId": None,
        }
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_log_state_classes(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test past-hour energy sensors publish no state class."""
    mock_myuplink_client.async_get_device_points.return_value = [
        _energy_point("25154", "Past hour sensor"),
        _energy_point("10077", "Current hour sensor"),
        _energy_point("25155", "Other category sensor", category="NIBE S1155"),
    ]

    with patch("homeassistant.components.myuplink.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    def _states(name: str) -> list[State]:
        """Return the states of all sensors named like this (one per device)."""
        states = [
            state
            for state in hass.states.async_all("sensor")
            if state.attributes["friendly_name"].endswith(name)
        ]
        assert states
        return states

    for state in _states("Past hour sensor"):
        assert state.attributes["device_class"] == "energy"
        assert state.attributes["unit_of_measurement"] == "kWh"
        assert "state_class" not in state.attributes

    for state in _states("Current hour sensor"):
        assert state.attributes["state_class"] == "total_increasing"

    for state in _states("Other category sensor"):
        assert state.attributes["state_class"] == "total_increasing"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor state."""

    with patch("homeassistant.components.myuplink.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
