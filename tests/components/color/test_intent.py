"""Tests for the Color helper intents."""

import pytest

from homeassistant.components.color import intent as color_intent
from homeassistant.components.color.const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_MODE,
    DOMAIN,
    FIELD_BRIGHTNESS,
    FIELD_KELVIN,
    KIND_CHROMATIC,
    KIND_WHITE,
    MODE_CHROMATIC,
    SERVICE_SET_BRIGHTNESS,
    SERVICE_SET_COLOR,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import MockConfigEntry, async_mock_service

ENTITY_ID = "color.test_color"


async def _create_entry(hass: HomeAssistant) -> None:
    """Set up a chromatic entry producing the test entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Color",
        data={
            CONF_NAME: "Test Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#FFFFFF",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is not None
    await color_intent.async_setup_intents(hass)


async def test_intent_set_color(hass: HomeAssistant) -> None:
    """A spoken color name reaches the entity as a color."""
    await _create_entry(hass)

    await intent.async_handle(
        hass,
        "test",
        color_intent.INTENT_SET,
        {"name": {"value": "Test Color"}, "color": {"value": "blue"}},
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_KIND] == KIND_CHROMATIC
    # The intent passes the name's rgb triple, which echoes back exactly.
    assert state.attributes[ATTR_RGB_COLOR] == [0, 0, 255]
    assert state.attributes[ATTR_BRIGHTNESS] is None


async def test_intent_set_color_temperature(hass: HomeAssistant) -> None:
    """A spoken color temperature is stored as a white color."""
    await _create_entry(hass)

    await intent.async_handle(
        hass,
        "test",
        color_intent.INTENT_SET,
        {"name": {"value": "Test Color"}, "temperature": {"value": 2700}},
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_KIND] == KIND_WHITE
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2700


@pytest.mark.parametrize(
    ("percentage", "expected"),
    [(0, 0), (20, 51), (50, 128), (100, 255)],
)
async def test_intent_brightness_is_a_percentage(
    hass: HomeAssistant, percentage: int, expected: int
) -> None:
    """Brightness is spoken as a percentage and stored on the 0-255 scale."""
    await _create_entry(hass)

    await intent.async_handle(
        hass,
        "test",
        color_intent.INTENT_SET,
        {
            "name": {"value": "Test Color"},
            "color": {"value": "red"},
            "brightness": {"value": percentage},
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_RGB_COLOR] == [255, 0, 0]
    assert state.attributes[ATTR_BRIGHTNESS] == expected


async def test_intent_brightness_only_routes_to_set_brightness(
    hass: HomeAssistant,
) -> None:
    """Without a color slot the call must go to set_brightness.

    set_color requires a color, so routing a brightness-only command there
    would fail validation instead of dimming the helper.
    """
    await _create_entry(hass)
    set_color_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_COLOR)
    set_brightness_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_BRIGHTNESS)

    await intent.async_handle(
        hass,
        "test",
        color_intent.INTENT_SET,
        {"name": {"value": "Test Color"}, "brightness": {"value": 40}},
    )
    await hass.async_block_till_done()

    assert not set_color_calls
    assert len(set_brightness_calls) == 1
    assert set_brightness_calls[0].data == {
        ATTR_ENTITY_ID: ENTITY_ID,
        FIELD_BRIGHTNESS: 102,
    }


async def test_intent_color_and_temperature_go_to_set_color(
    hass: HomeAssistant,
) -> None:
    """A color slot routes to set_color, carrying brightness along."""
    await _create_entry(hass)
    calls = async_mock_service(hass, DOMAIN, SERVICE_SET_COLOR)

    await intent.async_handle(
        hass,
        "test",
        color_intent.INTENT_SET,
        {
            "name": {"value": "Test Color"},
            "temperature": {"value": 3000},
            "brightness": {"value": 100},
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: ENTITY_ID,
        FIELD_KELVIN: 3000,
        FIELD_BRIGHTNESS: 255,
    }


async def test_intent_only_targets_color_entities(hass: HomeAssistant) -> None:
    """required_domains keeps an identically named light out of the match."""
    await _create_entry(hass)
    hass.states.async_set("light.test_color", "off", {"friendly_name": "Test Color"})
    light_calls = async_mock_service(hass, "light", "turn_on")
    color_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_COLOR)

    await intent.async_handle(
        hass,
        "test",
        color_intent.INTENT_SET,
        {"name": {"value": "Test Color"}, "color": {"value": "green"}},
    )
    await hass.async_block_till_done()

    assert not light_calls
    assert len(color_calls) == 1
    assert color_calls[0].data[ATTR_ENTITY_ID] == ENTITY_ID


@pytest.mark.parametrize(
    "slots",
    [
        {"color": {"value": "not-a-color"}},
        {"temperature": {"value": 500}},
        {"temperature": {"value": 40000}},
        {"brightness": {"value": 150}},
        {"brightness": {"value": -1}},
    ],
)
async def test_intent_rejects_out_of_range_slots(
    hass: HomeAssistant, slots: dict
) -> None:
    """Bad slot values fail validation rather than reaching a service."""
    await _create_entry(hass)

    with pytest.raises(intent.InvalidSlotInfo):
        await intent.async_handle(
            hass,
            "test",
            color_intent.INTENT_SET,
            {"name": {"value": "Test Color"}} | slots,
        )


async def test_intent_unknown_entity(hass: HomeAssistant) -> None:
    """Naming a helper that does not exist fails to match."""
    await _create_entry(hass)

    with pytest.raises(intent.MatchFailedError):
        await intent.async_handle(
            hass,
            "test",
            color_intent.INTENT_SET,
            {"name": {"value": "Nonexistent"}, "color": {"value": "blue"}},
        )
