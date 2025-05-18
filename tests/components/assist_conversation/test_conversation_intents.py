"""Test intents for the default agent."""

from datetime import datetime
from unittest.mock import patch

from freezegun import freeze_time

from homeassistant.components import (
    conversation,
    cover,
    light,
    media_player,
    todo,
    vacuum,
    valve,
)
from homeassistant.components.cover import intent as cover_intent
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    intent as media_player_intent,
)
from homeassistant.components.vacuum import intent as vaccum_intent
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_CLOSED,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    floor_registry as fr,
    intent,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_mock_service


class MockTodoListEntity(todo.TodoListEntity):
    """Test todo list entity."""

    def __init__(self, items: list[todo.TodoItem] | None = None) -> None:
        """Initialize entity."""
        self._attr_todo_items = items or []

    @property
    def items(self) -> list[todo.TodoItem]:
        """Return the items in the To-do list."""
        return self._attr_todo_items

    async def async_create_todo_item(self, item: todo.TodoItem) -> None:
        """Add an item to the To-do list."""
        self._attr_todo_items.append(item)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete an item in the To-do list."""
        self._attr_todo_items = [item for item in self.items if item.uid not in uids]


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


async def test_cover_device_class(
    hass: HomeAssistant,
    init_components,
) -> None:
    """Test the open position for covers by device class."""
    await cover_intent.async_setup_intents(hass)

    entity_id = f"{cover.DOMAIN}.front"
    hass.states.async_set(
        entity_id, STATE_CLOSED, attributes={"device_class": "garage"}
    )
    async_expose_entity(hass, conversation.DOMAIN, entity_id, True)

    # Open service
    calls = async_mock_service(hass, cover.DOMAIN, cover.SERVICE_OPEN_COVER)
    result = await conversation.async_converse(
        hass, "open the garage door", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "Opened the garage"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}


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
    attributes = {
        ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
    }

    hass.states.async_set(entity_id, STATE_PLAYING, attributes=attributes)
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

    # Unpause requires paused state
    hass.states.async_set(entity_id, STATE_PAUSED, attributes=attributes)

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
    assert response.speech["plain"]["speech"] == "Resumed"
    assert len(calls) == 1
    call = calls[0]
    assert call.data == {"entity_id": entity_id}

    # Next track requires playing state
    hass.states.async_set(entity_id, STATE_PLAYING, attributes=attributes)

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


async def test_turn_floor_lights_on_off(
    hass: HomeAssistant,
    init_components,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test that we can turn lights on/off for an entire floor."""
    floor_ground = floor_registry.async_create("ground", aliases={"downstairs"})
    floor_upstairs = floor_registry.async_create("upstairs")

    # Kitchen and living room are on the ground floor
    area_kitchen = area_registry.async_get_or_create("kitchen_id")
    area_kitchen = area_registry.async_update(
        area_kitchen.id, name="kitchen", floor_id=floor_ground.floor_id
    )

    area_living_room = area_registry.async_get_or_create("living_room_id")
    area_living_room = area_registry.async_update(
        area_living_room.id, name="living_room", floor_id=floor_ground.floor_id
    )

    # Bedroom is upstairs
    area_bedroom = area_registry.async_get_or_create("bedroom_id")
    area_bedroom = area_registry.async_update(
        area_bedroom.id, name="bedroom", floor_id=floor_upstairs.floor_id
    )

    # One light per area
    kitchen_light = entity_registry.async_get_or_create(
        "light", "demo", "kitchen_light"
    )
    kitchen_light = entity_registry.async_update_entity(
        kitchen_light.entity_id, area_id=area_kitchen.id
    )
    hass.states.async_set(kitchen_light.entity_id, "off")

    living_room_light = entity_registry.async_get_or_create(
        "light", "demo", "living_room_light"
    )
    living_room_light = entity_registry.async_update_entity(
        living_room_light.entity_id, area_id=area_living_room.id
    )
    hass.states.async_set(living_room_light.entity_id, "off")

    bedroom_light = entity_registry.async_get_or_create(
        "light", "demo", "bedroom_light"
    )
    bedroom_light = entity_registry.async_update_entity(
        bedroom_light.entity_id, area_id=area_bedroom.id
    )
    hass.states.async_set(bedroom_light.entity_id, "off")

    # Target by floor
    on_calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    result = await conversation.async_converse(
        hass, "turn on all lights downstairs", None, Context(), None
    )

    assert len(on_calls) == 2
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert {s.entity_id for s in result.response.matched_states} == {
        kitchen_light.entity_id,
        living_room_light.entity_id,
    }

    on_calls.clear()
    result = await conversation.async_converse(
        hass, "upstairs lights on", None, Context(), None
    )

    assert len(on_calls) == 1
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert {s.entity_id for s in result.response.matched_states} == {
        bedroom_light.entity_id
    }

    off_calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_OFF)
    result = await conversation.async_converse(
        hass, "turn upstairs lights off", None, Context(), None
    )

    assert len(off_calls) == 1
    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert {s.entity_id for s in result.response.matched_states} == {
        bedroom_light.entity_id
    }


async def test_todo_add_item_fr(
    hass: HomeAssistant,
    init_components,
) -> None:
    """Test that wildcard matches prioritize results with more literal text matched."""
    assert await async_setup_component(hass, todo.DOMAIN, {})
    hass.states.async_set("todo.liste_des_courses", 0, {})

    with (
        patch.object(hass.config, "language", "fr"),
        patch(
            "homeassistant.components.todo.intent.ListAddItemIntent.async_handle",
            return_value=intent.IntentResponse(hass.config.language),
        ) as mock_handle,
    ):
        await conversation.async_converse(
            hass, "Ajoute de la farine a la liste des courses", None, Context(), None
        )
        mock_handle.assert_called_once()
        assert mock_handle.call_args.args
        intent_obj = mock_handle.call_args.args[0]
        assert intent_obj.slots.get("item", {}).get("value", "").strip() == "farine"


@freeze_time(
    datetime(
        year=2013,
        month=9,
        day=17,
        hour=1,
        minute=2,
        tzinfo=dt_util.UTC,
    )
)
async def test_date_time(
    hass: HomeAssistant,
    init_components,
) -> None:
    """Test the date and time intents."""
    await hass.config.async_set_time_zone("UTC")
    result = await conversation.async_converse(
        hass, "what is the date", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "September 17th, 2013"

    result = await conversation.async_converse(
        hass, "what time is it", None, Context(), None
    )
    await hass.async_block_till_done()

    response = result.response
    assert response.response_type == intent.IntentResponseType.ACTION_DONE
    assert response.speech["plain"]["speech"] == "1:02 AM"
