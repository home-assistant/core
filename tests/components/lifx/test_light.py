"""Tests for the lifx integration light platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import aiolifx_effects
import pytest

from homeassistant.components import lifx
from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.const import _ATTR_COLOR_TEMP, ATTR_POWER
from homeassistant.components.lifx.light import ATTR_INFRARED, ATTR_ZONES
from homeassistant.components.lifx.manager import (
    ATTR_CLOUD_SATURATION_MAX,
    ATTR_CLOUD_SATURATION_MIN,
    ATTR_DIRECTION,
    ATTR_PALETTE,
    ATTR_SATURATION_MAX,
    ATTR_SATURATION_MIN,
    ATTR_SKY_TYPE,
    ATTR_SPEED,
    ATTR_THEME,
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_MORPH,
    SERVICE_EFFECT_MOVE,
    SERVICE_EFFECT_SKY,
    SERVICE_PAINT_THEME,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_ON,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    IP_ADDRESS,
    MAC_ADDRESS,
    SERIAL,
    MockFailingLifxCommand,
    MockLifxCommand,
    MockMessage,
    _mocked_brightness_bulb,
    _mocked_bulb,
    _mocked_bulb_new_firmware,
    _mocked_ceiling,
    _mocked_clean_bulb,
    _mocked_light_strip,
    _mocked_tile,
    _mocked_white_bulb,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
def patch_lifx_state_settle_delay():
    """Set asyncio.sleep for state settles to zero."""
    with patch("homeassistant.components.lifx.light.LIFX_STATE_SETTLE_DELAY", 0):
        yield


async def test_light_unique_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a light unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "1.2.3.4"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    assert entity_registry.async_get(entity_id).unique_id == SERIAL

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, SERIAL)}
    )
    assert device.identifiers == {(DOMAIN, SERIAL)}


async def test_light_unique_id_new_firmware(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a light unique id with newer firmware."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "1.2.3.4"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb_new_firmware()
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    assert entity_registry.async_get(entity_id).unique_id == SERIAL
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
    )
    assert device.identifiers == {(DOMAIN, SERIAL)}


async def test_light_strip(hass: HomeAssistant) -> None:
    """Test a light strip."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
    bulb.power_level = 65535
    bulb.color = [65535, 65535, 65535, 65535]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
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
    assert len(bulb.set_color_zones.calls) == 0
    bulb.set_color_zones.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    assert len(bulb.set_color_zones.calls) == 0
    bulb.set_color_zones.reset_mock()

    bulb.color_zones = [
        (0, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
    ]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    # Single color uses the fast path
    assert bulb.set_color.calls[1][0][0] == [1820, 19660, 65535, 3500]
    bulb.set_color.reset_mock()
    assert len(bulb.set_color_zones.calls) == 0

    bulb.color_zones = [
        (0, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
    ]

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (255, 10, 30)},
        blocking=True,
    )
    # Single color uses the fast path
    assert bulb.set_color.calls[0][0][0] == [64643, 62964, 65535, 3500]
    bulb.set_color.reset_mock()
    assert len(bulb.set_color_zones.calls) == 0

    bulb.color_zones = [
        (0, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
    ]

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_XY_COLOR: (0.3, 0.7)},
        blocking=True,
    )
    # Single color uses the fast path
    assert bulb.set_color.calls[0][0][0] == [15848, 65535, 65535, 3500]
    bulb.set_color.reset_mock()
    assert len(bulb.set_color_zones.calls) == 0

    bulb.color_zones = [
        (0, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
    ]

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    # multiple zones in effect and we are changing the brightness
    # we need to do each zone individually
    assert len(bulb.set_color.calls) == 0
    call_dict = bulb.set_color_zones.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "apply": 0,
        "color": [0, 65535, 32896, 3500],
        "duration": 0,
        "end_index": 0,
        "start_index": 0,
    }
    call_dict = bulb.set_color_zones.calls[1][1]
    call_dict.pop("callb")
    assert call_dict == {
        "apply": 0,
        "color": [54612, 65535, 32896, 3500],
        "duration": 0,
        "end_index": 1,
        "start_index": 1,
    }
    call_dict = bulb.set_color_zones.calls[7][1]
    call_dict.pop("callb")
    assert call_dict == {
        "apply": 1,
        "color": [46420, 65535, 32896, 3500],
        "duration": 0,
        "end_index": 7,
        "start_index": 7,
    }
    bulb.set_color_zones.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_RGB_COLOR: (255, 255, 255),
            ATTR_ZONES: [0, 2],
        },
        blocking=True,
    )
    # set a two zones
    assert len(bulb.set_color.calls) == 0
    call_dict = bulb.set_color_zones.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "apply": 0,
        "color": [0, 0, 65535, 3500],
        "duration": 0,
        "end_index": 0,
        "start_index": 0,
    }
    call_dict = bulb.set_color_zones.calls[1][1]
    call_dict.pop("callb")
    assert call_dict == {
        "apply": 1,
        "color": [0, 0, 65535, 3500],
        "duration": 0,
        "end_index": 2,
        "start_index": 2,
    }
    bulb.set_color_zones.reset_mock()

    bulb.get_color_zones.reset_mock()
    bulb.set_power.reset_mock()

    bulb.power_level = 0
    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (255, 255, 255), ATTR_ZONES: [3]},
        blocking=True,
    )
    # set a one zone
    assert len(bulb.set_power.calls) == 2
    assert len(bulb.get_color_zones.calls) == 1
    assert len(bulb.set_color.calls) == 0
    call_dict = bulb.set_color_zones.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "apply": 1,
        "color": [0, 0, 65535, 3500],
        "duration": 0,
        "end_index": 3,
        "start_index": 3,
    }
    bulb.get_color_zones.reset_mock()
    bulb.set_power.reset_mock()
    bulb.set_color_zones.reset_mock()

    bulb.set_color_zones = MockFailingLifxCommand(bulb)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_state",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_RGB_COLOR: (255, 255, 255),
                ATTR_ZONES: [3],
            },
            blocking=True,
        )

    bulb.set_color_zones = MockLifxCommand(bulb)
    bulb.get_color_zones = MockFailingLifxCommand(bulb)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_state",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_RGB_COLOR: (255, 255, 255),
                ATTR_ZONES: [3],
            },
            blocking=True,
        )

    bulb.get_color_zones = MockLifxCommand(
        bulb, msg_seq_num=0, msg_color=[0, 0, 65535, 3500] * 3, msg_index=0, msg_count=3
    )
    bulb.get_color = MockFailingLifxCommand(bulb)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_state",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_RGB_COLOR: (255, 255, 255),
                ATTR_ZONES: [3],
            },
            blocking=True,
        )


async def test_extended_multizone_messages(hass: HomeAssistant) -> None:
    """Test a light strip that supports extended multizone."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
    bulb.product = 38  # LIFX Beam
    bulb.power_level = 65535
    bulb.color = [65535, 65535, 65535, 3500]
    bulb.color_zones = [(65535, 65535, 65535, 3500)] * 8
    bulb.zones_count = 8
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
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
    assert len(bulb.set_color_zones.calls) == 0
    assert len(bulb.set_extended_color_zones.calls) == 1

    bulb.set_color_zones.reset_mock()
    bulb.set_extended_color_zones.reset_mock()
    bulb.set_power.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    assert len(bulb.set_color.calls) == 0
    assert len(bulb.set_color_zones.calls) == 0
    assert len(bulb.set_extended_color_zones.calls) == 1
    bulb.set_color.reset_mock()
    bulb.set_color_zones.reset_mock()
    bulb.set_extended_color_zones.reset_mock()

    bulb.color_zones = [
        (0, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
    ]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )

    assert len(bulb.set_color.calls) == 0
    assert len(bulb.set_color_zones.calls) == 0
    assert len(bulb.set_extended_color_zones.calls) == 1
    bulb.set_color.reset_mock()
    bulb.set_color_zones.reset_mock()
    bulb.set_extended_color_zones.reset_mock()

    bulb.color_zones = [
        (0, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
    ]

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (255, 10, 30)},
        blocking=True,
    )
    # always use a set_extended_color_zones
    assert len(bulb.set_color.calls) == 0
    assert len(bulb.set_color_zones.calls) == 0
    assert len(bulb.set_extended_color_zones.calls) == 1
    bulb.set_color.reset_mock()
    bulb.set_color_zones.reset_mock()
    bulb.set_extended_color_zones.reset_mock()

    bulb.color_zones = [
        (0, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (54612, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
        (46420, 65535, 65535, 3500),
    ]

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_XY_COLOR: (0.3, 0.7)},
        blocking=True,
    )
    # Single color uses the fast path
    assert len(bulb.set_color.calls) == 0
    assert len(bulb.set_color_zones.calls) == 0
    assert len(bulb.set_extended_color_zones.calls) == 1
    bulb.set_color.reset_mock()
    bulb.set_color_zones.reset_mock()
    bulb.set_extended_color_zones.reset_mock()

    bulb.color_zones = [
        [0, 65535, 65535, 3500],
        [54612, 65535, 65535, 3500],
        [54612, 65535, 65535, 3500],
        [54612, 65535, 65535, 3500],
        [46420, 65535, 65535, 3500],
        [46420, 65535, 65535, 3500],
        [46420, 65535, 65535, 3500],
        [46420, 65535, 65535, 3500],
    ]

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    # always use set_extended_color_zones
    assert len(bulb.set_color.calls) == 0
    assert len(bulb.set_color_zones.calls) == 0
    assert len(bulb.set_extended_color_zones.calls) == 1
    bulb.set_color.reset_mock()
    bulb.set_color_zones.reset_mock()
    bulb.set_extended_color_zones.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_RGB_COLOR: (255, 255, 255),
            ATTR_ZONES: [0, 2],
        },
        blocking=True,
    )
    # set a two zones
    assert len(bulb.set_color.calls) == 0
    assert len(bulb.set_color_zones.calls) == 0
    assert len(bulb.set_extended_color_zones.calls) == 1
    bulb.set_color.reset_mock()
    bulb.set_color_zones.reset_mock()
    bulb.set_extended_color_zones.reset_mock()

    bulb.power_level = 0
    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (255, 255, 255), ATTR_ZONES: [3]},
        blocking=True,
    )
    # set a one zone
    assert len(bulb.set_power.calls) == 2
    assert len(bulb.get_color_zones.calls) == 0
    assert len(bulb.set_color.calls) == 0
    assert len(bulb.set_color_zones.calls) == 0

    bulb.get_color_zones.reset_mock()
    bulb.set_power.reset_mock()
    bulb.set_color_zones.reset_mock()

    bulb.set_extended_color_zones = MockFailingLifxCommand(bulb)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_state",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_RGB_COLOR: (255, 255, 255),
                ATTR_ZONES: [3],
            },
            blocking=True,
        )

    bulb.set_extended_color_zones = MockLifxCommand(bulb)
    bulb.get_extended_color_zones = MockFailingLifxCommand(bulb)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_state",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_RGB_COLOR: (255, 255, 255),
                ATTR_ZONES: [3],
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_discovery")
async def test_matrix_flame_morph_effects(hass: HomeAssistant) -> None:
    """Test the firmware flame and morph effects on a matrix device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_tile()
    bulb.power_level = 0
    bulb.color = [65535, 65535, 65535, 65535]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    # FLAME effect test
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "effect_flame"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(bulb.set_power.calls) == 1
    assert len(bulb.set_tile_effect.calls) == 1

    call_dict = bulb.set_tile_effect.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "effect": 3,
        "speed": 3,
        "palette": [],
        "sky_type": None,
        "cloud_saturation_min": None,
        "cloud_saturation_max": None,
    }
    bulb.get_tile_effect.reset_mock()
    bulb.set_tile_effect.reset_mock()
    bulb.set_power.reset_mock()

    # MORPH effect tests
    bulb.power_level = 0
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_MORPH,
        {ATTR_ENTITY_ID: entity_id, ATTR_SPEED: 4, ATTR_THEME: "autumn"},
        blocking=True,
    )

    bulb.power_level = 65535
    bulb.effect = {
        "effect": "MORPH",
        "speed": 4.0,
        "palette": [
            (5643, 65535, 32768, 3500),
            (15109, 65535, 32768, 3500),
            (8920, 65535, 32768, 3500),
            (10558, 65535, 32768, 3500),
        ],
    }
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    assert len(bulb.set_power.calls) == 1
    assert len(bulb.set_tile_effect.calls) == 1
    call_dict = bulb.set_tile_effect.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "effect": 2,
        "speed": 4,
        "palette": [
            (5643, 65535, 32768, 3500),
            (15109, 65535, 32768, 3500),
            (8920, 65535, 32768, 3500),
            (10558, 65535, 32768, 3500),
        ],
        "sky_type": None,
        "cloud_saturation_min": None,
        "cloud_saturation_max": None,
    }
    bulb.get_tile_effect.reset_mock()
    bulb.set_tile_effect.reset_mock()
    bulb.set_power.reset_mock()

    bulb.power_level = 0
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_MORPH,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_SPEED: 6,
            ATTR_PALETTE: [
                (0, 100, 255, 3500),
                (60, 100, 255, 3500),
                (120, 100, 255, 3500),
                (180, 100, 255, 3500),
                (240, 100, 255, 3500),
                (300, 100, 255, 3500),
            ],
        },
        blocking=True,
    )

    bulb.power_level = 65535
    bulb.effect = {
        "effect": "MORPH",
        "speed": 6,
        "palette": [
            (0, 65535, 65535, 3500),
            (10922, 65535, 65535, 3500),
            (21845, 65535, 65535, 3500),
            (32768, 65535, 65535, 3500),
            (43690, 65535, 65535, 3500),
            (54612, 65535, 65535, 3500),
        ],
    }
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    assert len(bulb.set_power.calls) == 1
    assert len(bulb.set_tile_effect.calls) == 1
    call_dict = bulb.set_tile_effect.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "effect": 2,
        "speed": 6,
        "palette": [
            (0, 65535, 65535, 3500),
            (10922, 65535, 65535, 3500),
            (21845, 65535, 65535, 3500),
            (32768, 65535, 65535, 3500),
            (43690, 65535, 65535, 3500),
            (54613, 65535, 65535, 3500),
        ],
        "sky_type": None,
        "cloud_saturation_min": None,
        "cloud_saturation_max": None,
    }
    bulb.get_tile_effect.reset_mock()
    bulb.set_tile_effect.reset_mock()
    bulb.set_power.reset_mock()


@pytest.mark.usefixtures("mock_discovery")
async def test_sky_effect(hass: HomeAssistant) -> None:
    """Test the firmware sky effect on a ceiling device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_ceiling()
    bulb.power_level = 0
    bulb.color = [65535, 65535, 65535, 65535]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    # SKY effect test
    bulb.power_level = 0
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_SKY,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_PALETTE: [],
            ATTR_SKY_TYPE: "Clouds",
            ATTR_CLOUD_SATURATION_MAX: 180,
            ATTR_CLOUD_SATURATION_MIN: 50,
        },
        blocking=True,
    )

    bulb.power_level = 65535
    bulb.effect = {
        "effect": "SKY",
        "palette": [],
        "sky_type": 2,
        "cloud_saturation_min": 50,
        "cloud_saturation_max": 180,
    }
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    assert len(bulb.set_power.calls) == 1
    assert len(bulb.set_tile_effect.calls) == 1
    call_dict = bulb.set_tile_effect.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "effect": 5,
        "speed": 50,
        "palette": [],
        "sky_type": 2,
        "cloud_saturation_min": 50,
        "cloud_saturation_max": 180,
    }
    bulb.get_tile_effect.reset_mock()
    bulb.set_tile_effect.reset_mock()
    bulb.set_power.reset_mock()

    bulb.power_level = 0
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_SKY,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_PALETTE: [
                (200, 100, 1, 3500),
                (241, 100, 1, 3500),
                (189, 100, 8, 3500),
                (40, 100, 100, 3500),
                (40, 50, 100, 3500),
                (0, 0, 100, 6500),
            ],
            ATTR_SKY_TYPE: "Sunrise",
            ATTR_CLOUD_SATURATION_MAX: 180,
            ATTR_CLOUD_SATURATION_MIN: 50,
        },
        blocking=True,
    )

    bulb.power_level = 65535
    bulb.effect = {
        "effect": "SKY",
        "palette": [
            (200, 100, 1, 3500),
            (241, 100, 1, 3500),
            (189, 100, 8, 3500),
            (40, 100, 100, 3500),
            (40, 50, 100, 3500),
            (0, 0, 100, 6500),
        ],
        "sky_type": 0,
        "cloud_saturation_min": 50,
        "cloud_saturation_max": 180,
    }
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    assert len(bulb.set_power.calls) == 1
    assert len(bulb.set_tile_effect.calls) == 1
    call_dict = bulb.set_tile_effect.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "effect": 5,
        "speed": 50,
        "palette": [
            (36408, 65535, 65535, 3500),
            (43872, 65535, 65535, 3500),
            (34406, 65535, 5243, 3500),
            (7281, 65535, 65535, 3500),
            (7281, 32768, 65535, 3500),
            (0, 0, 65535, 6500),
        ],
        "sky_type": 0,
        "cloud_saturation_min": 50,
        "cloud_saturation_max": 180,
    }
    bulb.get_tile_effect.reset_mock()
    bulb.set_tile_effect.reset_mock()
    bulb.set_power.reset_mock()


@pytest.mark.usefixtures("mock_discovery")
async def test_lightstrip_move_effect(hass: HomeAssistant) -> None:
    """Test the firmware move effect on a light strip."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
    bulb.product = 38
    bulb.power_level = 0
    bulb.color = [65535, 65535, 65535, 65535]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "effect_move"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(bulb.set_power.calls) == 1
    assert len(bulb.set_multizone_effect.calls) == 1

    call_dict = bulb.set_multizone_effect.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "effect": 1,
        "speed": 3.0,
        "direction": 0,
    }

    bulb.get_multizone_effect.reset_mock()
    bulb.set_multizone_effect.reset_mock()
    bulb.set_power.reset_mock()

    bulb.power_level = 0
    await hass.services.async_call(
        DOMAIN,
        SERVICE_EFFECT_MOVE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_SPEED: 4.5,
            ATTR_DIRECTION: "left",
            ATTR_THEME: "sports",
        },
        blocking=True,
    )

    bulb.power_level = 65535
    bulb.effect = {"name": "MOVE", "speed": 4.5, "direction": "Left"}
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    assert len(bulb.set_power.calls) == 1
    assert len(bulb.set_extended_color_zones.calls) == 1
    assert len(bulb.set_multizone_effect.calls) == 1
    call_dict = bulb.set_multizone_effect.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "effect": 1,
        "speed": 4.5,
        "direction": 1,
    }
    bulb.get_multizone_effect.reset_mock()
    bulb.set_multizone_effect.reset_mock()
    bulb.set_power.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "effect_stop"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(bulb.set_power.calls) == 0
    assert len(bulb.set_multizone_effect.calls) == 1
    call_dict = bulb.set_multizone_effect.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
        "effect": 0,
        "speed": 3.0,
        "direction": 0,
    }
    bulb.get_multizone_effect.reset_mock()
    bulb.set_multizone_effect.reset_mock()
    bulb.set_power.reset_mock()


@pytest.mark.usefixtures("mock_discovery")
async def test_paint_theme_service(hass: HomeAssistant) -> None:
    """Test the firmware flame and morph effects on a matrix device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.power_level = 0
    bulb.color = [65535, 65535, 65535, 65535]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    bulb.power_level = 0
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PAINT_THEME,
        {ATTR_ENTITY_ID: entity_id, ATTR_TRANSITION: 4, ATTR_THEME: "autumn"},
        blocking=True,
    )

    bulb.power_level = 65535

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    assert len(bulb.set_power.calls) == 1
    assert len(bulb.set_color.calls) == 1
    call_dict = bulb.set_color.calls[0][1]
    call_dict.pop("callb")
    assert call_dict["value"] in [
        (5643, 65535, 32768, 3500),
        (15109, 65535, 32768, 3500),
        (8920, 65535, 32768, 3500),
        (10558, 65535, 32768, 3500),
    ]
    assert call_dict["duration"] == 4000
    bulb.set_color.reset_mock()
    bulb.set_power.reset_mock()

    bulb.power_level = 0
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PAINT_THEME,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TRANSITION: 6,
            ATTR_PALETTE: [
                (0, 100, 255, 3500),
                (60, 100, 255, 3500),
                (120, 100, 255, 3500),
                (180, 100, 255, 3500),
                (240, 100, 255, 3500),
                (300, 100, 255, 3500),
            ],
        },
        blocking=True,
    )

    bulb.power_level = 65535
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    assert len(bulb.set_power.calls) == 1
    assert len(bulb.set_color.calls) == 1
    call_dict = bulb.set_color.calls[0][1]
    call_dict.pop("callb")
    hue = round(call_dict["value"][0] / 65535 * 360)
    sat = round(call_dict["value"][1] / 65535 * 100)
    bri = call_dict["value"][2] >> 8
    kel = call_dict["value"][3]
    assert (hue, sat, bri, kel) in [
        (0, 100, 255, 3500),
        (60, 100, 255, 3500),
        (120, 100, 255, 3500),
        (180, 100, 255, 3500),
        (240, 100, 255, 3500),
        (300, 100, 255, 3500),
    ]
    assert call_dict["duration"] == 6000

    bulb.set_color.reset_mock()
    bulb.set_power.reset_mock()


async def test_color_light_with_temp(
    hass: HomeAssistant, mock_effect_conductor
) -> None:
    """Test a color light with temp."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.power_level = 65535
    bulb.color = [65535, 65535, 65535, 65535]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
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

    bulb.color = [32000, None, 32000, 6000]

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is True
    bulb.set_power.reset_mock()
    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 125
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    ]
    assert attributes[ATTR_HS_COLOR] == (30.754, 7.122)
    assert attributes[ATTR_RGB_COLOR] == (255, 246, 237)
    assert attributes[ATTR_XY_COLOR] == (0.339, 0.338)
    bulb.color = [65535, 65535, 65535, 65535]

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
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS_PCT: 50, ATTR_SATURATION_MAX: 90},
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
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128, ATTR_SATURATION_MIN: 90},
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
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_white_bulb()
    bulb.power_level = 65535
    bulb.color = [32000, None, 32000, 6000]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
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
    assert attributes[ATTR_COLOR_TEMP_KELVIN] == 6000
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
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 2500},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [32000, 0, 32000, 2500]
    bulb.set_color.reset_mock()


@pytest.mark.usefixtures("mock_discovery")
async def test_config_zoned_light_strip_fails(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we handle failure to update zones."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    light_strip = _mocked_light_strip()
    entity_id = "light.my_bulb"

    class MockFailingLifxCommand:
        """Mock a lifx command that fails on the 2nd try."""

        def __init__(self, bulb, **kwargs: Any) -> None:
            """Init command."""
            self.bulb = bulb
            self.call_count = 0

        def __call__(self, callb=None, *args, **kwargs):
            """Call command."""
            self.call_count += 1
            response = (
                None
                if self.call_count >= 2
                else MockMessage(seq_num=0, color=[], index=0, count=0)
            )
            if callb:
                callb(self.bulb, response)

    light_strip.get_color_zones = MockFailingLifxCommand(light_strip)

    with _patch_discovery(device=light_strip), _patch_device(device=light_strip):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert entity_registry.async_get(entity_id).unique_id == SERIAL
        assert hass.states.get(entity_id).state == STATE_OFF

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_legacy_zoned_light_strip(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we handle failure to update zones."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    light_strip = _mocked_light_strip()
    entity_id = "light.my_bulb"

    class MockPopulateLifxZonesCommand:
        """Mock populating the number of zones."""

        def __init__(self, bulb, **kwargs: Any) -> None:
            """Init command."""
            self.bulb = bulb
            self.call_count = 0

        def __call__(self, callb=None, *args, **kwargs):
            """Call command."""
            self.call_count += 1
            self.bulb.color_zones = [None] * 12
            if callb:
                callb(
                    self.bulb,
                    MockMessage(
                        seq_num=0,
                        index=0,
                        count=self.bulb.zones_count,
                        color=self.bulb.color_zones,
                    ),
                )

    get_color_zones_mock = MockPopulateLifxZonesCommand(light_strip)
    light_strip.get_color_zones = get_color_zones_mock

    with _patch_discovery(device=light_strip), _patch_device(device=light_strip):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert entity_registry.async_get(entity_id).unique_id == SERIAL
        assert hass.states.get(entity_id).state == STATE_OFF
        # 1 to get the number of zones
        # 2 get populate the zones
        assert get_color_zones_mock.call_count == 3

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == STATE_OFF
        # 2 get populate the zones
        assert get_color_zones_mock.call_count == 5


async def test_white_light_fails(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we handle failure to power on off."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_white_bulb()
    entity_id = "light.my_bulb"

    bulb.set_power = MockFailingLifxCommand(bulb)

    with _patch_discovery(device=bulb), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()
        assert entity_registry.async_get(entity_id).unique_id == SERIAL
        assert hass.states.get(entity_id).state == STATE_OFF
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
            )
        assert bulb.set_power.calls[0][0][0] is True
        bulb.set_power.reset_mock()

        bulb.set_power = MockLifxCommand(bulb)
        bulb.set_color = MockFailingLifxCommand(bulb)

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                "turn_on",
                {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP_KELVIN: 6000},
                blocking=True,
            )
        assert bulb.set_color.calls[0][0][0] == [1, 0, 3, 6000]
        bulb.set_color.reset_mock()


async def test_brightness_bulb(hass: HomeAssistant) -> None:
    """Test a brightness only bulb."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_brightness_bulb()
    bulb.power_level = 65535
    bulb.color = [32000, None, 32000, 6000]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 125
    assert attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.BRIGHTNESS,
    ]
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


async def test_transitions_brightness_only(hass: HomeAssistant) -> None:
    """Test transitions with a brightness only device."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_brightness_bulb()
    bulb.power_level = 65535
    bulb.color = [32000, None, 32000, 6000]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 125
    assert attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.BRIGHTNESS,
    ]
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is False
    bulb.set_power.reset_mock()
    bulb.power_level = 0

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_TRANSITION: 5, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    assert bulb.set_power.calls[0][0][0] is True
    call_dict = bulb.set_power.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {"duration": 5000}
    bulb.set_power.reset_mock()

    bulb.power_level = 0

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_TRANSITION: 5, ATTR_BRIGHTNESS: 200},
        blocking=True,
    )
    assert bulb.set_power.calls[0][0][0] is True
    call_dict = bulb.set_power.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {"duration": 5000}
    bulb.set_power.reset_mock()

    await hass.async_block_till_done()
    bulb.get_color.reset_mock()

    # Ensure we force an update after the transition
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert len(bulb.get_color.calls) == 2


async def test_transitions_color_bulb(hass: HomeAssistant) -> None:
    """Test transitions with a color bulb."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb_new_firmware()
    bulb.power_level = 65535
    bulb.color = [32000, None, 32000, 6000]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 125
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is False
    bulb.set_power.reset_mock()
    bulb.power_level = 0

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_off",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TRANSITION: 5,
        },
        blocking=True,
    )
    assert bulb.set_power.calls[0][0][0] is False
    call_dict = bulb.set_power.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {"duration": 0}  # already off
    bulb.set_power.reset_mock()
    bulb.set_color.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            ATTR_RGB_COLOR: (255, 5, 10),
            ATTR_ENTITY_ID: entity_id,
            ATTR_TRANSITION: 5,
            ATTR_BRIGHTNESS: 100,
        },
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [65316, 64249, 25700, 3500]
    assert bulb.set_power.calls[0][0][0] is True
    call_dict = bulb.set_power.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {"duration": 5000}
    bulb.set_power.reset_mock()
    bulb.set_color.reset_mock()

    bulb.power_level = 12800

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            ATTR_RGB_COLOR: (5, 5, 10),
            ATTR_ENTITY_ID: entity_id,
            ATTR_TRANSITION: 5,
            ATTR_BRIGHTNESS: 200,
        },
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [43690, 32767, 51400, 3500]
    call_dict = bulb.set_color.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {"duration": 5000}
    bulb.set_power.reset_mock()
    bulb.set_color.reset_mock()

    await hass.async_block_till_done()
    bulb.get_color.reset_mock()

    # Ensure we force an update after the transition
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert len(bulb.get_color.calls) == 2

    bulb.set_power.reset_mock()
    bulb.set_color.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_off",
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TRANSITION: 5,
        },
        blocking=True,
    )
    assert bulb.set_power.calls[0][0][0] is False
    call_dict = bulb.set_power.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {"duration": 5000}
    bulb.set_power.reset_mock()
    bulb.set_color.reset_mock()


async def test_lifx_set_state_color(hass: HomeAssistant) -> None:
    """Test lifx.set_state works with color names and RGB."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb_new_firmware()
    bulb.power_level = 65535
    bulb.color = [32000, None, 32000, 2700]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    # brightness should convert from 8 to 16 bits
    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [32000, None, 65535, 2700]
    bulb.set_color.reset_mock()

    # brightness_pct should convert into 16 bit
    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS_PCT: 90},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [32000, None, 59110, 2700]
    bulb.set_color.reset_mock()

    # color name should turn into hue, saturation
    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_NAME: "red", ATTR_BRIGHTNESS_PCT: 100},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [0, 65535, 65535, 3500]
    bulb.set_color.reset_mock()

    # unknown color name should reset back to neutral white, i.e. 3500K
    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_NAME: "deepblack"},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [0, 0, 32000, 3500]
    bulb.set_color.reset_mock()

    # RGB should convert to hue, saturation
    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_RGB_COLOR: (0, 255, 0)},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [21845, 65535, 32000, 3500]
    bulb.set_color.reset_mock()

    # XY should convert to hue, saturation
    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_XY_COLOR: (0.34, 0.339)},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [5461, 5139, 32000, 3500]
    bulb.set_color.reset_mock()


async def test_lifx_set_state_kelvin(hass: HomeAssistant) -> None:
    """Test set_state works with kelvin parameter names."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb_new_firmware()
    bulb.power_level = 65535
    bulb.color = [32000, None, 32000, 6000]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 125
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is False
    bulb.set_power.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100, ATTR_COLOR_TEMP_KELVIN: 2700},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [32000, 0, 25700, 2700]
    bulb.set_color.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255, _ATTR_COLOR_TEMP: 400},
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [32000, 0, 65535, 2500]
    bulb.set_color.reset_mock()


async def test_infrared_color_bulb(hass: HomeAssistant) -> None:
    """Test setting infrared with a color bulb."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb_new_firmware()
    bulb.power_level = 65535
    bulb.color = [32000, None, 32000, 6000]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 125
    assert attributes[ATTR_COLOR_MODE] == ColorMode.COLOR_TEMP
    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is False
    bulb.set_power.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "set_state",
        {
            ATTR_INFRARED: 100,
            ATTR_ENTITY_ID: entity_id,
            ATTR_BRIGHTNESS: 100,
        },
        blocking=True,
    )
    assert bulb.set_infrared.calls[0][0][0] == 25700


async def test_color_bulb_is_actually_off(hass: HomeAssistant) -> None:
    """Test setting a color when we think a bulb is on but its actually off."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb_new_firmware()
    bulb.power_level = 65535
    bulb.color = [32000, None, 32000, 6000]
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"

    class MockLifxCommandActuallyOff:
        """Mock a lifx command that will update our power level state."""

        def __init__(self, bulb, **kwargs: Any) -> None:
            """Init command."""
            self.bulb = bulb
            self.calls = []

        def __call__(self, *args, **kwargs):
            """Call command."""
            bulb.power_level = 0
            if callb := kwargs.get("callb"):
                callb(self.bulb, MockMessage())
            self.calls.append([args, kwargs])

    bulb.set_color = MockLifxCommandActuallyOff(bulb)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {
            ATTR_RGB_COLOR: (100, 100, 100),
            ATTR_ENTITY_ID: entity_id,
            ATTR_BRIGHTNESS: 100,
        },
        blocking=True,
    )
    assert bulb.set_color.calls[0][0][0] == [0, 0, 25700, 3500]
    assert len(bulb.set_power.calls) == 1


async def test_clean_bulb(hass: HomeAssistant) -> None:
    """Test setting HEV cycle state on Clean bulbs."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_clean_bulb()
    bulb.power_level = 0
    bulb.hev_cycle = {"duration": 7200, "remaining": 0, "last_power": False}
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    state = hass.states.get(entity_id)
    assert state.state == "off"
    await hass.services.async_call(
        DOMAIN,
        "set_hev_cycle_state",
        {ATTR_ENTITY_ID: entity_id, ATTR_POWER: True},
        blocking=True,
    )

    call_dict = bulb.set_hev_cycle.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {"duration": 0, "enable": True}
    bulb.set_hev_cycle.reset_mock()


async def test_set_hev_cycle_state_fails_for_color_bulb(hass: HomeAssistant) -> None:
    """Test that set_hev_cycle_state fails for a non-Clean bulb."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.power_level = 0
    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    state = hass.states.get(entity_id)
    assert state.state == "off"

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "set_hev_cycle_state",
            {ATTR_ENTITY_ID: entity_id, ATTR_POWER: True},
            blocking=True,
        )


async def test_light_strip_zones_not_populated_yet(hass: HomeAssistant) -> None:
    """Test a light strip were zones are not populated initially."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=SERIAL
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_light_strip()
    bulb.power_level = 65535
    bulb.color_zones = None
    bulb.color = [65535, 65535, 65535, 65535]
    bulb.get_color_zones = next(
        iter(
            [
                MockLifxCommand(
                    bulb,
                    msg_seq_num=0,
                    msg_color=[0, 0, 65535, 3500] * 8,
                    msg_index=0,
                    msg_count=16,
                ),
                MockLifxCommand(
                    bulb,
                    msg_seq_num=1,
                    msg_color=[0, 0, 65535, 3500] * 8,
                    msg_index=0,
                    msg_count=16,
                ),
                MockLifxCommand(
                    bulb,
                    msg_seq_num=2,
                    msg_color=[0, 0, 65535, 3500] * 8,
                    msg_index=8,
                    msg_count=16,
                ),
            ]
        )
    )
    assert bulb.get_color_zones.calls == []

    with (
        _patch_discovery(device=bulb),
        _patch_config_flow_try_connect(device=bulb),
        _patch_device(device=bulb),
    ):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    # Make sure we at least try to fetch the first zone
    # to ensure we populate the zones from the 503 response
    assert len(bulb.get_color_zones.calls) == 3
    # Once to populate the number of zones
    assert bulb.get_color_zones.calls[0][1]["start_index"] == 0
    # Again once we know the number of zones
    assert bulb.get_color_zones.calls[1][1]["start_index"] == 0
    assert bulb.get_color_zones.calls[2][1]["start_index"] == 8

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
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert bulb.set_power.calls[0][0][0] is True
    bulb.set_power.reset_mock()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
