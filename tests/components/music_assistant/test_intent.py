"""The tests for the Music Assistant intents."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.music_assistant import (
    DOMAIN,
    intent as music_assistant_intent,
)
from homeassistant.components.music_assistant.const import SERVICE_PLAY_MEDIA_ADVANCED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er, intent

from .common import (
    create_library_albums_from_fixture,
    create_library_artists_from_fixture,
    create_library_playlists_from_fixture,
    create_library_radios_from_fixture,
    create_library_tracks_from_fixture,
    setup_integration_from_fixtures,
)

from tests.common import async_mock_service


async def test_play_media_assist_intent(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the play_media_assist intent."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    create_library_artists_from_fixture()
    create_library_albums_from_fixture()
    create_library_playlists_from_fixture()
    create_library_tracks_from_fixture()
    create_library_radios_from_fixture()
    await music_assistant_intent.async_setup_intents(hass)

    entity_id = "media_player.test_player_1"
    media_id = "W O L F C L U B"

    office_area = area_registry.async_create(name="Office")
    entity_registry.async_update_entity(entity_id, area_id=office_area.id)

    calls = async_mock_service(hass, DOMAIN, SERVICE_PLAY_MEDIA_ADVANCED)

    # Test with artist and device name
    response = await intent.async_handle(
        hass,
        "test",
        music_assistant_intent.INTENT_PLAY_MEDIA_ASSIST,
        {
            "name": {"value": "Test Player 1"},
            "artist": {"value": "W O L F C L U B"},
        },
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_PLAY_MEDIA_ADVANCED
    assert call.data == {"entity_id": entity_id, "media_id": media_id}

    # Test with album and device area
    entity_id = "media_player.test_player_1"
    media_id = "Synth Punk EP"

    response = await intent.async_handle(
        hass,
        "test",
        music_assistant_intent.INTENT_PLAY_MEDIA_ASSIST,
        {
            "area": {"value": "Office"},
            "album": {"value": "Synth Punk EP"},
        },
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 2
    call = calls[1]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_PLAY_MEDIA_ADVANCED
    assert call.data == {"entity_id": entity_id, "media_id": media_id}

    # Test with playlist and device area
    entity_id = "media_player.test_player_1"
    media_id = "1970s Rock Hits"

    response = await intent.async_handle(
        hass,
        "test",
        music_assistant_intent.INTENT_PLAY_MEDIA_ASSIST,
        {
            "area": {"value": "Office"},
            "playlist": {"value": "1970s Rock Hits"},
        },
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 3
    call = calls[2]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_PLAY_MEDIA_ADVANCED
    assert call.data == {"entity_id": entity_id, "media_id": media_id}

    # Test with track and device area
    entity_id = "media_player.test_player_1"
    media_id = "Tennessee Whiskey"

    response = await intent.async_handle(
        hass,
        "test",
        music_assistant_intent.INTENT_PLAY_MEDIA_ASSIST,
        {
            "area": {"value": "Office"},
            "track": {"value": "Tennessee Whiskey"},
        },
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 4
    call = calls[3]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_PLAY_MEDIA_ADVANCED
    assert call.data == {"entity_id": entity_id, "media_id": media_id}

    # Test with radio and device area
    entity_id = "media_player.test_player_1"
    media_id = "fm4 | ORF | HQ"

    response = await intent.async_handle(
        hass,
        "test",
        music_assistant_intent.INTENT_PLAY_MEDIA_ASSIST,
        {
            "area": {"value": "Office"},
            "radio": {"value": "fm4 | ORF | HQ"},
        },
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 5
    call = calls[4]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_PLAY_MEDIA_ADVANCED
    assert call.data == {"entity_id": entity_id, "media_id": media_id}

    # Test with track, device area and radio mode
    entity_id = "media_player.test_player_1"
    media_id = "Tennessee Whiskey"

    response = await intent.async_handle(
        hass,
        "test",
        music_assistant_intent.INTENT_PLAY_MEDIA_ASSIST,
        {
            "name": {"value": "Test Player 1"},
            "track": {"value": "Tennessee Whiskey"},
            "radio_mode": {"value": True},
        },
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 6
    call = calls[5]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_PLAY_MEDIA_ADVANCED
    assert call.data == {
        "entity_id": entity_id,
        "media_id": media_id,
        "radio_mode": True,
    }

    # Test error response when player is not found
    with pytest.raises(intent.MatchFailedError) as error:
        response = await intent.async_handle(
            hass,
            "test",
            music_assistant_intent.INTENT_PLAY_MEDIA_ASSIST,
            {"name": {"value": "The None Existent Player"}},
        )

    # Exception should contain details of what we tried to match
    assert isinstance(error.value, intent.MatchFailedError)
    assert error.value.result.no_match_reason == intent.MatchFailedReason.NAME
    constraints = error.value.constraints
    assert constraints.name == "The None Existent Player"
    assert constraints.area_name is None
    assert constraints.domains and (set(constraints.domains) == {MEDIA_PLAYER_DOMAIN})
    assert constraints.device_classes is None
