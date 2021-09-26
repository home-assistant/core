"""Tests for switch platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from kasa import SmartDeviceException

from homeassistant.components import tplink
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
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
    plug = _mocked_strip()
    with _patch_discovery(device=plug), _patch_single_discovery(device=plug):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    entity_id = "switch.my_strip"
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
