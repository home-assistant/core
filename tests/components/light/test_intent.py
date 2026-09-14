"""Tests for the light intents."""

import pytest

from homeassistant.components import light
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode, intent
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.intent import MatchFailedError, async_handle
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service

ASSISTANT = "conversation"


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
