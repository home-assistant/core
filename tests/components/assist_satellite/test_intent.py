"""Test assist satellite intents."""

from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
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
