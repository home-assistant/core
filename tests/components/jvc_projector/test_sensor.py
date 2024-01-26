"""Tests for the JVC Projector binary sensor device."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

ENTITY_ID = "binary_sensor.jvc_projector_power"


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test sensors."""
    entity = hass.states.get("sensor.jvc_projector_input")
    entry = entity_registry.async_get("sensor.jvc_projector_input")
    assert entity
    assert entity.state == "none"
    assert entry
    # assert entry.unique_id == f"{MOCK_SERIAL}-media_location"

    entity = hass.states.get("sensor.jvc_projector_power_status")
    entry = entity_registry.async_get("sensor.jvc_projector_power_status")
    assert entity
    assert entity.state == "none"
    assert entry
    # assert entry.unique_id == f"{MOCK_SERIAL}-play_status"
