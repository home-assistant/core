"""Tests for Intent component."""

import pytest

from homeassistant.components.cover import SERVICE_OPEN_COVER
from homeassistant.components.lock import SERVICE_LOCK
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er, intent
from homeassistant.setup import async_setup_component

from tests.common import MockUser, async_mock_service
from tests.typing import ClientSessionGenerator


async def test_http_handle_intent(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_admin_user: MockUser
) -> None:
    """Test handle intent via HTTP API."""

    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "OrderBeer"

        async def async_handle(self, intent_obj):
            """Handle the intent."""
            assert intent_obj.context.user_id == hass_admin_user.id
            response = intent_obj.create_response()
            response.async_set_speech(
                f"I've ordered a {intent_obj.slots['type']['value']}!"
            )
            response.async_set_card(
                "Beer ordered",
                f"You chose a {intent_obj.slots['type']['value']}.",
            )
            return response

    intent.async_register(hass, TestIntentHandler())

    result = await async_setup_component(hass, "intent", {})
    assert result

    client = await hass_client()
    resp = await client.post(
        "/api/intent/handle", json={"name": "OrderBeer", "data": {"type": "Belgian"}}
    )

    assert resp.status == 200
    data = await resp.json()

    assert data == {
        "card": {
            "simple": {"content": "You chose a Belgian.", "title": "Beer ordered"}
        },
        "speech": {
            "plain": {
                "extra_data": None,
                "speech": "I've ordered a Belgian!",
            }
        },
        "language": hass.config.language,
        "response_type": "action_done",
        "data": {"targets": [], "success": [], "failed": []},
    }


async def test_cover_intents_loading(hass: HomeAssistant) -> None:
    """Test Cover Intents Loading."""
    assert await async_setup_component(hass, "intent", {})

    with pytest.raises(intent.UnknownIntent):
        await intent.async_handle(
            hass, "test", "HassOpenCover", {"name": {"value": "garage door"}}
        )

    assert await async_setup_component(hass, "cover", {})
    await hass.async_block_till_done()

    hass.states.async_set("cover.garage_door", "closed")
    calls = async_mock_service(hass, "cover", SERVICE_OPEN_COVER)

    response = await intent.async_handle(
        hass, "test", "HassOpenCover", {"name": {"value": "garage door"}}
    )
    await hass.async_block_till_done()

    assert response.speech["plain"]["speech"] == "Opening garage door"
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "cover"
    assert call.service == "open_cover"
    assert call.data == {"entity_id": "cover.garage_door"}


async def test_turn_on_intent(hass: HomeAssistant) -> None:
    """Test HassTurnOn intent."""
    result = await async_setup_component(hass, "homeassistant", {})
    result = await async_setup_component(hass, "intent", {})
    await hass.async_block_till_done()
    assert result

    hass.states.async_set("light.test_light", "off")
    calls = async_mock_service(hass, "light", SERVICE_TURN_ON)

    await intent.async_handle(
        hass, "test", "HassTurnOn", {"name": {"value": "test light"}}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "light"
    assert call.service == "turn_on"
    assert call.data == {"entity_id": ["light.test_light"]}


async def test_translated_turn_on_intent(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test HassTurnOn intent on domains which don't have the intent."""
    result = await async_setup_component(hass, "homeassistant", {})
    result = await async_setup_component(hass, "intent", {})
    await hass.async_block_till_done()
    assert result

    cover = entity_registry.async_get_or_create("cover", "test", "cover_uid")
    lock = entity_registry.async_get_or_create("lock", "test", "lock_uid")

    hass.states.async_set(cover.entity_id, "closed")
    hass.states.async_set(lock.entity_id, "unlocked")
    cover_service_calls = async_mock_service(hass, "cover", SERVICE_OPEN_COVER)
    lock_service_calls = async_mock_service(hass, "lock", SERVICE_LOCK)

    await intent.async_handle(
        hass, "test", "HassTurnOn", {"name": {"value": cover.entity_id}}
    )
    await intent.async_handle(
        hass, "test", "HassTurnOn", {"name": {"value": lock.entity_id}}
    )
    await hass.async_block_till_done()

    assert len(cover_service_calls) == 1
    call = cover_service_calls[0]
    assert call.domain == "cover"
    assert call.service == "open_cover"
    assert call.data == {"entity_id": cover.entity_id}

    assert len(lock_service_calls) == 1
    call = lock_service_calls[0]
    assert call.domain == "lock"
    assert call.service == "lock"
    assert call.data == {"entity_id": lock.entity_id}


async def test_turn_off_intent(hass: HomeAssistant) -> None:
    """Test HassTurnOff intent."""
    result = await async_setup_component(hass, "homeassistant", {})
    result = await async_setup_component(hass, "intent", {})
    assert result

    hass.states.async_set("light.test_light", "on")
    calls = async_mock_service(hass, "light", SERVICE_TURN_OFF)

    await intent.async_handle(
        hass, "test", "HassTurnOff", {"name": {"value": "test light"}}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "light"
    assert call.service == "turn_off"
    assert call.data == {"entity_id": ["light.test_light"]}


async def test_toggle_intent(hass: HomeAssistant) -> None:
    """Test HassToggle intent."""
    result = await async_setup_component(hass, "homeassistant", {})
    result = await async_setup_component(hass, "intent", {})
    assert result

    hass.states.async_set("light.test_light", "off")
    calls = async_mock_service(hass, "light", SERVICE_TOGGLE)

    await intent.async_handle(
        hass, "test", "HassToggle", {"name": {"value": "test light"}}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "light"
    assert call.service == "toggle"
    assert call.data == {"entity_id": ["light.test_light"]}


async def test_turn_on_multiple_intent(hass: HomeAssistant) -> None:
    """Test HassTurnOn intent with multiple similar entities.

    This tests that matching finds the proper entity among similar names.
    """
    result = await async_setup_component(hass, "homeassistant", {})
    result = await async_setup_component(hass, "intent", {})
    assert result

    hass.states.async_set("light.test_light", "off")
    hass.states.async_set("light.test_lights_2", "off")
    hass.states.async_set("light.test_lighter", "off")
    calls = async_mock_service(hass, "light", SERVICE_TURN_ON)

    await intent.async_handle(
        hass, "test", "HassTurnOn", {"name": {"value": "test lights 2"}}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "light"
    assert call.service == "turn_on"
    assert call.data == {"entity_id": ["light.test_lights_2"]}


async def test_turn_on_all(hass: HomeAssistant) -> None:
    """Test HassTurnOn intent with "all" name."""
    result = await async_setup_component(hass, "homeassistant", {})
    result = await async_setup_component(hass, "intent", {})
    assert result

    hass.states.async_set("light.test_light", "off")
    hass.states.async_set("light.test_light_2", "off")
    calls = async_mock_service(hass, "light", SERVICE_TURN_ON)

    await intent.async_handle(
        hass,
        "test",
        "HassTurnOn",
        {"name": {"value": "all"}, "domain": {"value": "light"}},
    )
    await hass.async_block_till_done()

    # All lights should be on now
    assert len(calls) == 2
    entity_ids = set()
    for call in calls:
        assert call.domain == "light"
        assert call.service == "turn_on"
        entity_ids.update(call.data.get("entity_id", []))

    assert entity_ids == {"light.test_light", "light.test_light_2"}


async def test_get_state_intent(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test HassGetState intent.

    This tests name, area, domain, device class, and state constraints.
    """
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})

    bedroom = area_registry.async_get_or_create("bedroom")
    kitchen = area_registry.async_get_or_create("kitchen")
    office = area_registry.async_get_or_create("office")

    # 1 light in bedroom (off)
    # 1 light in kitchen (on)
    # 1 sensor in kitchen (50)
    # 2 binary sensors in the office (problem, moisture, on)
    bedroom_light = entity_registry.async_get_or_create("light", "demo", "1")
    entity_registry.async_update_entity(bedroom_light.entity_id, area_id=bedroom.id)

    kitchen_sensor = entity_registry.async_get_or_create("sensor", "demo", "2")
    entity_registry.async_update_entity(kitchen_sensor.entity_id, area_id=kitchen.id)

    kitchen_light = entity_registry.async_get_or_create("light", "demo", "3")
    entity_registry.async_update_entity(kitchen_light.entity_id, area_id=kitchen.id)

    kitchen_sensor = entity_registry.async_get_or_create("sensor", "demo", "4")
    entity_registry.async_update_entity(kitchen_sensor.entity_id, area_id=kitchen.id)

    problem_sensor = entity_registry.async_get_or_create("binary_sensor", "demo", "5")
    entity_registry.async_update_entity(problem_sensor.entity_id, area_id=office.id)

    moisture_sensor = entity_registry.async_get_or_create("binary_sensor", "demo", "6")
    entity_registry.async_update_entity(moisture_sensor.entity_id, area_id=office.id)

    hass.states.async_set(
        bedroom_light.entity_id, "off", attributes={ATTR_FRIENDLY_NAME: "bedroom light"}
    )
    hass.states.async_set(
        kitchen_light.entity_id, "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )
    hass.states.async_set(
        kitchen_sensor.entity_id,
        "50.0",
        attributes={ATTR_FRIENDLY_NAME: "kitchen sensor"},
    )
    hass.states.async_set(
        problem_sensor.entity_id,
        "on",
        attributes={ATTR_FRIENDLY_NAME: "problem sensor", ATTR_DEVICE_CLASS: "problem"},
    )
    hass.states.async_set(
        moisture_sensor.entity_id,
        "on",
        attributes={
            ATTR_FRIENDLY_NAME: "moisture sensor",
            ATTR_DEVICE_CLASS: "moisture",
        },
    )

    # ---
    # is bedroom light off?
    result = await intent.async_handle(
        hass,
        "test",
        "HassGetState",
        {"name": {"value": "bedroom light"}, "state": {"value": "off"}},
    )

    # yes
    assert result.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert result.matched_states and (
        result.matched_states[0].entity_id == bedroom_light.entity_id
    )
    assert not result.unmatched_states

    # ---
    # is light in kitchen off?
    result = await intent.async_handle(
        hass,
        "test",
        "HassGetState",
        {
            "area": {"value": "kitchen"},
            "domain": {"value": "light"},
            "state": {"value": "off"},
        },
    )

    # no, it's on
    assert result.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert not result.matched_states
    assert result.unmatched_states and (
        result.unmatched_states[0].entity_id == kitchen_light.entity_id
    )

    # ---
    # what is the value of the kitchen sensor?
    result = await intent.async_handle(
        hass,
        "test",
        "HassGetState",
        {
            "name": {"value": "kitchen sensor"},
        },
    )

    assert result.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert result.matched_states and (
        result.matched_states[0].entity_id == kitchen_sensor.entity_id
    )
    assert not result.unmatched_states

    # ---
    # is there a problem in the office?
    result = await intent.async_handle(
        hass,
        "test",
        "HassGetState",
        {
            "area": {"value": "office"},
            "device_class": {"value": "problem"},
            "state": {"value": "on"},
        },
    )

    # yes
    assert result.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert result.matched_states and (
        result.matched_states[0].entity_id == problem_sensor.entity_id
    )
    assert not result.unmatched_states

    # ---
    # is there a problem or a moisture sensor in the office?
    result = await intent.async_handle(
        hass,
        "test",
        "HassGetState",
        {
            "area": {"value": "office"},
            "device_class": {"value": ["problem", "moisture"]},
        },
    )

    # yes, 2 of them
    assert result.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(result.matched_states) == 2 and {
        state.entity_id for state in result.matched_states
    } == {problem_sensor.entity_id, moisture_sensor.entity_id}
    assert not result.unmatched_states

    # ---
    # are there any binary sensors in the kitchen?
    result = await intent.async_handle(
        hass,
        "test",
        "HassGetState",
        {
            "area": {"value": "kitchen"},
            "domain": {"value": "binary_sensor"},
        },
    )

    # no
    assert result.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert not result.matched_states and not result.unmatched_states

    # Test unknown area failure
    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            "HassGetState",
            {
                "area": {"value": "does-not-exist"},
                "domain": {"value": "light"},
            },
        )


async def test_set_position_intent_unsupported_domain(hass: HomeAssistant) -> None:
    """Test that HassSetPosition intent fails with unsupported domain."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})

    # Can't set position of lights
    hass.states.async_set("light.test_light", "off")

    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            "HassSetPosition",
            {"name": {"value": "test light"}, "position": {"value": 100}},
        )


async def test_intents_with_no_responses(hass: HomeAssistant) -> None:
    """Test intents that should not return a response during handling."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})

    # The "respond" intent gets its response text from home-assistant-intents
    for intent_name in (intent.INTENT_NEVERMIND, intent.INTENT_RESPOND):
        response = await intent.async_handle(hass, "test", intent_name, {})
        assert not response.speech
