"""Test the Zimi cover entity."""

from unittest.mock import MagicMock

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import ENTITY_INFO, check_states, mock_entity, setup_platform


async def test_cover_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_api: MagicMock
) -> None:
    """Tests cover entity."""

    device_name = "Cover Controller"
    entity_key = "cover.cover_controller_test_entity_name"
    entity_type = Platform.COVER

    mock_api.doors = [mock_entity(device_name=device_name, entity_type=entity_type)]

    await setup_platform(hass, entity_type)

    entity = entity_registry.entities[entity_key]
    assert entity.unique_id == ENTITY_INFO["id"]

    assert (
        entity.supported_features
        == CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    await check_states(hass, entity_type, entity_key)

    services = hass.services.async_services()

    assert "close_cover" in services[entity_type]
    await hass.services.async_call(
        entity_type,
        "close_cover",
        {"entity_id": entity_key},
        blocking=True,
    )
    assert mock_api.doors[0].close_door.called

    assert "open_cover" in services[entity_type]
    await hass.services.async_call(
        entity_type,
        "open_cover",
        {"entity_id": entity_key},
        blocking=True,
    )
    assert mock_api.doors[0].open_door.called

    assert "set_cover_position" in services[entity_type]
    await hass.services.async_call(
        entity_type,
        "set_cover_position",
        {"entity_id": entity_key, "position": 50},
        blocking=True,
    )
    assert mock_api.doors[0].open_to_percentage.called
