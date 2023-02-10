"""Tests for Intent component."""
import pytest

from homeassistant.components.cover import SERVICE_OPEN_COVER
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry, entity_registry, intent
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


async def test_http_handle_intent(hass, hass_client, hass_admin_user):
    """Test handle intent via HTTP API."""

    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "OrderBeer"

        async def async_handle(self, intent):
            """Handle the intent."""
            assert intent.context.user_id == hass_admin_user.id
            response = intent.create_response()
            response.async_set_speech(
                "I've ordered a {}!".format(intent.slots["type"]["value"])
            )
            response.async_set_card(
                "Beer ordered", "You chose a {}.".format(intent.slots["type"]["value"])
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

    assert response.speech["plain"]["speech"] == "Opened garage door"
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


async def test_get_state_intent(hass: HomeAssistant) -> None:
    """Test HassGetState intent.

    This tests name, area, domain, device class, and state constraints.
    """
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})

    areas = area_registry.async_get(hass)
    bedroom = areas.async_get_or_create("bedroom")
    kitchen = areas.async_get_or_create("kitchen")

    # 1 light in bedroom (off)
    # 1 binary sensor (problem, on)
    # 1 light in kitchen (on)
    # 1 sensor in kitchen (50)
    entities = entity_registry.async_get(hass)
    bedroom_light = entities.async_get_or_create("light", "demo", "1")
    entities.async_update_entity(bedroom_light.entity_id, area_id=bedroom.id)

    bedroom_sensor = entities.async_get_or_create("binary_sensor", "demo", "2")
    entities.async_update_entity(bedroom_sensor.entity_id, area_id=bedroom.id)

    kitchen_sensor = entities.async_get_or_create("sensor", "demo", "3")
    entities.async_update_entity(kitchen_sensor.entity_id, area_id=kitchen.id)

    kitchen_light = entities.async_get_or_create("light", "demo", "4")
    entities.async_update_entity(kitchen_light.entity_id, area_id=kitchen.id)

    kitchen_sensor = entities.async_get_or_create("sensor", "demo", "5")
    entities.async_update_entity(kitchen_sensor.entity_id, area_id=kitchen.id)

    hass.states.async_set(
        bedroom_light.entity_id, "off", attributes={ATTR_FRIENDLY_NAME: "bedroom light"}
    )
    hass.states.async_set(
        bedroom_sensor.entity_id,
        "on",
        attributes={ATTR_FRIENDLY_NAME: "bedroom sensor", ATTR_DEVICE_CLASS: "problem"},
    )
    hass.states.async_set(
        kitchen_light.entity_id, "on", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )
    hass.states.async_set(
        kitchen_sensor.entity_id,
        50.0,
        attributes={ATTR_FRIENDLY_NAME: "kitchen sensor"},
    )

    # is bedroom light off?
    result = await intent.async_handle(
        hass,
        "test",
        "HassGetState",
        {"name": {"value": "bedroom light"}, "state": {"value": "off"}},
    )

    # yes
    assert result.matched_states and (
        result.matched_states[0].entity_id == bedroom_light.entity_id
    )
    assert not result.unmatched_states

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
    assert not result.matched_states
    assert result.unmatched_states and (
        result.unmatched_states[0].entity_id == kitchen_light.entity_id
    )

    # what is the value of the kitchen sensor?
    result = await intent.async_handle(
        hass,
        "test",
        "HassGetState",
        {
            "name": {"value": "kitchen sensor"},
        },
    )

    assert result.matched_states and (
        result.matched_states[0].entity_id == kitchen_sensor.entity_id
    )
    assert not result.unmatched_states

    # is there a problem in the bedroom?
    result = await intent.async_handle(
        hass,
        "test",
        "HassGetState",
        {
            "area": {"value": "bedroom"},
            "device_class": {"value": "problem"},
            "state": {"value": "on"},
        },
    )

    # yes
    assert result.matched_states and (
        result.matched_states[0].entity_id == bedroom_sensor.entity_id
    )
    assert not result.unmatched_states

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
    assert not result.matched_states and not result.unmatched_states

    # Test unknown area failure
    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            "HassGetState",
            {
                "area": {"value": "does-not-exist"},
                "domain": {"value": "light"},
            },
        )
