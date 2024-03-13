"""Tests for the JVC Projector binary sensor device."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

ENTITY_ID = "binary_sensor.jvc_projector_power"


async def test_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Tests entity state is registered."""
    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity_registry.async_get(entity.entity_id)
