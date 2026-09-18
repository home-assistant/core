"""Test sensor platform for Swing2Sleep Smarla integration."""

from typing import Any
from unittest.mock import MagicMock, patch

from pysmarlaapi.federwiege.services.types import SpringStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, update_property_listeners

from tests.common import MockConfigEntry, snapshot_platform

SENSOR_ENTITIES = [
    {
        "entity_id": "sensor.smarla_amplitude",
        "service": "analyser",
        "property": "oscillation",
        "initial_state": "0",
        "test": ([1, 0], "1"),
    },
    {
        "entity_id": "sensor.smarla_period",
        "service": "analyser",
        "property": "oscillation",
        "initial_state": "0",
        "test": ([0, 1], "1"),
    },
    {
        "entity_id": "sensor.smarla_activity",
        "service": "analyser",
        "property": "activity",
        "initial_state": "0",
        "test": (1, "1"),
    },
    {
        "entity_id": "sensor.smarla_swing_count",
        "service": "analyser",
        "property": "swing_count",
        "initial_state": "0",
        "test": (1, "1"),
    },
    {
        "entity_id": "sensor.smarla_total_swing_time",
        "service": "info",
        "property": "total_swing_time",
        "initial_state": "0.0",
        "test": (3600, "1.0"),
    },
    {
        "entity_id": "sensor.smarla_spring_status",
        "service": "analyser",
        "property": "spring_status",
        "initial_state": STATE_UNKNOWN,
        "test": (SpringStatus.NORMAL, "normal"),
    },
]


@pytest.mark.usefixtures("mock_federwiege")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Smarla entities."""
    with (
        patch("homeassistant.components.smarla.PLATFORMS", [Platform.SENSOR]),
    ):
        assert await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize("entity_info", SENSOR_ENTITIES)
async def test_sensor_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    entity_info: dict[str, Any],
) -> None:
    """Test Smarla Sensor callback."""
    assert await setup_integration(hass, mock_config_entry)

    mock_sensor_property = mock_federwiege.get_property(
        entity_info["service"], entity_info["property"]
    )

    entity_id = entity_info["entity_id"]

    # Verify initial state
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == entity_info["initial_state"]

    test_value, expected_state = entity_info["test"]

    # Set new value and trigger update
    mock_sensor_property.get.return_value = test_value
    await update_property_listeners(mock_sensor_property)
    await hass.async_block_till_done()

    # Verify updated state
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
