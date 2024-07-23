"""The tests for the media_player platform."""

import pytest

from homeassistant.components.media_player import (
    DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_VOLUME_SET,
    intent as media_player_intent,
)
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
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
        await hass.async_block_till_done()

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
        await hass.async_block_till_done()


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
        await hass.async_block_till_done()


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
        await hass.async_block_till_done()

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
        await hass.async_block_till_done()


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
        await hass.async_block_till_done()

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
        await hass.async_block_till_done()


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
        await hass.async_block_till_done()

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
