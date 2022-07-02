"""Tests for the lifx integration light platform."""

from datetime import timedelta

import aiolifx_effects
import pytest

from homeassistant.components import lifx
from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.manager import SERVICE_EFFECT_COLORLOOP
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    IP_ADDRESS,
    MAC_ADDRESS,
    PHYSICAL_MAC_ADDRESS_NEW_FIRMWARE,
    MockFailingLifxCommand,
    MockMessage,
    _mocked_bulb,
    _mocked_bulb_new_firmware,
    _mocked_light_strip,
    _mocked_white_bulb,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_light_unique_id(hass: HomeAssistant) -> None:
    """Test a light unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "1.2.3.4"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == MAC_ADDRESS

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers=set(), connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)}
    )
    assert device.identifiers == {(DOMAIN, MAC_ADDRESS)}


async def test_light_unique_id_new_firmware(hass: HomeAssistant) -> None:
    """Test a light unique id with newer firmware."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "1.2.3.4"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb_new_firmware()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == MAC_ADDRESS
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers=set(),
        connections={(dr.CONNECTION_NETWORK_MAC, PHYSICAL_MAC_ADDRESS_NEW_FIRMWARE)},
    )
    assert device.identifiers == {(DOMAIN, MAC_ADDRESS)}


async def test_light_strip(hass: HomeAssistant) -> None:
    """Test a light strip."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
    bulb.power_level = 65535
    bulb.color = [65535, 65535, 65535, 65535]
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 255
    assert attributes[ATTR_COLOR_MODE] == ColorMode.HS
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    ]
    assert attributes[ATTR_HS_COLOR] == (360.0, 100.0)
    assert attributes[ATTR_RGB_COLOR] == (255, 0, 0)
    assert attributes[ATTR_XY_COLOR] == (0.701, 0.299)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is False
    bulb.set_power.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is True
    bulb.set_power.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    call_dict = bulb.set_color_zones.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "apply": 0,
        "color": [],
        "duration": 0,
        "end_index": 0,
        "start_index": 0,
    }
    bulb.set_color_zones.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    call_dict = bulb.set_color_zones.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "apply": 0,
        "color": [],
        "duration": 0,
        "end_index": 0,
        "start_index": 0,
    }
    bulb.set_color_zones.reset_mock()


async def test_color_light_with_temp(
    hass: HomeAssistant, mock_effect_conductor
) -> None:
    """Test a color light with temp."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.power_level = 65535
    bulb.color = [65535, 65535, 65535, 65535]
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 255
    assert attributes[ATTR_COLOR_MODE] == ColorMode.HS
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    ]
    assert attributes[ATTR_HS_COLOR] == (360.0, 100.0)
    assert attributes[ATTR_RGB_COLOR] == (255, 0, 0)
    assert attributes[ATTR_XY_COLOR] == (0.701, 0.299)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is False
    bulb.set_power.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is True
    bulb.set_power.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [65535, 65535, 25700, 65535]
    bulb.set_color.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [1820, 19660, 65535, 3500]
    bulb.set_color.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (255, 30, 80)},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [63107, 57824, 65535, 3500]
    bulb.set_color.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_XY_COLOR: (0.46, 0.376)},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [4956, 30583, 65535, 3500]
    bulb.set_color.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "effect_colorloop"},
        blocking=True,
    )
    start_call = mock_effect_conductor.start.mock_calls
    first_call = start_call[0][1]
    assert isinstance(first_call[0], aiolifx_effects.EffectColorloop)
    assert first_call[1][0] == bulb
    mock_effect_conductor.start.reset_mock()
    mock_effect_conductor.stop.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_COLORLOOP,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    start_call = mock_effect_conductor.start.mock_calls
    first_call = start_call[0][1]
    assert isinstance(first_call[0], aiolifx_effects.EffectColorloop)
    assert first_call[1][0] == bulb
    mock_effect_conductor.start.reset_mock()
    mock_effect_conductor.stop.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "effect_pulse"},
        blocking=True,
    )
    assert len(mock_effect_conductor.stop.mock_calls) == 1
    start_call = mock_effect_conductor.start.mock_calls
    first_call = start_call[0][1]
    assert isinstance(first_call[0], aiolifx_effects.EffectPulse)
    assert first_call[1][0] == bulb
    mock_effect_conductor.start.reset_mock()
    mock_effect_conductor.stop.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "effect_stop"},
        blocking=True,
    )
    assert len(mock_effect_conductor.stop.mock_calls) == 2


async def test_white_bulb(hass: HomeAssistant) -> None:
    """Test a white bulb."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_white_bulb()
    bulb.power_level = 65535
    bulb.color = [32000, None, 32000, 6000]
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 125
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
    ]
    assert attributes[ATTR_COLOR_TEMP] == 166
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is False
    bulb.set_power.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is True
    bulb.set_power.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [32000, None, 25700, 6000]
    bulb.set_color.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 400},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [32000, 0, 32000, 2500]
    bulb.set_color.reset_mock()


async def test_config_zoned_light_strip_fails(hass):
    """Test we handle failure to update zones."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    light_strip = _mocked_light_strip()
    entity_id = "light.my_bulb"

    class MockFailingLifxCommand:
        """Mock a lifx command that fails on the 3rd try."""

        def __init__(self, bulb, **kwargs):
            """Init command."""
            self.bulb = bulb
            self.call_count = 0

        def __call__(self, callb=None, *args, **kwargs):
            """Call command."""
            self.call_count += 1
            response = None if self.call_count >= 3 else MockMessage()
            if callb:
                callb(self.bulb, response)

    light_strip.get_color_zones = MockFailingLifxCommand(light_strip)

    with _patch_discovery(device=light_strip), _patch_device(device=light_strip):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        entity_registry = er.async_get(hass)
        assert entity_registry.async_get(entity_id).unique_id == MAC_ADDRESS
        assert hass.states.get(entity_id).state == STATE_OFF

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_white_light_fails(hass):
    """Test we handle failure to power on off."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_white_bulb()
    entity_id = "light.my_bulb"

    bulb.set_power = MockFailingLifxCommand(bulb)

    with _patch_discovery(device=bulb), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        entity_registry = er.async_get(hass)
        assert entity_registry.async_get(entity_id).unique_id == MAC_ADDRESS
        assert hass.states.get(entity_id).state == STATE_OFF
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
            )
        assert bulb.set_power.calls[0][0][0] is True
        bulb.set_power.reset_mock()
