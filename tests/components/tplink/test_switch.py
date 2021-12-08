"""Tests for switch platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from kasa import SmartDeviceException

from homeassistant.components import tplink
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    MAC_ADDRESS,
    _mocked_plug,
    _mocked_strip,
    _patch_discovery,
    _patch_single_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_plug(hass: HomeAssistant) -> None:
    """Test a smart plug."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_plug()
    with _patch_discovery(device=plug), _patch_single_discovery(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_plug"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    plug.turn_off.assert_called_once()
    plug.turn_off.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    plug.turn_on.assert_called_once()
    plug.turn_on.reset_mock()


async def test_plug_led(hass: HomeAssistant) -> None:
    """Test a smart plug LED."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_plug()
    with _patch_discovery(device=plug), _patch_single_discovery(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_plug"
    state = hass.states.get(entity_id)

    led_entity_id = f"{entity_id}_led"
    led_state = hass.states.get(led_entity_id)
    assert led_state.state == STATE_ON
    assert led_state.name == f"{state.name} LED"

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: led_entity_id}, blocking=True
    )
    plug.set_led.assert_called_once_with(False)
    plug.set_led.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: led_entity_id}, blocking=True
    )
    plug.set_led.assert_called_once_with(True)
    plug.set_led.reset_mock()


async def test_plug_unique_id(hass: HomeAssistant) -> None:
    """Test a plug unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_plug()
    with _patch_discovery(device=plug), _patch_single_discovery(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_plug"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == "aa:bb:cc:dd:ee:ff"


async def test_plug_update_fails(hass: HomeAssistant) -> None:
    """Test a smart plug update failure."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    plug = _mocked_plug()
    with _patch_discovery(device=plug), _patch_single_discovery(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_plug"
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    plug.update = AsyncMock(side_effect=SmartDeviceException)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE


async def test_strip(hass: HomeAssistant) -> None:
    """Test a smart strip."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    strip = _mocked_strip()
    with _patch_discovery(device=strip), _patch_single_discovery(device=strip):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    # Verify we only create entities for the children
    # since this is what the previous version did
    assert hass.states.get("switch.my_strip") is None

    for plug_id in range(2):
        entity_id = f"switch.plug{plug_id}"
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        strip.children[plug_id].turn_off.assert_called_once()
        strip.children[plug_id].turn_off.reset_mock()

        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        strip.children[plug_id].turn_on.assert_called_once()
        strip.children[plug_id].turn_on.reset_mock()


async def test_strip_led(hass: HomeAssistant) -> None:
    """Test a smart strip LED."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    strip = _mocked_strip()
    with _patch_discovery(device=strip), _patch_single_discovery(device=strip):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    # We should have a LED entity for the strip
    led_entity_id = "switch.my_strip_led"
    led_state = hass.states.get(led_entity_id)
    assert led_state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: led_entity_id}, blocking=True
    )
    strip.set_led.assert_called_once_with(False)
    strip.set_led.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: led_entity_id}, blocking=True
    )
    strip.set_led.assert_called_once_with(True)
    strip.set_led.reset_mock()


async def test_strip_unique_ids(hass: HomeAssistant) -> None:
    """Test a strip unique id."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    strip = _mocked_strip()
    with _patch_discovery(device=strip), _patch_single_discovery(device=strip):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    for plug_id in range(2):
        entity_id = f"switch.plug{plug_id}"
        entity_registry = er.async_get(hass)
        assert (
            entity_registry.async_get(entity_id).unique_id == f"PLUG{plug_id}DEVICEID"
        )
