"""Tests for light platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock

import pytest

from homeassistant.components import tplink
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import (
    MAC_ADDRESS,
    _mocked_bulb,
    _mocked_smart_light_strip,
    _patch_discovery,
    _patch_single_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_light_unique_id(hass: HomeAssistant) -> None:
    """Test a light unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.color_temp = None
    with _patch_discovery(device=bulb), _patch_single_discovery(device=bulb):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == "AABBCCDDEEFF"


@pytest.mark.parametrize(
    "bulb, transition", [(_mocked_bulb(), 2.0), (_mocked_smart_light_strip(), None)]
)
async def test_color_light(
    hass: HomeAssistant, bulb: MagicMock, transition: float | None
) -> None:
    """Test a color light and that all transitions are correctly passed."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb.color_temp = None
    with _patch_discovery(device=bulb), _patch_single_discovery(device=bulb):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"
    KASA_TRANSITION_VALUE = transition * 1_000 if transition is not None else None

    BASE_PAYLOAD = {ATTR_ENTITY_ID: entity_id}
    if transition:
        BASE_PAYLOAD[ATTR_TRANSITION] = transition

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "hs"
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["brightness", "color_temp", "hs"]
    assert attributes[ATTR_MIN_MIREDS] == 111
    assert attributes[ATTR_MAX_MIREDS] == 250
    assert attributes[ATTR_HS_COLOR] == (10, 30)
    assert attributes[ATTR_RGB_COLOR] == (255, 191, 178)
    assert attributes[ATTR_XY_COLOR] == (0.42, 0.336)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", BASE_PAYLOAD, blocking=True
    )
    bulb.turn_off.assert_called_once_with(transition=KASA_TRANSITION_VALUE)

    await hass.services.async_call(LIGHT_DOMAIN, "turn_on", BASE_PAYLOAD, blocking=True)
    bulb.turn_on.assert_called_once_with(transition=KASA_TRANSITION_VALUE)
    bulb.turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {**BASE_PAYLOAD, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(39, transition=KASA_TRANSITION_VALUE)
    bulb.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {**BASE_PAYLOAD, ATTR_COLOR_TEMP: 150},
        blocking=True,
    )
    bulb.set_color_temp.assert_called_with(
        6666, brightness=None, transition=KASA_TRANSITION_VALUE
    )
    bulb.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {**BASE_PAYLOAD, ATTR_COLOR_TEMP: 150},
        blocking=True,
    )
    bulb.set_color_temp.assert_called_with(
        6666, brightness=None, transition=KASA_TRANSITION_VALUE
    )
    bulb.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {**BASE_PAYLOAD, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    bulb.set_hsv.assert_called_with(10, 30, None, transition=KASA_TRANSITION_VALUE)
    bulb.set_hsv.reset_mock()


async def test_color_light_no_temp(hass: HomeAssistant) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.is_variable_color_temp = False
    type(bulb).color_temp = PropertyMock(side_effect=Exception)
    with _patch_discovery(device=bulb), _patch_single_discovery(device=bulb):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "hs"
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["brightness", "hs"]
    assert attributes[ATTR_HS_COLOR] == (10, 30)
    assert attributes[ATTR_RGB_COLOR] == (255, 191, 178)
    assert attributes[ATTR_XY_COLOR] == (0.42, 0.336)

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_off.assert_called_once()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_on.assert_called_once()
    bulb.turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(39, transition=None)
    bulb.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_HS_COLOR: (10, 30)},
        blocking=True,
    )
    bulb.set_hsv.assert_called_with(10, 30, None, transition=None)
    bulb.set_hsv.reset_mock()


@pytest.mark.parametrize(
    "bulb, is_color", [(_mocked_bulb(), True), (_mocked_smart_light_strip(), False)]
)
async def test_color_temp_light(
    hass: HomeAssistant, bulb: MagicMock, is_color: bool
) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb.is_color = is_color
    bulb.color_temp = 4000
    bulb.is_variable_color_temp = True

    with _patch_discovery(device=bulb), _patch_single_discovery(device=bulb):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "color_temp"
    if bulb.is_color:
        assert attributes[ATTR_SUPPORTED_COLOR_MODES] == [
            "brightness",
            "color_temp",
            "hs",
        ]
    else:
        assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["brightness", "color_temp"]
    assert attributes[ATTR_MIN_MIREDS] == 111
    assert attributes[ATTR_MAX_MIREDS] == 250
    assert attributes[ATTR_COLOR_TEMP] == 250

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_off.assert_called_once()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_on.assert_called_once()
    bulb.turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(39, transition=None)
    bulb.set_brightness.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 150},
        blocking=True,
    )
    bulb.set_color_temp.assert_called_with(6666, brightness=None, transition=None)
    bulb.set_color_temp.reset_mock()


async def test_brightness_only_light(hass: HomeAssistant) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.is_color = False
    bulb.is_variable_color_temp = False

    with _patch_discovery(device=bulb), _patch_single_discovery(device=bulb):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_BRIGHTNESS] == 128
    assert attributes[ATTR_COLOR_MODE] == "brightness"
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["brightness"]

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_off.assert_called_once()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_on.assert_called_once()
    bulb.turn_on.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    bulb.set_brightness.assert_called_with(39, transition=None)
    bulb.set_brightness.reset_mock()


async def test_on_off_light(hass: HomeAssistant) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.is_color = False
    bulb.is_variable_color_temp = False
    bulb.is_dimmable = False

    with _patch_discovery(device=bulb), _patch_single_discovery(device=bulb):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "on"
    attributes = state.attributes
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["onoff"]

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_off.assert_called_once()

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_on.assert_called_once()
    bulb.turn_on.reset_mock()


async def test_off_at_start_light(hass: HomeAssistant) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.is_color = False
    bulb.is_variable_color_temp = False
    bulb.is_dimmable = False
    bulb.is_on = False

    with _patch_discovery(device=bulb), _patch_single_discovery(device=bulb):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "off"
    attributes = state.attributes
    assert attributes[ATTR_SUPPORTED_COLOR_MODES] == ["onoff"]


async def test_dimmer_turn_on_fix(hass: HomeAssistant) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    bulb.is_dimmer = True
    bulb.is_on = False

    with _patch_discovery(device=bulb), _patch_single_discovery(device=bulb):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    bulb.turn_on.assert_called_once_with(transition=1)
    bulb.turn_on.reset_mock()


async def test_smart_strip_effects(hass: HomeAssistant) -> None:
    """Test smart strip effects."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    strip = _mocked_smart_light_strip()

    with _patch_discovery(device=strip), _patch_single_discovery(device=strip):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == "Effect1"
    assert state.attributes[ATTR_EFFECT_LIST] == ["Effect1", "Effect2"]

    # Ensure setting color temp when an effect
    # is in progress calls set_hsv to clear the effect
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_COLOR_TEMP: 250},
        blocking=True,
    )
    strip.set_hsv.assert_called_once_with(0, 0, None)
    strip.set_color_temp.assert_called_once_with(4000, brightness=None, transition=None)
    strip.set_hsv.reset_mock()
    strip.set_color_temp.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "Effect2"},
        blocking=True,
    )
    strip.set_effect.assert_called_once_with("Effect2")
    strip.set_effect.reset_mock()

    strip.effect = {"name": "Effect1", "enable": 0, "custom": 0}
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert ATTR_EFFECT not in state.attributes

    strip.is_off = True
    strip.is_on = False
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert ATTR_EFFECT not in state.attributes

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    strip.turn_on.assert_called_once()
    strip.turn_on.reset_mock()

    strip.is_off = False
    strip.is_on = True
    strip.effect_list = None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT_LIST] is None


async def test_smart_strip_custom_random_effect(hass: HomeAssistant) -> None:
    """Test smart strip custom random effects."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    strip = _mocked_smart_light_strip()

    with _patch_discovery(device=strip), _patch_single_discovery(device=strip):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        "random_effect",
        {
            ATTR_ENTITY_ID: entity_id,
            "init_states": [340, 20, 50],
            "backgrounds": [[340, 20, 50], [20, 50, 50], [0, 100, 50]],
        },
        blocking=True,
    )
    strip.set_custom_effect.assert_called_once_with(
        {
            "custom": 1,
            "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
            "brightness": 100,
            "name": "Custom",
            "segments": [0],
            "expansion_strategy": 1,
            "enable": 1,
            "duration": 0,
            "transition": 0,
            "type": "random",
            "init_states": [[340, 20, 50]],
            "random_seed": 100,
            "backgrounds": [(340, 20, 50), (20, 50, 50), (0, 100, 50)],
        }
    )
    strip.set_custom_effect.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "random_effect",
        {
            ATTR_ENTITY_ID: entity_id,
            "init_states": [340, 20, 50],
            "random_seed": 600,
        },
        blocking=True,
    )
    strip.set_custom_effect.assert_called_once_with(
        {
            "custom": 1,
            "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
            "brightness": 100,
            "name": "Custom",
            "segments": [0],
            "expansion_strategy": 1,
            "enable": 1,
            "duration": 0,
            "transition": 0,
            "type": "random",
            "init_states": [[340, 20, 50]],
            "random_seed": 600,
        }
    )
    strip.set_custom_effect.reset_mock()

    strip.effect = {
        "custom": 1,
        "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
        "brightness": 100,
        "name": "Custom",
        "enable": 1,
    }
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    strip.is_off = True
    strip.is_on = False
    strip.effect = {
        "custom": 1,
        "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
        "brightness": 100,
        "name": "Custom",
        "enable": 0,
    }
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert ATTR_EFFECT not in state.attributes

    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    strip.turn_on.assert_called_once()
    strip.turn_on.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        "random_effect",
        {
            ATTR_ENTITY_ID: entity_id,
            "init_states": [340, 20, 50],
            "backgrounds": [[340, 20, 50], [20, 50, 50], [0, 100, 50]],
            "random_seed": 50,
            "brightness": 80,
            "duration": 5000,
            "transition": 2000,
            "fadeoff": 3000,
            "hue_range": [0, 360],
            "saturation_range": [0, 100],
            "brightness_range": [0, 100],
            "transition_range": [2000, 3000],
        },
    )
    await hass.async_block_till_done()

    strip.set_custom_effect.assert_called_once_with(
        {
            "custom": 1,
            "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
            "brightness": 80,
            "name": "Custom",
            "segments": [0],
            "expansion_strategy": 1,
            "enable": 1,
            "duration": 5000,
            "transition": 0,
            "type": "random",
            "init_states": [[340, 20, 50]],
            "random_seed": 50,
            "backgrounds": [(340, 20, 50), (20, 50, 50), (0, 100, 50)],
            "fadeoff": 3000,
            "hue_range": [0, 360],
            "saturation_range": [0, 100],
            "brightness_range": [0, 100],
            "transition_range": [2000, 3000],
        }
    )
    strip.set_custom_effect.reset_mock()


async def test_smart_strip_custom_random_effect_at_start(hass: HomeAssistant) -> None:
    """Test smart strip custom random effects at startup."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    strip = _mocked_smart_light_strip()
    strip.effect = {
        "custom": 1,
        "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
        "brightness": 100,
        "name": "Custom",
        "enable": 0,
    }
    with _patch_discovery(device=strip), _patch_single_discovery(device=strip):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    # fallback to set HSV when custom effect is not known so it does turn back on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    strip.turn_on.assert_called_once()
    strip.turn_on.reset_mock()


async def test_smart_strip_custom_sequence_effect(hass: HomeAssistant) -> None:
    """Test smart strip custom sequence effects."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    strip = _mocked_smart_light_strip()

    with _patch_discovery(device=strip), _patch_single_discovery(device=strip):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "light.my_bulb"

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        "sequence_effect",
        {
            ATTR_ENTITY_ID: entity_id,
            "sequence": [[340, 20, 50], [20, 50, 50], [0, 100, 50]],
        },
        blocking=True,
    )
    strip.set_custom_effect.assert_called_once_with(
        {
            "custom": 1,
            "id": "yMwcNpLxijmoKamskHCvvravpbnIqAIN",
            "brightness": 100,
            "name": "Custom",
            "segments": [0],
            "expansion_strategy": 1,
            "enable": 1,
            "duration": 0,
            "transition": 0,
            "type": "sequence",
            "sequence": [(340, 20, 50), (20, 50, 50), (0, 100, 50)],
            "repeat_times": 0,
            "spread": 1,
            "direction": 4,
        }
    )
    strip.set_custom_effect.reset_mock()
