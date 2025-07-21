"""Test the Zimi cover entity."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import ENTITY_INFO, mock_api_device, setup_platform


async def test_cover_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests cover entity."""

    device_name = "Cover Controller"
    entity_key = "cover.cover_controller_test_entity_name"
    entity_type = Platform.COVER

    mock_api.doors = [mock_api_device(device_name=device_name, entity_type=entity_type)]

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

    state = hass.states.get(entity_key)
    assert state == snapshot

    services = hass.services.async_services()

    assert SERVICE_CLOSE_COVER in services[entity_type]
    await hass.services.async_call(
        entity_type,
        SERVICE_CLOSE_COVER,
        {"entity_id": entity_key},
        blocking=True,
    )
    assert mock_api.doors[0].close_door.called

    assert SERVICE_OPEN_COVER in services[entity_type]
    await hass.services.async_call(
        entity_type,
        SERVICE_OPEN_COVER,
        {"entity_id": entity_key},
        blocking=True,
    )
    assert mock_api.doors[0].open_door.called

    assert SERVICE_SET_COVER_POSITION in services[entity_type]
    await hass.services.async_call(
        entity_type,
        SERVICE_SET_COVER_POSITION,
        {"entity_id": entity_key, "position": 50},
        blocking=True,
    )
    assert mock_api.doors[0].open_to_percentage.called
