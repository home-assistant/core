"""The tests for the media_player platform."""

import pytest

from homeassistant.components.media_player import (
    DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_PLAY_MEDIA,
    SERVICE_SEARCH_MEDIA,
    SERVICE_VOLUME_SET,
    BrowseMedia,
    MediaClass,
    MediaType,
    SearchMedia,
    intent as media_player_intent,
)
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    floor_registry as fr,
    intent,
)

from tests.common import async_mock_service


async def test_pause_media_player_intent(hass: HomeAssistant) -> None:
    """Test HassMediaPause intent for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_media_player"
    attributes = {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.PAUSE}

    hass.states.async_set(entity_id, STATE_PLAYING, attributes=attributes)
    calls = async_mock_service(
        hass,
        DOMAIN,
        SERVICE_MEDIA_PAUSE,
    )

    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_PAUSE,
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_MEDIA_PAUSE
    assert call.data == {"entity_id": entity_id}

    # Test if not playing
    hass.states.async_set(entity_id, STATE_IDLE, attributes=attributes)

    with pytest.raises(intent.MatchFailedError):
        response = await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_PAUSE,
        )

    # Test feature not supported
    hass.states.async_set(
        entity_id,
        STATE_PLAYING,
        attributes={ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature(0)},
    )

    with pytest.raises(intent.MatchFailedError):
        response = await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_PAUSE,
        )


async def test_unpause_media_player_intent(hass: HomeAssistant) -> None:
    """Test HassMediaUnpause intent for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_media_player"
    hass.states.async_set(entity_id, STATE_PAUSED)
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PLAY)

    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_UNPAUSE,
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_MEDIA_PLAY
    assert call.data == {"entity_id": entity_id}

    # Test if not paused
    hass.states.async_set(
        entity_id,
        STATE_PLAYING,
    )

    with pytest.raises(intent.MatchFailedError):
        response = await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_UNPAUSE,
        )


async def test_next_media_player_intent(hass: HomeAssistant) -> None:
    """Test HassMediaNext intent for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_media_player"
    attributes = {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.NEXT_TRACK}

    hass.states.async_set(entity_id, STATE_PLAYING, attributes=attributes)

    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_NEXT_TRACK)

    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_NEXT,
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_MEDIA_NEXT_TRACK
    assert call.data == {"entity_id": entity_id}

    # Test if not playing
    hass.states.async_set(entity_id, STATE_IDLE, attributes=attributes)

    with pytest.raises(intent.MatchFailedError):
        response = await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_NEXT,
        )

    # Test feature not supported
    hass.states.async_set(
        entity_id,
        STATE_PLAYING,
        attributes={ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature(0)},
    )

    with pytest.raises(intent.MatchFailedError):
        response = await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_NEXT,
            {"name": {"value": "test media player"}},
        )


async def test_previous_media_player_intent(hass: HomeAssistant) -> None:
    """Test HassMediaPrevious intent for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_media_player"
    attributes = {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.PREVIOUS_TRACK}

    hass.states.async_set(entity_id, STATE_PLAYING, attributes=attributes)

    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK)

    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_PREVIOUS,
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_MEDIA_PREVIOUS_TRACK
    assert call.data == {"entity_id": entity_id}

    # Test if not playing
    hass.states.async_set(entity_id, STATE_IDLE, attributes=attributes)

    with pytest.raises(intent.MatchFailedError):
        response = await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_PREVIOUS,
        )

    # Test feature not supported
    hass.states.async_set(
        entity_id,
        STATE_PLAYING,
        attributes={ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature(0)},
    )

    with pytest.raises(intent.MatchFailedError):
        response = await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_PREVIOUS,
            {"name": {"value": "test media player"}},
        )


async def test_volume_media_player_intent(hass: HomeAssistant) -> None:
    """Test HassSetVolume intent for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_media_player"
    attributes = {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.VOLUME_SET}

    hass.states.async_set(entity_id, STATE_PLAYING, attributes=attributes)
    calls = async_mock_service(hass, DOMAIN, SERVICE_VOLUME_SET)

    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_SET_VOLUME,
        {"volume_level": {"value": 50}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_VOLUME_SET
    assert call.data == {"entity_id": entity_id, "volume_level": 0.5}

    # Test if not playing
    hass.states.async_set(entity_id, STATE_IDLE, attributes=attributes)

    with pytest.raises(intent.MatchFailedError):
        response = await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_SET_VOLUME,
            {"volume_level": {"value": 50}},
        )

    # Test feature not supported
    hass.states.async_set(
        entity_id,
        STATE_PLAYING,
        attributes={ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature(0)},
    )

    with pytest.raises(intent.MatchFailedError):
        response = await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_SET_VOLUME,
            {"volume_level": {"value": 50}},
        )


async def test_multiple_media_players(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test HassMedia* intents with multiple media players."""
    await media_player_intent.async_setup_intents(hass)

    attributes = {
        ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
    }

    # House layout
    # Floor 1 (ground):
    #   - Kitchen
    #     - Smart speaker
    #   - Living room
    #     - TV
    #     - Smart speaker
    # Floor 2 (upstairs):
    #   - Bedroom
    #     - TV
    #     - Smart speaker
    #   - Bathroom
    #     - Smart speaker

    # Floor 1
    floor_1 = floor_registry.async_create("first floor", aliases={"ground"})
    area_kitchen = area_registry.async_get_or_create("kitchen")
    area_kitchen = area_registry.async_update(
        area_kitchen.id, floor_id=floor_1.floor_id
    )
    area_living_room = area_registry.async_get_or_create("living room")
    area_living_room = area_registry.async_update(
        area_living_room.id, floor_id=floor_1.floor_id
    )

    kitchen_smart_speaker = entity_registry.async_get_or_create(
        "media_player", "test", "kitchen_smart_speaker"
    )
    kitchen_smart_speaker = entity_registry.async_update_entity(
        kitchen_smart_speaker.entity_id, name="smart speaker", area_id=area_kitchen.id
    )
    hass.states.async_set(
        kitchen_smart_speaker.entity_id, STATE_PAUSED, attributes=attributes
    )

    living_room_smart_speaker = entity_registry.async_get_or_create(
        "media_player", "test", "living_room_smart_speaker"
    )
    living_room_smart_speaker = entity_registry.async_update_entity(
        living_room_smart_speaker.entity_id,
        name="smart speaker",
        area_id=area_living_room.id,
    )
    hass.states.async_set(
        living_room_smart_speaker.entity_id, STATE_PAUSED, attributes=attributes
    )

    living_room_tv = entity_registry.async_get_or_create(
        "media_player", "test", "living_room_tv"
    )
    living_room_tv = entity_registry.async_update_entity(
        living_room_tv.entity_id, name="TV", area_id=area_living_room.id
    )
    hass.states.async_set(
        living_room_tv.entity_id, STATE_PLAYING, attributes=attributes
    )

    # Floor 2
    floor_2 = floor_registry.async_create("second floor", aliases={"upstairs"})
    area_bedroom = area_registry.async_get_or_create("bedroom")
    area_bedroom = area_registry.async_update(
        area_bedroom.id, floor_id=floor_2.floor_id
    )
    area_bathroom = area_registry.async_get_or_create("bathroom")
    area_bathroom = area_registry.async_update(
        area_bathroom.id, floor_id=floor_2.floor_id
    )

    bedroom_tv = entity_registry.async_get_or_create(
        "media_player", "test", "bedroom_tv"
    )
    bedroom_tv = entity_registry.async_update_entity(
        bedroom_tv.entity_id, name="TV", area_id=area_bedroom.id
    )
    hass.states.async_set(bedroom_tv.entity_id, STATE_PLAYING, attributes=attributes)

    bedroom_smart_speaker = entity_registry.async_get_or_create(
        "media_player", "test", "bedroom_smart_speaker"
    )
    bedroom_smart_speaker = entity_registry.async_update_entity(
        bedroom_smart_speaker.entity_id, name="smart speaker", area_id=area_bedroom.id
    )
    hass.states.async_set(
        bedroom_smart_speaker.entity_id, STATE_PAUSED, attributes=attributes
    )

    bathroom_smart_speaker = entity_registry.async_get_or_create(
        "media_player", "test", "bathroom_smart_speaker"
    )
    bathroom_smart_speaker = entity_registry.async_update_entity(
        bathroom_smart_speaker.entity_id, name="smart speaker", area_id=area_bathroom.id
    )
    hass.states.async_set(
        bathroom_smart_speaker.entity_id, STATE_PAUSED, attributes=attributes
    )

    # -----

    # There are multiple TV's currently playing
    with pytest.raises(intent.MatchFailedError):
        response = await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_PAUSE,
            {"name": {"value": "TV"}},
        )

    # Pause the upstairs TV
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PAUSE)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_PAUSE,
        {"name": {"value": "TV"}, "floor": {"value": "upstairs"}},
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": bedroom_tv.entity_id}
    hass.states.async_set(bedroom_tv.entity_id, STATE_PAUSED, attributes=attributes)

    # Now we can pause the only playing TV (living room)
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PAUSE)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_PAUSE,
        {"name": {"value": "TV"}},
    )

    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": living_room_tv.entity_id}
    hass.states.async_set(living_room_tv.entity_id, STATE_PAUSED, attributes=attributes)

    # Unpause the kitchen smart speaker (explicit area)
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PLAY)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_UNPAUSE,
        {"name": {"value": "smart speaker"}, "area": {"value": "kitchen"}},
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": kitchen_smart_speaker.entity_id}
    hass.states.async_set(
        kitchen_smart_speaker.entity_id, STATE_PLAYING, attributes=attributes
    )

    # Unpause living room smart speaker (context area)
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PLAY)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_UNPAUSE,
        {
            "name": {"value": "smart speaker"},
            "preferred_area_id": {"value": area_living_room.id},
        },
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": living_room_smart_speaker.entity_id}
    hass.states.async_set(
        living_room_smart_speaker.entity_id, STATE_PLAYING, attributes=attributes
    )

    # Unpause all of the upstairs media players
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PLAY)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_UNPAUSE,
        {"floor": {"value": "upstairs"}},
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 3
    assert {call.data["entity_id"] for call in calls} == {
        bedroom_tv.entity_id,
        bedroom_smart_speaker.entity_id,
        bathroom_smart_speaker.entity_id,
    }
    for entity in (bedroom_tv, bedroom_smart_speaker, bathroom_smart_speaker):
        hass.states.async_set(entity.entity_id, STATE_PLAYING, attributes=attributes)

    # Pause bedroom TV (context floor)
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PAUSE)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_PAUSE,
        {
            "name": {"value": "TV"},
            "preferred_floor_id": {"value": floor_2.floor_id},
        },
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": bedroom_tv.entity_id}
    hass.states.async_set(bedroom_tv.entity_id, STATE_PAUSED, attributes=attributes)

    # Set volume in the bathroom
    calls = async_mock_service(hass, DOMAIN, SERVICE_VOLUME_SET)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_SET_VOLUME,
        {"area": {"value": "bathroom"}, "volume_level": {"value": 50}},
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": bathroom_smart_speaker.entity_id,
        "volume_level": 0.5,
    }

    # Next track in the kitchen (only media player that is playing on ground floor)
    hass.states.async_set(
        living_room_smart_speaker.entity_id, STATE_PAUSED, attributes=attributes
    )

    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_NEXT_TRACK)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_NEXT,
        {"floor": {"value": "ground"}},
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": kitchen_smart_speaker.entity_id}

    # Pause the kitchen smart speaker (all ground floor media players are now paused)
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PAUSE)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_PAUSE,
        {"area": {"value": "kitchen"}},
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": kitchen_smart_speaker.entity_id}

    hass.states.async_set(
        kitchen_smart_speaker.entity_id, STATE_PAUSED, attributes=attributes
    )

    # Unpause with no context (only kitchen should be resumed)
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PLAY)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_UNPAUSE,
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": kitchen_smart_speaker.entity_id}

    hass.states.async_set(
        kitchen_smart_speaker.entity_id, STATE_PLAYING, attributes=attributes
    )


async def test_manual_pause_unpause(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unpausing a media player that was manually paused outside of voice."""
    await media_player_intent.async_setup_intents(hass)

    attributes = {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.PAUSE}

    # Create two playing devices
    device_1 = entity_registry.async_get_or_create("media_player", "test", "device-1")
    device_1 = entity_registry.async_update_entity(device_1.entity_id, name="device 1")
    hass.states.async_set(device_1.entity_id, STATE_PLAYING, attributes=attributes)

    device_2 = entity_registry.async_get_or_create("media_player", "test", "device-2")
    device_2 = entity_registry.async_update_entity(device_2.entity_id, name="device 2")
    hass.states.async_set(device_2.entity_id, STATE_PLAYING, attributes=attributes)

    # Pause both devices by voice
    context = Context()
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PAUSE)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_PAUSE,
        context=context,
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 2

    hass.states.async_set(
        device_1.entity_id, STATE_PAUSED, attributes=attributes, context=context
    )
    hass.states.async_set(
        device_2.entity_id, STATE_PAUSED, attributes=attributes, context=context
    )

    # Unpause both devices by voice
    context = Context()
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PLAY)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_UNPAUSE,
        context=context,
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 2

    hass.states.async_set(
        device_1.entity_id, STATE_PLAYING, attributes=attributes, context=context
    )
    hass.states.async_set(
        device_2.entity_id, STATE_PLAYING, attributes=attributes, context=context
    )

    # Pause the first device by voice
    context = Context()
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PAUSE)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_PAUSE,
        {"name": {"value": "device 1"}},
        context=context,
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": device_1.entity_id}

    hass.states.async_set(
        device_1.entity_id, STATE_PAUSED, attributes=attributes, context=context
    )

    # "Manually" pause the second device (outside of voice)
    context = Context()
    hass.states.async_set(
        device_2.entity_id, STATE_PAUSED, attributes=attributes, context=context
    )

    # Unpause with no constraints.
    # Should resume the more recently (manually) paused device.
    context = Context()
    calls = async_mock_service(hass, DOMAIN, SERVICE_MEDIA_PLAY)
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_UNPAUSE,
        context=context,
    )
    await hass.async_block_till_done()
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert len(calls) == 1
    assert calls[0].data == {"entity_id": device_2.entity_id}


async def test_search_and_play_media_player_intent(hass: HomeAssistant) -> None:
    """Test HassMediaSearchAndPlay intent for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{DOMAIN}.test_media_player"
    attributes = {
        ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.SEARCH_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
    }
    hass.states.async_set(entity_id, STATE_IDLE, attributes=attributes)

    # Test successful search and play
    search_result_item = BrowseMedia(
        title="Test Track",
        media_class=MediaClass.MUSIC,
        media_content_type=MediaType.MUSIC,
        media_content_id="library/artist/123/album/456/track/789",
        can_play=True,
        can_expand=False,
    )

    # Mock service calls
    search_results = [search_result_item]
    search_calls = async_mock_service(
        hass,
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        response={entity_id: SearchMedia(result=search_results)},
    )
    play_calls = async_mock_service(hass, DOMAIN, SERVICE_PLAY_MEDIA)

    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_SEARCH_AND_PLAY,
        {"search_query": {"value": "test query"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE

    # Response should contain a "media" slot with the matched item.
    assert not response.speech
    media = response.speech_slots.get("media")
    assert isinstance(media, BrowseMedia)
    assert media.title == "Test Track"

    assert len(search_calls) == 1
    search_call = search_calls[0]
    assert search_call.domain == DOMAIN
    assert search_call.service == SERVICE_SEARCH_MEDIA
    assert search_call.data == {
        "entity_id": entity_id,
        "search_query": "test query",
    }

    assert len(play_calls) == 1
    play_call = play_calls[0]
    assert play_call.domain == DOMAIN
    assert play_call.service == SERVICE_PLAY_MEDIA
    assert play_call.data == {
        "entity_id": entity_id,
        "media_content_id": search_result_item.media_content_id,
        "media_content_type": search_result_item.media_content_type,
    }

    # Test no search results
    search_results.clear()
    response = await intent.async_handle(
        hass,
        "test",
        media_player_intent.INTENT_MEDIA_SEARCH_AND_PLAY,
        {"search_query": {"value": "another query"}},
    )
    await hass.async_block_till_done()

    assert response.response_type == intent.IntentResponseType.ACTION_DONE

    # A search failure is indicated by no "media" slot in the response.
    assert not response.speech
    assert "media" not in response.speech_slots
    assert len(search_calls) == 2  # Search was called again
    assert len(play_calls) == 1  # Play was not called again

    # Test feature not supported
    hass.states.async_set(
        entity_id,
        STATE_IDLE,
        attributes={},
    )
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_SEARCH_AND_PLAY,
            {"search_query": {"value": "test query"}},
        )

    # Test feature not supported (missing SEARCH_MEDIA)
    hass.states.async_set(
        entity_id,
        STATE_IDLE,
        attributes={ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.PLAY_MEDIA},
    )
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_SEARCH_AND_PLAY,
            {"search_query": {"value": "test query"}},
        )

    # Test play media service errors
    search_results.append(search_result_item)
    hass.states.async_set(
        entity_id,
        STATE_IDLE,
        attributes={ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.SEARCH_MEDIA},
    )

    async_mock_service(
        hass,
        DOMAIN,
        SERVICE_PLAY_MEDIA,
        raise_exception=HomeAssistantError("Play failed"),
    )
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_SEARCH_AND_PLAY,
            {"search_query": {"value": "play error query"}},
        )

    # Test search service error
    hass.states.async_set(entity_id, STATE_IDLE, attributes=attributes)
    async_mock_service(
        hass,
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        raise_exception=HomeAssistantError("Search failed"),
    )
    with pytest.raises(intent.IntentHandleError, match="Error searching media"):
        await intent.async_handle(
            hass,
            "test",
            media_player_intent.INTENT_MEDIA_SEARCH_AND_PLAY,
            {"search_query": {"value": "error query"}},
        )
