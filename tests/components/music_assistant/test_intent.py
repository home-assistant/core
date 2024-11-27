"""The tests for the Music Assistant intents."""

from unittest.mock import MagicMock

from homeassistant.components.music_assistant import (
    DOMAIN,
    intent as music_assistant_intent,
)
from homeassistant.components.music_assistant.const import SERVICE_PLAY_MEDIA_ADVANCED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .common import setup_integration_from_fixtures

from tests.common import async_mock_service


async def test_play_media_assist_intent(
    hass: HomeAssistant, music_assistant_client: MagicMock
) -> None:
    """Test the play_media_assist intent."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    await music_assistant_intent.async_setup_intents(hass)

    entity_id = "media_player.test_player_1"

    calls = async_mock_service(hass, DOMAIN, SERVICE_PLAY_MEDIA_ADVANCED)

    response = await intent.async_handle(
        hass,
        "test",
        music_assistant_intent.INTENT_PLAY_MEDIA_ASSIST,
        {"name": {"value": "Test Player 1"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_PLAY_MEDIA_ADVANCED
    assert call.data == {"entity_id": entity_id}
