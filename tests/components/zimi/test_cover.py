"""Test the Zimi cover entity."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN, CoverEntityFeature
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import mock_api_device, setup_platform


async def test_cover_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests cover entity."""

    blind_device_name = "Blind Controller"
    blind_entity_key = "cover.test_entity_room_blind_controller_test_entity_name"
    blind_entity_id = "test-entity-id-blind"
    door_device_name = "Cover Controller"
    door_entity_key = "cover.test_entity_room_cover_controller_test_entity_name"
    door_entity_id = "test-entity-id-door"
    entity_type = "cover"

    mock_api.blinds = [
        mock_api_device(
            device_name=blind_device_name,
            entity_type=entity_type,
            entity_id=blind_entity_id,
        )
    ]
    mock_api.doors = [
        mock_api_device(
            device_name=door_device_name,
            entity_type=entity_type,
            entity_id=door_entity_id,
        )
    ]

    await setup_platform(hass, Platform.COVER)

    blind_entity = entity_registry.entities[blind_entity_key]
    assert blind_entity.unique_id == blind_entity_id

    assert (
        blind_entity.supported_features
        == CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    door_entity = entity_registry.entities[door_entity_key]
    assert door_entity.unique_id == door_entity_id

    assert (
        door_entity.supported_features
        == CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    state = hass.states.get(door_entity_key)
    assert state == snapshot

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {"entity_id": door_entity_key},
        blocking=True,
    )
    assert mock_api.doors[0].close_door.called

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {"entity_id": door_entity_key},
        blocking=True,
    )
    assert mock_api.doors[0].open_door.called

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {"entity_id": door_entity_key, "position": 50},
        blocking=True,
    )
    assert mock_api.doors[0].open_to_percentage.called
