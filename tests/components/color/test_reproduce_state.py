"""Scene reproduce_state tests for the Color helper."""

from homeassistant.components.color.const import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_MODE,
    DOMAIN,
    KIND_CHROMATIC,
    KIND_WHITE,
    MODE_CHROMATIC,
)
from homeassistant.components.color.reproduce_state import async_reproduce_states
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry

ENTITY_ID = "color.test_color"


async def _setup_entity(hass: HomeAssistant) -> None:
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


async def test_reproduce_chromatic_hex(hass: HomeAssistant) -> None:
    """Test reproducing a chromatic snapshot from its hex state."""
    await _setup_entity(hass)
    snapshot = State(
        ENTITY_ID,
        "#00FF00",
        {ATTR_KIND: KIND_CHROMATIC, ATTR_BRIGHTNESS: None},
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    _r, g, _b = state.attributes[ATTR_RGB_COLOR]
    assert g > 200
    assert state.attributes[ATTR_BRIGHTNESS] is None


async def test_reproduce_white_with_brightness(hass: HomeAssistant) -> None:
    """Test reproducing a white snapshot restores kelvin and brightness."""
    await _setup_entity(hass)
    snapshot = State(
        ENTITY_ID,
        "#FFFFFF",
        {ATTR_KIND: KIND_WHITE, ATTR_COLOR_TEMP_KELVIN: 3500, ATTR_BRIGHTNESS: 200},
    )
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_KIND] == KIND_WHITE
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3500
    assert state.attributes[ATTR_BRIGHTNESS] == 200


async def test_reproduce_unknown_entity_is_a_noop(hass: HomeAssistant) -> None:
    """Test reproducing a state for a missing entity logs and returns."""
    await _setup_entity(hass)
    snapshot = State("color.does_not_exist", "#00FF00", {ATTR_KIND: KIND_CHROMATIC})
    await async_reproduce_states(hass, [snapshot])
    await hass.async_block_till_done()
    assert hass.states.get("color.does_not_exist") is None
