"""Tests for the light intents."""

import pytest

from homeassistant.components import light
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode, intent
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.intent import (
    IntentResponseTargetType,
    MatchFailedError,
    MatchFailedReason,
    async_handle,
)
from homeassistant.setup import async_setup_component

from .common import MockLight

from tests.common import async_mock_service, setup_test_component_platform

ASSISTANT = "conversation"
DIMMABLE_ATTRIBUTES = {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS]}


async def test_intent_set_color(hass: HomeAssistant) -> None:
    """Test the set color intent."""
    hass.states.async_set(
        "light.hello_2", "off", {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS]}
    )
    hass.states.async_set("switch.hello", "off")
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET,
        {"name": {"value": "Hello 2"}, "color": {"value": "blue"}},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == "light.hello_2"
    assert call.data.get(light.ATTR_RGB_COLOR) == (0, 0, 255)


async def test_intent_set_color_and_brightness(hass: HomeAssistant) -> None:
    """Test the set color intent."""
    hass.states.async_set(
        "light.hello_2", "off", {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS]}
    )
    hass.states.async_set("switch.hello", "off")
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET,
        {
            "name": {"value": "Hello 2"},
            "color": {"value": "blue"},
            "brightness": {"value": "20"},
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == "light.hello_2"
    assert call.data.get(light.ATTR_RGB_COLOR) == (0, 0, 255)
    assert call.data.get(light.ATTR_BRIGHTNESS_PCT) == 20


async def test_intent_set_temperature(hass: HomeAssistant) -> None:
    """Test setting the color temperature in kevin via intent."""
    hass.states.async_set(
        "light.test", "off", {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP]}
    )
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET,
        {
            "name": {"value": "Test"},
            "temperature": {"value": 2000},
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == "light.test"
    assert call.data.get(light.ATTR_COLOR_TEMP_KELVIN) == 2000


async def test_intent_set_area_only_targets_lights(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only lights are targeted when an area is used without a domain slot."""
    kitchen = area_registry.async_create("Kitchen")
    for domain, unique_id in (("light", "l1"), ("switch", "s1"), ("sensor", "t1")):
        entry = entity_registry.async_get_or_create(domain, "test", unique_id)
        entity_registry.async_update_entity(entry.entity_id, area_id=kitchen.id)
        hass.states.async_set(entry.entity_id, "off")

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET,
        {"area": {"value": "Kitchen"}, "brightness": {"value": "20"}},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get(ATTR_ENTITY_ID) == "light.test_l1"
    assert calls[0].data.get(light.ATTR_BRIGHTNESS_PCT) == 20


async def test_intent_set_without_name_or_area_skips_unexposed(
    hass: HomeAssistant,
) -> None:
    """Test that unexposed lights are not targeted when no name or area is given."""
    assert await async_setup_component(hass, "homeassistant", {})
    hass.states.async_set("light.exposed", "off")
    hass.states.async_set("light.hidden", "off")
    async_expose_entity(hass, ASSISTANT, "light.hidden", False)

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET,
        {"brightness": {"value": "20"}},
        assistant=ASSISTANT,
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get(ATTR_ENTITY_ID) == "light.exposed"


async def test_intent_set_without_name_or_area_all_unexposed(
    hass: HomeAssistant,
) -> None:
    """Test that no lights are targeted when none are exposed."""
    assert await async_setup_component(hass, "homeassistant", {})
    hass.states.async_set("light.hidden", "off")
    async_expose_entity(hass, ASSISTANT, "light.hidden", False)

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    with pytest.raises(MatchFailedError):
        await async_handle(
            hass,
            "test",
            intent.INTENT_SET,
            {"brightness": {"value": "20"}},
            assistant=ASSISTANT,
        )

    assert not calls


@pytest.mark.parametrize(
    ("brightness_step", "expected_step_pct"),
    [
        pytest.param("up", 10, id="up"),
        pytest.param("down", -10, id="down"),
        pytest.param(25, 25, id="increase_by_amount"),
        pytest.param(-25, -25, id="decrease_by_amount"),
    ],
)
async def test_intent_set_brightness_relative(
    hass: HomeAssistant, brightness_step: str | int, expected_step_pct: int
) -> None:
    """Test increasing and decreasing the brightness of a light by name."""
    hass.states.async_set("light.test", "on", DIMMABLE_ATTRIBUTES)
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET_BRIGHTNESS_RELATIVE,
        {
            "name": {"value": "test"},
            "brightness_step": {"value": brightness_step},
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == ["light.test"]
    assert call.data.get(light.ATTR_BRIGHTNESS_STEP_PCT) == expected_step_pct


async def test_intent_set_brightness_relative_includes_off_lights(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test lights that are off are adjusted too, coming up from zero brightness."""
    kitchen = area_registry.async_create("Kitchen")
    for unique_id, state in (("l1", "on"), ("l2", "off")):
        entry = entity_registry.async_get_or_create("light", "test", unique_id)
        entity_registry.async_update_entity(entry.entity_id, area_id=kitchen.id)
        hass.states.async_set(entry.entity_id, state, DIMMABLE_ATTRIBUTES)

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET_BRIGHTNESS_RELATIVE,
        {"area": {"value": "Kitchen"}, "brightness_step": {"value": 10}},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get(ATTR_ENTITY_ID) == ["light.test_l1", "light.test_l2"]
    assert calls[0].data.get(light.ATTR_BRIGHTNESS_STEP_PCT) == 10


async def test_intent_set_brightness_relative_from_off(hass: HomeAssistant) -> None:
    """Test increasing brightness in a dark room brings the light up from zero."""
    entity = MockLight("Test", STATE_OFF, {ColorMode.BRIGHTNESS})
    setup_test_component_platform(hass, light.DOMAIN, [entity])
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {"platform": "test"}}
    )
    await hass.async_block_till_done()
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET_BRIGHTNESS_RELATIVE,
        {"name": {"value": "Test"}, "brightness_step": {"value": 10}},
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes[light.ATTR_BRIGHTNESS] == round(255 * 0.1)


async def test_intent_set_brightness_relative_skips_onoff_lights(
    hass: HomeAssistant,
) -> None:
    """Test lights without brightness support are not adjusted."""
    hass.states.async_set(
        "light.test", "on", {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.ONOFF]}
    )
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    with pytest.raises(MatchFailedError) as err:
        await async_handle(
            hass,
            "test",
            intent.INTENT_SET_BRIGHTNESS_RELATIVE,
            {"name": {"value": "test"}, "brightness_step": {"value": "up"}},
        )

    assert err.value.result.no_match_reason == MatchFailedReason.FEATURE
    assert not calls


async def test_intent_set_brightness_relative_unknown_name(
    hass: HomeAssistant,
) -> None:
    """Test a name that matches no light is reported as a name failure."""
    hass.states.async_set("light.test", "on", DIMMABLE_ATTRIBUTES)
    await intent.async_setup_intents(hass)

    with pytest.raises(MatchFailedError) as err:
        await async_handle(
            hass,
            "test",
            intent.INTENT_SET_BRIGHTNESS_RELATIVE,
            {"name": {"value": "does not exist"}, "brightness_step": {"value": "up"}},
        )

    assert err.value.result.no_match_reason == MatchFailedReason.NAME


async def test_intent_set_brightness_relative_duplicate_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a shared name is unambiguous when only one light can be dimmed."""
    dimmable = entity_registry.async_get_or_create(
        "light", "test", "l1", suggested_object_id="dimmable"
    )
    onoff = entity_registry.async_get_or_create(
        "light", "test", "l2", suggested_object_id="onoff"
    )
    for entry in (dimmable, onoff):
        entity_registry.async_update_entity(entry.entity_id, name="Lamp")
    hass.states.async_set(dimmable.entity_id, "on", DIMMABLE_ATTRIBUTES)
    hass.states.async_set(
        onoff.entity_id, "on", {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.ONOFF]}
    )

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET_BRIGHTNESS_RELATIVE,
        {"name": {"value": "Lamp"}, "brightness_step": {"value": "up"}},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get(ATTR_ENTITY_ID) == [dimmable.entity_id]


async def test_intent_set_brightness_relative_all(hass: HomeAssistant) -> None:
    """Test the reserved "all" name targets every light."""
    hass.states.async_set("light.one", "on", DIMMABLE_ATTRIBUTES)
    hass.states.async_set("light.two", "on", DIMMABLE_ATTRIBUTES)
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET_BRIGHTNESS_RELATIVE,
        {"name": {"value": "all"}, "brightness_step": {"value": "up"}},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data.get(ATTR_ENTITY_ID) == ["light.one", "light.two"]


async def test_intent_set_brightness_relative_response_targets(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the response reports the adjusted lights as successful targets."""
    kitchen = area_registry.async_create("Kitchen")
    entry = entity_registry.async_get_or_create("light", "test", "l1")
    entity_registry.async_update_entity(entry.entity_id, area_id=kitchen.id)
    hass.states.async_set(entry.entity_id, "on", DIMMABLE_ATTRIBUTES)

    async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    response = await async_handle(
        hass,
        "test",
        intent.INTENT_SET_BRIGHTNESS_RELATIVE,
        {"area": {"value": "Kitchen"}, "brightness_step": {"value": "up"}},
    )
    await hass.async_block_till_done()

    assert response.as_dict()["data"]["success"] == [
        {
            "type": IntentResponseTargetType.AREA,
            "name": "Kitchen",
            "id": kitchen.id,
        },
        {
            "type": IntentResponseTargetType.ENTITY,
            "name": "test l1",
            "id": entry.entity_id,
        },
    ]
