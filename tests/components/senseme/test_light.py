"""Tests for senseme light platform."""
from aiosenseme import SensemeDevice

from homeassistant.components import senseme
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ColorMode,
)
from homeassistant.components.senseme.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import _mock_device, _patch_device, _patch_discovery

from tests.common import MockConfigEntry


async def _setup_mocked_entry(hass: HomeAssistant, device: SensemeDevice) -> None:
    """Set up a mocked entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"info": device.get_device_info},
        unique_id=device.uuid,
    )
    entry.add_to_hass(hass)
    with _patch_discovery(), _patch_device(device=device):
        await async_setup_component(hass, senseme.DOMAIN, {senseme.DOMAIN: {}})
        await hass.async_block_till_done()


async def test_light_unique_id(hass: HomeAssistant) -> None:
    """Test a light unique id."""
    device = _mock_device()
    await _setup_mocked_entry(hass, device)
    entity_id = "light.haiku_fan"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == f"{device.uuid}-LIGHT"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_fan_light(hass: HomeAssistant) -> None:
    """Test a fan light."""
    device = _mock_device()
    await _setup_mocked_entry(hass, device)
    entity_id = "light.haiku_fan"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 255
    assert attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert device.light_on is False

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert device.light_on is True


async def test_fan_light_no_brightness(hass: HomeAssistant) -> None:
    """Test a fan light without brightness."""
    device = _mock_device()
    device.brightness = None
    await _setup_mocked_entry(hass, device)
    entity_id = "light.haiku_fan"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 255
    assert attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]


async def test_standalone_light(hass: HomeAssistant) -> None:
    """Test a standalone light."""
    device = _mock_device()
    device.is_light = True
    device.light_color_temp_max = 6500
    device.light_color_temp_min = 2700
    device.light_color_temp = 4000
    await _setup_mocked_entry(hass, device)
    entity_id = "light.haiku_fan_light"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 255
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.COLOR_TEMP]
    assert attributes[ATTR_COLOR_TEMP] == 250

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert device.light_on is False

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert device.light_on is True
