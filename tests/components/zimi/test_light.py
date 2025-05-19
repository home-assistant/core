"""Test the Zimi light entity."""

from unittest.mock import MagicMock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import mock_entity, setup_platform


async def test_light_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_api: MagicMock
) -> None:
    """Tests lights are registered in the entity registry."""

    mock_api.lights = [mock_entity(device_name="Light Controller", entity_type="light")]

    await setup_platform(hass, Platform.LIGHT)

    entity = entity_registry.entities["light.light_controller_test_entity_name"]
    assert entity.unique_id == "test-entity-id"
