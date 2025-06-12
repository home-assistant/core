"""Test sensor platform for Swing2Sleep Smarla integration."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, update_property_listeners

from tests.common import MockConfigEntry, snapshot_platform

SENSOR_ENTITIES = [
    {
        "entity_id": "sensor.smarla_amplitude",
        "service": "analyser",
        "property": "oscillation",
        "test_value": [1, 0],
    },
    {
        "entity_id": "sensor.smarla_period",
        "service": "analyser",
        "property": "oscillation",
        "test_value": [0, 1],
    },
    {
        "entity_id": "sensor.smarla_activity",
        "service": "analyser",
        "property": "activity",
        "test_value": 1,
    },
    {
        "entity_id": "sensor.smarla_swing_count",
        "service": "analyser",
        "property": "swing_count",
        "test_value": 1,
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
    entity_info: dict[str, str],
) -> None:
    """Test Smarla Sensor callback."""
    assert await setup_integration(hass, mock_config_entry)

    mock_sensor_property = mock_federwiege.get_property(
        entity_info["service"], entity_info["property"]
    )

    entity_id = entity_info["entity_id"]

    assert hass.states.get(entity_id).state == "0"

    mock_sensor_property.get.return_value = entity_info["test_value"]

    await update_property_listeners(mock_sensor_property)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "1"
