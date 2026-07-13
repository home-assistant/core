"""Tests for light platform."""

from unittest.mock import AsyncMock

from pywizlight import PilotBuilder, PilotParser, wizlight
from pywizlight.bulblibrary import BulbType

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.wiz.light import EFFECT_TV_SYNC
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    FAKE_MAC,
    FAKE_OLD_FIRMWARE_DIMMABLE_BULB,
    FAKE_RGBW_BULB,
    FAKE_RGBWW_BULB,
    FAKE_RGBWW_NO_EFFECT_BULB,
    FAKE_TURNABLE_BULB,
    FAKE_TV_SYNC_BOX,
    _mocked_wizlight,
    async_push_update,
    async_setup_integration,
)


async def test_light_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a light unique id."""
    await async_setup_integration(hass)
    entity_id = "light.mock_title"
    assert entity_registry.async_get(entity_id).unique_id == FAKE_MAC
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_light_operation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a light operation."""
    bulb, _ = await async_setup_integration(hass)
    entity_id = "light.mock_title"
    assert entity_registry.async_get(entity_id).unique_id == FAKE_MAC
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_off.assert_called_once()

    await async_push_update(hass, bulb, {"mac": FAKE_MAC, "state": False})
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_on.assert_called_once()

    await async_push_update(hass, bulb, {"mac": FAKE_MAC, "state": True})
    assert hass.states.get(entity_id).state == STATE_ON


async def test_rgbww_light(hass: HomeAssistant) -> None:
    """Test a light operation with a rgbww light."""
    bulb, _ = await async_setup_integration(hass, bulb_type=FAKE_RGBWW_BULB)
    entity_id = "light.mock_title"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBWW_COLOR: (1, 2, 3, 4, 5)},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {"b": 3, "c": 4, "g": 2, "r": 1, "w": 5}

    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, **pilot.pilot_params}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGBWW_COLOR] == (1, 2, 3, 4, 5)

    bulb.turn_on.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 6535, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {"dimming": 50, "temp": 6535}
    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, **pilot.pilot_params}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 6535

    bulb.turn_on.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "Ocean", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {"dimming": 50, "sceneId": 1}
    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, **pilot.pilot_params}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "Ocean"
    assert state.attributes[ATTR_COLOR_MODE] == "brightness"

    bulb.turn_on.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "Forest"},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {"sceneId": 7}
    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, **pilot.pilot_params}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "Forest"
    assert state.attributes[ATTR_COLOR_MODE] == "onoff"

    bulb.turn_on.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "Rhythm"},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {}


async def test_rgbw_light(hass: HomeAssistant) -> None:
    """Test a light operation with a rgbww light."""
    bulb, _ = await async_setup_integration(hass, bulb_type=FAKE_RGBW_BULB)
    entity_id = "light.mock_title"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_RGBW_COLOR: (1, 2, 3, 4)},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {"b": 3, "g": 2, "r": 1, "w": 4}

    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, **pilot.pilot_params}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGBW_COLOR] == (1, 2, 3, 4)

    bulb.turn_on.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 6535, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {"dimming": 50, "temp": 6535}


async def test_turnable_light(hass: HomeAssistant) -> None:
    """Test a light operation with a turnable light."""
    bulb, _ = await async_setup_integration(hass, bulb_type=FAKE_TURNABLE_BULB)
    entity_id = "light.mock_title"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 6535, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {"dimming": 50, "temp": 6535}

    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, **pilot.pilot_params}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 6535


async def test_old_firmware_dimmable_light(hass: HomeAssistant) -> None:
    """Test a light operation with a dimmable light with old firmware."""
    bulb, _ = await async_setup_integration(
        hass, bulb_type=FAKE_OLD_FIRMWARE_DIMMABLE_BULB
    )
    entity_id = "light.mock_title"
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {"dimming": 50}

    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, **pilot.pilot_params}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128

    bulb.turn_on.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {"dimming": 100}


def _mocked_wizlight_without_color_state(
    bulb_type: BulbType, dimming: bool
) -> wizlight:
    """Mock a color bulb whose state has neither color values nor a scene."""
    bulb = _mocked_wizlight(None, None, bulb_type)
    params = {"mac": FAKE_MAC, "state": True, "sceneId": 0}
    if dimming:
        params["dimming"] = 100
    state = PilotParser(params)
    bulb.state = state
    bulb.updateState = AsyncMock(return_value=state)
    return bulb


async def test_tv_sync_product_without_color_state(hass: HomeAssistant) -> None:
    """Test a TV sync product pushing states without color values or a scene.

    TV ambient light products (DMORGB/MHORGB) do this while syncing to
    the TV; without a fallback the light would never report a color mode.
    """
    bulb = _mocked_wizlight_without_color_state(FAKE_TV_SYNC_BOX, dimming=True)
    await async_setup_integration(hass, wizlight=bulb)
    entity_id = "light.mock_title"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "brightness"
    assert state.attributes[ATTR_EFFECT] == EFFECT_TV_SYNC

    # A second identical push must keep reporting the pseudo effect
    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, "sceneId": 0, "dimming": 100}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_COLOR_MODE] == "brightness"
    assert state.attributes[ATTR_EFFECT] == EFFECT_TV_SYNC

    # A push update with color values clears the pseudo effect
    await async_push_update(
        hass,
        bulb,
        {"mac": FAKE_MAC, "state": True, "r": 1, "g": 2, "b": 3, "c": 4, "w": 5},
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_COLOR_MODE] == "rgbww"
    assert state.attributes[ATTR_RGBWW_COLOR] == (1, 2, 3, 4, 5)
    assert state.attributes[ATTR_EFFECT] is None

    # Returning to a colorless state restores the pseudo effect
    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, "sceneId": 0, "dimming": 100}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_COLOR_MODE] == "brightness"
    assert state.attributes[ATTR_EFFECT] == EFFECT_TV_SYNC

    # Reproducing a captured state must not send the pseudo effect to the
    # device, where it is not a real scene
    bulb.turn_on.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: EFFECT_TV_SYNC, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    pilot: PilotBuilder = bulb.turn_on.mock_calls[0][1][0]
    assert pilot.pilot_params == {"dimming": 50}


async def test_tv_sync_product_without_color_state_or_brightness(
    hass: HomeAssistant,
) -> None:
    """Test a TV sync product pushing a state with neither color values nor dimming."""
    bulb = _mocked_wizlight_without_color_state(FAKE_TV_SYNC_BOX, dimming=False)
    await async_setup_integration(hass, wizlight=bulb)
    state = hass.states.get("light.mock_title")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "onoff"
    assert state.attributes[ATTR_EFFECT] == EFFECT_TV_SYNC


async def test_color_light_without_color_state(hass: HomeAssistant) -> None:
    """Test a regular color light pushing states without color values or a scene.

    Only TV sync products report the pseudo effect; other lights fall back
    to a supported color mode and keep the last known mode afterwards.
    """
    bulb = _mocked_wizlight_without_color_state(FAKE_RGBWW_BULB, dimming=True)
    await async_setup_integration(hass, wizlight=bulb)
    entity_id = "light.mock_title"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "color_temp"
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] is None
    assert state.attributes[ATTR_EFFECT] is None

    await async_push_update(
        hass,
        bulb,
        {"mac": FAKE_MAC, "state": True, "r": 1, "g": 2, "b": 3, "c": 4, "w": 5},
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_COLOR_MODE] == "rgbww"

    # A colorless push keeps the last known color mode
    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, "sceneId": 0, "dimming": 100}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_COLOR_MODE] == "rgbww"
    assert state.attributes[ATTR_EFFECT] is None

    # While a scene is active BRIGHTNESS is reported
    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, "sceneId": 1, "dimming": 100}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_COLOR_MODE] == "brightness"
    assert state.attributes[ATTR_EFFECT] == "Ocean"

    # A colorless push after a scene must not retain the unsupported
    # BRIGHTNESS mode but restore the last supported color mode
    await async_push_update(
        hass, bulb, {"mac": FAKE_MAC, "state": True, "sceneId": 0, "dimming": 100}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_COLOR_MODE] == "rgbww"
    assert state.attributes[ATTR_EFFECT] is None


async def test_light_without_color_state_or_effect_support(
    hass: HomeAssistant,
) -> None:
    """Test a colorless state on a color light that does not support effects.

    The pseudo effect is not allowed here, so the light must fall back to
    one of its supported color modes.
    """
    bulb = _mocked_wizlight_without_color_state(FAKE_RGBWW_NO_EFFECT_BULB, dimming=True)
    await async_setup_integration(hass, wizlight=bulb)
    state = hass.states.get("light.mock_title")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_COLOR_MODE] == "color_temp"
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] is None
    assert ATTR_EFFECT not in state.attributes
