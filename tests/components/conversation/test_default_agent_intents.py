"""Test intents for the default agent."""

import pytest

from homeassistant.components import conversation, cover, media_player, vacuum, valve
from homeassistant.components.cover import intent as cover_intent
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.media_player import intent as media_player_intent
from homeassistant.components.vacuum import intent as vaccum_intent
from homeassistant.const import STATE_CLOSED
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.fixture
async def init_components(hass: HomeAssistant):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})


async def test_cover_set_position(
    hass: HomeAssistant,
    init_components,
) -> None:
    """Test the open/close/set position for covers."""
    await cover_intent.async_setup_intents(hass)

    entity_id = f"{cover.DOMAIN}.garage_door"
    hass.states.async_set(entity_id, STATE_CLOSED)
    async_expose_entity(hass, conversation.DOMAIN, entity_id, True)

    # open
    calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_OPEN_COVER)
    result = await conversation.async_converse(
        hass, "open the garage door", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Opened"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}

    # close
    calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_CLOSE_COVER)
    result = await conversation.async_converse(
        hass, "close garage door", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Closed"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}

    # set position
    calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_SET_COVER_POSITION)
    result = await conversation.async_converse(
        hass, "set garage door to 50%", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Position set"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id, cover.ATTR_POSITION: 50}


async def test_valve_intents(
    hass: HomeAssistant,
    init_components,
) -> None:
    """Test open/close/set position for valves."""
    entity_id = f"{valve.DOMAIN}.main_valve"
    hass.states.async_set(entity_id, STATE_CLOSED)
    async_expose_entity(hass, conversation.DOMAIN, entity_id, True)

    # open
    calls = async_mock_service(hass, valve.DOMAIN, valve.SERVICE_OPEN_VALVE)
    result = await conversation.async_converse(
        hass, "open the main valve", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Opened"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}

    # close
    calls = async_mock_service(hass, valve.DOMAIN, valve.SERVICE_CLOSE_VALVE)
    result = await conversation.async_converse(
        hass, "close main valve", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Closed"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}

    # set position
    calls = async_mock_service(hass, valve.DOMAIN, valve.SERVICE_SET_VALVE_POSITION)
    result = await conversation.async_converse(
        hass, "set main valve position to 25", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Position set"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id, valve.ATTR_POSITION: 25}


async def test_vacuum_intents(
    hass: HomeAssistant,
    init_components,
) -> None:
    """Test start/return to base for vacuums."""
    await vaccum_intent.async_setup_intents(hass)

    entity_id = f"{vacuum.DOMAIN}.rover"
    hass.states.async_set(entity_id, STATE_CLOSED)
    async_expose_entity(hass, conversation.DOMAIN, entity_id, True)

    # start
    calls = async_mock_service(hass, vacuum.DOMAIN, vacuum.SERVICE_START)
    result = await conversation.async_converse(
        hass, "start rover", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Started"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}

    # return to base
    calls = async_mock_service(hass, vacuum.DOMAIN, vacuum.SERVICE_RETURN_TO_BASE)
    result = await conversation.async_converse(
        hass, "return rover to base", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Returning"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}


async def test_media_player_intents(
    hass: HomeAssistant,
    init_components,
) -> None:
    """Test pause/unpause/next/set volume for media players."""
    await media_player_intent.async_setup_intents(hass)

    entity_id = f"{media_player.DOMAIN}.tv"
    hass.states.async_set(entity_id, media_player.STATE_PLAYING)
    async_expose_entity(hass, conversation.DOMAIN, entity_id, True)

    # pause
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PAUSE
    )
    result = await conversation.async_converse(hass, "pause tv", None, Context(), None)
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Paused"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}

    # unpause
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PLAY
    )
    result = await conversation.async_converse(
        hass, "unpause tv", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Unpaused"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}

    # next
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_NEXT_TRACK
    )
    result = await conversation.async_converse(
        hass, "next item on tv", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Playing next"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}

    # volume
    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_SET
    )
    result = await conversation.async_converse(
        hass, "set tv volume to 75 percent", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Volume set"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {
        "entity_id": entity_id,
        media_player.ATTR_MEDIA_VOLUME_LEVEL: 0.75,
    }
