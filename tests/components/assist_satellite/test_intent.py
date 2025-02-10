"""Test assist satellite intents."""

from unittest.mock import patch

import pytest

from homeassistant.components.media_source import PlayMedia
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .conftest import TEST_DOMAIN, MockAssistSatellite


@pytest.fixture
def mock_tts():
    """Mock TTS service."""
    with (
        patch(
            "homeassistant.components.assist_satellite.entity.tts_generate_media_source_id",
            return_value="media-source://bla",
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=PlayMedia(
                url="https://www.home-assistant.io/resolved.mp3",
                mime_type="audio/mp3",
            ),
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
