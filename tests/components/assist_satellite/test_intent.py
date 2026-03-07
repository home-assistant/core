"""Test assist satellite intents."""

from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er, intent
from homeassistant.setup import async_setup_component

from .conftest import TEST_DOMAIN, MockAssistSatellite

from tests.components.tts.common import MockResultStream


@pytest.fixture
async def mock_tts(hass: HomeAssistant):
    """Mock TTS service."""
    assert await async_setup_component(hass, "tts", {})
    with (
        patch(
            "homeassistant.components.tts.generate_media_source_id",
            return_value="media-source://bla",
        ),
        patch(
            "homeassistant.components.tts.async_create_stream",
            return_value=MockResultStream(hass, "wav", b""),
        ),
    ):
        yield


async def test_broadcast_intent(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    entity_no_features: MockAssistSatellite,
    mock_tts: None,
) -> None:
    """Test we can invoke a broadcast intent."""

    with patch(
        "homeassistant.components.tts.async_resolve_engine",
        return_value="tts.cloud",
    ):
        result = await intent.async_handle(
            hass, "test", intent.INTENT_BROADCAST, {"message": {"value": "Hello"}}
        )

    assert result.as_dict() == {
        "card": {},
        "data": {
            "failed": [],
            "success": [
                {
                    "id": "assist_satellite.test_entity",
                    "name": "Test Entity",
                    "type": intent.IntentResponseTargetType.ENTITY,
                },
                {
                    "id": "assist_satellite.test_entity_2",
                    "name": "Test Entity 2",
                    "type": intent.IntentResponseTargetType.ENTITY,
                },
            ],
            "targets": [],
        },
        "language": "en",
        "response_type": "action_done",
        "speech": {},  # response comes from intents
    }
    assert len(entity.announcements) == 1
    assert len(entity2.announcements) == 1
    assert len(entity_no_features.announcements) == 0

    with patch(
        "homeassistant.components.tts.async_resolve_engine",
        return_value="tts.cloud",
    ):
        result = await intent.async_handle(
            hass,
            "test",
            intent.INTENT_BROADCAST,
            {"message": {"value": "Hello"}},
            device_id=entity.device_entry.id,
        )
    # Broadcast doesn't targets device that triggered it.
    assert result.as_dict() == {
        "card": {},
        "data": {
            "failed": [],
            "success": [
                {
                    "id": "assist_satellite.test_entity_2",
                    "name": "Test Entity 2",
                    "type": intent.IntentResponseTargetType.ENTITY,
                },
            ],
            "targets": [],
        },
        "language": "en",
        "response_type": "action_done",
        "speech": {},  # response comes from intents
    }
    assert len(entity.announcements) == 1
    assert len(entity2.announcements) == 2


async def test_broadcast_intent_excluded_domains(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    mock_tts: None,
) -> None:
    """Test that the broadcast intent filters out entities in excluded domains."""

    # Exclude the "test" domain
    with patch(
        "homeassistant.components.assist_satellite.intent.EXCLUDED_DOMAINS",
        new={TEST_DOMAIN},
    ):
        result = await intent.async_handle(
            hass, "test", intent.INTENT_BROADCAST, {"message": {"value": "Hello"}}
        )
        assert result.as_dict() == {
            "card": {},
            "data": {
                "failed": [],
                "success": [],  # no satellites
                "targets": [],
            },
            "language": "en",
            "response_type": "action_done",
            "speech": {},
        }


async def test_broadcast_intent_to_area(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    mock_tts: None,
) -> None:
    """Test broadcasting to a specific area."""
    # Set up areas
    area_reg = ar.async_get(hass)
    kitchen_area = area_reg.async_create("Kitchen")
    bedroom_area = area_reg.async_create("Bedroom")

    # Assign entities to areas
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get("assist_satellite.test_entity")
    ent_reg.async_update_entity(entity_entry.entity_id, area_id=kitchen_area.id)

    entity2_entry = ent_reg.async_get("assist_satellite.test_entity_2")
    ent_reg.async_update_entity(entity2_entry.entity_id, area_id=bedroom_area.id)

    # Broadcast to kitchen only
    with patch(
        "homeassistant.components.tts.async_resolve_engine",
        return_value="tts.cloud",
    ):
        result = await intent.async_handle(
            hass,
            "test",
            intent.INTENT_BROADCAST,
            {"message": {"value": "Kitchen message"}, "area": {"value": "Kitchen"}},
        )

    # Only entity in kitchen should receive broadcast
    assert result.as_dict()["data"]["success"] == [
        {
            "id": "assist_satellite.test_entity",
            "name": "Test Entity",
            "type": intent.IntentResponseTargetType.ENTITY,
        },
    ]
    assert len(entity.announcements) == 1
    assert len(entity2.announcements) == 0


async def test_broadcast_intent_by_name(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    mock_tts: None,
) -> None:
    """Test broadcasting to a specific entity by name."""

    with patch(
        "homeassistant.components.tts.async_resolve_engine",
        return_value="tts.cloud",
    ):
        result = await intent.async_handle(
            hass,
            "test",
            intent.INTENT_BROADCAST,
            {
                "message": {"value": "Specific message"},
                "name": {"value": "Test Entity 2"},
            },
        )

    # Only entity2 should receive broadcast
    assert result.as_dict()["data"]["success"] == [
        {
            "id": "assist_satellite.test_entity_2",
            "name": "Test Entity 2",
            "type": intent.IntentResponseTargetType.ENTITY,
        },
    ]
    assert len(entity.announcements) == 0
    assert len(entity2.announcements) == 1


async def test_broadcast_intent_invalid_area(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    mock_tts: None,
) -> None:
    """Test broadcasting to an invalid area raises MatchFailedError."""

    with (
        patch(
            "homeassistant.components.tts.async_resolve_engine",
            return_value="tts.cloud",
        ),
        pytest.raises(intent.MatchFailedError) as exc_info,
    ):
        await intent.async_handle(
            hass,
            "test",
            intent.INTENT_BROADCAST,
            {
                "message": {"value": "Test message"},
                "area": {"value": "NonExistentArea"},
            },
        )

    # Verify error is about invalid area
    assert (
        exc_info.value.result.no_match_reason == intent.MatchFailedReason.INVALID_AREA
    )


async def test_broadcast_intent_area_with_invoking_device(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    mock_tts: None,
) -> None:
    """Test that invoking device is excluded even when filtering by area."""
    # Set up area
    area_reg = ar.async_get(hass)
    kitchen_area = area_reg.async_create("Kitchen")

    # Assign both entities to the same area
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get("assist_satellite.test_entity")
    ent_reg.async_update_entity(entity_entry.entity_id, area_id=kitchen_area.id)

    entity2_entry = ent_reg.async_get("assist_satellite.test_entity_2")
    ent_reg.async_update_entity(entity2_entry.entity_id, area_id=kitchen_area.id)

    # Broadcast to kitchen from entity1's device
    with patch(
        "homeassistant.components.tts.async_resolve_engine",
        return_value="tts.cloud",
    ):
        result = await intent.async_handle(
            hass,
            "test",
            intent.INTENT_BROADCAST,
            {"message": {"value": "Kitchen message"}, "area": {"value": "Kitchen"}},
            device_id=entity.device_entry.id,
        )

    # Only entity2 should receive broadcast (entity1 is the invoking device)
    assert result.as_dict()["data"]["success"] == [
        {
            "id": "assist_satellite.test_entity_2",
            "name": "Test Entity 2",
            "type": intent.IntentResponseTargetType.ENTITY,
        },
    ]
    assert len(entity.announcements) == 0
    assert len(entity2.announcements) == 1


async def test_broadcast_intent_area_only_invoking_device(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    mock_tts: None,
) -> None:
    """Test empty success when area contains only invoking device."""
    # Set up areas
    area_reg = ar.async_get(hass)
    kitchen_area = area_reg.async_create("Kitchen")
    bedroom_area = area_reg.async_create("Bedroom")

    # Assign entities to different areas
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get("assist_satellite.test_entity")
    ent_reg.async_update_entity(entity_entry.entity_id, area_id=kitchen_area.id)

    entity2_entry = ent_reg.async_get("assist_satellite.test_entity_2")
    ent_reg.async_update_entity(entity2_entry.entity_id, area_id=bedroom_area.id)

    # Broadcast to kitchen from entity1's device (only device in kitchen)
    with patch(
        "homeassistant.components.tts.async_resolve_engine",
        return_value="tts.cloud",
    ):
        result = await intent.async_handle(
            hass,
            "test",
            intent.INTENT_BROADCAST,
            {"message": {"value": "Kitchen message"}, "area": {"value": "Kitchen"}},
            device_id=entity.device_entry.id,
        )

    # No devices should receive broadcast (only device in area is invoking device)
    assert result.as_dict()["data"]["success"] == []
    assert len(entity.announcements) == 0
    assert len(entity2.announcements) == 0


async def test_broadcast_intent_entity_without_registry_entry(
    hass: HomeAssistant,
    init_components: ConfigEntry,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    mock_tts: None,
) -> None:
    """Test that entities without registry entries are skipped gracefully."""
    ent_reg = er.async_get(hass)
    original_async_get = ent_reg.async_get

    # Mock async_get to return None for entity1 (simulating missing registry entry)
    def mock_async_get(entity_id):
        if entity_id == "assist_satellite.test_entity":
            return None
        return original_async_get(entity_id)

    with (
        patch(
            "homeassistant.components.tts.async_resolve_engine",
            return_value="tts.cloud",
        ),
        patch.object(ent_reg, "async_get", side_effect=mock_async_get),
    ):
        result = await intent.async_handle(
            hass, "test", intent.INTENT_BROADCAST, {"message": {"value": "Hello"}}
        )

    # Only entity2 should receive broadcast (entity1 has no registry entry)
    assert result.as_dict()["data"]["success"] == [
        {
            "id": "assist_satellite.test_entity_2",
            "name": "Test Entity 2",
            "type": intent.IntentResponseTargetType.ENTITY,
        },
    ]
    assert len(entity.announcements) == 0
    assert len(entity2.announcements) == 1
