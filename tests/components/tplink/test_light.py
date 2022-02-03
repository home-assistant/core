"""Tests for light platform."""
from __future__ import annotations

from unittest.mock import PropertyMock

import pytest

from homeassistant.components import tplink
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
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
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import MAC_ADDRESS, _mocked_bulb, _patch_discovery, _patch_single_discovery

from tests.common import MockConfigEntry


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


@pytest.mark.parametrize("transition", [2.0, None])
async def test_color_light(hass: HomeAssistant, transition: float | None) -> None:
    """Test a color light and that all transitions are correctly passed."""
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


@pytest.mark.parametrize("is_color", [True, False])
async def test_color_temp_light(hass: HomeAssistant, is_color: bool) -> None:
    """Test a light."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
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
