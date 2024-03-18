"""The tests for the litejet component."""

from homeassistant.components import light
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_TRANSITION
from homeassistant.components.litejet.const import CONF_DEFAULT_TRANSITION
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from . import async_init_integration

ENTITY_LIGHT = "light.mock_load_1"
ENTITY_LIGHT_NUMBER = 1
ENTITY_OTHER_LIGHT = "light.mock_load_2"
ENTITY_OTHER_LIGHT_NUMBER = 2


async def test_on_brightness(hass: HomeAssistant, mock_litejet) -> None:
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


async def test_default_transition(hass: HomeAssistant, mock_litejet) -> None:
    """Test turning the light on with the default transition option."""
    entry = await async_init_integration(hass)

    hass.config_entries.async_update_entry(entry, options={CONF_DEFAULT_TRANSITION: 12})
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == "off"
    assert hass.states.get(ENTITY_OTHER_LIGHT).state == "off"

    assert not light.is_on(hass, ENTITY_LIGHT)

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 102},
        blocking=True,
    )
    mock_litejet.activate_load_at.assert_called_with(ENTITY_LIGHT_NUMBER, 39, 12)


async def test_transition(hass: HomeAssistant, mock_litejet) -> None:
    """Test turning the light on with transition."""
    await async_init_integration(hass)

    assert hass.states.get(ENTITY_LIGHT).state == "off"
    assert hass.states.get(ENTITY_OTHER_LIGHT).state == "off"

    assert not light.is_on(hass, ENTITY_LIGHT)

    # On
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_TRANSITION: 5},
        blocking=True,
    )
    mock_litejet.activate_load_at.assert_called_with(ENTITY_LIGHT_NUMBER, 99, 5)

    # Off
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_TRANSITION: 5},
        blocking=True,
    )
    mock_litejet.activate_load_at.assert_called_with(ENTITY_LIGHT_NUMBER, 0, 5)


async def test_on_off(hass: HomeAssistant, mock_litejet) -> None:
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


async def test_activated_event(hass: HomeAssistant, mock_litejet) -> None:
    """Test handling an event from LiteJet."""

    await async_init_integration(hass)

    # Light 1
    mock_litejet.get_load_level.return_value = 99
    mock_litejet.get_load_level.reset_mock()
    mock_litejet.load_activated_callbacks[ENTITY_LIGHT_NUMBER](99)
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
    mock_litejet.load_activated_callbacks[ENTITY_OTHER_LIGHT_NUMBER](40)
    await hass.async_block_till_done()

    mock_litejet.get_load_level.assert_called_once_with(ENTITY_OTHER_LIGHT_NUMBER)

    assert light.is_on(hass, ENTITY_LIGHT)
    assert light.is_on(hass, ENTITY_OTHER_LIGHT)
    assert hass.states.get(ENTITY_LIGHT).state == "on"
    assert hass.states.get(ENTITY_OTHER_LIGHT).state == "on"
    assert hass.states.get(ENTITY_OTHER_LIGHT).attributes.get(ATTR_BRIGHTNESS) == 103


async def test_deactivated_event(hass: HomeAssistant, mock_litejet) -> None:
    """Test handling an event from LiteJet."""
    await async_init_integration(hass)

    # Initial state is on.
    mock_litejet.get_load_level.return_value = 99

    mock_litejet.load_activated_callbacks[ENTITY_OTHER_LIGHT_NUMBER](99)
    await hass.async_block_till_done()

    assert light.is_on(hass, ENTITY_OTHER_LIGHT)

    # Event indicates it is off now.

    mock_litejet.get_load_level.reset_mock()
    mock_litejet.get_load_level.return_value = 0

    mock_litejet.load_deactivated_callbacks[ENTITY_OTHER_LIGHT_NUMBER](0)
    await hass.async_block_till_done()

    # (Requesting the level is not strictly needed with a deactivated
    # event but the implementation happens to do it. This could be
    # changed to an assert_not_called in the future.)
    mock_litejet.get_load_level.assert_called_with(ENTITY_OTHER_LIGHT_NUMBER)

    assert not light.is_on(hass, ENTITY_OTHER_LIGHT)
    assert not light.is_on(hass, ENTITY_LIGHT)
    assert hass.states.get(ENTITY_LIGHT).state == "off"
    assert hass.states.get(ENTITY_OTHER_LIGHT).state == "off"


async def test_connected_event(hass: HomeAssistant, mock_litejet) -> None:
    """Test handling an event from LiteJet."""

    await async_init_integration(hass)

    # Initial state is available.
    assert hass.states.get(ENTITY_LIGHT).state == STATE_OFF

    # Event indicates it is disconnected now.
    mock_litejet.connected_changed(False, "test")
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_UNAVAILABLE

    # Event indicates it is connected now.
    mock_litejet.connected_changed(True, None)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_OFF
