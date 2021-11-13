"""Test the light domain for the HALO Home integration."""

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    COLOR_MODE_COLOR_TEMP,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components.halohome.test_config_flow import (
    ENTITY_ID_LIGHT_1,
    ENTITY_NAME_LIGHT_1,
)
from tests.components.halohome.test_init import setup_halo


async def test_default_states(hass: HomeAssistant):
    """Test the default states of a HALO Home light."""
    await setup_halo(hass)
    state = hass.states.get(ENTITY_ID_LIGHT_1)
    assert state.state == STATE_OFF
    assert state.attributes["friendly_name"] == ENTITY_NAME_LIGHT_1
    assert state.attributes["min_mireds"] == 200
    assert state.attributes["max_mireds"] == 370
    assert state.attributes["supported_color_modes"] == [COLOR_MODE_COLOR_TEMP]


async def test_turn_on(hass: HomeAssistant):
    """Test turning on a HALO Home light."""
    await setup_halo(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID_LIGHT_1},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID_LIGHT_1)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 255
    assert state.attributes.get(ATTR_COLOR_TEMP) is None


async def test_turn_off(hass: HomeAssistant):
    """Test turning off a HALO Home light."""
    await setup_halo(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID_LIGHT_1},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID_LIGHT_1)
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_BRIGHTNESS) is None
    assert state.attributes.get(ATTR_COLOR_TEMP) is None


async def test_set_brightness(hass: HomeAssistant):
    """Test setting the brightness of a HALO Home light."""
    await setup_halo(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID_LIGHT_1, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID_LIGHT_1)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128
    assert state.attributes.get(ATTR_COLOR_TEMP) is None


async def test_turn_on_previous_state(hass: HomeAssistant):
    """Test turning on maintains the previous brightness and color temp."""
    await setup_halo(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID_LIGHT_1, ATTR_BRIGHTNESS: 40, ATTR_COLOR_TEMP: 220},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID_LIGHT_1)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 40
    assert state.attributes.get(ATTR_COLOR_TEMP) == 220

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID_LIGHT_1},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID_LIGHT_1)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID_LIGHT_1},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID_LIGHT_1)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 40
    assert state.attributes.get(ATTR_COLOR_TEMP) == 220


async def test_set_color_temp(hass: HomeAssistant):
    """Test setting the color temperature of a HALO Home light."""
    await setup_halo(hass)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID_LIGHT_1, ATTR_COLOR_TEMP: 250},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID_LIGHT_1)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) is None
    assert state.attributes.get(ATTR_COLOR_TEMP) == 250
