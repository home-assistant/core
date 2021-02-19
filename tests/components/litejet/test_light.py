"""The tests for the litejet component."""
import logging

from homeassistant.components import light
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON

from . import async_init_integration

_LOGGER = logging.getLogger(__name__)

ENTITY_LIGHT = "light.mock_load_1"
ENTITY_LIGHT_NUMBER = 1
ENTITY_OTHER_LIGHT = "light.mock_load_2"
ENTITY_OTHER_LIGHT_NUMBER = 2


async def test_on_brightness(hass, mock_litejet):
    """Test turning the light on with brightness."""
    await async_init_integration(hass)

    assert hass.states.get(ENTITY_LIGHT).state == "off"
    assert hass.states.get(ENTITY_OTHER_LIGHT).state == "off"

    assert not light.is_on(hass, ENTITY_LIGHT)

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 102},
        blocking=True,
    )
    mock_litejet.activate_load_at.assert_called_with(ENTITY_LIGHT_NUMBER, 39, 0)


async def test_on_off(hass, mock_litejet):
    """Test turning the light on and off."""
    await async_init_integration(hass)

    assert hass.states.get(ENTITY_LIGHT).state == "off"
    assert hass.states.get(ENTITY_OTHER_LIGHT).state == "off"

    assert not light.is_on(hass, ENTITY_LIGHT)

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    mock_litejet.activate_load.assert_called_with(ENTITY_LIGHT_NUMBER)

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    mock_litejet.deactivate_load.assert_called_with(ENTITY_LIGHT_NUMBER)


async def test_activated_event(hass, mock_litejet):
    """Test handling an event from LiteJet."""

    await async_init_integration(hass)

    # Light 1
    mock_litejet.get_load_level.return_value = 99
    mock_litejet.get_load_level.reset_mock()
    mock_litejet.load_activated_callbacks[ENTITY_LIGHT_NUMBER]()
    await hass.async_block_till_done()

    mock_litejet.get_load_level.assert_called_once_with(ENTITY_LIGHT_NUMBER)

    assert light.is_on(hass, ENTITY_LIGHT)
    assert not light.is_on(hass, ENTITY_OTHER_LIGHT)
    assert hass.states.get(ENTITY_LIGHT).state == "on"
    assert hass.states.get(ENTITY_OTHER_LIGHT).state == "off"
    assert hass.states.get(ENTITY_LIGHT).attributes.get(ATTR_BRIGHTNESS) == 255

    # Light 2

    mock_litejet.get_load_level.return_value = 40
    mock_litejet.get_load_level.reset_mock()
    mock_litejet.load_activated_callbacks[ENTITY_OTHER_LIGHT_NUMBER]()
    await hass.async_block_till_done()

    mock_litejet.get_load_level.assert_called_once_with(ENTITY_OTHER_LIGHT_NUMBER)

    assert light.is_on(hass, ENTITY_LIGHT)
    assert light.is_on(hass, ENTITY_OTHER_LIGHT)
    assert hass.states.get(ENTITY_LIGHT).state == "on"
    assert hass.states.get(ENTITY_OTHER_LIGHT).state == "on"
    assert (
        int(hass.states.get(ENTITY_OTHER_LIGHT).attributes.get(ATTR_BRIGHTNESS)) == 103
    )


async def test_deactivated_event(hass, mock_litejet):
    """Test handling an event from LiteJet."""
    await async_init_integration(hass)

    # Initial state is on.
    mock_litejet.get_load_level.return_value = 99

    mock_litejet.load_activated_callbacks[ENTITY_OTHER_LIGHT_NUMBER]()
    await hass.async_block_till_done()

    assert light.is_on(hass, ENTITY_OTHER_LIGHT)

    # Event indicates it is off now.

    mock_litejet.get_load_level.reset_mock()
    mock_litejet.get_load_level.return_value = 0

    mock_litejet.load_deactivated_callbacks[ENTITY_OTHER_LIGHT_NUMBER]()
    await hass.async_block_till_done()

    # (Requesting the level is not strictly needed with a deactivated
    # event but the implementation happens to do it. This could be
    # changed to an assert_not_called in the future.)
    mock_litejet.get_load_level.assert_called_with(ENTITY_OTHER_LIGHT_NUMBER)

    assert not light.is_on(hass, ENTITY_OTHER_LIGHT)
    assert not light.is_on(hass, ENTITY_LIGHT)
    assert hass.states.get(ENTITY_LIGHT).state == "off"
    assert hass.states.get(ENTITY_OTHER_LIGHT).state == "off"
