"""Tests for light platform."""

from homeassistant.components import flux_led
from homeassistant.components.flux_led.const import DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import (
    DEFAULT_ENTRY_TITLE,
    MAC_ADDRESS,
    _mocked_bulb,
    _patch_discovery,
    _patch_wifibulb,
)

from tests.common import MockConfigEntry


async def test_light_unique_id(hass: HomeAssistant) -> None:
    """Test a light unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: DEFAULT_ENTRY_TITLE}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == MAC_ADDRESS


async def test_rgb_light(hass: HomeAssistant) -> None:
    """Test an rgb light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: DEFAULT_ENTRY_TITLE}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(device=bulb), _patch_wifibulb(device=bulb):
        await async_setup_component(hass, flux_led.DOMAIN, {flux_led.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.az120444_aabbccddeeff"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "rgbw"
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp", "hs", "rgbw"]
    assert attributes[ATTR_HS_COLOR] == (0, 100)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOff.assert_called_once()

    bulb.is_on = False

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turnOn.assert_called_once()
    bulb.turnOn.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.setRgbw.assert_called_with(255, 0, 0, w=None, brightness=100)
    bulb.setRgbw.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 150},
        blocking=True,
    )
    bulb.setRgbw.assert_called_with(w2=128)
    bulb.setRgbw.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 150},
        blocking=True,
    )
    bulb.setRgbw.assert_called_with(w2=128)
    bulb.setRgbw.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    bulb.setRgbw.assert_called_with(255, 191, 178, w=None, brightness=128)
    bulb.setRgbw.reset_mock()
