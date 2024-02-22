"""The tests for the media_player platform."""

from homeassistant.components.media_player import (
    DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_VOLUME_SET,
    intent as media_player_intent,
)
from homeassistant.const import STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_mock_service


async def test_pause_media_player_intent(hass: HomeAssistant) -> None:
    """Test HassMediaPause intent for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_media_player"
    hass.states.async_set(entity_id, STATE_IDLE)
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PAUSE)

    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_PAUSE,
        {"name": {"value": "test media player"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_MEDIA_PAUSE
    assert call.data == {"entity_id": entity_id}


async def test_unpause_media_player_intent(hass: HomeAssistant) -> None:
    """Test HassMediaUnpause intent for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_media_player"
    hass.states.async_set(entity_id, STATE_IDLE)
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PLAY)

    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_UNPAUSE,
        {"name": {"value": "test media player"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_MEDIA_PLAY
    assert call.data == {"entity_id": entity_id}


async def test_next_media_player_intent(hass: HomeAssistant) -> None:
    """Test HassMediaNext intent for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_media_player"
    hass.states.async_set(entity_id, STATE_IDLE)
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_NEXT_TRACK)

    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_NEXT,
        {"name": {"value": "test media player"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_MEDIA_NEXT_TRACK
    assert call.data == {"entity_id": entity_id}


async def test_volume_media_player_intent(hass: HomeAssistant) -> None:
    """Test HassSetVolume intent for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_media_player"
    hass.states.async_set(entity_id, STATE_IDLE)
    calls = async_mock_service(hass, DOMAIN, SERVICE_VOLUME_SET)

    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_SET_VOLUME,
        {"name": {"value": "test media player"}, "volume_level": {"value": 50}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_VOLUME_SET
    assert call.data == {"entity_id": entity_id, "volume_level": 0.5}
